# Task 2: 加映射 helper + 重构错误 helper 为 XML error 格式

**Files:**
- Modify: `nbrag/mcp_tools.py`（顶部加映射 helper 约 L74 后；重构错误 helper L122-L180）

**Interfaces:**
- Consumes: `retrieval.py` 底层 dict key（`source` / `index` / `filename`）
- Produces:
  - `_meta_file_path(meta: dict) -> str`：映射 `source` / `filename` → canonical `file_path`
  - `_meta_chunk_index(meta: dict) -> str`：映射 `chunk_index` / `index` → canonical `chunk_index`
  - `_path_error(field_name: str) -> str`：返回 `<error type="invalid_file_path" field="...">` XML
  - `_collection_issue_text(collection_name: str, total: int) -> str`：返回 `<error type="empty_collection">` 或空字符串
  - `_collection_presence_issue_text(collection_name: str) -> str`：返回 `<error type="missing_collection">` XML（含 available collections 列表）
  - `_no_search_results_text(total: int) -> str`：返回 `<error type="no_results" field="query">` XML

**背景**：错误返回和底层 key 映射是后续所有函数的基础设施。先做底层 helper，上层函数（Task 3-8）才能直接用 canonical 字段名和 XML error 格式。

## Steps

- [ ] **Step 1: 在 `mcp_tools.py` 顶部（`_bool_param` 后，约 L74 后）加两个映射 helper**

```python
def _meta_file_path(meta: dict) -> str:
    """Map retrieval.py's source key to canonical file_path handle."""
    return str(meta.get("source", meta.get("filename", "?")))


def _meta_chunk_index(meta: dict) -> str:
    """Map retrieval.py's index key to canonical chunk_index handle."""
    return str(meta.get("chunk_index", meta.get("index", "?")))
```

- [ ] **Step 2: 重构 `_path_error`（约 L122）为 XML error 格式**

先读当前 `_path_error` 实现，然后改成：
```python
def _path_error(field_name: str) -> str:
    return (
        f"<error type=\"invalid_file_path\" field=\"{field_name}\">\n"
        f"{field_name} must be a full absolute file_path returned by nbrag tools.\n"
        f"Recovery: use nbrag_find_files(pattern, collection_name) when you only know a filename, "
        f"or nbrag_list(collection_name) to browse available file_path values.\n"
        f"</error>"
    )
```

- [ ] **Step 3: 重构 `_collection_issue_text`（约 L131）拆成 empty_collection 错误**

先读当前实现（L131-L149），理解它当前返回什么、在什么场景被调用。然后改成：当 `total == 0` 时返回 `<error type="empty_collection">`，否则返回空字符串：
```python
def _collection_issue_text(collection_name: str, total: int) -> str:
    if total == 0:
        return (
            f"<error type=\"empty_collection\" field=\"collection_name\">\n"
            f"collection '{collection_name}' exists but has 0 chunks.\n"
            f"Recovery: ingest documents first, or call nbrag_stats() to inspect other collections.\n"
            f"</error>"
        )
    return ""
```
注意：如果原函数还有"不存在"判断逻辑，保留该逻辑但把返回文本改成 `<error type="missing_collection">` 格式。读代码后判断。

- [ ] **Step 4: 重构 `_collection_presence_issue_text`（约 L150）为 missing_collection 错误**

先读当前实现（L150-L172）。这个函数当前可能返回一段散文说明 collection 不存在。改成：
```python
def _collection_presence_issue_text(collection_name: str) -> str:
    from nbrag import get_stats
    stats = get_stats()
    available = [c.get("collection_name", c.get("name", "?")) for c in stats.get("collections", [])]
    return (
        f"<error type=\"missing_collection\" field=\"collection_name\">\n"
        f"collection '{collection_name}' does not exist.\n"
        f"Available collections: {available}\n"
        f"Recovery: call nbrag_stats() to inspect valid collection_name values, then retry with the correct prepared knowledge base.\n"
        f"</error>"
    )
```
注意：如果原函数已有获取 available collections 的逻辑，复用它而非重复实现。读代码后判断。

- [ ] **Step 5: 重构 `_no_search_results_text`（约 L173）为 no_results 错误**

先读当前实现（L173-L181），然后改成：
```python
def _no_search_results_text(total: int) -> str:
    return (
        f"<error type=\"no_results\" field=\"query\">\n"
        f"No results (collection has {total} chunks).\n"
        f"Recovery: verify collection_name, minimally normalize the natural-language query without changing intent, "
        f"provide a bm25_query as lexical anchors, try nbrag_grep for exact terms, "
        f"or use nbrag_find_files + filter_file_path to narrow to a known file.\n"
        f"</error>"
    )
```

- [ ] **Step 6: 验证 helper 能被 import 且返回包含 `<error`**

Run:
```powershell
D:/ProgramData/miniconda3/envs/py312/python.exe -c "from nbrag.mcp_tools import _path_error, _no_search_results_text, _meta_file_path, _meta_chunk_index; print(_path_error('filter_file_path')); print(_no_search_results_text(100)); print(_meta_file_path({'source':'D:/foo.py'})); print(_meta_chunk_index({'index':3}))"
```
Expected: 输出包含 `<error type="invalid_file_path"` 和 `<error type="no_results"` 和 `D:/foo.py` 和 `3`

- [ ] **Step 7: Commit**

```bash
git add nbrag/mcp_tools.py
git commit -m "refactor(mcp_tools): add handle mapping helpers + XML error format"
```

## Global Constraints（适用于本 Task）

- **Python 解释器**：`D:/ProgramData/miniconda3/envs/py312/python.exe`
- **不改函数签名**：helper 函数的签名（入参名、类型、返回类型）按本 brief 定义
- **不动检索逻辑**：只改 helper 函数的返回文本格式，不改它们的调用条件
- **canonical handle 字段集**：`file_path` / `doc_id` / `chunk_index` / `total_chunks` / `line_start` / `line_end`
- **不写正式测试**：Step 6 的 import 验证就够了
- **读代码再改**：每个 helper 改之前先读当前实现，理解调用场景，避免破坏调用方
