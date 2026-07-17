# Task 8 Review

## Spec compliance: ✅

### Step 1: `nbrag_find_files` rewrite — PASS
- L647-649 (param normalization + `find_files` call) preserved unchanged.
- No-results path returns `<error type="no_results" field="pattern">` XML (line 655).
- Header `<nbrag_find_files>` + handle reminder `Follow-up handle in <file>: file_path.` (lines 663-664).
- Each item emits `<file file_path="..." doc_id="..." filename="..." total_chunks="..." match="..."/>` with the exact attribute order from the brief (lines 674-676).
- `file_path = item.get("source", item.get("file_path", "?"))` (line 669) — matches brief fallback chain.
- `total_chunks = item.get("total_chunks", item.get("chunk_count", "?"))` (line 672) — matches brief fallback chain.
- `_collection_presence_issue_text(collection_name)` 3-branch pattern preserved before `no_results` fallback (lines 651-653).

### Step 2: `nbrag_list` rewrite — PASS
- L893-895 (param normalization + `list_documents` call) preserved unchanged.
- No-results path returns `<error type="no_results" field="collection_name">` XML (line 907).
- Header `<nbrag_list collection_name="..." offset="..." limit="...">` echoes all three input attrs (line 915) + handle reminder `Follow-up handles in <document>: doc_id, file_path.` (line 916).
- Each `doc_id, row` emits `<document doc_id="..." file_path="..." filename="..." total_chunks="..."/>` with the exact attribute order from the brief (lines 924-926).
- `total_chunks = row.get("total_chunks", row.get("chunk_count", "?"))` (line 923) — matches brief fallback chain.
- `_collection_presence_issue_text(collection_name)` 3-branch pattern preserved (lines 903-905).

### Step 3: `nbrag_stats` rewrite — PASS
- L919-920 (`get_stats` call + `collections` extraction) preserved unchanged.
- No-collections path returns `<error type="no_results" field="collection_name">` XML (line 939). (No `_collection_presence_issue_text` call here — correct, since `nbrag_stats()` takes no `collection_name` parameter.)
- Header `<nbrag_stats>` (line 946).
- Exactly 1 routing line before `<collections>`: `Use collection_name exactly as shown below when calling retrieval tools.` (line 947).
- Exactly 1 routing line after `</collections>`: `After choosing collection_name, continue with nbrag_search_and_fetch for most questions.` (line 979).
- Each collection emits `<collection collection_name="..." docs="..." chunks="..." .../>` self-closing tag (line 976).
- Optional fields (`display_name`, `description`, `aliases`, `tags`, `chunk_size`, `chunk_overlap`, `last_ingested_at`) emitted only when present, in the exact order shown in the brief example (lines 962-975).
- `aliases` / `tags` (list-typed) joined by `", "` (lines 967, 969).
- Removed all forbidden prose: "If this is the first nbrag call...", "This tool resolves collection routing only...", "After choosing collection_name, continue with nbrag_help-guided retrieval planning...", and "Use nbrag_search_and_fetch() for most semantic/source-backed questions..." — all confirmed gone from the diff.
- The old `collection_name(知识库名字)` Chinese parenthetical was simplified to `collection_name`, matching the brief's exact wording.

### Step 4: grep scan — PASS
Pattern `chunk_count` in `nbrag/mcp_tools.py` returns 4 hits, all inside `.get("chunk_count", ...)` fallback positions:
- Line 181: pre-existing `_collection_issue_text` helper (Task 2, out of scope).
- Line 672: `nbrag_find_files` fallback.
- Line 923: `nbrag_list` fallback.
- Line 953: `nbrag_stats` fallback.
No `chunk_count` appears as an output XML attribute name.

### Step 5: import verification — PASS
Report claims `import OK` with exit code 0 from `D:/ProgramData/miniconda3/envs/py312/python.exe -c "from nbrag.mcp_tools import nbrag_find_files, nbrag_list, nbrag_stats; print('import OK')"`. Code inspection confirms syntactic validity; the AST syntax check also reportedly passed. The runtime smoke-test failure (`memory allocation ... STATUS_STACK_OVERFLOW`) is an environment-level issue explicitly noted in the brief's "Critical context" and is unrelated to the diff.

