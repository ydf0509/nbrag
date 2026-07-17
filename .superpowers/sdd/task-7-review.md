# Task 7 Review — 4 chunk view functions → XML

## Spec Compliance ✅

All 4 functions in `nbrag/mcp_tools.py` (L678-889) verified against brief.

### Signatures (unchanged) ✅
- L678 `nbrag_get_adjacent_chunks(doc_id: str, chunk_index: int, collection_name: str, window: int = 3) -> str`
- L740 `nbrag_get_file_chunks(file_path: str, collection_name: str, start_chunk: int = 0, max_chunks: int = 10) -> str`
- L796 `nbrag_get_chunks_by_lines(doc_id: str, line_start: int, line_end: int, collection_name: str) -> str`
- L856 `nbrag_get_raw_file(file_path: str, collection_name: str, line_start: int = -1, line_end: int = -1) -> str`

### `nbrag_get_adjacent_chunks` (L678-737) ✅
- Param normalization + `get_context_chunks` call untouched.
- Both not-found paths (`data.found=False` and `chunks==[]`) → `<error type="not_found" field="doc_id">` XML with recovery hint.
- Root attrs: `file_path` (from `str(data.get("source", "?"))`), `doc_id`, `total_chunks`, `window`, `anchor_chunk_index` (= input `chunk_index`) — all present, matches brief.
- `<chunk>` uses canonical attrs (`chunk_index`/`total_chunks`/`line_start`/`line_end`, optional `scope`); `chunk_index` from `_meta_chunk_index(chunk)`.
- `<chunks>` wrapper + closing `</nbrag_get_adjacent_chunks>` present.

### `nbrag_get_file_chunks` (L740-793) ✅
- Param normalization + `_is_absolute_file_path` + `get_file_chunks` call untouched.
- Not-found → `<error type="not_found" field="file_path">` XML.
- `has_more = str(data.get("end_chunk", 0) < data.get("total_chunks", 0) - 1).lower()` — matches brief formula exactly.
- Root attrs include `start_chunk` + `max_chunks` (input values) — matches brief.
- `<chunk>` format identical to adjacent function; `_meta_chunk_index` used.

### `nbrag_get_chunks_by_lines` (L796-853) ✅
- Param normalization + `get_context_chunks` call untouched.
- Both not-found paths → `<error type="not_found" field="doc_id">` XML.
- Root attrs: `requested_line_start` / `requested_line_end` = input `line_start` / `line_end` — matches brief.
- `<chunk>` format identical; `_meta_chunk_index` used.

### `nbrag_get_raw_file` (L856-889) ✅
- Param normalization + `_is_absolute_file_path` + `get_file_chunks(raw=True)` call untouched.
- Not-found → `<error type="not_found" field="file_path">` XML.
- Root attrs: `file_path`, `doc_id`, `total_lines`, `line_start`, `line_end` (from `data`, not input) — matches brief.
- NO `<chunks>` collection tag — `<content>` placed directly under root, then closing `</nbrag_get_raw_file>`. ✅

### Deprecated forms scan ✅
Grep pattern `chunk:\d|chunk:[A-Z]|line:\d|line:[A-Z]|original_file|line_range` over `nbrag/mcp_tools.py` returns 3 hits, **none inside L678-889**:
- L121 `def _merge_line_ranges` — function name, brief-excluded.
- L266 `nbrag_help()` prose `line:N-M` — outside Task 7 scope (brief: "Only 4 functions modified").
- L500 `_merge_line_ranges(...)` call — brief-excluded.

No occurrences of `chunk:X` / `line:N-M` / `original_file` / `line_range` in any of the 4 refactored functions.

### Helper usage ✅
- `_meta_chunk_index(chunk)` used in all 3 chunk-emitting functions (adjacent / file_chunks / by_lines) for `chunk_index` attribute.
- `_path_error("file_path")` reused for path-validation errors in `nbrag_get_file_chunks` / `nbrag_get_raw_file`.

## Quality — Approved

Implementation is clean, consistent across the 4 functions, and mirrors the XML patterns established in Tasks 1-6. No deviations from brief. Report's self-noted concerns (nbrag_help prose at L266 still mentioning `line:N-M`; no runtime smoke test) are both explicitly out of scope per brief constraints.

No fixes required.

## Summary
spec ✅ | quality Approved | 4 个 chunk 视图函数全部正确重构为 XML，签名未变，handle 字段全部 canonical，无废弃字段名，错误统一为 `<error type="not_found">`。
