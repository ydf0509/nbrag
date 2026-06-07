# AI 重大更新记录

## 2026-06-07: BM25 + RRF 混合检索

**改动范围**：core.py, server.py, pyproject.toml, README.md, SKILL.md, AGENTS.md

**核心变化**：
- `search()` 从纯 Vector → **Vector + BM25 → RRF 融合 → Rerank** 三层混合检索
- 使用 `bm25s` 库（100-500x faster than rank_bm25），索引持久化到 `rag_db/bm25_index/`
- RRF 融合 k=60（SIGIR 2009 标准值），只看排名不看分数
- 代码感知分词器：拆 camelCase/snake_case，去 chunk header
- MCP 工具 `nbrag_search` 新增 `use_bm25` 参数（默认 True）
- 双存储 → 三存储（ChromaDB + raw_files + bm25_index）

**新增函数**：
- `_preprocess_for_bm25()` — 代码感知预处理
- `build_bm25_index()` — 构建并持久化 BM25 索引
- `_load_bm25_index()` — 从磁盘加载 BM25 索引
- `_bm25_search()` — BM25 检索
- `_rrf_fusion()` — Reciprocal Rank Fusion
- `invalidate_bm25_cache()` — 清除 BM25 缓存

**生命周期挂接**：
- `batch_ingest()` 完成后自动构建 BM25 索引
- `ingest_file()` 写入后清除内存缓存（下次搜索时自动重建）
- `delete_document()` / `delete_collection()` 清除 BM25 缓存 + 磁盘索引

---

## 2026-06-07: pyproject.toml 动态版本 + 发布脚本修复

**改动范围**：pyproject.toml, nbrag/__init__.py, pub_pypi_nbrag.py

**核心变化**：
- `version = "0.3.0"` → `dynamic = ["version"]` + `[tool.hatch.version]`，版本号从 `__init__.py` 动态读取
- `license = "MIT"` → `license = {text = "MIT"}`（避免 PEP 639 `License-Expression` 字段导致旧 twine 报错）
- `pub_pypi_nbrag.py`：`os.system("python ...")` → `os.system(f'"{sys.executable}" ...')`，确保用正确的 Python 解释器
