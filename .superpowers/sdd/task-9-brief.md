# Task 9: 清理 `nbrag_help` + workflow SKILL.md 中的废弃字段名

**Files:**
- Modify: `nbrag/mcp_tools.py:239-270`（`nbrag_help`）
- Modify: `nbrag/skills/nbrag-workflow/SKILL.md`

## 当前代码结构

### `nbrag_help`（实际 L239-270，注意 plan 写的 L218-251 已过时）

`nbrag_help` 不是单纯返回 SKILL.md 文本，而是：
1. L240 调 `_load_workflow_skill_text()` 读取 SKILL.md（剥掉 frontmatter）→ `skill_text`
2. L241-267 自建 `skeleton` list（独立于 SKILL.md 的简短 routing 提醒）
3. L268-269 若 `skill_text` 非空，append `"nbrag workflow skill:"` + `skill_text` 到 skeleton
4. L270 `return "\n".join(skeleton)`

**skeleton 里的废弃字段名（L266）：**
```python
"Stable follow-up fields: file_path, doc_id, chunk_index, line:N-M.",
```
→ `line:N-M` 是废弃形式，必须改成 `line_start, line_end`。

### `nbrag/skills/nbrag-workflow/SKILL.md`

通过初步扫描发现以下废弃字段名（行号基于当前文件）：

| 行号 | 当前文本 | 废弃形式 | 改成 |
|---|---|---|---|
| L64 | `You know `doc_id` + `line:N-M` and want chunk/scope context` | `line:N-M` | `line_start + line_end` |
| L201 | `- `line:N-M`` | `line:N-M` | `- `line_start`, `line_end`` |
| L220 | `- `chunk:X/Y`` | `chunk:X/Y` | `- `chunk_index` (from search results)` |
| L221 | `- `chunk_index:X`` | `chunk_index:X`（变体形式） | 合并到 L220 一行，或改成 `- `chunk_index`` |
| L225 | `### `doc_id + line:N-M`` | `line:N-M` | `### `doc_id + line_start + line_end`` |

**注意：** 上表是初步扫描，implementer 必须用 Grep 全量扫描 SKILL.md 确认所有命中，不要只改上表列出的。

## 目标

- `nbrag_help` skeleton 里 L266 改成：`"Stable follow-up fields: file_path, doc_id, chunk_index, line_start, line_end."`
- SKILL.md 所有废弃字段名（`chunk:X/Y` / `line:N-M` / `matched_line` / `line_range` / `chunk_count`）改成 canonical 形式
- 改完后 `nbrag_help()` 输出（含 appended SKILL.md 文本）里不再出现废弃形式
- **不动 SKILL.md 的整体结构、章节、其他文案**——只改字段名引用
- **不改 `nbrag_help` 的 skeleton 结构**——只改 L266 那一行的字段名

## Steps

- [ ] **Step 1: 全量 Grep 扫描 SKILL.md 找所有废弃字段名**

Run Grep:
```
pattern: "chunk:\\d|line:\\d|matched_line|line_range|chunk_count|chunk:X/Y|chunk_index:X"
path: nbrag/skills/nbrag-workflow/SKILL.md
output_mode: content, -n=true
```
记录所有命中行号和文本。补充上表未列出的命中。

- [ ] **Step 2: 全量 Grep 扫描 `nbrag_help` 函数体（mcp_tools.py L239-270）**

Run Grep:
```
pattern: "chunk:\\d|line:\\d|matched_line|line_range|chunk_count|chunk:X/Y|chunk_index:X"
path: nbrag/mcp_tools.py
output_mode: content, -n=true
```
重点看 L239-270 区间。预期 L266 命中 `line:N-M`。

- [ ] **Step 3: 改 `nbrag_help` skeleton L266**

把：
```python
"Stable follow-up fields: file_path, doc_id, chunk_index, line:N-M.",
```
改成：
```python
"Stable follow-up fields: file_path, doc_id, chunk_index, line_start, line_end.",
```

