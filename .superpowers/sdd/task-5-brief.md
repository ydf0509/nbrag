# Task 5: 重构 `nbrag_grep`（废弃 `matched_line`）

**Files:**
- Modify: `nbrag/mcp_tools.py:529-575`（`nbrag_grep`）

**Interfaces:**
- Consumes: Task 2 的 `_meta_file_path` helper（或直接 `item.get("source", "?")`，因为 grep 的 item 不是 meta dict）；Task 2 的 `_collection_presence_issue_text` / `_path_error`
- Produces: `nbrag_grep` 返回 `<nbrag_grep>` XML，`<match>` 用 `line_start==line_end` 表达单行匹配

## 当前代码（L529-575）

```python
def nbrag_grep(keyword, collection_name, max_results=10, case_sensitive=False, filter_file_path="", match_context_chars=...) -> str:
    # param normalization + path_filter validation (L537-543) — KEEP
    results = grep_knowledge(keyword, collection_name, max_results, case_sensitive, filter_file_path=path_filter, match_context_chars=match_context_chars)
    if not results:
        collection_issue = _collection_presence_issue_text(collection_name)
        if collection_issue:
            return collection_issue
        return "No grep matches. Possible adjustments: ..."  # prose — change to XML error
    
    lines = [
        f"grep matches: {len(results)}",
        "",
        "match_context_chars is per grep match: ...",
        "Returned handle fields for follow-up: file_path, doc_id, matched_line, line_range.",
        "",
    ]
    for item in results:
        line_number = item.get("line_number", "?")
        lines.append(f"{item.get('filename', '?')} | matched_line: {line_number} | line_range: line:{line_number}-{line_number} | doc_id: {item.get('doc_id', '?')}")
        lines.append(f"file_path: {item.get('source', '?')}")
        lines.append(str(item.get("context", "")))
        lines.append("")
    return "\n".join(lines)
```

grep result item 的 key：`line_number` (int) / `filename` (str) / `doc_id` (str) / `source` (str = file_path) / `context` (str = 匹配行+上下文)

## 目标 XML 格式

```xml
<nbrag_grep case_sensitive="false">
Follow-up handles in <match>: file_path, doc_id, line_start, line_end.

<matches>
<match file_path="D:/codes/foo.py" doc_id="abc123" line_start="15" line_end="15">
<content>
    raise ValueError("invalid id")
</content>
</match>
</matches>

</nbrag_grep>
```

- 单行匹配：`line_start == line_end == line_number`
- `filter_file_path` 非空时加到根属性：`filter_file_path="..."`
- 无结果时返回 `<error type="no_results" field="keyword">` XML
- 删除 header 散文（"grep matches: N" / "match_context_chars is per..." / "Returned handle fields..."）

## Steps

- [ ] **Step 1: 重写 `nbrag_grep` 返回部分（L553-575）为 XML**

保留 L537-543（param normalization + path_filter validation）和 L545-552（`grep_knowledge` 调用）不变。

改写 L553-575：

```python
    if not results:
        collection_issue = _collection_presence_issue_text(collection_name)
        if collection_issue:
            return collection_issue
        return (
            '<error type="no_results" field="keyword">\n'
            'No grep matches.\n'
            'Recovery: check exact wording/case, escape regex metacharacters if you intended literal matching, '
            'try regex if appropriate, or switch to nbrag_search_and_fetch for semantic discovery '
            'when this is a concept, alias, or paraphrase rather than exact source wording.\n'
            '</error>'
        )

    root_attrs = [f'case_sensitive="{"true" if case_sensitive else "false"}"']
    if path_filter:
        root_attrs.append(f'filter_file_path="{path_filter}"')
    lines = [f'<nbrag_grep {" ".join(root_attrs)}>', 'Follow-up handles in <match>: file_path, doc_id, line_start, line_end.', '', '<matches>']
    for item in results:
        line_number = item.get("line_number", "?")
        ln = str(line_number)
        file_path = str(item.get("source", "?"))
        doc_id = str(item.get("doc_id", "?"))
        context = str(item.get("context", ""))
        lines.append(f'<match file_path="{file_path}" doc_id="{doc_id}" line_start="{ln}" line_end="{ln}">')
        lines.append('<content>')
        lines.append(context)
        lines.append('</content>')
        lines.append('</match>')
    lines.append('</matches>')
    lines.append('')
    lines.append('</nbrag_grep>')
    return "\n".join(lines)
```

- [ ] **Step 2: grep 扫描确认 `matched_line` / `line_range` 在 mcp_tools.py 里无残留**

Run Grep:
```
pattern: "matched_line|line_range"
path: nbrag/mcp_tools.py
```
Expected: 0 命中

- [ ] **Step 3: import 验证**

Run:
```powershell
$env:OPENBLAS_NUM_THREADS=1
D:/ProgramData/miniconda3/envs/py312/python.exe -c "from nbrag.mcp_tools import nbrag_grep; print('import OK')"
```

- [ ] **Step 4: Commit**

```bash
git add nbrag/mcp_tools.py
git commit -m "refactor(mcp_tools): XML format for nbrag_grep, deprecate matched_line/line_range"
```

## Global Constraints

- **Python 解释器**：`D:/ProgramData/miniconda3/envs/py312/python.exe`，`$env:OPENBLAS_NUM_THREADS=1`
- **不改函数签名**
- **canonical handle 字段集**：`file_path` / `doc_id` / `line_start` / `line_end`
- **禁止变体**：`matched_line` / `line_range` / `line:N-M`
- **正文零转义**
- **不写正式测试**
