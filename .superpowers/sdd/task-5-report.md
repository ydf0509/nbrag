# Task 5 Report: 重构 `nbrag_grep`（废弃 `matched_line`）

## Status
✅ Done

## Commit hash
`f2f48a06d98705386937162ed44783abe476641e`
(short: `f2f48a0`)

Message: `refactor(mcp_tools): XML format for nbrag_grep, deprecate matched_line/line_range`

## Files changed
- `nbrag/mcp_tools.py`（仅 `nbrag_grep` 函数，L553-589）

## Changes summary
- 改写 `nbrag_grep` 返回部分为 `<nbrag_grep>` XML：
  - 根属性 `case_sensitive`；`path_filter` 非空时附加 `filter_file_path`
  - 每个 match 用 `<match file_path doc_id line_start line_end>` + `<content>` 包裹
  - 单行匹配：`line_start == line_end == line_number`
  - 无结果：返回 `<error type="no_results" field="keyword">` XML（保留 recovery 建议）
- 保留：param normalization（L537-541）、`path_filter` 绝对路径校验（L542-543）、`grep_knowledge` 调用（L545-552）、`_collection_presence_issue_text` 短路
- 删除 header 散文（`grep matches: N` / `match_context_chars is per...` / `Returned handle fields... matched_line, line_range`）

## Test summary
未写正式测试（按 brief 要求）。
- Import 验证通过：`from nbrag.mcp_tools import nbrag_grep` → `import OK`（exit 0）
- Grep 扫描 `nbrag_grep` 函数体（L529-589）：0 处 `matched_line|line_range` 残留

## Concerns
1. **文件级 grep 与 brief 期望不符（已知冲突，按 brief 优先级处理）**
   Brief Step 2 期望 `nbrag/mcp_tools.py` 全文件 `matched_line|line_range` 命中 0，但同时规定 "Do NOT touch other functions or files"。文件级仍有 3 处命中，全部在 `nbrag_grep` 之外：
   - L121: `def _merge_line_ranges` — helper 函数名，`line_range` 是 `line_ranges` 的子串误匹配（非废弃字段）。
   - L500: `merged_ranges = _merge_line_ranges(expanded_ranges)` — 同上，调用点（在 `nbrag_search_and_fetch` 内，该函数已用 XML `line_start/line_end`）。
   - L774: `f"file_path: ... | line_range: line:{line_start}-{line_end}"` — 在 `nbrag_get_chunks`（或同名函数）内，仍使用废弃的 `line_range: line:N-M` 散文格式，但属于其他函数，超出 Task 5 范围（推测为后续 task 处理对象）。
   按 brief "Do NOT touch other functions" 规则未改动这三处。`nbrag_grep` 函数体本身已 0 残留。

2. **`nbrag_get_chunks`（L774）的 `line_range` 散文**：建议在后续 task 中按相同 XML 规范重构，统一 handle 字段。

3. **`_merge_line_ranges` 命名**：若后续仍需 grep `line_range` 字段残留，建议该 helper 改名为 `_merge_line_spans` 以避免子串误匹配；当前为内部 helper，不影响 AI-facing 返回字段。
