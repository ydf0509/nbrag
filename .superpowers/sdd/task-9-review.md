# Task 9 Review

## Spec compliance: ✅

Verified against the brief (`task-9-brief.md`), the implementer's report (`task-9-report.md`), and the review-package diff (`task-9-review-package.diff`). All 8 brief steps PASS.

| Step | Brief requirement | Result | Evidence |
|---|---|---|---|
| 1 | Full Grep scan of SKILL.md for deprecated forms | PASS | Implementer used augmented pattern `line:N-M\|chunk_id\|matched_line\|line_range\|chunk_count\|chunk:X/Y\|chunk_index:X` (justified — see concern #1). Found exactly 5 hits: L64, L201, L220, L221, L225 — matches brief's table. No extras. Independently re-verified: Grep on current HEAD returns "No matches found" for the deprecated-form set. |
| 2 | Full Grep scan of `nbrag_help` body (L239-270) | PASS | Single hit at L266 (`line:N-M`). Out-of-scope hits outside L239-270 recorded for visibility (concern #4). |
| 3 | Change L266 skeleton line | PASS | Diff line 17: `-        "Stable follow-up fields: file_path, doc_id, chunk_index, line:N-M.",` → `+        "Stable follow-up fields: file_path, doc_id, chunk_index, line_start, line_end.",`. Matches brief's target text exactly. |
| 4 | Edit SKILL.md deprecated field names | PASS | All 5 locations replaced with canonical forms (see table below). No new deprecated forms introduced in the L220-221 rewrite — only canonical `chunk_index` references with source attribution. |
| 5 | Rescan SKILL.md for deprecated forms | PASS | Independent Grep with pattern `line:N-M\|chunk_id\|matched_line\|line_range\|chunk_count\|chunk:X/Y\|chunk_index:X\|chunk:\d\|line:\d` → "No matches found". |
| 6 | Rescan `nbrag_help` body for deprecated forms | PASS | L239-270 is clean. Out-of-scope `chunk_count` / `_merge_line_ranges` hits remain outside the range (concern #4 — Task 1-8 territory). |
| 7 | Import verification with `OPENBLAS_NUM_THREADS=1` | PASS | Implementer's output confirms: `line_start, line_end` present (True); `line:N-M`, `chunk:X/Y`, `chunk_index:X` all absent (False). L266 area prints exactly as expected: `Stable follow-up fields: file_path, doc_id, chunk_index, line_start, line_end.` |
| 8 | Commit | PASS | Single commit `8a48948` on branch `optimize_ret_for_llm`, parent `374004e` matches brief's BASE. 2 files, 7 insertions, 7 deletions. Commit message follows conventional-commits style. |

### SKILL.md edits detail (Step 4)

| Line | Before | After | Canonical? |
|---|---|---|---|
| L64 | `You know \`doc_id\` + \`line:N-M\` and want chunk/scope context` | `You know \`doc_id\` + \`line_start + line_end\` and want chunk/scope context` | ✅ |
| L201 | `- \`line:N-M\`` | `- \`line_start\`, \`line_end\`` | ✅ |
| L220 | `- \`chunk:X/Y\`` | `- \`chunk_index\` attribute on \`<hit>\` from \`nbrag_search\` / \`nbrag_search_and_fetch\`` | ✅ |
| L221 | `- \`chunk_index:X\`` | `- \`chunk_index\` attribute on \`<chunk>\` from \`nbrag_get_file_chunks\`` | ✅ |
| L225 | `### \`doc_id + line:N-M\`` | `### \`doc_id + line_start + line_end\`` | ✅ |

## Concerns adjudication

### Concern #1: Augmented grep pattern — BENIGN

The brief's Step 1 pattern `chunk:\d|line:\d|...` literally would NOT match the placeholder form `line:N-M` because `N` and `M` are letters, not digits (`\d` requires `[0-9]`). The implementer correctly identified this gap and augmented the pattern to `line:N-M|chunk_id|matched_line|line_range|chunk_count|chunk:X/Y|chunk_index:X`. The augmented pattern is a strict superset of the brief's intent (it covers all forms in the "禁止变体" list). It found exactly the 5 hits the brief's table listed — no more, no less. This is a correct and necessary augmentation, not a deviation.

### Concern #2: BOM stripped from SKILL.md — BENIGN

The Edit tool changed `-﻿---` (UTF-8 BOM + `---`) to `---` at L1 of SKILL.md. Verified harmless by reading `_strip_markdown_frontmatter` at `nbrag/mcp_tools.py:29-39`:

```python
def _strip_markdown_frontmatter(text: str) -> str:
    text = text.lstrip("\ufeff")  # strips BOM if present
    if not text.startswith("---"):
        return text.strip()
    ...
```

The function explicitly calls `text.lstrip("\ufeff")` to strip a BOM before parsing frontmatter. So the runtime behavior was already BOM-agnostic — the file with BOM and the file without BOM produce identical `nbrag_help()` output. Step 7 import verification confirms the skill body still appends correctly. The BOM removal is a no-op for AI-facing behavior. No action needed.

### Concern #3: L220-221 two-item list rewrite choice — BENIGN

The brief explicitly offered two options (merge into one line, or keep two-item list with canonical names). The implementer chose the two-item list form:

```
- `chunk_index` attribute on `<hit>` from `nbrag_search` / `nbrag_search_and_fetch`
- `chunk_index` attribute on `<chunk>` from `nbrag_get_file_chunks`
```

This preserves the original list structure (minimal structural change), uses only canonical `chunk_index` references, and adds useful source attribution (which tool returns which XML element). Both options were pre-approved by the brief. No issue.

### Concern #4: Out-of-scope `chunk_count` / `_merge_line_ranges` hits — BENIGN (correctly out of scope)

Independent Grep confirms the 6 hits the implementer reported:
- L121: `def _merge_line_ranges(...)` — function name (not an AI-facing field reference)
- L181: `info.get("chunks", info.get("chunk_count", 0))` — fallback dict key
- L500: `_merge_line_ranges(expanded_ranges)` — function call
- L672: `item.get("total_chunks", item.get("chunk_count", "?"))` — fallback dict key
- L923: `row.get("total_chunks", row.get("chunk_count", "?"))` — fallback dict key
- L953: `info.get("chunks", info.get("chunk_count", 0))` — fallback dict key

All 6 are outside L239-270. The 4 `chunk_count` hits are all in `.get("chunk_count", ...)` fallback positions, which the brief's exception explicitly permits ("`chunk_count` is allowed inside `.get("chunk_count", ...)` fallback positions when reading the underlying layer"). The 2 `_merge_line_ranges` hits are a function name, not an AI-facing field reference. Brief Step 6 explicitly says: "其他函数体里若有命中是 Task 1-8 的遗留，不在本 task 范围". Correctly out of scope.

## Code quality

- **Critical findings (must fix before merge):** None.
- **Important findings (should fix):** None.
- **Minor findings (nice to have):** None.

The diff is minimal (7 insertions, 7 deletions across 2 files), surgical (only the targeted field names changed), and structurally conservative (skeleton list order preserved, SKILL.md sections and paragraphs preserved). The L220-221 rewrite is the only place where the wording changed beyond a strict token swap, and it stays within the brief's pre-approved options while using only canonical field names. No new deprecated forms were introduced.

## Verdict

**APPROVED** — The implementation matches the brief on all 8 steps, honors all global constraints (canonical handle set, no SKILL.md structural changes, no `nbrag_help` skeleton reordering, correct Python interpreter used for verification), and all 4 implementer-flagged concerns are benign observations rather than real issues. The diff is clean, minimal, and ready to merge.
