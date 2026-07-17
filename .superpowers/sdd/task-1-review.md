# Task 1 Review: 清理 `server.py` 文案 + 补 boundary case 说明

## Verdicts

- **Spec compliance**: ✅ (all requirements met, nothing extra)
- **Task quality**: Approved (with 2 Minor findings, both inherited from the brief's literal mapping rules, not implementer errors)

## 1. Spec compliance — 逐条核对

| Brief 要求 | 实现情况 | 结论 |
|---|---|---|
| 只改 `nbrag/server.py` | `git show --stat 4cf345b` 确认仅 1 file changed (12 +, 12 -) | ✅ |
| 不改函数签名/逻辑 | diff 全部落在 Field description 与 docstring 文本内，无入参名/类型/默认值/return 语句变化 | ✅ |
| `start_chunk` 保留为合法入参名 | L320 / L331 仍为 `start_chunk`，未改名 | ✅ |
| `filter_file_path` 保留为合法入参名 | L97 / L110 / L164 / L192 / L222 / L267 均保留 | ✅ |
| `filter_file_path` 追加值兼容说明 | L97 末尾追加 "Value comes from the file_path handle returned by nbrag tools."（逐字） | ✅ |
| `start_chunk` 追加值兼容说明 | L320 末尾追加 "0-based chunk index; same value space as the chunk_index handle, but used as a pagination cursor (semantic: 'start browsing from chunk N')."（逐字） | ✅ |
| `chunk:X/Y` → `chunk_index + total_chunks` | L133, L353 已替换 | ✅ |
| `line:N-M` → `line_start + line_end` | L68, L136, L245, L370, L371 已替换 | ✅ |
| `matched_line` → `line_start == line_end` | L276 已替换 | ✅ |
| `line_range` → `line_start + line_end` | L276, L379 已替换 | ✅ |
| `chunk_count` → `total_chunks` | L395 已删除 `chunk_count`（因 `total_chunks` 已在同列表中，做去重处理） | ✅ |
| `chunk_id`（暴露给 AI）必须废弃 | grep `chunk_id` 0 命中 | ✅ |
| Step 5 grep 验证 0 命中 | 实测 `chunk:\d\|line:\d\|matched_line\|line_range\|chunk_count` = 0；扩展模式 `chunk:X\|line:N\|chunk_id` = 0 | ✅ |
| 不写测试 | diff 无测试文件 | ✅ |
| commit message 格式 | `refactor(server): clean deprecated field names from Field descriptions` 与 brief 一致 | ✅ |

**结论**：12 处编辑全部对应 brief 的明确要求，无多余改动，无遗漏项。

## 2. Task quality — 代码质量审查

### ✅ 通过项

- **范围纪律**：implementer 严格限定在文案替换，未顺手重构列表结构、未改 mcp_tools 调用、未触碰非 server.py 文件。
- **去重判断**（Edit 12, L395）：`nbrag_list` 原文案为 `chunk_count, total_chunks`，直接套用 `chunk_count → total_chunks` 会产生 `total_chunks, total_chunks` 的重复。implementer 选择删除 `chunk_count` 而非保留重复项，这是合理的语义保持决策，并在 report 中明确说明。
- **brief grep 模式缺陷识别**：brief Step 1 的 grep 模式用 `\d` 匹配数字，但 server.py 实际用的是字母占位符 `X/Y/N/M`，导致 grep 漏匹配。implementer 主动做人工扫描补齐，并在 report "Concerns / doubts" 节明确指出该缺陷——这是良好的审查留痕。
- **report 透明度**：4 条 concerns/doubts 全部如实记录（grep 模式缺陷、L133 冗余、"line range" 空格形式保留、start_chunk 注释内冗余），便于下游 reviewer 复核。
- **`start_chunk` 合法性说明**：L320 追加的注释明确指出 "same value space as the chunk_index handle, but used as a pagination cursor"，对 AI 理解 `start_chunk` 与 `chunk_index` 的值空间相同但语义不同很有帮助。

### ⚠ Minor findings

#### M1. L276 `nbrag_grep` docstring — `line_start == line_end` 作为 "field" 列出语义略生硬
- **位置**：`nbrag/server.py` L276
- **现状**：`Returned text includes reusable follow-up fields such as line_start == line_end, line_start + line_end, doc_id, and file_path.`
- **问题**：`line_start == line_end` 是一个布尔条件（表示单行匹配），不是一个 "field"。在 "follow-up fields such as ..." 的列举语境里，把条件当 field 列出，对 AI 消费者略有歧义。
- **根因**：brief 明确规定 `matched_line` → `line_start == line_end`，implementer 逐字遵循。
- **严重度**：Minor（继承自 brief 的映射规则，非 implementer 自主决策）
- **建议**：如后续 Task 涉及 nbrag_grep 返回 XML 化，可考虑改为 `line_start + line_end (for single-line matches, line_start == line_end)` 之类更清晰的表述。本 Task 不要求修。

#### M2. L133-135 `nbrag_search` docstring — 列表冗余
- **位置**：`nbrag/server.py` L133-135
- **现状**：
  ```
  - chunk_index + total_chunks
  - chunk_index:X
  - total_chunks:Y
  ```
- **问题**：L133 是 `chunk:X/Y` 的替换结果（`chunk_index + total_chunks`），与紧随其后的 L134 (`chunk_index:X`) 和 L135 (`total_chunks:Y`) 信息重复。AI 看到三行里两行说的是同一件事，可能短暂困惑。
- **根因**：brief 规定 `chunk:X/Y` → `chunk_index + total_chunks`，implementer 逐字替换未做列表重构（report Concern #2 已说明"为不超出 task scope 未做列表重构"）。
- **严重度**：Minor（implementer 的范围纪律判断是正确的；如擅自重构反而可能违反"只改文案不动结构"的隐含约束）
- **建议**：可在后续清理 Task 中考虑把 L133-135 合并为 `chunk_index:X / total_chunks:Y` 一行。本 Task 不要求修。

### ✅ 无 Critical / Important 问题

- 无函数签名变更
- 无逻辑变更
- 无非 server.py 文件被改
- 无废弃字段名残留（grep 三连验证通过）
- 无硬编码密码或敏感信息引入
- commit message 符合 brief 规定格式

## 3. 与 report 的一致性核对

implementer report 中列出的 12 处 Edit 与 review-package diff 完全一致：
- 行号、before/after 文本、映射规则全部对得上
- report 中 "4. Concerns / doubts" 的 4 条疑虑均经本次 review 复核确认属实
- report 中提到的 commit hash `4cf345b` 经 `git show` 验证存在且 stat 匹配

## 4. 最终结论

**Spec compliance: ✅** — 12 处编辑全部命中 brief 要求，无多余、无遗漏、无越界。

**Task quality: Approved** — 实现干净、范围纪律严格、report 透明。2 个 Minor finding 均继承自 brief 的字面映射规则，implementer 的逐字遵循是正确选择，不建议在本 Task 内修复。
