# nbrag BM25 + RRF 混合检索实现计划

## 一、背景

### 当前检索架构

```
nbrag_search (语义搜索)
├── embed(query) → query_vec
├── ChromaDB cosine query (召回 top_k * 4)
├── BGE-Reranker 精排 (取 top_k)
└── 返回 chunks
```

### 问题

纯向量搜索有系统性盲区：
- 搜索 `"BrokerEnum"` 这种精确类名时，向量距离不一定最近
- 搜索 `"def push"` 这种精确代码片段时，语义搜索可能返回相关但不精确的结果
- 稀有术语（项目专属命名）在向量空间中缺乏足够的语义锚点

虽然 nbrag 有 `nbrag_grep` 做精确匹配补充，但那需要 AI 额外调用一轮工具。
如果 `nbrag_search` 本身就能同时做语义 + 关键词检索，单次调用的质量就会更高。

### 业界共识（2026）

生产级 RAG 的标准三层架构：
1. **并行召回**：Vector + BM25 同时检索 top-50~100
2. **RRF 融合**：用排名而非分数合并两路结果（避免分数尺度不可比的问题）
3. **Cross-encoder 精排**：Reranker 对融合后的候选做最终排序

nbrag 目前有第 1 层（vector）和第 3 层（reranker），缺第 1 层的 BM25 和第 2 层的 RRF。

---

## 二、BM25 库选型

| 库 | 性能 | 依赖 | 持久化 | 维护 | 推荐 |
|----|------|------|--------|------|------|
| `bm25s` | 极快（100-1000 QPS） | numpy + scipy | **内置 save/load** | 活跃开发中 | **推荐** |
| `rank_bm25` | 慢（1-50 QPS） | numpy | 无（需自己 pickle） | 2022 停更 | 不推荐 |
| 自实现 | 中等 | 零依赖 | 需自己实现 | - | 备选 |

**决策**：用 `bm25s`，理由：
1. 100-500x 快于 rank_bm25，即使 nbrag corpus 不大，也没必要用慢的
2. **内置持久化**（`save()`/`load()`）和 nbrag 双存储设计理念一致，索引直接落盘
3. scipy 不算重（chromadb 已经带了 numpy/onnxruntime 等更重的依赖）
4. 活跃维护，rank_bm25 已停更 4 年
5. 支持 mmap，大 collection（10万+ chunks）无压力

---

## 三、架构设计

### 3.1 整体流程

```
nbrag_search(query, collection_name, top_k=5, use_bm25=True, use_rerank=True)
│
├── [并行路径 1] Vector Search
│   ├── embed(query)
│   └── ChromaDB.query(top_k * 4)  →  vector_results (ranked)
│
├── [并行路径 2] BM25 Search  (新增)
│   ├── tokenize(query)
│   └── bm25_index.get_top_n(top_k * 4)  →  bm25_results (ranked)
│
├── [融合] RRF  (新增)
│   ├── rrf_score(doc) = Σ 1/(k + rank_i(doc)),  k=60
│   └── 取 fused top candidates
│
├── [精排] Reranker  (已有)
│   └── BGE-Reranker 精排 → top_k
│
└── 返回最终 top_k 结果
```

### 3.2 BM25 索引的生命周期

```
导入时 (ingest)
├── _write_to_db()          # 已有: 写 ChromaDB + 缓存 raw_file
├── _update_bm25_index()    # 新增: 更新 BM25 索引
└── invalidate_bm25_cache() # 新增: 清除内存缓存

检索时 (search)
├── _get_bm25_index()       # 新增: 懒加载 BM25 索引
│   ├── 内存缓存命中 → 直接返回
│   ├── 磁盘缓存命中 → 加载到内存
│   └── 无缓存 → 从 ChromaDB 读取所有 documents 构建
└── bm25.get_scores(query)  # 检索

删除时 (delete)
├── col.delete()            # 已有: 删 ChromaDB
├── _delete_raw_file()      # 已有: 删 raw cache
└── invalidate_bm25_cache() # 新增: 标记 BM25 索引过期
```

### 3.3 BM25 索引存储方案

**持久化到磁盘（bm25s 原生支持）**

