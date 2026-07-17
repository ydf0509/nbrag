# Task 6: 重构 `nbrag_find_definition`

**Files:**
- Modify: `nbrag/mcp_tools.py:592-642`（`nbrag_find_definition`）

## 当前代码（L592-642）

`find_symbol_definition` 返回的 result item key：`symbol_type` / `qualified_name` / `source`(=file_path) / `line_start` / `line_end` / `doc_id` / `definition`(或 `content`) / `methods_summary`

`python_symbol_types = {"class", "function", "method"}`，非 Python 的 `symbol_type` → `display_symbol_type = "regex_fallback"`

当前格式用 `line:N-M` / `doc_id:xxx` 散文 + `file_path: xxx`。

## 目标 XML 格式

```xml
<nbrag_find_definition>
Follow-up handles in <definition>: file_path, doc_id, line_start, line_end.

<definitions>
<definition symbol_type="class" qualified_name="UserService" file_path="D:/codes/services.py" doc_id="abc123" line_start="10" line_end="50">
<content>
class UserService:
    ...
</content>
<methods_summary>
- get_by_id(id)
- delete(id)
</methods_summary>
</definition>
</definitions>

</nbrag_find_definition>
```

关键规则：
- `symbol_type`：`class` / `function` / `method` / `regex_fallback`
- `methods_summary` 为空时省略该子元素
- `definition` 取 `r.get("definition") or r.get("content", "")`
- 无结果 → `<error type="no_results" field="symbol">` XML
- "Only regex fallback" 警告：当 `has_non_python_fallback and not has_python_definition` 时，在 `<definitions>` 前加一行散文提醒（不加 XML 标签）
- 删除 header 散文（"definitions: N" / "Returned handle fields..."）

## Steps

- [ ] **Step 1: 重写 `nbrag_find_definition` 返回部分（L599-642）为 XML**

保留 L597-598（param normalization + `find_symbol_definition` 调用）不变。

改写 L599-642：

```python
    if not results:
        collection_issue = _collection_presence_issue_text(collection_name)
        if collection_issue:
            return collection_issue
        return (
            '<error type="no_results" field="symbol">\n'
            'No definition found. Python source may use a different exact name, or this knowledge base may be non-Python text.\n'
            'Recovery: try nbrag_grep for exact text/regex, use nbrag_search_and_fetch for concept/example discovery, '
            'or verify that this collection actually contains Python .py source files.\n'
            '</error>'
        )

    python_symbol_types = {"class", "function", "method"}
    has_python_definition = any(str(r.get("symbol_type", "")).lower() in python_symbol_types for r in results)
    has_non_python_fallback = any(str(r.get("symbol_type", "")).lower() not in python_symbol_types for r in results)

    lines = ['<nbrag_find_definition>', 'Follow-up handles in <definition>: file_path, doc_id, line_start, line_end.', '']
    if has_non_python_fallback and not has_python_definition:
        lines.append('Only regex fallback results were found. For non-Python text, use nbrag_grep for exact wording lookup.')
        lines.append('')
    lines.append('<definitions>')
    for r in results:
        symbol_type = str(r.get("symbol_type", "unknown"))
        qualified_name = r.get("qualified_name") or symbol
        file_path = str(r.get("source", "?"))
        line_start = str(r.get("line_start", "?"))
        line_end = str(r.get("line_end", "?"))
        doc_id = str(r.get("doc_id", "?"))
        definition = str(r.get("definition") or r.get("content", ""))
        methods_summary = str(r.get("methods_summary", ""))
        display_symbol_type = symbol_type if symbol_type.lower() in python_symbol_types else "regex_fallback"

        lines.append(f'<definition symbol_type="{display_symbol_type}" qualified_name="{qualified_name}" file_path="{file_path}" doc_id="{doc_id}" line_start="{line_start}" line_end="{line_end}">')
        lines.append('<content>')
        lines.append(definition)
        lines.append('</content>')
        if methods_summary:
            lines.append('<methods_summary>')
            lines.append(methods_summary)
            lines.append('</methods_summary>')
        lines.append('</definition>')
    lines.append('</definitions>')
    lines.append('')
    lines.append('</nbrag_find_definition>')
    return "\n".join(lines)
```

- [ ] **Step 2: grep 扫描确认该函数内无 `line:N-M` 残留**

- [ ] **Step 3: import 验证**

```powershell
$env:OPENBLAS_NUM_THREADS=1
D:/ProgramData/miniconda3/envs/py312/python.exe -c "from nbrag.mcp_tools import nbrag_find_definition; print('import OK')"
```

- [ ] **Step 4: Commit**

```bash
git add nbrag/mcp_tools.py
git commit -m "refactor(mcp_tools): XML format for nbrag_find_definition"
```

## Global Constraints

- **Python 解释器**：`D:/ProgramData/miniconda3/envs/py312/python.exe`，`$env:OPENBLAS_NUM_THREADS=1`
- **不改函数签名**
- **canonical handle 字段集**：`file_path` / `doc_id` / `line_start` / `line_end`
- **禁止变体**：`line:N-M` / `doc_id:xxx`（key:value 形式）
- **正文零转义**
- **不写正式测试**
