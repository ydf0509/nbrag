# Task 10 Review

## Spec compliance: ✅

Independent verification confirms the implementer's report. The script `scripts/test_xml_format.py` (480 lines, committed as `b369994`) matches the diff in the review package exactly, and every brief requirement is met.

### Brief step-by-step table — all 15 PASS

| Step | Call | Verification | Result | Evidence |
|---|---|---|---|---|
| 1 | `nbrag_help()` | contains `line_start`/`line_end`; no `line:N-M`/`chunk:X/Y`/`chunk_index:X` | PASS | script lines 127-133 check all 5 conditions |
| 2 | `nbrag_stats()` | `<nbrag_stats>` wrapper, `<collections>`, `<collection `; extracts first collection_name with chunks>0 | PASS | script lines 143-172; adaptive collection picking via regex on `<collection .../>` |
| 3 | `nbrag_search_and_fetch(...)` | `<nbrag_search_and_fetch`/`<ranked_hits>`/`<hit `/`<fetched_raw>`; extracts 5 handles from `<hit>` | PASS | script lines 209-231; extracts `file_path`/`doc_id`/`chunk_index`/`line_start`/`line_end` into `S` |
| 4 | `nbrag_search(..., include_content=False)` | `<nbrag_search`/`<ranked_hits>`/`<hit `; no `<content>` | PASS | script lines 244-249; checks `"<content>" not in out` |
| 5 | `nbrag_search_only_bm25(...)` | `<nbrag_search_only_bm25` | PASS | script line 258 |
| 6 | `nbrag_search_only_vector(...)` | `<nbrag_search_only_vector` | PASS | script line 268 |
| 7 | `nbrag_grep(...)` | `<nbrag_grep`/`<matches>`/`<match `; `<match>` has `line_start`/`line_end`; extract `file_path`/`doc_id`/`line_start`/`line_end` | PASS | script lines 278-298; uses `keyword=` (correct per `mcp_tools.py:530` signature `def nbrag_grep(keyword: str, ...)`) — brief's table shows `pattern=` as conceptual shorthand, actual param is `keyword` |
| 8 | `nbrag_find_definition(...)` | `<nbrag_find_definition`/`<definitions>`/`<definition ` OR tolerant error types | PASS | script lines 307-321; tolerates `not_found`/`no_results`/`missing_collection`/`empty_collection` (extra 2 are reasonable defensive extension) |
| 9 | `nbrag_find_files(...)` | `<nbrag_find_files`/`<files>`/`<file `; `<file>` has `total_chunks` (not `chunk_count`) | PASS | script lines 328-343; checks `has_total and not has_count` |
| 10 | `nbrag_list(...)` | `<nbrag_list`/`<documents>`/`<document `; `<document>` has `doc_id`/`file_path`/`total_chunks` (not `chunk_count`) | PASS | script lines 351-369; checks all 4 conditions |
| 11 | `nbrag_read_more_original_text(file_path=<step3或7的>)` | `<nbrag_read_more_original_text`/`<content>` | PASS | script lines 376-387; reuses `hit_file_path`/`grep_file_path` (with `_list_file_path` fallback — see Minor finding 1) |
| 12 | `nbrag_get_file_chunks(...)` | `<nbrag_get_file_chunks`/`<chunks>`/`<chunk `; `<chunk>` has `chunk_index`/`line_start`/`line_end` | PASS | script lines 394-415; verifies all 3 handle fields on `<chunk>` |
| 13 | `nbrag_get_adjacent_chunks(doc_id=<step3>, chunk_index=<step3>)` | `<nbrag_get_adjacent_chunks`/`anchor_chunk_index=`/`<chunks>` | PASS | script lines 422-441; reuses `hit_doc_id`/`hit_chunk_index` from step 3 |
| 14 | `nbrag_get_chunks_by_lines(doc_id=<step3>, line_start=<step3>, line_end=<step3>)` | `<nbrag_get_chunks_by_lines`/`requested_line_start=`/`requested_line_end=` | PASS | script lines 448-469; reuses `hit_doc_id`/`hit_line_start`/`hit_line_end` from step 3 |
| 15 | `nbrag_read_more_original_text(file_path="INVALID_PATH")` | `<error type="invalid_file_path" field="file_path">` | PASS | script line 478; exact substring match |

### Global constraints — all met