```
rag_db/
  bm25_index/
    {collection_name}/         # bm25s.save() 自动管理的文件
      indices.npy              # 稀疏矩阵索引
      data.npy                 # 稀疏矩阵数据
      indptr.npy               # 稀疏矩阵指针
      vocab.json               # 词汇表
      params.json              # BM25 参数 (k1, b, etc.)
      chunk_ids.json           # chunk ID 列表（自定义，映射回 ChromaDB）
```

```python
import bm25s

_bm25_cache = {}  # collection_name -> (retriever, chunk_ids)

def _get_bm25_index(collection_name):
    """加载 BM25 索引：内存缓存 → 磁盘 → 从 ChromaDB 构建。"""
    if collection_name in _bm25_cache:
        return _bm25_cache[collection_name]
    
    index_dir = os.path.join(_cfg().storage.db_path, "bm25_index", collection_name)
    
    # 尝试从磁盘加载
    if os.path.isdir(index_dir):
        retriever = bm25s.BM25.load(index_dir, mmap=True)
        chunk_ids = _load_chunk_ids(index_dir)
        _bm25_cache[collection_name] = (retriever, chunk_ids)
        return retriever, chunk_ids
    
    # 从 ChromaDB 构建（首次）
    col = _get_existing_collection(collection_name)
    all_data = col.get(include=["documents"])
    
    corpus_tokens = bm25s.tokenize(
        [_preprocess_for_bm25(doc) for doc in all_data["documents"]]
    )
    retriever = bm25s.BM25()
    retriever.index(corpus_tokens)
    
    # 持久化
    os.makedirs(index_dir, exist_ok=True)
    retriever.save(index_dir)
    _save_chunk_ids(index_dir, all_data["ids"])
    
    _bm25_cache[collection_name] = (retriever, all_data["ids"])
    return retriever, all_data["ids"]
```

**优点**：
- 导入时一次构建，持久化到磁盘
- 后续搜索直接 load（mmap 模式，几乎零加载时间）
- 和 ChromaDB + raw_files 形成三存储体系

### 3.4 代码分词器 (tokenizer)

BM25 的效果很大程度取决于分词质量。代码场景需要特殊处理：

```python
import re

def _tokenize_for_bm25(text: str) -> list[str]:
    """代码感知的 BM25 分词器。"""
    # 1. 拆分 camelCase 和 PascalCase: getUserById → get User By Id
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    text = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', text)
    
    # 2. 拆分 snake_case: get_user_by_id → get user by id
    text = text.replace('_', ' ')
    
    # 3. 统一小写
    text = text.lower()
    
    # 4. 按非字母数字字符分词
    tokens = re.findall(r'[a-z0-9\u4e00-\u9fff]+', text)
    
    # 5. 过滤过短的 token（1 字符的英文 token 没有检索价值）
    tokens = [t for t in tokens if len(t) > 1 or '\u4e00' <= t <= '\u9fff']
    
    return tokens
```

**为什么需要代码感知分词？**
- 用户搜 `"getUserById"` → 分词为 `["get", "user", "by", "id"]`
- BM25 就能匹配到 `"def get_user_by_id(...)"`
- 如果不做 camelCase/snake_case 拆分，BM25 只能匹配完全一样的字符串

### 3.5 RRF 融合

```python
def _rrf_fusion(vector_ids: list[str], vector_scores: list[float],
                bm25_ids: list[str], bm25_scores: list[float],
                k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion — 合并两路检索结果。
    
    公式: RRF_score(doc) = Σ 1/(k + rank_i(doc))
    k=60 是 2009 年 SIGIR 论文的默认值，2026 年仍是业界标准。
    """
    scores = {}
    
    # Vector 路排名贡献
    for rank, doc_id in enumerate(vector_ids):
        scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
    
    # BM25 路排名贡献
    for rank, doc_id in enumerate(bm25_ids):
        scores[doc_id] = scores.get(doc_id, 0) + 1.0 / (k + rank + 1)
    
    # 按融合分数排序
    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return fused
```

**RRF 的优势**：
- 不需要归一化两路分数（BM25 分数无界，cosine 分数 [-1, 1]，直接加权不可比）
- 只看排名，不看分数，鲁棒性极强
- k=60 是 magic number，无需调参
- 两路都排在前面的文档得分最高（共识奖励）

---

## 四、改动文件清单

### 4.1 `core.py` — 核心逻辑