- [ ] **Step 4: 逐个改 SKILL.md 里的废弃字段名**

按 Step 1 的命中清单逐个 Edit。映射规则：
- `chunk:X/Y` → `chunk_index + total_chunks`
- `line:N-M` → `line_start + line_end`（若在散文里描述"知道 doc_id + line range"，改成 `doc_id + line_start + line_end`）
- `matched_line` → `line_start == line_end`（表达单行匹配语义）
- `line_range` → `line_start + line_end`
- `chunk_count` → `total_chunks`
- `chunk_index:X` → `chunk_index`（去掉 `:X` 后缀，canonical 就是字段名本身）

**特别注意 L220-221 区域：**
当前是：
```
Get `chunk_index` from search results such as:
- `chunk:X/Y`
- `chunk_index:X`
```
建议改成（合并两行，因为两种废弃形式都是指同一个 chunk_index 来源）：
```
Get `chunk_index` from search results such as:
- the `chunk_index` attribute on `<hit>` returned by `nbrag_search` / `nbrag_search_and_fetch`
```
或保留 list 形式但用 canonical：
```
Get `chunk_index` from search results such as:
- `chunk_index` attribute on `<hit>` from `nbrag_search` / `nbrag_search_and_fetch`
- `chunk_index` attribute on `<chunk>` from `nbrag_get_file_chunks`
```
选哪种由 implementer 判断，只要不含废弃形式即可。

- [ ] **Step 5: 改完后 Grep 复扫确认 SKILL.md 无废弃字段名**

Run Grep:
```
pattern: "chunk:\\d|line:\\d|matched_line|line_range|chunk_count|chunk:X/Y|chunk_index:X"
path: nbrag/skills/nbrag-workflow/SKILL.md
```
Expected: 0 命中

- [ ] **Step 6: Grep 复扫 `nbrag_help` 函数体无废弃字段名**

Run Grep:
```
pattern: "chunk:\\d|line:\\d|matched_line|line_range|chunk_count|chunk:X/Y|chunk_index:X"
path: nbrag/mcp_tools.py
```
重点看 L239-270 区间无命中（其他函数体里若有命中是 Task 1-8 的遗留，不在本 task 范围；但若发现新遗漏可记录到 report 里）。

- [ ] **Step 7: import 验证**

```powershell
$env:OPENBLAS_NUM_THREADS=1
D:/ProgramData/miniconda3/envs/py312/python.exe -c "from nbrag.mcp_tools import nbrag_help; print(nbrag_help()[:500])"
```
Expected: 输出前 500 字符里含 `line_start, line_end`，不含 `line:N-M` 或 `chunk:X/Y`。

- [ ] **Step 8: Commit**

```bash
git add nbrag/mcp_tools.py nbrag/skills/nbrag-workflow/SKILL.md
git commit -m "refactor: clean deprecated field names from nbrag_help and workflow SKILL"
```

## Global Constraints

- **Python 解释器**：`D:/ProgramData/miniconda3/envs/py312/python.exe`，`$env:OPENBLAS_NUM_THREADS=1`
- **canonical handle 字段集**：`file_path` / `doc_id` / `chunk_index` / `total_chunks` / `line_start` / `line_end`
- **禁止变体**：`chunk:X/Y` / `line:N-M` / `matched_line` / `line_range` / `chunk_count` / `chunk_id` / `index`（暴露给 AI）/ `chunk_index:X`
- **不动 SKILL.md 章节结构**：只改字段名引用，不删章节、不改其他文案
- **不改 `nbrag_help` skeleton 结构**：只改 L266 那一行的字段名
- **不写正式测试**
- **`_load_workflow_skill_text` 会剥 frontmatter**：SKILL.md 顶部 `---\nname:...\n---` 会被剥掉，不进入 `nbrag_help` 输出；所以 frontmatter 里的字段名无需扫描
