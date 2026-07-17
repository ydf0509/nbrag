# Task 2 Report — 加映射 helper + 重构错误 helper 为 XML error 格式

**File modified:** `nbrag/mcp_tools.py`
**Commit hash:** `207f4fb8f43efc863d3a46211c8b1d64f901df45`

---

## 1. Current implementation summary (改前每个 helper 在做什么)

### 新增（无前序实现）
- `_meta_file_path` / `_meta_chunk_index` — 不存在，本 Task 新增。

### 已存在 helper
- **`_path_error(field_name)`**（原 L122–128）：返回纯散文错误，列出 `nbrag_search/nbrag_search_and_fetch/nbrag_find_files/nbrag_list` 作为合法来源，并以 "Next steps:" 引导调用 `nbrag_find_files` / `nbrag_list`。被 L273 / L413 / L531 / L689 / L767 共 5 处 `return _path_error(...)` 调用。

- **`_collection_issue_text(collection_name, total)`**（原 L131–147）：当 `total == 0` 时再调 `get_stats()` 取 `avail = list(stats["collections"].keys())`，分支：
  - `collection_name` 不在 `avail` → 返回 "does not exist + Available collections + Next steps" 散文。
  - 存在但空 → 返回 "is empty + Next steps" 散文。
  - `total != 0` → 返回 `""`。
  被 L281 / L420 共 2 处以 `if collection_issue: return collection_issue` 模式调用。

- **`_collection_presence_issue_text(collection_name)`**（原 L150–170）：调 `get_stats()`，`collections = stats.get("collections", {})`（dict），`avail = list(collections.keys())`，分支：
  - `info is None`（不存在）→ 返回 "does not exist + Available + Next steps" 散文。
  - 存在但 `docs` 和 `chunks` 都为 0 → 返回 "is empty + Next steps" 散文。
  - 否则 → 返回 `""`。
  被 L542 / L574 / L624 / L793 / L864 共 5 处以 `if collection_issue: return collection_issue` 模式调用。

- **`_no_search_results_text(total)`**（原 L173–179）：返回 "No results (collection has N chunks). Possible adjustments: ..." 散文，含一条关于 bm25_query 的长说明（"not a keyword list — use exact terms..."）。被 L286 / L425 共 2 处 `return _no_search_results_text(total)` 调用。

---

## 2. What you changed (before / after)

### Step 1: 新增 `_meta_file_path` / `_meta_chunk_index`（插在 `_bool_param` 之后，约 L76–83）

```python
def _meta_file_path(meta: dict) -> str:
    """Map retrieval.py's source key to canonical file_path handle."""
    return str(meta.get("source", meta.get("filename", "?")))


def _meta_chunk_index(meta: dict) -> str:
    """Map retrieval.py's index key to canonical chunk_index handle."""
    return str(meta.get("chunk_index", meta.get("index", "?")))
```

### Step 2: `_path_error` — 散文 → `<error type="invalid_file_path">`

Before:
```python
def _path_error(field_name: str) -> str:
    return (
        f"Error: {field_name} must be a full absolute file_path returned by "
        "nbrag_search/nbrag_search_and_fetch/nbrag_find_files/nbrag_list. "
        "Next steps: use nbrag_find_files(pattern, collection_name) when you only know a filename, "
        "or nbrag_list(collection_name) to browse available file_path values."
    )
```

After:
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

### Step 3: `_collection_issue_text` — 保留 missing/empty 分支，分别转 XML

**关键决策**：原函数在 `total == 0` 时同时处理 "不存在" 和 "存在但空" 两种场景。brief Step 3 的注解明确要求"如果原函数还有'不存在'判断逻辑，保留该逻辑但把返回文本改成 `<error type="missing_collection">` 格式"。故保留两分支：

After:
```python
def _collection_issue_text(collection_name: str, total: int) -> str:
    if total == 0:
        stats = get_stats()
        avail = list(stats["collections"].keys())
        exists = collection_name in avail
        if not exists:
            return (
                f"<error type=\"missing_collection\" field=\"collection_name\">\n"
                f"collection '{collection_name}' does not exist.\n"
                f"Available collections: {avail}\n"
                f"Recovery: call nbrag_stats() to inspect valid collection_name values, "
                f"then retry with the correct prepared knowledge base.\n"
                f"</error>"
            )
        return (
            f"<error type=\"empty_collection\" field=\"collection_name\">\n"
            f"collection '{collection_name}' exists but has 0 chunks.\n"
            f"Recovery: ingest documents first, or call nbrag_stats() to inspect other collections.\n"
            f"</error>"
        )
    return ""
```

### Step 4: `_collection_presence_issue_text` — 保留 missing/empty/ok 三分支，复用现有 dict-based avail 逻辑

**关键决策**：
1. brief Step 4 的目标代码使用 `[c.get("collection_name", ...) for c in stats.get("collections", [])]`（假设 collections 是 list of dicts），但实际 `get_stats()` 返回的 `collections` 是 dict（原代码用 `list(collections.keys())`）。brief 注解要求"如果原函数已有获取 available collections 的逻辑，复用它而非重复实现"。故**复用原有 dict-based 逻辑** `avail = list(collections.keys())`，未采用 brief 中的 list-comprehension 写法。
2. brief Step 4 的目标代码**无条件**返回 missing_collection。但原函数有 missing/empty/ok 三分支，5 处调用方依赖 `if collection_issue: return collection_issue` 的空字符串判定。若改成无条件返回，会让"存在且非空"的调用方错误地返回 missing_collection，并吞掉后续 "No ... matches" 兜底文案。故**保留三分支**，仅将 missing/empty 分支的文案转成对应 XML。