### Step 6: commit — PASS
Single commit `374004e` with message `refactor(mcp_tools): XML format for 3 listing functions, deprecate chunk_count`. Diffstat: `1 file changed, 64 insertions(+), 43 deletions(-)` — matches the report exactly. No unrelated files touched.

## Global constraints check

- **Canonical handle field set** (`file_path` / `doc_id` / `total_chunks`): PASS — all three used as output attribute names across the 3 functions.
- **Forbidden variants** (`chunk_count` / `chunk_id` / `index` / `original_file` / `matched_line` / `line_range` / `chunk:X/Y` / `line:N-M`): PASS — none appear as output attribute names; `chunk_count` survives only inside `.get()` fallbacks.
- **正文零转义** (zero body escaping): PASS — all item tags are self-closing with attributes only; no body content to escape.
- **不改函数签名**: PASS — all three signatures unchanged:
  - `nbrag_find_files(pattern: str, collection_name: str, max_results: int = 20, case_sensitive: bool = False) -> str`
  - `nbrag_list(collection_name: str, offset: int = 0, limit: int = 100) -> str`
  - `nbrag_stats() -> str`
- **不写正式测试**: PASS — no test files added.
- **Python 解释器**: PASS — report used `D:/ProgramData/miniconda3/envs/py312/python.exe` with `$env:OPENBLAS_NUM_THREADS=1`.
- **Handle consistency**: PASS — `file_path` returned here matches the `file_path` parameter name in `nbrag_get_file_chunks` / `nbrag_get_raw_file`; `doc_id` matches the `doc_id` parameter in retrieval functions.
- **Error format**: PASS — all three no-results paths use `<error type="no_results" field="...">...</error>`; `no_results` is in the allowed type set.
- **Root tag = function name**: PASS — `<nbrag_find_files>`, `<nbrag_list ...>`, `<nbrag_stats>`.
- **Routing prose in `nbrag_stats`**: PASS — exactly 1 line before + 1 line after, all other prose removed.

## Code quality

### Critical findings (must fix before merge)
None.

### Important findings (should fix)
None.

### Minor findings (nice to have)
1. **Attribute values are not XML-escaped.** If a `filename`, `description`, or `display_name` contained a `"` character, the emitted XML would be malformed. The brief's examples show simple unescaped values, and the global "正文零转义" constraint only governs body content (not attributes), so this is consistent with the codebase pattern established in earlier tasks — but worth flagging for future hardening.
2. **Inconsistent `str()` wrapping of `doc_id` in `nbrag_list`.** At line 925, `doc_id` is interpolated directly in the f-string (`doc_id="{doc_id}"`), whereas in `nbrag_find_files` (line 670) it is wrapped as `doc_id = str(item.get("doc_id", "?"))`. Since `doc_id` comes from `dict.items()` and is in practice already a string, this is cosmetic — but the asymmetry is slightly surprising.
3. **Asymmetric fallback defaults.** `nbrag_stats` uses `0` as the fallback default for `chunks`/`docs` (lines 952-953), while `nbrag_find_files` and `nbrag_list` use `"?"` for `total_chunks` (lines 672, 923). This is intentional per the brief (which specifies `0` for `nbrag_stats` and `"?"` for the other two) — noted only for traceability.

## Verdict
APPROVED — the diff faithfully implements all 6 steps of the brief, honors every applicable global constraint, preserves the 3-branch collection-presence pattern in `nbrag_find_files`/`nbrag_list`, correctly deprecates `chunk_count` as an output field name (keeping it only as a `.get()` fallback), trims `nbrag_stats` routing prose to exactly 1 line before + 1 line after, and touches no code outside the 3 target functions. No critical or important issues; the three minor findings are cosmetic and do not block merge.
