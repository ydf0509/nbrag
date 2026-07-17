# Task 3 Report — XML format for `_format_search_results`

**File modified:** `nbrag/mcp_tools.py` (only)
**Commit:** `8fe9c242466d179f2997177951ac56bbd2b7a6e7`
**Status:** DONE

---

## 1. What changed

### 1.1 `_format_search_results` — signature (Step 2)

Added `root_tag: str = "nbrag_search"` parameter after `bm25_query` (internal function, signature extension allowed).

**Before:**
```python
def _format_search_results(
    query: str,
    collection_name: str,
    top_k: int = 5,
    use_rerank: bool = True,
    use_bm25: bool = True,
    use_vector: bool = True,
    filter_file_path: str = "",
    include_content: bool = True,
    bm25_query: str = "",
) -> str:
```

**After:**
```python
def _format_search_results(
    query: str,
    collection_name: str,
    top_k: int = 5,
    use_rerank: bool = True,
    use_bm25: bool = True,
    use_vector: bool = True,
    filter_file_path: str = "",
    include_content: bool = True,
    bm25_query: str = "",
    root_tag: str = "nbrag_search",
) -> str:
```

### 1.2 `_format_search_results` — return section (Step 3)

Logic at L284-308 (param normalization, `path_filter` validation, `search()` call, `collection_issue` check, `no_results` check) is UNCHANGED.

The return-building section (formerly L309-354) was rewritten from prose to XML.

**Before (prose):**
```python
    rerank_str = cfg.rerank.model if rerank_used else "off"
    bm25_str = "off" if path_filter and use_vector else ("on" if use_bm25 else "off")
    lines = [f"[{collection_name}] {total} chunks | bm25: {bm25_str} | rerank: {rerank_str}"]
    if path_filter:
        lines[0] += f" | filter_file_path: {path_filter}"
    lines.extend([
        "",
        "Returned handle fields for follow-up: file_path, doc_id, chunk_index, line range.",
        "query is the main semantic query used by vector retrieval and reranking. bm25_query, when provided, is the lexical-anchor query used only by BM25.",
        "",
    ])
    if path_filter and use_vector:
        lines.extend([
            "Behavior note: with filter_file_path set, current hybrid behavior narrows vector retrieval to that single file and does not run cross-file BM25 fusion.",
            "",
        ])

    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
        if meta is None:
            meta = {}
        src = meta.get("source", meta.get("filename", "?"))
        ci = meta.get("chunk_index", "?")
        tc = meta.get("total_chunks", "?")
        ls = meta.get("line_start", "?")
        le = meta.get("line_end", "?")
        scope = str(meta.get("scope", ""))
        doc_id = str(meta.get("doc_id", "?"))

        meta_parts = [f"chunk:{ci}/{tc}", f"chunk_index:{ci}", f"total_chunks:{tc}", f"line:{ls}-{le}"]
        if scope:
            meta_parts.append(f"scope:{scope}")
        meta_parts.append(f"doc_id:{doc_id}")
        meta_parts.append(f"dist:{dist:.4f}")
        if rerank_scores and i < len(rerank_scores):
            meta_parts.append(f"score:{rerank_scores[i]:.4f}")

        lines.append(f"[{i + 1}/{len(documents)}] {meta.get('filename', '?')} {' '.join(meta_parts)}")
        lines.append(f"file_path: {src}")

        if include_content:
            lines.append(doc)
        else:
            lines.append("content omitted")
        lines.append("")

    return "\n".join(lines)
```

**After (XML):**
```python
    rerank_str = cfg.rerank.model if rerank_used else "off"
    bm25_str = "off" if path_filter and use_vector else ("on" if use_bm25 else "off")

    # 根标签属性
    root_attrs = [f'collection_name="{collection_name}"', f'total_chunks="{total}"', f'bm25="{bm25_str}"', f'rerank="{rerank_str}"']
    if path_filter:
        root_attrs.append(f'filter_file_path="{path_filter}"')
    lines = [f"<{root_tag} {' '.join(root_attrs)}>"]
    lines.append("Follow-up handles in <hit>: file_path, doc_id, chunk_index, line_start, line_end.")
    lines.append("")
    lines.append("<ranked_hits>")

    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
        if meta is None:
            meta = {}
        file_path = _meta_file_path(meta)
        chunk_index = _meta_chunk_index(meta)
        total_chunks = str(meta.get("total_chunks", "?"))
        line_start = str(meta.get("line_start", "?"))
        line_end = str(meta.get("line_end", "?"))
        scope = str(meta.get("scope", ""))
        doc_id = str(meta.get("doc_id", "?"))

        hit_attrs = [
            f'rank="{i + 1}"',
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
        if rerank_scores and i < len(rerank_scores):
            hit_attrs.append(f'score="{rerank_scores[i]:.4f}"')

        if include_content:
            lines.append(f'<hit {" ".join(hit_attrs)}>')
            lines.append("<content>")
            lines.append(doc)
            lines.append("</content>")
            lines.append("</hit>")
        else:
            lines.append(f'<hit {" ".join(hit_attrs)} />')

    lines.append("</ranked_hits>")
    lines.append("")
    lines.append(f"</{root_tag}>")
    return "\n".join(lines)
```

Key behavioral rules applied:
- Uses Task 2 helpers `_meta_file_path(meta)` / `_meta_chunk_index(meta)` (no inline `meta.get("source", ...)` / `meta.get("chunk_index", meta.get("index", ...))`).
- `include_content=False` → self-closing `<hit ... />` with no `<content>`.
- `scope` empty → attribute omitted (no `scope=""`).
- `score` only written when `rerank_scores` has a value for that index.
- `filter_file_path` empty → omitted from root attrs; non-empty → included.
- Removed prose: query/bm25_query explanation, behavior note, "Returned handle fields" prose (replaced with concise "Follow-up handles in <hit>: ..." line).
- Canonical handle field names only: `file_path` / `doc_id` / `chunk_index` / `total_chunks` / `line_start` / `line_end`.

