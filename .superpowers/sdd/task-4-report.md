# Task 4 Report: `nbrag_search_and_fetch` XML refactor

**File modified:** `d:\codes\nbrag\nbrag\mcp_tools.py`
**Commit:** `db0eaee5613e981a82d97df2349fa3136d0fe576`
**Diff stat:** 1 file changed, 61 insertions(+), 80 deletions(-)

---

## 1. `_format_hit_xml` helper implementation

Added at `nbrag/mcp_tools.py:273-300`, immediately before `_format_search_results`. Signature and body match the brief verbatim:

```python
def _format_hit_xml(meta: dict, rank: int, dist: float, rerank_score: float | None, include_content: bool, doc: str = "") -> str:
    """Format one ranked hit as <hit> XML. Shared by _format_search_results and nbrag_search_and_fetch."""
    file_path = _meta_file_path(meta)
    chunk_index = _meta_chunk_index(meta)
    total_chunks = str(meta.get("total_chunks", "?"))
    line_start = str(meta.get("line_start", "?"))
    line_end = str(meta.get("line_end", "?"))
    scope = str(meta.get("scope", ""))
    doc_id = str(meta.get("doc_id", "?"))

    hit_attrs = [
        f'rank="{rank}"',
        f'file_path="{file_path}"',
        f'doc_id="{doc_id}"',
        f'chunk_index="{chunk_index}"',
        f'total_chunks="{total_chunks}"',
        f'line_start="{line_start}"',
        f'line_end="{line_end}"',
    ]
    if scope:
        hit_attrs.append(f'scope="{scope}"')
    hit_attrs.append(f'dist="{dist:.4f}"')
    if rerank_score is not None:
        hit_attrs.append(f'score="{rerank_score:.4f}"')

    if include_content:
        return f'<hit {" ".join(hit_attrs)}>\n<content>\n{doc}\n</content>\n</hit>'
    return f'<hit {" ".join(hit_attrs)} />'
```

Uses Task 2's `_meta_file_path` / `_meta_chunk_index` for canonical handle extraction. Emits canonical attribute set (`file_path` / `doc_id` / `chunk_index` / `total_chunks` / `line_start` / `line_end`) plus optional `scope` / `dist` / `score`.

---

## 2. `_format_search_results` DRY refactor

Replaced the inline 30-line hit-formatting block (formerly L322-355) with a single delegation call at `nbrag/mcp_tools.py:352-356`:

```python
    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
        if meta is None:
            meta = {}
        rerank_score = rerank_scores[i] if rerank_scores and i < len(rerank_scores) else None
        lines.append(_format_hit_xml(meta, i + 1, dist, rerank_score, include_content, doc=doc))
```

Behavior preservation:
- `include_content=True` → `<hit ...>\n<content>\n{doc}\n</content>\n</hit>` (multi-line, identical to old output joined with `\n`)
- `include_content=False` → `<hit ... />` (self-closing)
- `score` attribute added only when `rerank_score is not None` (equivalent to old `rerank_scores and i < len(rerank_scores)` gate)
- `scope` attribute added only when non-empty

---

## 3. `nbrag_search_and_fetch` rewrite summary

Function now at `nbrag/mcp_tools.py:428-526`. Body fully replaced from L459 onward (after the unchanged param-validation + search + collection-issue + no-results prelude).

### ranked hits (`<ranked_hits>`)
- Builds `lines_hits: list[str]` via `_format_hit_xml(meta, i+1, dist, rerank_score, include_content=True, doc=doc)` — always `include_content=True` per brief (search_and_fetch always returns body).
- Same loop simultaneously populates `fetch_targets: dict[doc_id, {src, ranges}]` for the first `fetch_top_n_raw` hits. Source resolution now uses `_meta_file_path(meta)` (canonical) instead of the old inline `meta.get("source", meta.get("filename", "?"))` — equivalent behavior, DRY with Task 2 helpers.

### fetched_raw (`<fetched_raw>`)
- Gated by `if fetch_top_n_raw > 0 and fetch_targets:` — omitted entirely when empty (per brief).
- Per `doc_id`, calls `get_file_chunks(src, collection_name, 0, 0, raw=True)` to fetch stored original.
- Range expansion preserved verbatim: `_line_window_from_context_chars(raw_lines, offsets, ls, le, fetch_context_chars)` per original hit range, then `_merge_line_ranges` to coalesce.
- Each merged `(start, end)` emits one `<raw>` element. `line_start`/`line_end` are the **expanded+merged** ranges (not the original hit ranges) — per brief requirement.
- Same file with N disjoint merged ranges → N parallel `<raw>` elements, each carrying `file_path` / `doc_id` / `line_start` / `line_end`.
- `<content>` body is the raw excerpt (zero XML escaping, per global constraint).

### Root assembly
```python
    lines = [f"<nbrag_search_and_fetch {' '.join(root_attrs)}>"]
    lines.append("Follow-up handles in <hit>: file_path, doc_id, chunk_index, line_start, line_end.")
    lines.append("")
    lines.append("<ranked_hits>")
    lines.extend(lines_hits)
    lines.append("</ranked_hits>")
    lines.append("")
    if lines_fetched:
        lines.append("<fetched_raw>")
        lines.extend(lines_fetched)
        lines.append("</fetched_raw>")
        lines.append("")
    lines.append("</nbrag_search_and_fetch>")
```

Root attrs: `collection_name`, `total_chunks`, `bm25="off" if path_filter else "on"`, `rerank`, optional `filter_file_path`.