```python
# 新增模块级变量
_bm25_cache = {}
_bm25_doc_ids_cache = {}
_bm25_cache_ts = {}

# 新增函数
def _tokenize_for_bm25(text: str) -> list[str]: ...
def _get_bm25_index(collection_name: str) -> tuple: ...
def _bm25_search(query: str, collection_name: str, top_k: int) -> tuple: ...
def _rrf_fusion(vector_ids, vector_scores, bm25_ids, bm25_scores, k=60) -> list: ...
def invalidate_bm25_cache(collection_name: str = None): ...

# 修改函数
def search():
    # 新增 use_bm25 参数
    # 并行执行 vector search + bm25 search
    # RRF 融合两路结果
    # Reranker 精排
    
def _write_to_db():
    # 末尾新增 invalidate_bm25_cache(collection_name)

def delete_document():
    # 末尾新增 invalidate_bm25_cache(collection_name)

def delete_collection():
    # 末尾新增 invalidate_bm25_cache(collection_name)
```

### 4.2 `server.py` — MCP 工具

```python
# 修改 nbrag_search 工具
@mcp.tool()
async def nbrag_search(..., use_bm25: bool = True):
    # 新增 use_bm25 参数（默认开启）
    # docstring 更新：说明混合检索模式

# 修改 nbrag_search_and_fetch 工具
async def nbrag_search_and_fetch(..., use_bm25: bool = True):
    # 同步新增 use_bm25 参数
```

### 4.3 `pyproject.toml` — 依赖

```toml
dependencies = [
    ...,
    "bm25s>=0.2.0",  # 新增：BM25 稀疏检索
]
```

### 4.4 `config.py` — 配置（可选）

```python
@dataclass
class SearchConfig:
    bm25_enabled: bool = True       # 是否默认启用 BM25
    rrf_k: int = 60                 # RRF 常数
    bm25_cache_ttl: int = 300       # BM25 索引缓存 TTL（秒）
```

---

## 五、完整的 `search()` 函数改造

```python
def search(query, collection_name="default", top_k=5, 
           use_rerank=True, use_bm25=True, filter_filename=None):
    """混合检索：Vector + BM25 → RRF 融合 → Reranker 精排。"""
    col = _get_existing_collection(collection_name)
    if col is None:
        return [], [], [], False, 0
    total = col.count()
    if total == 0:
        return [], [], [], False, 0

    # ── 路径 1: Vector Search ──
    query_vec = embed([query])[0]
    recall_k = min(top_k * 4, total) if (use_rerank or use_bm25) else min(top_k, total)
    
    where_filter = {"filename": filter_filename} if filter_filename else None
    vec_results = col.query(
        query_embeddings=[query_vec], n_results=recall_k,
        where=where_filter, include=["documents", "metadatas", "distances"],
    )
    vec_ids = vec_results["ids"][0]
    vec_docs = vec_results["documents"][0]
    vec_metas = vec_results["metadatas"][0]
    vec_dists = vec_results["distances"][0]

    # ── 路径 2: BM25 Search ──
    if use_bm25 and not filter_filename:  # filter_filename 时暂不支持 BM25
        bm25_ids, bm25_scores = _bm25_search(query, collection_name, recall_k)
        
        # ── RRF 融合 ──
        fused = _rrf_fusion(vec_ids, vec_dists, bm25_ids, bm25_scores)
        
        # 根据 fused 排名重组结果
        id_to_data = {}
        for i, vid in enumerate(vec_ids):
            id_to_data[vid] = (vec_docs[i], vec_metas[i], vec_dists[i])
        
        # BM25 命中但 vector 未命中的，需要从 ChromaDB 补充 metadata
        bm25_only_ids = [bid for bid, _ in fused if bid not in id_to_data]
        if bm25_only_ids:
            extra = col.get(ids=bm25_only_ids, include=["documents", "metadatas"])
            for i, eid in enumerate(extra["ids"]):
                id_to_data[eid] = (extra["documents"][i], extra["metadatas"][i], 999.0)
        
        # 按 RRF 排名取 top candidates
        candidate_ids = [fid for fid, _ in fused if fid in id_to_data]
        documents = [id_to_data[cid][0] for cid in candidate_ids]
        metadatas = [id_to_data[cid][1] for cid in candidate_ids]
        distances = [id_to_data[cid][2] for cid in candidate_ids]
    else:
        documents = vec_docs
        metadatas = vec_metas
        distances = vec_dists

    # ── Reranker 精排 ──
    rerank_used = False
    if use_rerank and _cfg().rerank.model and len(documents) > top_k:
        try:
            reranked_idx = rerank(query, documents, top_n=top_k)
            documents = [documents[i] for i in reranked_idx]
            metadatas = [metadatas[i] for i in reranked_idx]
            distances = [distances[i] for i in reranked_idx]
            rerank_used = True
        except Exception:
            documents = documents[:top_k]
            metadatas = metadatas[:top_k]
            distances = distances[:top_k]
    else:
        documents = documents[:top_k]
        metadatas = metadatas[:top_k]
        distances = distances[:top_k]

    return documents, metadatas, distances, rerank_used, total
```