### 1.3 `nbrag_search` (Step 4)

**Before:**
```python
    return _format_search_results(
        query=query,
        collection_name=collection_name,
        top_k=top_k,
        use_rerank=use_rerank,
        use_bm25=use_bm25,
        use_vector=True,
        filter_file_path=filter_file_path,
        include_content=include_content,
        bm25_query=bm25_query,
    )
```

**After:** added `root_tag="nbrag_search",` line.

### 1.4 `nbrag_search_only_bm25` (Step 5)

**Before:**
```python
    return _format_search_results(
        query=  bm25_query,
        collection_name=collection_name,
        top_k=top_k,
        use_rerank=False,
        use_bm25=True,
        use_vector=False,
        filter_file_path=filter_file_path,
        include_content=include_content,
    )
```

**After:** added `root_tag="nbrag_search_only_bm25",` line. (Existing `query=  bm25_query,` whitespace left untouched — out of scope.)

### 1.5 `nbrag_search_only_vector` (Step 6)

This is the structural change: previously delegated to `nbrag_search`, now calls `_format_search_results` directly so it can pass the correct `root_tag`.

**Before:**
```python
def nbrag_search_only_vector(
    query: str,
    collection_name: str,
    top_k: int = 5,
    filter_file_path: str = "",
    include_content: bool = True,
) -> str:
    return nbrag_search(
        query=query,
        collection_name=collection_name,
        top_k=top_k,
        use_rerank=False,
        use_bm25=False,
        filter_file_path=filter_file_path,
        include_content=include_content,
    )
```

**After:**
```python
def nbrag_search_only_vector(
    query: str,
    collection_name: str,
    top_k: int = 5,
    filter_file_path: str = "",
    include_content: bool = True,
) -> str:
    return _format_search_results(
        query=query,
        collection_name=collection_name,
        top_k=top_k,
        use_rerank=False,
        use_bm25=False,
        use_vector=True,
        filter_file_path=filter_file_path,
        include_content=include_content,
        root_tag="nbrag_search_only_vector",
    )
```

Public signature unchanged (per Global Constraints).

---

## 2. Step 7 — grep results (deprecated field names)

Pattern: `chunk:\d|chunk:[A-Z]|line:\d|line:[A-Z]|matched_line|line_range|chunk_count`
Path: `nbrag/mcp_tools.py`

**18 matches total, NONE in L273-L414 (Task 3 scope).** All matches are in other functions outside this task's scope:

| Line | Location | Note |
|------|----------|------|
| 121 | `_merge_line_ranges` | function name itself (out of scope) |
| 181 | `nbrag_stats` | `info.get("chunks", info.get("chunk_count", 0))` |
| 266 | `nbrag_workflow_skeleton` | prose string `"line:N-M"` |
| 469 | `nbrag_search_and_fetch` | prose string `"line:N-M"` |
| 537 | `nbrag_search_and_fetch` | `_merge_line_ranges` call |
| 585 | `nbrag_search_and_fetch` | prose `"matched_line, line_range"` |
| 590 | `nbrag_search_and_fetch` | `matched_line: ... line_range: line:N-M` |
| 670, 671, 675 | `nbrag_get_adjacent_chunks` | `chunk_count` / `total_chunks` / match formatting |
| 690, 699 | `nbrag_get_adjacent_chunks` | prose `"chunk:X/Y or chunk_index:X"` |
| 763, 772, 779 | `nbrag_get_chunks_by_lines` | prose + `line_range: line:N-M` |
| 838, 839, 861 | `nbrag_get_file_chunks` / `nbrag_stats` | `chunk_count` |

**Conclusion:** L273-L414 is clean of deprecated field-name variants. The matches above belong to other functions scheduled for later tasks (Task 4+).

---

## 3. Step 8 — import verification

Command:
```powershell
$env:OPENBLAS_NUM_THREADS=1
D:/ProgramData/miniconda3/envs/py312/python.exe -c "from nbrag.mcp_tools import _format_search_results, nbrag_search, nbrag_search_only_bm25, nbrag_search_only_vector; print('import OK')"
```

Output:
```
import OK
```

Exit code: 0 — module imports cleanly, all 4 symbols resolve.

---

## 4. Commit hash

```
8fe9c242466d179f2997177951ac56bbd2b7a6e7
```

Commit message: `refactor(mcp_tools): XML format for _format_search_results (affects 3 search fns)`
Diff stat: `1 file changed, 39 insertions(+), 29 deletions(-)`

---

## 5. Concerns

None blocking. Minor observations:

1. **Out-of-scope deprecated patterns remain** in `nbrag_search_and_fetch`, `nbrag_get_adjacent_chunks`, `nbrag_get_chunks_by_lines`, `nbrag_get_file_chunks`, `nbrag_workflow_skeleton`, and `nbrag_stats` (see Step 7 table). These are explicitly out of Task 3's scope and presumably slated for later tasks (Task 4+). Flagging here so the parent agent knows they were not missed.

2. **`nbrag_search_only_bm25` preserves existing `query=  bm25_query,`** (double-space cosmetic quirk) — left untouched per "don't change unrelated code" rule. Will be cleaned up if/when a later task touches that function's body.

3. **`<content>` body is unescaped** per the brief's "正文零转义" rule. If stored chunk text ever contains literal `</content>` or `<hit` substrings, downstream XML parsing could break. This is by design per the brief; noted only as a known constraint.

4. No tests written (per Task 3 constraints — functional verification deferred to Task 10).
