# Task 7 Report — 4 chunk view functions → XML

## Status
✅ Done

## Commit
`45f0456cc828da801e8a9a14034406eb0447671d` — `refactor(mcp_tools): XML format for 4 chunk view functions`

1 file changed, 130 insertions(+), 53 deletions(-)

## Test summary
Import validation passed: `from nbrag.mcp_tools import nbrag_get_adjacent_chunks, nbrag_get_file_chunks, nbrag_get_chunks_by_lines, nbrag_read_more_original_text` → `import OK` (no formal tests written, per brief).

## What changed (L678-889 in `nbrag/mcp_tools.py`)

### `nbrag_get_adjacent_chunks` (L678-737)
- Param normalization + `get_context_chunks` call untouched.
- `not_found` (both `data.found=False` and `chunks==[]` paths) → `<error type="not_found" field="doc_id">` XML with recovery hint.
- Header → `<nbrag_get_adjacent_chunks file_path="..." doc_id="..." total_chunks="..." window="..." anchor_chunk_index="...">` (`anchor_chunk_index` = input `chunk_index`; `file_path` = `str(data.get("source", "?"))`).
- Each chunk → `<chunk chunk_index="..." total_chunks="..." line_start="..." line_end="..." scope="..."><content>...</content></chunk>`, `chunk_index` from `_meta_chunk_index(chunk)`.

### `nbrag_get_file_chunks` (L740-793)
- Param normalization + `_is_absolute_file_path` + `get_file_chunks` call untouched.
- `not_found` → `<error type="not_found" field="file_path">` XML.
- `has_more` = `str(data.get("end_chunk", 0) < data.get("total_chunks", 0) - 1).lower()`.
- Header → `<nbrag_get_file_chunks file_path="..." doc_id="..." total_chunks="..." total_lines="..." start_chunk="..." max_chunks="..." has_more="...">`.
- Chunk format identical to above.

### `nbrag_get_chunks_by_lines` (L796-853)
- Param normalization + `get_context_chunks` call untouched.
- `not_found` (both paths) → `<error type="not_found" field="doc_id">` XML.
- Header → `<nbrag_get_chunks_by_lines doc_id="..." file_path="..." total_chunks="..." requested_line_start="..." requested_line_end="...">` (`requested_line_*` = input `line_start`/`line_end`).
- Chunk format identical.

### `nbrag_read_more_original_text` (L856-889)
- Param normalization + `_is_absolute_file_path` + `get_file_chunks(raw=True)` call untouched.
- `not_found` → `<error type="not_found" field="file_path">` XML.
- Header → `<nbrag_read_more_original_text file_path="..." doc_id="..." total_lines="..." line_start="..." line_end="...">` (`line_start`/`line_end` from `data`, not input).
- NO `<chunks>` collection — `<content>` placed directly under root, then closing tag.

## Grep scan
Pattern `chunk:\d|chunk:[A-Z]|line:\d|line:[A-Z]|original_file|line_range` over `nbrag/mcp_tools.py` returned 3 hits, none inside L678-889:
- L121 `def _merge_line_ranges` — function name, brief-excluded.
- L266 `nbrag_help()` prose `line:N-M` — outside Task 7 scope.
- L500 `_merge_line_ranges(...)` call — brief-excluded.

## Concerns
- `nbrag_help()` (L266) still mentions deprecated `line:N-M` marker in its prose. Out of scope for Task 7 (brief says "Do NOT touch other functions or files"), but should be cleaned up by a later task touching `nbrag_help` / workflow skill text.
- No runtime smoke test against a real collection was performed (only import check, per brief). The XML structure is straightforward and mirrors Task 1-6 patterns (`_format_hit_xml`, `_format_search_results`), so structural risk is low.
- `_meta_file_path` helper was not used for the root `file_path` attribute in `nbrag_get_adjacent_chunks` / `nbrag_get_chunks_by_lines`; brief explicitly specified `str(data.get("source", "?"))` for those two, so the helper's `filename` fallback is intentionally skipped there. `nbrag_get_file_chunks` / `nbrag_read_more_original_text` use `str(data.get("source", file_path))` (input fallback) per the same brief pattern.
