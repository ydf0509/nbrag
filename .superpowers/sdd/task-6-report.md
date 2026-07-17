# Task 6 Report: 重构 `nbrag_find_definition` 为 XML 格式

- **Status**: ✅ Done
- **Commit hash**: `a7f9a57`
- **Test summary**: `from nbrag.mcp_tools import nbrag_find_definition` 导入成功（exit 0），无语法错误。
- **Files changed**: `nbrag/mcp_tools.py`（仅 L599-643 区域）

## 改动要点

1. **无结果路径**：原散文字符串改为 `<error type="no_results" field="symbol">` XML，"Possible adjustments" 措辞替换为 "Recovery"。
2. **结果列表**：删除 `definitions: N` / "Returned handle fields..." header 散文；改为 `<nbrag_find_definition>` 根元素 + `Follow-up handles in <definition>: file_path, doc_id, line_start, line_end.` 一行提示 + `<definitions>` 容器。
3. **每条定义**：原 `[i/N] type name | line:N-M | doc_id:xxx` / `file_path: xxx` 散文改为单个 `<definition symbol_type="..." qualified_name="..." file_path="..." doc_id="..." line_start="..." line_end="...">` 元素，正文放入 `<content>` 子元素。
4. **methods_summary**：作为 `<methods_summary>` 子元素，为空时省略。
5. **symbol_type 归一**：保留 `display_symbol_type` 逻辑——Python 类型 (`class`/`function`/`method`) 原样输出，非 Python 输出 `regex_fallback`。
6. **regex fallback 警告**：当 `has_non_python_fallback and not has_python_definition` 时，在 `<definitions>` 前加一行散文提醒（无 XML 标签），符合 brief 要求。
7. **保留**：L597-598（`_int_param` 归一化 + `find_symbol_definition` 调用）未改动；函数签名未改动；`_collection_presence_issue_text` 优先返回逻辑未改动。

## Grep 扫描结果

对 `nbrag/mcp_tools.py` 搜索 `line:{` / `doc_id:{` / `file_path: ` / `definitions: \d`：
- `nbrag_find_definition`（L592-643）范围内**零匹配**，无残留 key:value 散文格式。
- 其余命中位于 L227 / L706 / L744 / L775 / L781 / L808，均属其他函数（`nbrag_list_collections`、`nbrag_fetch_chunks`、`nbrag_read_file` 等），不在 Task 6 范围。

## Concerns

- 无。改动严格遵循 brief，未触碰其他函数或文件，未写测试，未改函数签名，canonical handle 字段集 (`file_path`/`doc_id`/`line_start`/`line_end`) 与其他已重构函数一致。
