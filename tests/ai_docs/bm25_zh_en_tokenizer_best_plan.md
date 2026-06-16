# nbrag 中英文 BM25 Tokenizer 最佳方案

> 目标：不顾虑早期兼容、不顾虑重新 ingest、不顾虑新增 PyPI 依赖，以跨领域任意文本知识库的检索效果优先。目标内容包括但不限于法律、医学、金融、科研论文、企业制度、技术手册、教材、产品文档、代码库和业务知识库。

## 结论

最佳方案不是“换一个中文分词包”，而是升级为 **BM25 v2：多路 lexical analyzer + Weighted RRF 融合**。

保留 `bm25s` 作为 BM25 引擎；新增强依赖 `jieba`；把当前单一 BM25 索引拆成两到三路稀疏索引。`pkuseg` 可以作为实验增强，但不作为默认强依赖，因为它在 Python 3.12 + Windows 下需要编译旧 C 扩展，实测安装失败。

1. `word_bm25`：词级索引，主打精准语义词面匹配。
2. `ngram_bm25`：中文 2/3-gram 索引，主打召回和短语容错。
3. `code_bm25`：代码/标识符索引，可选；若实现成本优先，可先合入 `word_bm25`。

检索时：

```text
Vector Search
+ word_bm25
+ ngram_bm25
+ optional code_bm25
=> Weighted RRF
=> Reranker
=> top_k
```

这比单纯 `jieba.cut_for_search` 更稳，也比把 jieba token 和 ngram token 全塞进同一个 BM25 索引更可控。

## 为什么不是只用 jieba

`jieba.cut_for_search` 很适合中文搜索索引，它会把长词再次切分来提高召回，也支持用户自定义词典。但 BM25 是词面匹配，分词粒度不一致时仍然会漏。

例子：

```text
文档：用人单位违法解除劳动合同
查询：公司非法解除合同
```

词级分词可能只共享 `解除`、`合同`，而 2/3-gram 能额外提供：

```text
违法解除
解除劳动
劳动合同
解除合同
```

所以最佳检索不是“分词越准越好”，而是：

- 词级分词负责精准 token。
- ngram 负责短语召回。
- Reranker 负责压掉噪声。

## 为什么不是只用 ngram

只用中文 2/3-gram 的召回很强，但有三个问题：

1. token 数量暴涨，文档长度归一化会影响 BM25 分数。
2. 短 ngram 容易产生大量弱相关命中。
3. 专业术语无法天然获得更高权重，例如 `无固定期限劳动合同`、`竞业限制经济补偿`。

因此 ngram 不应该和词级 token 混在一个索引里无限堆 token，最好单独建一路 `ngram_bm25`，再通过 Weighted RRF 控制贡献。

## 推荐依赖

在 `pyproject.toml` 强依赖：

```toml
dependencies = [
    "jieba>=0.42.1",
]
```

保留：

```toml
"bm25s[full]>=0.2.0"
```

选择理由：

- `jieba`：搜索引擎模式成熟，支持自定义词典，适合作为高召回中文分词器，且纯 Python、安装稳定。
- `pkuseg`：多领域中文分词，默认模型和细领域模型的分词准确率通常强于 jieba；但当前不做默认强依赖，只在用户环境可安装时作为可选增强。
- `bm25s`：继续负责高速 BM25、持久化、mmap/低内存加载，不引入外部服务。

不建议默认上 HanLP：

- HanLP 很强，但模型和运行时更像完整 NLP 框架。
- 对 BM25 来说，SOTA 分词准确率的边际收益不一定超过 `jieba + ngram + rerank`。
- 如果未来要加，可以做 `tokenizer_backend = "hanlp"` 的实验选项，不作为 BM25 v2 默认路径。

## Tokenizer 设计

新增模块：

```text
nbrag/tokenizer.py
```

核心 API：

```python
def tokenize_word(text: str, *, user_dict: str | None = None) -> list[str]:
    """多领域中英文文本与代码混合词级 token。用于 word_bm25。"""

def tokenize_cjk_ngram(text: str, *, n_values: tuple[int, ...] = (2, 3)) -> list[str]:
    """中文 2/3-gram token。用于 ngram_bm25。"""

def tokenize_code(text: str) -> list[str]:
    """代码标识符、路径、函数名、类名、常量名 token。"""

def tokenize_query_all(query: str) -> dict[str, list[str]]:
    """同时生成 word/ngram/code 三路 query token。"""
```

### 统一预处理

所有 tokenizer 共享预处理：

1. Unicode NFKC normalize。
2. 去除 chunk header：`[File:] [Scope:] [Sig:] [Lines:]`。
3. 保留原始代码标识符、专业编号和结构化术语，同时生成拆分 token。
4. 英文统一小写；中文不做大小写。
5. 全角转半角。
6. 标准化连接符：`_`、`-`、`.`、`/`、`::`、空白。

### word_bm25 token

中文部分：

1. `jieba.cut_for_search` 分词，提供搜索引擎召回 token。
2. 可选 `pkuseg` 分词，环境可用时提供更准确的词级 token。
3. 加入用户词典和自动领域词典。
4. 去重，但保留必要频次策略，避免 token 被重复 analyzer 放大太多。

