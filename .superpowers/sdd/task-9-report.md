# Task 9 Report: Clean deprecated field names from `nbrag_help` and workflow SKILL.md

## Summary of changes

Replaced all deprecated field-name forms (`line:N-M`, `chunk:X/Y`, `chunk_index:X`) with canonical handle names (`line_start`, `line_end`, `chunk_index`, `total_chunks`) in two surfaces: the `nbrag_help()` function's skeleton list in `nbrag/mcp_tools.py` (L266), and the body of `nbrag/skills/nbrag-workflow/SKILL.md` (5 locations: L64, L201, L220, L221, L225). The SKILL.md body is appended verbatim into `nbrag_help()` output via `_load_workflow_skill_text()`, so cleaning it there fixes both the human-readable skill and the AI-facing `nbrag_help()` output at once.

No structural changes were made: the `nbrag_help` skeleton list keeps its original order and content except for the single L266 field-name swap; SKILL.md sections, paragraphs, and prose are unchanged except for the field-name references. The L220-221 list was rewritten to use canonical `chunk_index` attribute references (preserving the two-item list shape) instead of the deprecated `chunk:X/Y` / `chunk_index:X` forms.

## Final state of `nbrag_help` skeleton L266

**Before:**
```python
"Stable follow-up fields: file_path, doc_id, chunk_index, line:N-M.",
```

**After:**
```python
"Stable follow-up fields: file_path, doc_id, chunk_index, line_start, line_end.",
```

## List of all SKILL.md edits

| Line | Before | After |
|---|---|---|
| L64 | `\| Chunk view covering a line range \| \`nbrag_get_chunks_by_lines()\` \| You know \`doc_id\` + \`line:N-M\` and want chunk/scope context \| You only need raw source text \|` | `\| ... \| You know \`doc_id\` + \`line_start + line_end\` and want chunk/scope context \| ... \|` |
| L201 | `- \`line:N-M\`` | `- \`line_start\`, \`line_end\`` |
| L220 | `- \`chunk:X/Y\`` | `- \`chunk_index\` attribute on \`<hit>\` from \`nbrag_search\` / \`nbrag_search_and_fetch\`` |
| L221 | `- \`chunk_index:X\`` | `- \`chunk_index\` attribute on \`<chunk>\` from \`nbrag_get_file_chunks\`` |
| L225 | `### \`doc_id + line:N-M\`` | `### \`doc_id + line_start + line_end\`` |

## Step 1 grep result (SKILL.md scan)

