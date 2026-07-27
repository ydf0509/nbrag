# Final Whole-Branch Review

## Branch summary

This branch refactors all 13 nbrag MCP tool functions from prose/key-value plain text to a canonical XML format, with the goal of letting AI agents chain tool calls with zero-conversion handle reuse. Handle fields (`file_path` / `doc_id` / `chunk_index` / `total_chunks` / `line_start` / `line_end`) are now emitted as XML attributes on per-item tags, body text is placed in `<content>` children with zero escaping, and every error path returns `<error type="..." field="...">...</error>`.

The change touches 4 files across 11 commits: `nbrag/mcp_tools.py` (13 functions + helpers, including a shared `_format_hit_xml` helper and two `_meta_file_path` / `_meta_chunk_index` mapping helpers), `nbrag/server.py` (Field descriptions + docstrings cleaned of deprecated field names, boundary-case value-compatibility notes added for `filter_file_path` and `start_chunk`), `nbrag/skills/nbrag-workflow/SKILL.md` (5 deprecated-form references cleaned), and `scripts/test_xml_format.py` (new 15-step adaptive self-test). Function signatures, retrieval logic, and `retrieval.py` underlying dict keys are untouched, matching the spec's non-goals.

## Spec compliance: ✅

- **XML format总规范** (root tag = function name, handle as attrs, `<content>` for body): implemented across all 13 functions. Verified root tags match the spec's 标签命名约定表 for every function.
- **Canonical handle 字段集** (`file_path` / `doc_id` / `chunk_index` / `total_chunks` / `line_start` / `line_end`): used consistently in all 13 functions' output. No function emits a non-canonical handle name as an XML attribute.
- **禁止变体**: grep scan of `nbrag/mcp_tools.py`, `nbrag/server.py`, and `nbrag/skills/nbrag-workflow/SKILL.md` confirms zero matches for `chunk:\d`, `line:\d`, `matched_line`, `line_range` (as field name), `chunk_count` (as output attr), `chunk_id`, `chunk_index:X`. The only `chunk_count` occurrences in `mcp_tools.py` are `.get("chunk_count", ...)` fallbacks when reading the underlying layer (allowed per spec exception), and `_merge_line_ranges` is an internal function name (allowed per spec exception).
- **正文零转义**: `<content>` children emit raw text via f-strings / `lines.append(content)` with no JSON-style escaping. Verified in `_format_hit_xml`, `nbrag_grep`, `nbrag_find_definition`, `nbrag_get_adjacent_chunks`, `nbrag_get_file_chunks`, `nbrag_get_chunks_by_lines`, `nbrag_read_more_original_text`, and `nbrag_search_and_fetch`'s `<fetched_raw>` section.
- **不改函数签名**: all 13 MCP-exposed functions retain original names, params, types, and defaults. `nbrag_add_document` / `nbrag_delete` left unchanged (success paths still prose, as they're not MCP-exposed).
- **不动 retrieval.py 底层 dict key**: `source` / `index` / `line_number` kept as-is; mapped in `mcp_tools.py` via `_meta_file_path` / `_meta_chunk_index` helpers and inline `item.get("source", ...)` / `item.get("line_number", ...)` reads.
- **Error format**: all error paths use `<error type="..." field="...">` with types from the spec's enum (`invalid_file_path` / `missing_collection` / `empty_collection` / `no_results` / `not_found`). `invalid_param` is enumerated in the spec but not produced by any current path (acceptable — it's a reserved type).
- **底层 key 映射**: `_meta_file_path` and `_meta_chunk_index` helpers added at top of `mcp_tools.py`; grep's `line_number` → `line_start`+`line_end` (1→2 mapping) done inline in `nbrag_grep`; `find_definition`'s `r.get("source")` → `file_path` done inline with explicit `str()` wrap.
- **Boundary cases**: `filter_file_path` Field description includes "Value comes from the file_path handle returned by nbrag tools." `start_chunk` Field description includes "0-based chunk index; same value space as the chunk_index handle, but used as a pagination cursor".
- **nbrag_help + SKILL.md**: `nbrag_help` skeleton L266 uses canonical "Stable follow-up fields: file_path, doc_id, chunk_index, line_start, line_end." SKILL.md section 9 and section 3 table updated to canonical forms.

## Cross-task consistency