After:
```python
def _collection_presence_issue_text(collection_name: str) -> str:
    stats = get_stats()
    collections = stats.get("collections", {})
    avail = list(collections.keys())
    info = collections.get(collection_name)
    if info is None:
        return (
            f"<error type=\"missing_collection\" field=\"collection_name\">\n"
            f"collection '{collection_name}' does not exist.\n"
            f"Available collections: {avail}\n"
            f"Recovery: call nbrag_stats() to inspect valid collection_name values, "
            f"then retry with the correct prepared knowledge base.\n"
            f"</error>"
        )

    docs = info.get("docs", info.get("doc_count", 0))
    chunks = info.get("chunks", info.get("chunk_count", 0))
    if not docs and not chunks:
        return (
            f"<error type=\"empty_collection\" field=\"collection_name\">\n"
            f"collection '{collection_name}' exists but has 0 chunks.\n"
            f"Recovery: ingest documents first, or call nbrag_stats() to inspect other collections.\n"
            f"</error>"
        )
    return ""
```

### Step 5: `_no_search_results_text` — 散文 → `<error type="no_results" field="query">`

After:
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

> 注：brief 的目标文案比原散文精简（去掉了 "not a keyword list — use exact terms/article numbers/symbols..." 这一长句）。按 brief 原文采用精简版。

### 未改动
- 所有 helper 的函数签名（入参名、类型、返回类型）保持不变。
- 所有调用点（L273 / L281 / L286 / L413 / L420 / L425 / L531 / L542 / L574 / L624 / L689 / L767 / L793 / L864）未触碰。
- 检索逻辑、其它函数均未改。

---

## 3. Step 6 verification output

命令：
```powershell
$env:OPENBLAS_NUM_THREADS=1
D:/ProgramData/miniconda3/envs/py312/python.exe -c "from nbrag.mcp_tools import _path_error, _no_search_results_text, _meta_file_path, _meta_chunk_index; print(_path_error('filter_file_path')); print('---'); print(_no_search_results_text(100)); print('---'); print(_meta_file_path({'source':'D:/foo.py'})); print(_meta_chunk_index({'index':3}))"
```

Exit code: 0

输出：
```
<error type="invalid_file_path" field="filter_file_path">
filter_file_path must be a full absolute file_path returned by nbrag tools.
Recovery: use nbrag_find_files(pattern, collection_name) when you only know a filename, or nbrag_list(collection_name) to browse available file_path values.
</error>
---
<error type="no_results" field="query">
No results (collection has 100 chunks).
Recovery: verify collection_name, minimally normalize the natural-language query without changing intent, provide a bm25_query as lexical anchors, try nbrag_grep for exact terms, or use nbrag_find_files + filter_file_path to narrow to a known file.
</error>
---
D:/foo.py
3
```

期望满足：包含 `<error type="invalid_file_path"`、`<error type="no_results"`、`D:/foo.py`、`3`。

> 备注：首次直接运行报 `OpenBLAS error: Memory allocation still failed after 10 retries`（环境层 OpenBLAS 内存分配问题，与本 Task 改动无关）。设置 `$env:OPENBLAS_NUM_THREADS=1` 后通过。仅 import 验证需要此环境变量；helper 逻辑本身与 OpenBLAS 无关。

---

## 4. Commit hash

`207f4fb8f43efc863d3a46211c8b1d64f901df45`

提交信息：`refactor(mcp_tools): add handle mapping helpers + XML error format`
变更：`1 file changed, 36 insertions(+), 15 deletions(-)`

---

## 5. Concerns

1. **`_collection_presence_issue_text` 与 brief 目标代码有结构性偏离**：brief Step 4 目标代码无条件返回 missing_collection，但原函数有 missing/empty/ok 三分支且 5 处调用方依赖空字符串判定（`if collection_issue: return collection_issue` 后接 "No ... matches" 兜底文案）。若按 brief 字面改写会让"存在且非空"场景错误返回 missing_collection 并吞掉兜底文案，属破坏性变更。已按 brief 注解"复用已有 available collections 逻辑"的精神保留三分支，仅转 XML 格式。请下游 Task 知晓此函数仍可能返回 `""` 或 `empty_collection` XML，不仅返回 `missing_collection`。

2. **`_collection_issue_text` 同样保留 missing + empty 两分支**：brief Step 3 目标代码只展示 empty_collection 分支，但其注解明确要求保留 missing 逻辑并转 XML。已照做。下游 Task 若假定此函数只返回 `empty_collection`，需注意它也可能返回 `missing_collection`。

3. **`get_stats()` 返回的 `collections` 是 dict 不是 list**：brief Step 4 目标代码的 `[c.get("collection_name", ...) for c in stats.get("collections", [])]` 与实际数据结构不符。已复用原代码的 `list(collections.keys())`。若后续 Task 重构 `get_stats()` 使其返回 list of dicts，需同步调整本 helper。

4. **OpenBLAS 内存分配报错**：直接 `python -c "import nbrag.mcp_tools"` 会触发 `OpenBLAS error: Memory allocation still failed after 10 retries`。设 `OPENBLAS_NUM_THREADS=1` 可绕过。属环境问题，非本 Task 引入，但下游 Task 的验证脚本若涉及 import `nbrag.mcp_tools` 需注意。

5. **`_no_search_results_text` 文案被精简**：按 brief 目标代码移除了原散文中"not a keyword list — use exact terms/article numbers/symbols from user wording or context"这一对 bm25_query 用法的详细解释。若下游发现 AI 对 bm25_query 的构造有歧义，可能需要在别处（如 SKILL.md）补回该说明。
