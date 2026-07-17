# Task 5 Review: 重构 `nbrag_grep`（废弃 `matched_line`）

## Spec Compliance ✅

| 约束 | 期望 | 实际 | 结果 |
|---|---|---|---|
| 只改 `nbrag_grep` | `nbrag/mcp_tools.py` 仅 `nbrag_grep` 一处修改 | diff 仅触及 L550-589 区段，无其他函数改动 | ✅ |
| 函数签名不变 | `nbrag_grep(keyword, collection_name, max_results=10, case_sensitive=False, filter_file_path="", match_context_chars=...)` | L529-536 签名与原一致 | ✅ |
| `line_start`/`line_end` 替代 `matched_line`/`line_range` | 单行匹配 `line_start==line_end==line_number` | L581: `line_start="{ln}" line_end="{ln}"`（同源变量） | ✅ |
| 无结果返回 XML error | `<error type="no_results" field="keyword">` | L558-563 完全匹配 | ✅ |
| 删除 header 散文 | 删除 `grep matches: N` / `match_context_chars is per...` / `Returned handle fields...` | diff 显示三行散文全部移除 | ✅ |
| param normalization 不变 | L537-541 原样保留 | L537-541 一字未改 | ✅ |
| path_filter 校验不变 | L542-543 原样保留 | L542-543 一字未改 | ✅ |
| `grep_knowledge` 调用不变 | L545-552 原样保留 | L545-552 一字未改 | ✅ |
| 不写测试 | 不新增测试文件 | 无测试文件改动 | ✅ |

## Verification Checklist

### 1. XML 良构 ✅
Mock 输出（注入伪 `grep_knowledge`，绕过 chromadb 基建异常）：

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

- 根标签开/闭匹配：`<nbrag_grep>` / `</nbrag_grep>`
- `<matches>` / `</matches>` 匹配
- 每个 `<match>` 有 `</match>` 闭合
- 每个 `<content>` 有 `</content>` 闭合
- 属性引号成对

### 2. `line_start==line_end` 单行匹配 ✅
L577: `ln = str(line_number)` → L581 `line_start="{ln}" line_end="{ln}"`，同变量双用，必然相等。

### 3. `case_sensitive` 根属性 ✅
L566: `root_attrs = [f'case_sensitive="{"true" if case_sensitive else "false"}"']` 永远附加；测试输出 `case_sensitive="false"` / `case_sensitive="true"` 均正确。

### 4. `filter_file_path` 条件附加 ✅
L567-568: `if path_filter: root_attrs.append(f'filter_file_path="{path_filter}"')`。
- 空 path_filter：仅 `case_sensitive` 属性
- 非空 path_filter：附加 `filter_file_path="..."`

### 5. `<content>` 包裹上下文 ✅
L582-584:
```python
lines.append('<content>')
lines.append(context)
lines.append('</content>')
```

### 6. 改动函数内无 `matched_line`/`line_range` 残留 ✅
Grep 全文件扫描命中 3 处，全部位于 `nbrag_grep`（L529-589）之外：
- L121: `def _merge_line_ranges` — helper 名（`line_ranges` 子串误匹配，非废弃字段）
- L500: `_merge_line_ranges(...)` 调用点（在 `nbrag_search_and_fetch` 内，该函数已是 XML 格式）
- L774: `line_range: line:{line_start}-{line_end}` — 在 `nbrag_get_chunks` 内（属后续 task 范围）

`nbrag_grep` 函数体本身 **0 残留**，符合 brief 的 "Do NOT touch other functions" 约束。

### 7. 无结果 error 格式 ✅
Mock 空结果输出：
```xml
<error type="no_results" field="keyword">
No grep matches.
Recovery: check exact wording/case, escape regex metacharacters if you intended literal matching, try regex if appropriate, or switch to nbrag_search_and_fetch for semantic discovery when this is a concept, alias, or paraphrase rather than exact source wording.
</error>
```
- 根标签 `<error type="no_results" field="keyword">`
- 包含 `No grep matches.` 简短说明
- 包含 `Recovery:` 建议路径（精确措辞/case、转义 regex 元字符、改用 `nbrag_search_and_fetch` 语义检索）
- `</error>` 闭合

### 8. Import 验证 ✅
`from nbrag.mcp_tools import nbrag_grep` → exit 0，输出 `import OK`。

### 9. Commit 验证 ✅
- Hash: `f2f48a06d98705386937162ed44783abe476641e`（短 `f2f48a0`）
- Message: `refactor(mcp_tools): XML format for nbrag_grep, deprecate matched_line/line_range`
- 与 brief Step 4 期望一致

## Quality Assessment: Approved

### 优点
1. **严格遵循 brief 边界**：仅改 L550-589 返回段，param normalization / path_filter 校验 / `grep_knowledge` 调用 / `_collection_presence_issue_text` 短路全部原样保留。
2. **canonical handle 字段集统一**：`file_path` / `doc_id` / `line_start` / `line_end` 与 Task 4 `nbrag_search_and_fetch` 保持一致，AI 可跨工具链式调用。
3. **recovery 建议保留**：无结果时不仅返回错误标签，还给出可操作的恢复路径（包括引导至 `nbrag_search_and_fetch` 做语义发现），对 AI agent 友好。
4. **mock 输出实测良构**：通过注入伪 `grep_knowledge` 验证三个分支（有结果无 filter / 有结果带 filter case_sensitive=True / 无结果）的 XML 结构均正确。
5. **报告透明披露冲突**：明确说明文件级 `line_range` 残留 3 处位于其他函数，按 brief "Do NOT touch other functions" 优先级未动，并建议后续 task 处理。

### 观察（非阻塞）
1. **正文零转义（设计约束，非缺陷）**：测试输出中 `x < y and y > z` 包含字面 `<` / `>`，未做 XML 转义。这是 brief 明确的 "正文零转义" 约束，是 nbrag 项目 AI-facing XML 的统一设计（内容面向 AI 解析，非严格 XML parser），与 `nbrag_search_and_fetch` 等其他工具一致。
2. **L774 `nbrag_get_chunks` 的 `line_range: line:N-M` 散文**：仍使用废弃格式，建议在后续 task 中按相同 XML 规范重构以统一 handle 字段（已在报告中提示）。

## 结论

- Spec ✅
- Quality: **Approved**
- Summary: `nbrag_grep` 已按 brief 重构为良构 XML，`line_start==line_end` 单行匹配、`case_sensitive`/`filter_file_path` 属性条件正确、无结果 `<error type="no_results" field="keyword">` 格式正确，函数体内无 `matched_line`/`line_range` 残留，签名与前置逻辑保持不变，import 与 commit 均已验证。