英文、数字、代码/技术符号部分：

1. 正则提取英文、数字、版本号、错误码。
2. camelCase/PascalCase 拆分。
3. snake_case/kebab-case/dotted.path 拆分。
4. 保留完整标识符 token：
   - `BrokerEnum`
   - `brokerenum`
   - `REDIS_BULK_PUSH`
   - `redis_bulk_push`
5. 对路径保留 basename、stem、后缀、目录片段。

示例：

```text
getUserById RedisBulkPush 劳动合同期限一年以上
```

生成：

```text
getuserbyid get user by id
redisbulkpush redis bulk push redis_bulk_push
劳动 合同 劳动合同 期限 一年 以上 一年以上
```

### ngram_bm25 token

只对连续中文片段做 2/3-gram，不处理英文。

示例：

```text
试用期不得超过二个月
```

生成：

```text
试用 用期 期不 不得 得超 超过 过二 二个 个月
试用期 用期不 期不得 不得超 得超过 超过二 过二个 二个月
```

建议不做 1-gram。单字召回噪声太大，除非 query 是一个字的专有名称。

### code_bm25 token

如果单独建 `code_bm25`，它服务代码、API 文档和含结构化符号的技术文本：

- Python symbol：类名、函数名、方法名、参数名、import path。
- Markdown/API 文档：反引号内代码、路径、命令、环境变量。
- 错误码和常量：`HTTP_404`、`ERR_INVALID_ARG`、`E11000`。

若第一版想少改，可以先把 `tokenize_code()` 的输出并入 `word_bm25`。

## 自动领域词典

新增：

```text
nbrag/resources/zh_seed_terms.txt
rag_db/tokenizer_userdict/{collection_name}.txt
```

### 内置种子词和通用模式

内置内容不要绑定某个具体知识领域。不要把劳动法、医学、金融等领域词大量写死到包里；这些词应该由每个 collection 的自动词典抽取。

内置只放跨领域高价值结构词、单位、编号模式和少量通用文档词：

```text
第一章
第二节
第八十二条
附录
定义
适用范围
注意事项
mg
ml
kg
API
HTTP
JSON
```

模式类信息不一定直接放进词典文件，也可以在 tokenizer 中用规则生成 token：

```text
第[一二三四五六七八九十百千0-9]+[章节条款项]
[A-Z]{2,}[_A-Z0-9]+
[A-Za-z]+Error
\d+(\.\d+)?(mg|ml|kg|%|ms|s)
```

### 每个知识库自动生成词典

在 ingest 时从以下位置抽取候选词：

1. 文件名：`糖尿病诊疗指南.md` -> `糖尿病诊疗指南`；`劳动合同法.md` -> `劳动合同法`。
2. Markdown 标题。
3. 中文书名号、引号、括号中的术语：`《劳动合同法》`、`“胰岛素抵抗”`。
4. 结构化编号：`第八十二条`、`3.2.1`、`RFC 9110`、`GB/T 35273`。
5. 连续中文专名：长度 4-12 的高频片段，例如疾病名、产品名、政策名、材料名、算法名、业务流程名。
6. 英文缩写、版本号、错误码、标准号、药品名、指标名、接口名。
7. Python 符号索引中的类名/函数名/常量名。

自动词典写入 collection 级文件，并传给 `jieba`；如果实验性启用了 `pkuseg`，也传给 `pkuseg(user_dict=...)`。

## 索引结构

旧：

```text
rag_db/bm25_index/{collection_name}/
```

新：

```text
rag_db/bm25_index_v2/{collection_name}/
  tokenizer_meta.json
  word/
    bm25s files...
    chunk_ids.json
  ngram/
    bm25s files...
    chunk_ids.json
  code/
    bm25s files...
    chunk_ids.json
```

`tokenizer_meta.json`：

```json
{
  "version": 2,
  "tokenizer": "jieba_search+cjk_2_3gram+code",
  "jieba_version": "...",
  "ngram": [2, 3],
  "user_dict_hash": "...",
  "created_at": "..."
}
```

不兼容旧索引，直接全量重建。

## 检索融合

当前 RRF 是两路：

```text
vector + bm25
```

升级为多路 Weighted RRF：

```python
sources = [
    ("vector", vector_ids, 1.00),
    ("word_bm25", word_ids, 1.10),
    ("ngram_bm25", ngram_ids, 0.75),
    ("code_bm25", code_ids, 1.20),
]
```

公式：

```text
score(doc) += weight(source) / (rrf_k + rank + 1)
```

默认权重：

| Source | Weight | 理由 |
|--------|--------|------|
| vector | 1.00 | 语义召回主力 |
| word_bm25 | 1.10 | 精确术语、条文、函数名应略微加权 |
| ngram_bm25 | 0.75 | 提升中文召回，但控制噪声 |
| code_bm25 | 1.20 | 代码标识符命中通常强相关 |

query 有明显精确检索意图时动态调权：