---

## 六、实现步骤（开发顺序）

### Phase 1: BM25 基础（~2小时）

1. `pyproject.toml` 添加 `rank-bm25>=0.2.2` 依赖
2. `core.py` 实现 `_tokenize_for_bm25()`
3. `core.py` 实现 `_get_bm25_index()` + 内存缓存
4. `core.py` 实现 `_bm25_search()`
5. 写单元测试验证 BM25 单独检索

### Phase 2: RRF 融合（~1小时）

6. `core.py` 实现 `_rrf_fusion()`
7. 写单元测试验证 RRF 融合逻辑（含边界情况）

### Phase 3: 集成到 search()（~2小时）

8. `core.py` 改造 `search()` 函数（如上设计）
9. `core.py` 在 `_write_to_db()`、`delete_document()`、`delete_collection()` 中添加缓存失效
10. `server.py` 更新 `nbrag_search` 和 `nbrag_search_and_fetch` 工具参数
11. 集成测试：对比 pure vector vs hybrid 的检索质量

### Phase 4: 文档更新（~1小时）

12. `README.md` 更新架构说明
13. `SKILL.md` 更新工作流（注明混合检索模式）
14. `AGENTS.md` 更新架构决策

### Phase 5: 可选优化（后续）

15. `filter_filename` 支持 BM25 路径过滤
16. 可配置的 RRF k 值和 BM25 权重
17. BM25 索引随 ingest 增量更新（而非全量重建）

---

## 七、风险与取舍

### 新增依赖
- `bm25s`（依赖 numpy + scipy，chromadb 已经带了 numpy）
- 包大小增加 < 50KB

### 性能影响
- 导入时同步构建 BM25 索引并持久化（和 ChromaDB upsert 并行，增加几秒）
- 搜索时从磁盘 mmap 加载，首次 < 0.5秒，后续命中内存缓存 < 1ms
- BM25 检索耗时可忽略（< 5ms for 50K chunks）

### 向后兼容
- `use_bm25=True` 为默认值，老用户自动获益
- `use_bm25=False` 可回退到纯 vector 模式
- MCP 工具参数新增 `use_bm25`，不影响已有调用

### 与 nbrag_grep 的关系
- **不冲突**：BM25 在 chunk 级别做有排名的关键词匹配；grep 在行级别做精确匹配
- BM25 提升 `nbrag_search` 的单次调用质量；grep 仍然是补充工具
- 典型场景：`nbrag_search`（hybrid）找到大致位置 → `nbrag_grep` 精确定位行号

---

## 八、效果预期

### 提升场景
| 查询类型 | 纯 Vector | Hybrid (Vector + BM25) |
|---------|-----------|----------------------|
| `"BrokerEnum 枚举类"` | 语义相关但可能排名靠后 | BM25 精确命中 + RRF 提升排名 |
| `"def push"` | 可能匹配到其他含 push 语义的代码 | BM25 精确匹配函数名 |
| `"REDIS_BULK_PUSH"` | 向量空间中常量名语义弱 | BM25 精确匹配常量名 |
| `"用户认证流程"` | 语义搜索主力，BM25 贡献小 | 两路结果互补 |

### 不变场景
- 纯自然语言查询：BM25 贡献有限，不会比纯 vector 差（RRF 不会降低好结果的排名）

### 预期收益
- 精确关键词查询的 recall@5 提升 20-40%
- AI 平均每次分析减少 0.5-1 轮工具调用（因为首次 search 质量更高）