### Removed prose
All header散文 deleted: `This tool returns both...`, `query is the main...`, `fetch_context_chars is per...`, `Behavior note...`, `Ranked search results:`, `Auto-fetched original content (N file(s)):`, `Returned raw snippets come from...`, and the old `[collection] N chunks | bm25: ... | rerank: ...` header line. Replaced with the single canonical "Follow-up handles in <hit>: ..." hint line (same convention as Task 3's `_format_search_results`).

### Public signature
Unchanged: `nbrag_search_and_fetch(query, collection_name, top_k=5, fetch_top_n_raw=3, fetch_context_chars=DEFAULT_FETCH_CONTEXT_CHARS, filter_file_path="", bm25_query="")`.

---

## 4. Step 7 grep results

Pattern: `chunk:\d|chunk:[A-Z]|line:\d|line:[A-Z]|matched_line|line_range|chunk_count|original_file`

18 total hits across the file. Inspecting each for location relative to `nbrag_search_and_fetch` (now L428-L526):

| Line | Match | Location | Verdict |
|------|-------|----------|---------|
| 121 | `_merge_line_ranges` def | helper def (out of range) | legit symbol |
| 181 | `chunk_count` fallback in `_collection_presence_issue_text` | helper (out of range) | legit dict key |
| 266 | `line:N-M` in `nbrag_help` docstring | out of range | unchanged prose |
| 500 | `_merge_line_ranges(expanded_ranges)` call | **inside nbrag_search_and_fetch** | legit function call — `line_range` substring of `_merge_line_ranges`, false positive |
| 566, 571 | `matched_line` / `line_range` in `nbrag_grep` | out of range | nbrag_grep unchanged, out of scope |
| 651, 652, 656 | `chunk_count` / `total_chunks:` in `nbrag_find_definition` | out of range | out of scope |
| 671, 680 | `chunk:X/Y` / `chunk_index:X` in `nbrag_get_adjacent_chunks` recovery text | out of range | out of scope |
| 744, 753 | `line:N-M` in `nbrag_get_chunks_by_lines` recovery text | out of range | out of scope |
| 760 | `line_range: line:N-M` in `nbrag_get_chunks_by_lines` | out of range | out of scope |
| 792 | `original_file:` in `nbrag_get_raw_file` | out of range | out of scope (Task 5+) |
| 819, 820, 842 | `chunk_count` in `nbrag_list` / stats | out of range | out of scope |

**Conclusion:** Inside `nbrag_search_and_fetch` (L428-L526) the only hit is the legitimate `_merge_line_ranges` function call (false-positive substring match). No deprecated field formats remain: no `chunk:X/Y`, no `chunk_index:X`, no `total_chunks:Y`, no `line:N-M`, no `doc_id:X`, no `dist:X`, no `score:X`, no `original_file`, no `range: line:N-M`. The old `original_file:` line in fetched_raw (was L542) is fully gone — it survives only in `nbrag_get_raw_file` at L792, which is out of Task 4 scope.

A narrower confirmatory grep for actual deprecated format strings (`original_file|chunk:\d|chunk:[A-Z]|line:\d|line:[A-Z]|chunk_index:\d|total_chunks:\d|dist:\d|score:\d|doc_id:[a-zA-Z0-9]|scope:[a-zA-Z]`) returned 6 hits, **none** inside L428-L526.

---

## 5. Step 8 import verification

Command:
```powershell
$env:OPENBLAS_NUM_THREADS=1
D:/ProgramData/miniconda3/envs/py312/python.exe -c "from nbrag.mcp_tools import nbrag_search_and_fetch, _format_hit_xml, _format_search_results; print('import OK')"
```

Output:
```
import OK
```

Exit code 0. All three symbols import cleanly.

---

## 6. Commit hash

```
db0eaee5613e981a82d97df2349fa3136d0fe576
```

Message: `refactor(mcp_tools): XML format for nbrag_search_and_fetch with fetched_raw section`

---

## 7. Concerns

1. **`_format_hit_xml` whitespace in `<content>`**: The helper wraps content as `<content>\n{doc}\n</content>` — i.e., a blank line is implied before/after `doc` only via the explicit `\n`. When `doc` itself is multi-line, the rendered XML has content on its own line(s) between `<content>` and `</content>`. This matches Task 3's existing behavior (verified: Task 3 emitted `<content>` / `doc` / `</content>` as separate list items, which joined to the same `\n`-separated form). No regression.

2. **DRY refactor of `_format_search_results` is behavior-preserving** — the old code appended 4 separate list lines for content hits (`<hit ...>`, `<content>`, `doc`, `</content>`, `</hit>` → 5 lines joined by `\n`); the new helper returns one string `<hit ...>\n<content>\n{doc}\n</content>\n</hit>` which, when appended as a single list item and joined with `\n`, produces byte-identical output. Verified by inspection.

3. **`bm25_str` semantics unchanged for nbrag_search_and_fetch**: kept as `"off" if path_filter else "on"` (the function always uses bm25+vector, so the path_filter-only gating is correct). Note this differs from `_format_search_results` which uses the more nuanced `"off" if path_filter and use_vector else ("on" if use_bm25 else "off")` — that nuance is unnecessary here because nbrag_search_and_fetch hardcodes `use_bm25=True` and implicit `use_vector=True` in its `search()` call.

4. **Out-of-scope deprecated fields remain in other functions** (nbrag_grep, nbrag_get_adjacent_chunks, nbrag_get_chunks_by_lines, nbrag_get_raw_file, nbrag_list) — these are flagged for later tasks (Task 5+) per the plan, not Task 4's responsibility.

5. **No tests written** — per brief Step 9 / global constraints. Import check is the only verification gate.
