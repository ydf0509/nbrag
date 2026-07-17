# Task 1 Report: 清理 `server.py` 文案 + 补 boundary case 说明

## Commit
- Hash: `4cf345b`
- Message: `refactor(server): clean deprecated field names from Field descriptions`
- File changed: `nbrag/server.py` (1 file, 12 insertions, 12 deletions)

## 1. What changed

All edits are in `nbrag/server.py`. No other files were touched. No function signatures or logic were changed — only Field description text and docstring text.

### Edit 1 — Line 68 (nbrag_help docstring)
- Before: `    - stable follow-up fields such as file_path, doc_id, chunk_index, and line:N-M`
- After:  `    - stable follow-up fields such as file_path, doc_id, chunk_index, and line_start + line_end`
- Mapping: `line:N-M` → `line_start + line_end`

### Edit 2 — Line 97 (FuncFields.filter_file_path, shared by nbrag_search / nbrag_search_only_bm25 / nbrag_search_only_vector / nbrag_search_and_fetch / nbrag_grep)
- Before: `...skips cross-file BM25 fusion.")`
- After:  `...skips cross-file BM25 fusion. Value comes from the file_path handle returned by nbrag tools.")`
- Step 3 value-compatibility note appended verbatim from brief.

### Edit 3 — Line 133 (nbrag_search docstring, field list)
- Before: `    - chunk:X/Y`
- After:  `    - chunk_index + total_chunks`
- Mapping: `chunk:X/Y` → `chunk_index + total_chunks`

### Edit 4 — Line 136 (nbrag_search docstring, field list)
- Before: `    - line:N-M`
- After:  `    - line_start + line_end`
- Mapping: `line:N-M` → `line_start + line_end`

### Edit 5 — Line 245 (nbrag_search_and_fetch docstring)
- Before: `    Follow-up fields preserved in ranked hits include file_path, doc_id, chunk_index, and line:N-M.`
- After:  `    Follow-up fields preserved in ranked hits include file_path, doc_id, chunk_index, and line_start + line_end.`
- Mapping: `line:N-M` → `line_start + line_end`

### Edit 6 — Line 276 (nbrag_grep docstring)
- Before: `    Returned text includes reusable follow-up fields such as matched_line, line_range, doc_id, and file_path.`
- After:  `    Returned text includes reusable follow-up fields such as line_start == line_end, line_start + line_end, doc_id, and file_path.`
- Mapping: `matched_line` → `line_start == line_end`; `line_range` → `line_start + line_end`

### Edit 7 — Line 320 (nbrag_get_file_chunks start_chunk Field)
- Before: `    start_chunk: int = Field(default=0, description="Start chunk index (0-based) for pagination")`
- After:  `    start_chunk: int = Field(default=0, description="Start chunk index (0-based) for pagination. 0-based chunk index; same value space as the chunk_index handle, but used as a pagination cursor (semantic: 'start browsing from chunk N').")`
- Step 4 value-compatibility note appended verbatim from brief. `start_chunk` parameter name preserved (legitimate input).

### Edit 8 — Line 353 (nbrag_get_adjacent_chunks chunk_index Field)
- Before: `    chunk_index: int = Field(description="Target chunk index from a search/search_and_fetch result field like chunk:X/Y or chunk_index:X")`
- After:  `    chunk_index: int = Field(description="Target chunk index from a search/search_and_fetch result field like chunk_index + total_chunks or chunk_index:X")`
- Mapping: `chunk:X/Y` → `chunk_index + total_chunks`

### Edit 9 — Line 370 (nbrag_get_chunks_by_lines line_start Field)
- Before: `    line_start: int = Field(description="Start line (1-based), usually copied from a prior line:N-M style result")`
- After:  `    line_start: int = Field(description="Start line (1-based), usually copied from a prior line_start + line_end style result")`
- Mapping: `line:N-M` → `line_start + line_end`

### Edit 10 — Line 371 (nbrag_get_chunks_by_lines line_end Field)
- Before: `    line_end: int = Field(description="End line (inclusive), usually copied from a prior line:N-M style result")`
- After:  `    line_end: int = Field(description="End line (inclusive), usually copied from a prior line_start + line_end style result")`
- Mapping: `line:N-M` → `line_start + line_end`

### Edit 11 — Line 379 (nbrag_get_chunks_by_lines docstring)
- Before: `    Returned text includes doc_id, file_path, requested line_range, and all overlapping chunks."""`
- After:  `    Returned text includes doc_id, file_path, requested line_start + line_end, and all overlapping chunks."""`
- Mapping: `line_range` → `line_start + line_end`

### Edit 12 — Line 395 (nbrag_list docstring)
- Before: `    Returned text includes per-document doc_id, filename, chunk_count, total_chunks, and file_path."""`
- After:  `    Returned text includes per-document doc_id, filename, total_chunks, and file_path."""`
- Mapping: `chunk_count` → `total_chunks`. Since `total_chunks` already appeared in the same list, the deprecated `chunk_count` entry was removed (rather than producing `total_chunks, total_chunks`).

## 2. Grep verification (Step 5)

### Brief's required pattern
```
pattern: "chunk:\d|line:\d|matched_line|line_range|chunk_count"
path: nbrag/server.py
```
Result: **0 matches** (confirmed)

### Extended pattern (letters, since file used X/Y/N/M placeholders not digits)
```
pattern: "chunk:X|line:N|chunk_id"
path: nbrag/server.py
```
Result: **0 matches** (confirmed)

Note: The brief's Step 1 grep pattern uses `\d` (digit) which does not match the letter placeholders `X`/`Y`/`N`/`M` used in `chunk:X/Y` and `line:N-M`. A manual file scan was performed to catch these additional deprecated references, and all were cleaned.

### `start_chunk` residual check
`start_chunk` still appears on lines 320 and 331 — this is the legitimate input parameter name for `nbrag_get_file_chunks` and is intentionally preserved per the brief.

## 3. Commit hash
`4cf345b` on branch `optimize_ret_for_llm`

## 4. Concerns / doubts

1. **Brief grep pattern gap**: The brief's Step 1 grep pattern `chunk:\d|line:\d` uses `\d` (digit class), but the deprecated forms in `server.py` used letter placeholders (`chunk:X/Y`, `line:N-M`). The grep therefore only caught `matched_line|line_range|chunk_count` and missed the `chunk:X/Y` / `line:N-M` references. These were caught via manual file scan and cleaned. The Step 5 grep also uses `\d`, so it would not detect letter-placeholder regressions — but since all instances are now removed, the result is still 0 matches.

2. **Line 133 redundancy**: After replacing `chunk:X/Y` → `chunk_index + total_chunks`, line 133 (`- chunk_index + total_chunks`) is now adjacent to lines 134-135 (`- chunk_index:X` / `- total_chunks:Y`). This is slightly redundant but follows the brief's literal mapping instruction ("change deprecated field names to canonical form"). No list restructuring was performed to stay within task scope.

3. **"line range" (space, no underscore) on lines 293 and 374/376**: These use plain English "line range" (descriptive) rather than the deprecated field name `line_range` (underscore). They were intentionally left unchanged — the brief only lists `line_range` (underscore) as deprecated, and the grep pattern only matches the underscore form.

4. **start_chunk note redundancy**: The appended note begins with "0-based chunk index" which partially restates the existing "(0-based)" in the original description. The text was appended verbatim per the brief's explicit instruction.
