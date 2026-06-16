# nbrag MCP 注释、RAG 功能、Skill 优化记录

日期：2026-06-16

范围：

- `nbrag/server.py`
- `nbrag/core.py`
- `nbrag/skills/nbrag-workflow/SKILL.md`
- `README.md`

## 最新约束

1. `raw_files/` 是 nbrag 的核心存储之一，AI 可见说明只描述如何读取已存储原文。
2. 所有读取文件、限定文件的 MCP 入参统一使用完整绝对 `file_path`。
3. 不兼容 `core.py`、`src/core.py` 这类短路径或相对路径，不做 basename fallback。
4. `nbrag_add_document` / `nbrag_delete` 是人工维护入口，不作为 MCP tool 暴露，也不在 AI 工作流中提示。

## 实测结论

对 `langchain_ai_codes_and_docs` 知识库实测：

- `nbrag_stats` 可发现 collection。
- `nbrag_search_and_fetch("LangChain create_agent 怎么用 model tools system_prompt 示例")` 能命中 LangChain quickstart、Databricks 示例、`factory.py` 等有效上下文。
- `nbrag_search_and_fetch("RunnableWithMessageHistory session_id config configurable chat history 怎么用 示例")` 能命中 `history.py` 类文档和示例。
- `nbrag_grep("RunnableWithMessageHistory")` 适合在语义搜索后精确确认行号。
- `nbrag_find_definition("create_agent", max_results=1)` 能返回完整定义；公共符号不宜默认取太多结果。

整体判断：RAG 主链路可用，默认推荐 `nbrag_search_and_fetch` 是合理的。

## 已实施优化点

### 1. 文件过滤统一改为完整路径

MCP 文件过滤参数统一为 `filter_file_path`。

行为：

- `nbrag_search(..., filter_file_path="D:/codes/proj/core.py")`
- `nbrag_search_and_fetch(..., filter_file_path="D:/codes/proj/core.py")`
- `nbrag_grep(..., filter_file_path="D:/codes/proj/core.py")`

内部统一按 Chroma metadata 的 `source` 字段过滤，不再按 `filename` 过滤。

### 2. 文件读取只接受完整绝对路径

`nbrag_get_raw_file` 和 `nbrag_get_file_chunks` 必须传搜索结果、`nbrag_find_files` 或 `nbrag_list` 返回的完整 `file_path`。

不接受：

- `core.py`
- `src/core.py`
- `docs/readme.md`

这样可以彻底避免同名文件混淆。

### 3. 删除 basename fallback

`core._query_file_by_identifier()` 不再做：

- path 查不到后 fallback 到 basename
- 直接用 `filename` metadata 查找

现在只做：

```python
where={"source": normalized_full_path}
```

### 4. 增加 `nbrag_find_files` 文件定位工具

AI 只有短文件名或路径片段时，不再尝试把短路径传给读取工具，而是先调用：

```python
nbrag_find_files(pattern="history.py", collection_name="langchain_ai_codes_and_docs")
```

该工具只返回匹配文件列表和完整绝对 `file_path`，用于后续：

- `nbrag_get_raw_file(file_path=...)`
- `nbrag_get_file_chunks(file_path=...)`
- `filter_file_path=...`

### 5. `nbrag_search` 增加输出量控制

默认 `include_content=True`，仍给出较充分 chunk preview，避免 AI 没拿到足够证据就回答。

高级场景可选：

- `include_content=False`：只要 metadata，用于先定位候选。
- `preview_chars=N`：控制每条结果的 preview 长度。
- `preview_chars=0`：等价 metadata-only。

### 6. 增加 `nbrag_help` 内置导航

考虑到用户不一定会把 `nbrag-workflow` Skill 复制到自己的项目，MCP 自身新增无参数导航工具：

```python
nbrag_help()
```

它返回简短组合拳：

`nbrag_stats` → `nbrag_search_and_fetch` → `nbrag_grep` / `nbrag_find_definition` → `nbrag_find_files` / `nbrag_get_raw_file`

该工具不描述人工维护入口，也不提示原文存储维护动作。

### 7. 修复行号范围 inclusive 边界

`nbrag_get_chunks_by_lines` 的 `line_start` / `line_end` 是 inclusive。

修复前 overlap 判断：

```python
cl_start < line_end and cl_end > line_start
```

修复后：

```python
cl_start <= line_end and cl_end >= line_start
```

这样查询单行边界，例如 `line_start=20, line_end=20`，可以命中覆盖 `10-20` 的 chunk。

### 8. AI 可见错误不提供原文存储维护建议

`grep_knowledge()` / `find_symbol_definition()` 无匹配时返回普通空结果。

`nbrag_get_raw_file()` 的 AI 工作流只关心通过完整 `file_path` 读取内容，不提供维护入口建议。

### 9. Skill 收紧路径规则

Skill 中新增硬规则：

> 所有需要 `file_path` / `filter_file_path` 的工具，都必须传搜索结果、`nbrag_find_files` 或 `nbrag_list` 返回的完整绝对路径。不要传 `core.py`、`src/core.py` 这类短路径或相对路径。

同时将“导入类型”改成“内容类型”，避免 AI 把检索 workflow 误解成导入 workflow。

## 仍建议后续处理

### 1. `ingest_file()` / `ingest_path()` 的索引一致性

虽然导入不是 MCP tool，但人工维护入口仍应保持一致性。

现状风险：

- `batch_ingest()` 会重建 BM25 / Symbol 索引。
- `ingest_file()` / `ingest_path()` 只清内存缓存，可能留下旧的磁盘 BM25 / Symbol 索引。

建议：

- `ingest_path()` 结束后统一重建 BM25 + Symbol。
- `ingest_file()` 至少 invalidate 磁盘索引，或明确只作为低层内部函数。

### 2. 大结果读取路径批处理

`get_context_chunks()` 仍直接 `col.get(where={"doc_id": doc_id})`。

如果单个文档 chunk 极多，后续可以复用 `_batch_get()` 风格做分页读取。不过这不是当前路径唯一性问题的阻塞项。

### 3. `find_definition` 输出大小控制

`nbrag_find_definition` 默认 `max_results=3`，比原来的 5 更克制，但仍保留足够候选。MCP docstring 已提醒公共符号先用 `max_results=1`。

后续可考虑在 server 层对超大 definition 做分段提示，但当前保持“完整定义”符合工具设计。

## 验收项

1. MCP `list_tools` 暴露 11 个检索/读取类工具 + `nbrag_help` 导航工具。
2. `nbrag_search` / `nbrag_search_and_fetch` / `nbrag_grep` 暴露 `filter_file_path`。
3. `nbrag_find_files` 能根据文件名/路径片段返回完整绝对 `file_path`。
4. `nbrag_search` 支持 `include_content` 和 `preview_chars`，默认仍返回较充分 preview。
5. `nbrag_get_raw_file("core.py", ...)` 和 `nbrag_get_file_chunks("src/core.py", ...)` 返回“需要完整绝对 file_path”。
6. 完整路径读取只按 metadata `source` 查询，不 fallback 到 `filename`。
7. `nbrag_get_chunks_by_lines(doc_id, line_start=N, line_end=N)` 能命中覆盖第 N 行的 chunk。
8. `nbrag_help` / Skill / README 只描述检索和读取 workflow，不描述原文存储维护 workflow。