| Query 特征 | 调整 |
|------------|------|
| 包含 `第...条` | `word_bm25 += 0.4`, `ngram_bm25 += 0.2` |
| 包含 `_`、`.`、`::`、大写常量 | `code_bm25 += 0.6` |
| 中文短 query，长度 <= 4 | `ngram_bm25 += 0.2` |
| 问答式长 query | 保持默认，依赖 vector + rerank |

RRF 后候选数建议：

```text
recall_k = max(top_k * 8, 40)
rerank_candidates = min(max(top_k * 6, 30), 100)
```

小知识库无所谓，大知识库更需要扩大 lexical recall。

## BM25 参数

使用 `bm25s.BM25(method="lucene")` 作为默认，因为它接近主流搜索引擎行为，便于理解和调参。

后续可以做离线评测比较：

- `method="lucene"`
- `method="bm25l"`
- `method="bm25+"`

第一版不要同时调太多参数，先把 tokenizer 和多路融合做正确。

## 实现步骤

### Phase 1：Tokenizer

1. 新增 `nbrag/tokenizer.py`。
2. 新增强依赖 `jieba`。
3. 实现：
   - `normalize_text_for_retrieval`
   - `tokenize_word`
   - `tokenize_cjk_ngram`
   - `tokenize_code`
   - `tokenize_query_all`
4. 添加单元测试：
   - 中文专业术语（法律、医学、金融、工程、产品、企业制度等）。
   - 中英混合。
   - 代码标识符。
   - Markdown header 去除。
   - 条文编号保留。

### Phase 2：BM25 v2 索引

1. 把 `build_bm25_index()` 改成构建多路索引。
2. 新增 `_bm25_index_dir_v2(collection_name, channel)`。
3. 新增 `_load_bm25_index_v2(collection_name, channel)`。
4. 新增 `_bm25_search_channel(query, collection_name, channel, top_k)`。
5. `invalidate_bm25_cache()` 同时清理 v1/v2。
6. batch ingest 后强制重建 v2。

### Phase 3：Weighted RRF

1. 把 `_rrf_fusion(vec_ids, bm25_ids)` 升级为通用多源：

```python
def _weighted_rrf_fusion(
    ranked_sources: list[tuple[str, list[str], float]],
    *,
    k: int = 60,
) -> list[str]:
    ...
```

2. `search()` 中并行跑：
   - vector
   - word_bm25
   - ngram_bm25
   - code_bm25 可选
3. 对 BM25-only 命中的 chunk，从 ChromaDB 补 metadata/documents。
4. 融合后再 rerank。

### Phase 4：领域词典

1. 新增内置词典。
2. ingest 时生成 collection 词典。
3. tokenizer 初始化时加载内置词典 + collection 词典。
4. 加 `rebuild_indexes(collection_name)` 内部函数，便于词典变更后重建。

### Phase 5：评测

建立 `tests/test_bm25_zh_tokenizer.py`，至少覆盖这些查询：

| Query | 期望 |
|-------|------|
| `试用期不得超过` | 命中《劳动合同法》第十九条 |
| `一年合同试用期最多几个月` | 命中试用期不得超过二个月 |
| `安排加班不支付加班费` | 命中《劳动合同法》第八十五条 |
| `公司不能解除劳动合同的情形` | 命中《劳动合同法》第四十二条 |
| `第八十二条 二倍工资` | 命中未签书面劳动合同二倍工资 |
| `getUserById` | 能匹配 `get_user_by_id` |
| `REDIS_BULK_PUSH` | 精确命中常量 |

评测指标：

1. BM25-only top5 hit。
2. Hybrid top5 hit。
3. Rerank 后 top3 hit。
4. 和旧版 BM25 对比。

## 文档需要同步修改

1. `README.md`
   - 修正“中文分词天然适用”的说法。
   - 说明 BM25 v2 使用多路 analyzer。
2. `AGENTS.md`
   - 更新架构决策：BM25 v2 多索引。
3. `nbrag/server.py` 工具 docstring
   - `nbrag_search` 说明 hybrid 包含 Vector + word BM25 + ngram BM25。
4. `nbrag/skills/nbrag-workflow/SKILL.md`
   - 建议 AI 对中文专业知识、制度、手册、文档类问题优先 `search_and_fetch`，精确词再 `grep`。

## 取舍

这个方案的核心取舍是：索引构建更复杂、磁盘多占一点，但检索效果更好。

因为 nbrag 是早期项目，而且已经有 ChromaDB、raw_files、symbol_index、bm25_index 四存储思想，升级到 BM25 v2 多路 sparse index 是一致的。

最重要的是：不要让 ngram 和词级 token 在同一个 BM25 分数空间里互相污染。多索引 + Weighted RRF 是更干净、更可控的方案。

## 参考

- jieba 支持搜索引擎模式、用户词典和 HMM 新词识别，搜索引擎模式会对长词再次切分以提高召回：https://github.com/fxsjy/jieba
- pkuseg 提供多领域中文分词模型、用户词典，并在其文档中的对比表里展示了相对 jieba 更高的默认模型分词效果：https://github.com/lancopku/pkuseg-python
- bm25s 提供纯 Python/Numpy/Scipy 的快速 BM25、持久化、多种 BM25 variant，并明确 tokenizer 可以扩展：https://bm25s.github.io/