- ✅ **OPENBLAS_NUM_THREADS=1 before any nbrag import**: set at line 24 (`os.environ["OPENBLAS_NUM_THREADS"] = "1"`), before `import my_load_config` (line 33) and any `nbrag.*` import (line 34+).
- ✅ **`import my_load_config` before `from nbrag.config import load_config`**: line 33 → line 34 → `load_config()` at line 36.
- ✅ **Direct import of all 14 `nbrag_*` functions**: lines 38-53 import exactly the 14 functions listed in the brief.
- ✅ **Adaptive (no hardcoded collection_name/query/pattern)**: collection derived from `nbrag_stats()` (lines 161-172); query/pattern/keyword derived from `nbrag_list()` filename via `_derive_query`/`_derive_pattern`/`_derive_grep_keyword` helpers. `_symbol = "main"` is per brief.
- ✅ **No `assert` statements**: independent grep for `^\s*assert\s` on the script file returned 0 matches.
- ✅ **Prints `X/15 passed` summary**: line 480 `print(f"{_passed}/{_TOTAL} passed")`.
- ✅ **Grep scan complete**: both `nbrag/*.py` (28 matches) and `SKILL.md` (0 matches) scanned with the exact patterns from the brief.
- ✅ **Run output 15/15 passed**: report shows full run output with all 15 steps PASS.

### Grep scan — independently re-verified

**Scan 1 (`nbrag/*.py`, pattern `line:N-M|chunk:X/Y|chunk_index:X|matched_line|line_range`):** 28 matches across 6 files, exactly as reported.

- 26 internal function/variable names containing `line_range` substring (`chunker.py`, `ingest.py`, `mcp_tools.py`, `retrieval.py`, `symbol_index.py`) — acceptable per brief.
- **2 AI-facing `chunk_index:X` in `server.py`** — confirmed at:
  - **Line 134**: `- chunk_index:X` in `nbrag_search_and_fetch` docstring (lists example returned fields)
  - **Line 353**: `Field(description="...chunk_index:X")` for `nbrag_get_adjacent_chunks` `chunk_index` parameter

Both are AI-facing surfaces (docstrings and Field descriptions visible to MCP clients/LLM agents). These are **Task 1 leftovers** (Task 1 was responsible for `server.py` docstring/Field cleanup) — correctly classified as findings for final review, NOT Task 10 defects. Task 10's scope is verification only.

**Scan 2 (`SKILL.md`, pattern with `chunk_count` added):** 0 matches — clean. ✅

### Commit verification

- HEAD `b369994` on branch `optimize_ret_for_llm`, parent `8a48948` — matches brief's BASE/HEAD.
- Single commit, 1 file changed, 480 insertions — matches review package stat.
- Commit message: `test: add XML format verification script for 9109 port + direct import` — matches brief's Step 4.

## Code quality

### Critical findings (must fix before merge)
None.

### Important findings (should fix)
None. The 2 `server.py` `chunk_index:X` occurrences are Task 1 leftovers, not Task 10 defects — they are correctly flagged in the implementer's report for final review action. Task 10 is verification-only and the script correctly does not modify `server.py`.

### Minor findings (nice to have)

1. **Step 11 file_path fallback deviates from brief's literal wording.** Brief step 11 says `file_path=<step3或7的>`, but the script (lines 376-380) falls back to `_list_file_path` (from `nbrag_list()`) if both `hit_file_path` and `grep_file_path` are missing. This is a defensive fallback that did not trigger in the actual run (step 3 extracted `hit_file_path` successfully, so step 11 PASSED using the step-3 handle). Non-issue in practice; technically a tiny extension beyond the brief's literal scope.

2. **Step 8 tolerates extra error types beyond brief.** Brief says `not_found` or `no_results` count as PASS; the script (lines 311-316) also accepts `missing_collection` and `empty_collection`. This is a reasonable defensive extension — these are legitimate error types the function can return, and accepting them doesn't weaken the verification. Not a violation.

3. **`_symbol = "main"` is hardcoded.** This is explicitly per brief ("若 collection 有 .py 文件用 `"main"`"), so not a defect — but if the picked collection has no `.py` files, step 8 relies on the tolerant error path. The run output shows step 8 PASSED, so the collection either had `.py` files with a `main` symbol, or returned a tolerated error. Either way, compliant.

4. **Script structure is linear/procedural (not wrapped in functions).** This is appropriate for a one-shot self-test script — wrapping 15 sequential steps in functions would add ceremony without value. No change needed.

## Verdict

**APPROVED**

Task 10 fully satisfies its brief: the self-test script is adaptive (derives collection/query/pattern from `nbrag_stats()` + `nbrag_list()`), sets `OPENBLAS_NUM_THREADS=1` before any nbrag import, imports `my_load_config` before `load_config()`, directly imports all 14 `nbrag_*` functions, covers all 15 verification steps from the brief's table, extracts and reuses the 5 canonical handles across steps 3→11-14 (verifying zero-conversion handle flow), uses no `assert` statements, prints `15/15 passed` summary, and runs the complete grep scan on both `nbrag/*.py` and `SKILL.md`. The script ran successfully with 15/15 PASS. The 2 `server.py` `chunk_index:X` findings are correctly identified as Task 1 leftovers (AI-facing docstring/Field surfaces) and flagged for final review — they are NOT Task 10 defects and do not affect the verification result.

The script is committed (`b369994`) and retained per brief; final deletion decision deferred to user at final review.