Pattern used (augmented beyond the brief's pattern, because `line:\d` does not match the literal placeholder form `line:N-M` where `N`/`M` are letters):

```
pattern: line:N-M|chunk_id|matched_line|line_range|chunk_count|chunk:X/Y|chunk_index:X
path:    nbrag/skills/nbrag-workflow/SKILL.md
```

Output (5 hits):
```
64:| Chunk view covering a line range | `nbrag_get_chunks_by_lines()` | You know `doc_id` + `line:N-M` and want chunk/scope context | You only need raw source text |
201:- `line:N-M`
220:- `chunk:X/Y`
221:- `chunk_index:X`
225:### `doc_id + line:N-M`
```

These match the brief's table exactly. No additional hits beyond the brief's list.

## Step 2 grep result (mcp_tools.py scan)

Pattern used (same augmented pattern):

```
pattern: line:N-M|chunk_id|matched_line|chunk:X/Y|chunk_index:X
path:    nbrag/mcp_tools.py
```

Output (1 hit in target range L239-270):
```
266:        "Stable follow-up fields: file_path, doc_id, chunk_index, line:N-M.",
```

For completeness, an earlier scan with the brief's original pattern (`chunk:\d|line:\d|matched_line|line_range|chunk_count|chunk:X/Y|chunk_index:X`) also surfaced out-of-scope hits in `nbrag/mcp_tools.py` outside L239-270:
- L121: `def _merge_line_ranges(...)` — function name containing `line_range` substring (not an AI-facing field name)
- L181, L672, L923, L953: `chunk_count` used as a fallback dict key inside `.get("chunks", info.get("chunk_count", 0))` patterns (Task 1-8 territory, kept as backward-compatible fallbacks)
- L500: `_merge_line_ranges(expanded_ranges)` — function call

These are all outside the `nbrag_help` function body (L239-270) and are Task 1-8 leftovers. Per the brief, they are out of scope for Task 9.

## Step 5 grep result (SKILL.md rescan, 0 hits)

```
pattern: line:N-M|chunk_id|matched_line|line_range|chunk_count|chunk:X/Y|chunk_index:X|chunk:\d|line:\d
path:    nbrag/skills/nbrag-workflow/SKILL.md
```

Output:
```
No matches found
```

## Step 6 grep result (mcp_tools.py rescan, L239-270 clean)

```
pattern: line:N-M|chunk_id|matched_line|chunk:X/Y|chunk_index:X
path:    nbrag/mcp_tools.py
```

Output:
```
No matches found
```

L239-270 is clean. (Out-of-scope `chunk_count` / `_merge_line_ranges` hits outside L239-270 remain as Task 1-8 leftovers.)

## Step 7 import verification output

Command:
```powershell
$env:OPENBLAS_NUM_THREADS=1
D:/ProgramData/miniconda3/envs/py312/python.exe -c "from nbrag.mcp_tools import nbrag_help; out = nbrag_help(); print('CONTAINS line_start, line_end:', 'line_start, line_end' in out); print('CONTAINS line:N-M:', 'line:N-M' in out); print('CONTAINS chunk:X/Y:', 'chunk:X/Y' in out); print('CONTAINS chunk_index:X:', 'chunk_index:X' in out); print('---L266 area---'); idx = out.find('Stable follow-up fields'); print(out[idx:idx+120])"
```

Output:
```
CONTAINS line_start, line_end: True
CONTAINS line:N-M: False
CONTAINS chunk:X/Y: False
CONTAINS chunk_index:X: False
---L266 area---
Stable follow-up fields: file_path, doc_id, chunk_index, line_start, line_end.

nbrag workflow skill:
# role and goal

I
```

All assertions pass: canonical `line_start, line_end` is present; deprecated `line:N-M`, `chunk:X/Y`, `chunk_index:X` are absent from the full `nbrag_help()` output (which includes both the skeleton and the appended SKILL.md body).

## Final commit hash

- Short: `8a48948`
- Full: `8a489486738abfaf793e3b1cd1c440425a4aa44d`
- Parent (base): `374004e` (matches the brief's BASE commit)
- Branch: `optimize_ret_for_llm`
- Files changed: 2 files, 7 insertions(+), 7 deletions(-)

## Concerns or deviations from the brief

1. **Augmented grep pattern.** The brief's Step 1 pattern `chunk:\d|line:\d|matched_line|line_range|chunk_count|chunk:X/Y|chunk_index:X` does NOT match the literal placeholder form `line:N-M` (because `N` and `M` are letters, not digits, so `line:\d` fails to match). I augmented the pattern to `line:N-M|chunk_id|matched_line|line_range|chunk_count|chunk:X/Y|chunk_index:X` to catch all deprecated forms listed in the brief's "禁止变体" set. This is how I found the L64, L201, L225 hits that the brief's table listed but the brief's pattern would have missed. No new hits beyond the brief's table were found.

2. **BOM stripped from SKILL.md.** The Edit tool removed the UTF-8 BOM (`\xEF\xBB\xBF`) from the start of `nbrag/skills/nbrag-workflow/SKILL.md` (diff shows `-﻿---` → `---`). This was an unintended side effect of the Edit tool, not a deliberate change. It is harmless: `_load_workflow_skill_text()` still strips the frontmatter correctly (confirmed by Step 7 import verification, which shows the skill body is appended without the frontmatter). The BOM removal does not affect any AI-facing behavior.

3. **L220-221 rewrite choice.** The brief offered two options for the L220-221 region (merge into one line, or keep two-item list with canonical names). I chose the two-item list form to preserve the original list structure with minimal structural change:
   ```
   - `chunk_index` attribute on `<hit>` from `nbrag_search` / `nbrag_search_and_fetch`
   - `chunk_index` attribute on `<chunk>` from `nbrag_get_file_chunks`
   ```
   This adds useful source attribution (which tool returns which XML element) while staying canonical.

4. **Out-of-scope `chunk_count` references remain.** As noted in Step 2, `nbrag/mcp_tools.py` still contains `chunk_count` as a fallback dict key in several functions outside L239-270 (L181, L672, L923, L953) and `_merge_line_ranges` as a function name (L121, L500). These are Task 1-8 territory (backward-compatible fallbacks for older metadata) and are explicitly out of scope per the brief. Recording here for visibility; Task 10 verification may want to confirm they do not leak into AI-facing output.