**Handle field names**: All 13 functions emit the canonical 6-handle set as XML attributes. Verified per-function:
- `_format_hit_xml` (shared by `nbrag_search` / `nbrag_search_only_bm25` / `nbrag_search_only_vector` / `nbrag_search_and_fetch`): `file_path`, `doc_id`, `chunk_index`, `total_chunks`, `line_start`, `line_end` ✓
- `nbrag_grep` `<match>`: `file_path`, `doc_id`, `line_start`, `line_end` (no `chunk_index` — correct, grep doesn't provide it) ✓
- `nbrag_find_definition` `<definition>`: `file_path`, `doc_id`, `line_start`, `line_end` ✓
- `nbrag_find_files` `<file>`: `file_path`, `doc_id`, `total_chunks` ✓
- `nbrag_list` `<document>`: `doc_id`, `file_path`, `total_chunks` ✓
- `nbrag_stats` `<collection>`: `collection_name`, `docs`, `chunks` (no handle fields — correct, stats is routing not evidence) ✓
- `nbrag_get_file_chunks` / `nbrag_get_adjacent_chunks` / `nbrag_get_chunks_by_lines` `<chunk>`: `chunk_index`, `total_chunks`, `line_start`, `line_end` (+ optional `scope`) ✓
- `nbrag_read_more_original_text` root: `file_path`, `doc_id`, `total_lines`, `line_start`, `line_end` ✓
- `nbrag_search_and_fetch` `<raw>`: `file_path`, `doc_id`, `line_start`, `line_end` ✓

**XML structure**: All functions follow root tag = function name, handle as attrs, `<content>` for body. Listing-type functions (`nbrag_find_files`, `nbrag_list`, `nbrag_stats`) use self-closing tags (`<file .../>`, `<document .../>`, `<collection .../>`) with no `<content>`, matching spec. `nbrag_read_more_original_text` has no `<chunks>` collection tag — `<content>` is a direct child of root, matching spec.

**Error formats**: All 13 functions' error paths produce `<error type="..." field="...">...</error>` with a `Recovery:` line. Error type usage is consistent:
- `invalid_file_path`: `_path_error` (used by `nbrag_search`, `nbrag_search_and_fetch`, `nbrag_grep`, `nbrag_get_file_chunks`, `nbrag_read_more_original_text` for bad `filter_file_path`/`file_path`)
- `missing_collection` / `empty_collection`: `_collection_issue_text` + `_collection_presence_issue_text` (used by all retrieval + listing functions)
- `no_results`: `_no_search_results_text` (search), inline strings (`nbrag_grep`, `nbrag_find_definition`, `nbrag_find_files`, `nbrag_list`, `nbrag_stats`)
- `not_found`: `nbrag_get_adjacent_chunks`, `nbrag_get_file_chunks`, `nbrag_get_chunks_by_lines`, `nbrag_read_more_original_text`

**Handle flow end-to-end**: Verified all chaining paths work with zero conversion:
- `nbrag_find_files` / `nbrag_list` → `file_path` → `nbrag_read_more_original_text` / `nbrag_get_file_chunks` / `filter_file_path` ✓
- `nbrag_search` / `nbrag_search_and_fetch` → `doc_id` + `chunk_index` → `nbrag_get_adjacent_chunks` ✓
- `nbrag_search` / `nbrag_search_and_fetch` → `doc_id` + `line_start` + `line_end` → `nbrag_get_chunks_by_lines` ✓
- `nbrag_search` / `nbrag_search_and_fetch` → `file_path` → `nbrag_read_more_original_text` ✓
- `nbrag_grep` → `file_path` + `line_start` + `line_end` → `nbrag_read_more_original_text` ✓
- `nbrag_grep` → `doc_id` + `line_start` + `line_end` → `nbrag_get_chunks_by_lines` ✓
- `nbrag_find_definition` → `file_path` + `line_start` + `line_end` → `nbrag_read_more_original_text` ✓
- `nbrag_get_file_chunks` → `chunk_index` (per-chunk) + `doc_id` (root) → `nbrag_get_adjacent_chunks` ✓
- `nbrag_read_more_original_text` → `file_path` + `line_start` + `line_end` → `nbrag_read_more_original_text` (narrower range) ✓

**Root tag attributes**: Difference information is consistently placed on root tags: `nbrag_get_file_chunks` has `start_chunk`/`max_chunks`/`has_more`; `nbrag_get_adjacent_chunks` has `window`/`anchor_chunk_index`; `nbrag_get_chunks_by_lines` has `requested_line_start`/`requested_line_end`; search functions have `bm25`/`rerank`/`total_chunks`/`filter_file_path`. Matches spec.

**`nbrag_delete` side effect**: Not MCP-exposed, but its collection-issue path now inherits the XML error format from `_collection_presence_issue_text`. This is a benign side effect of Task 2's helper refactor — the success path remains prose, which is acceptable for a non-exposed function.

## Deferred Minor findings triage

1. **Task 1 Minor (a)** — `server.py` L276 field list phrasing: **NOT AN ISSUE**. Inherited from brief; the line "Returned text includes reusable follow-up fields such as line_start == line_end, line_start + line_end, doc_id, and file_path" is slightly redundant but not wrong and doesn't affect AI handle extraction from the actual XML output.

2. **Task 1 Minor (b)** — `server.py` L133-135 list redundancy: **NICE TO HAVE (defer)**. The `nbrag_search` docstring field list mixes three notations (`chunk_index + total_chunks`, `chunk_index="..." (XML attribute on <hit>)`, `total_chunks:Y`) and mentions `chunk_index`/`total_chunks` twice. The `total_chunks:Y` form is misleading (actual output uses XML attribute, not key:value). Cosmetic docstring issue; doesn't affect AI behavior. Could be simplified to a single consistent list. (Promoted to Minor finding #2 below.)

3. **Task 2 Minor (a)** — `bm25_query` text in `_no_search_results_text` may need SKILL.md补充: **NOT AN ISSUE**. SKILL.md section 4/5 already covers `bm25_query` semantics. The error text's "provide a bm25_query as lexical anchors" is a recovery hint, not a definition.

4. **Task 2 Minor (b)** — `stats` 容错差异 pre-existing: **NOT AN ISSUE**. Pre-existing code behavior in `get_stats()` return shape, not introduced by this refactor. Out of scope.

5. **Task 8 Minor (a)** — Attribute values not XML-escaped: **NOT AN ISSUE**. The spec's 风险点 section explicitly accepts this: "属性值里的引号：`file_path`/`scope`/`aliases`/`tags` 不会含引号，先不转义，遇真实 bug 再加。" YAGNI applies. The "正文零转义" rule governs body content, not attributes, and is correctly implemented.

6. **Task 8 Minor (b)** — `nbrag_list` L925 `doc_id` not wrapped in `str()`: **NOT AN ISSUE**. `doc_id` comes from `rows.items()` (dict keys), which are always strings. The `str()` wrap in `nbrag_find_files` L670 is defensive but unnecessary for `nbrag_list`. Cosmetic asymmetry, no behavioral difference.

7. **Task 8 Minor (c)** — Asymmetric fallback defaults (`0` vs `"?"`): **NOT AN ISSUE**. `nbrag_stats` reads `get_stats()` which always returns numeric `docs`/`chunks` fields (fallback `0` is type-correct). `nbrag_find_files`/`nbrag_list` read `find_files()`/`list_documents()` where `total_chunks` may be absent (fallback `"?"` is a safe sentinel). The asymmetry reflects different data-source guarantees, not an inconsistency.

8. **Task 10 Minor (a)** — Step 11 list-fallback path didn't trigger: **NOT AN ISSUE**. The fallback chain `hit_file_path or grep_file_path or _list_file_path` is defensive coding. In the test run, `hit_file_path` was populated, so the fallback didn't fire. This is correct behavior, not a bug.

9. **Task 10 Minor (b)** — Step 8 accepts extra error types: **NOT AN ISSUE**. `nbrag_find_definition` can legitimately return `missing_collection` / `empty_collection` (via `_collection_presence_issue_text`) or `no_results` (no matches). The test script's acceptance of these is correct coverage, not over-acceptance.

10. **Task 10 Minor (c)** — `_symbol = "main"` hardcoded: **NOT AN ISSUE**. The test script is adaptive where it matters (collection_name, query, pattern derived from actual data). A fixed `symbol="main"` is a reasonable test value for Python collections and avoids over-engineering a symbol-discovery step. Per brief.

11. **Task 10 Minor (d)** — Linear script structure: **NOT AN ISSUE**. A linear top-to-bottom structure is appropriate for a verification checklist script. Abstracting into functions would add ceremony without improving readability for this use case.

## Critical findings (must fix before merge)

None.

## Important findings (should fix)

None.

## Minor findings (nice to have)

1. **`server.py` L293 + L346 — "line range" used as field-name reference in "Returned text includes..." lists.** Task 1 cleaned `line:N-M` / `line_range` from docstrings but left two prose references that function as field-name listings:
   - L293 (`nbrag_find_definition` docstring): `Returned text includes doc_id, file_path, line range, and the definition body.`
   - L346 (`nbrag_read_more_original_text` docstring): `Returned text includes original_file, file_path, doc_id, total_lines, and the returned line range.`
   
   These should ideally say `line_start + line_end` to match the actual XML attributes. L346 also mentions `original_file` which doesn't appear as an attribute in the new XML output (the root tag is `<nbrag_read_more_original_text>`). Note: "line range" (prose, with space) is NOT in the spec's forbidden-form list (which targets `line_range` underscore and `line:N-M`), so this is a cosmetic inconsistency, not a spec violation. The AI sees the actual XML attributes, so behavior is unaffected.

2. **`server.py` L132-138 — `nbrag_search` docstring field list uses mixed notation and redundancy.** The list mixes `chunk_index + total_chunks` (`+` notation), `chunk_index="..." (XML attribute on <hit>)` (`="..."` notation), and `total_chunks:Y` / `doc_id:...` / `file_path:...` (`:value` notation). `chunk_index` and `total_chunks` are each mentioned twice. The `:Y` / `:...` notation is misleading because the actual output uses XML attributes, not key:value pairs. Could be simplified to a single consistent list like:
   ```
   - file_path (XML attribute on <hit>)
   - doc_id (XML attribute on <hit>)
   - chunk_index (XML attribute on <hit>)
   - total_chunks (XML attribute on <hit>)
   - line_start (XML attribute on <hit>)
   - line_end (XML attribute on <hit>)
   ```
   Cosmetic only; doesn't affect AI behavior.

## Test script recommendation

**Recommendation: KEEP `scripts/test_xml_format.py`.**

Reasoning:
- It is a genuinely useful regression tool, not a formal test. It has no pytest/CI integration — it's a standalone script that prints PASS/FAIL per step, matching the spec's "不写正式测试" rule (which prohibits formal test suites, not verification scripts).
- It is adaptive: picks `collection_name` from `nbrag_stats()`, derives `query`/`pattern` from actual filenames via `nbrag_list()`, and threads handles from `nbrag_search_and_fetch` output into `nbrag_read_more_original_text` / `nbrag_get_file_chunks` / `nbrag_get_adjacent_chunks` / `nbrag_get_chunks_by_lines` — verifying the zero-conversion handle-flow property that is the whole point of this refactor.
- It is already working (15/15 passed per progress ledger).
- It provides future regression protection: if someone accidentally reintroduces a deprecated form (`chunk:X/Y`, `matched_line`, `chunk_count` as output attr), the script's shape checks will catch it.
- The plan's "改造完可删" is permissive ("can be deleted"), not prescriptive ("must be deleted"). The plan explicitly leaves the decision open: "如果用户不想保留...删除它。如果用户想保留作为后续回归工具，commit 它."
- The script correctly verifies the spec's hardest requirement: handle-flow works end-to-end with zero conversion (steps 3 → 11-14 extract handles from `<hit>` XML attributes and pass them directly as int/str params to follow-up tools).

If the user prefers a minimal repo, the script can be deleted without affecting functionality — but keeping it costs nothing and provides regression value.

## Verdict

**APPROVED FOR MERGE**

- 0 Critical findings
- 0 Important findings
- 2 Minor findings (both cosmetic docstring issues in `server.py` — "line range" prose in two "Returned text includes..." lists, and mixed notation in `nbrag_search` docstring field list). Neither affects AI behavior or spec compliance; both can be cleaned up in a follow-up commit.
- All 11 deferred Minor findings triaged: 10 NOT AN ISSUE, 1 NICE TO HAVE (defer) — the NICE TO HAVE is the same as Minor finding #2 above.
- All spec sections implemented and verified.
- Cross-task consistency verified: canonical handle fields, XML structure, error formats, and handle-flow paths are consistent across all 13 functions.
- Test script recommended to KEEP.
