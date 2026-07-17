# Task 3 Review — XML format for `_format_search_results`

**Reviewer verdict date:** 2026-07-16
**Commit reviewed:** `8fe9c242466d179f2997177951ac56bbd2b7a6e7`
**File reviewed:** `nbrag/mcp_tools.py` (only file modified — confirmed via diff header)

---

## Verdict 1 — Spec compliance: ✅

All global constraints and Task-3-specific requirements satisfied:

| Requirement | Status | Evidence |
|---|---|---|
| Only `nbrag/mcp_tools.py` modified | ✅ | diff header `diff --git a/nbrag/mcp_tools.py` |
| 3 search functions' public signatures unchanged | ✅ | `nbrag_search` (L363-372), `nbrag_search_only_bm25` (L387-393), `nbrag_search_only_vector` (L407-413) — signatures identical to pre-change |
| `_format_search_results` got `root_tag` param (internal, allowed) | ✅ | Added at L283, after `bm25_query` — exact placement per Step 2 |
| Uses `_meta_file_path(meta)` / `_meta_chunk_index(meta)` from Task 2 | ✅ | L325-326; helpers defined at L76/L81 (no inline `meta.get("source",...)` mapping in scope) |
| Canonical handle fields as XML attributes: `file_path` / `doc_id` / `chunk_index` / `total_chunks` / `line_start` / `line_end` | ✅ | L335-340 in `hit_attrs` |
| Deprecated forms NOT in changed region (L273-L414): `chunk:X/Y` / `line:N-M` / `chunk_index:X` / `total_chunks:Y` | ✅ | grep scan returned 23 hits, ALL outside L273-L414 (in `_merge_line_ranges`, `nbrag_stats`, `nbrag_workflow_skeleton`, `nbrag_search_and_fetch`, `nbrag_get_adjacent_chunks`, `nbrag_get_chunks_by_lines`, `nbrag_get_file_chunks`) — slated for Task 4+ |
| `include_content=False` → self-closing `<hit ... />` | ✅ | L355 `<hit {" ".join(hit_attrs)} />` |
| `scope` empty → omit attribute (not `scope=""`) | ✅ | L342-343 `if scope: hit_attrs.append(...)` |
| `score` only when `rerank_scores` available | ✅ | L345-346 `if rerank_scores and i < len(rerank_scores):` |
| `filter_file_path` empty → omit from root attrs | ✅ | L315-316 `if path_filter: root_attrs.append(...)` |
| Logic before return section unchanged (param normalization, `search()` call, error checks) | ✅ | L285-308 — all lines preserved unchanged in diff (no `+`/`-` prefix on those lines) |
| `nbrag_search_only_vector` calls `_format_search_results` directly (not via `nbrag_search`) | ✅ | L414 `return _format_search_results(` — was `return nbrag_search(` before |
| `nbrag_search_only_vector` passes its own `root_tag` | ✅ | L420 `use_vector=True`, L423 `root_tag="nbrag_search_only_vector"` |
| 3 callers pass correct `root_tag` values | ✅ | `nbrag_search`→`"nbrag_search"` (L383), `nbrag_search_only_bm25`→`"nbrag_search_only_bm25"` (L403), `nbrag_search_only_vector`→`"nbrag_search_only_vector"` (L423) |
| No tests written | ✅ | Confirmed — no test files in diff |
| Header prose (query/bm25_query explanation, behavior note) removed | ✅ | All prose strings removed in diff; replaced with single concise "Follow-up handles in <hit>: ..." line |
| Output matches target XML format from brief | ✅ | Root `<nbrag_search ...>` → handles line → `<ranked_hits>` → `<hit rank="..." ...>` → `<content>` ... `</content>` → `</hit>` → `</ranked_hits>` → `</nbrag_search>` — byte-for-byte structural match to brief's target block |

No gaps. No extras beyond spec.

---

## Verdict 2 — Task quality: Approved

Findings (severity-rated):

### Info (no action needed)

1. **[Info] Unescaped `<content>` body** — `<content>` wraps `doc` as raw text per the brief's "正文零转义" rule. If stored chunk text ever contains literal `</content>`, `<hit`, or `</nbrag_search>` substrings, downstream XML parsing could break. This is a known design constraint per Task 3 brief, not a defect. Implementer correctly flagged it in their report §5.3.

2. **[Info] `query=  bm25_query,` cosmetic quirk preserved** — `nbrag_search_only_bm25` (L395) retains the pre-existing double-space between `query=` and `bm25_query`. Implementer left it untouched per "don't change unrelated code" rule. Appropriate — out of Task 3 scope; can be cleaned up if a later task touches that function body.

3. **[Info] Out-of-scope deprecated patterns** — `nbrag_search_and_fetch`, `nbrag_get_adjacent_chunks`, `nbrag_get_chunks_by_lines`, `nbrag_get_file_chunks`, `nbrag_workflow_skeleton`, `nbrag_stats` still use `chunk:X/Y` / `line:N-M` / `chunk_index:X` / `total_chunks:Y` / `matched_line` / `line_range` / `chunk_count` patterns. These are explicitly Task 4+ scope. Implementer correctly did not touch them. Flagging for parent agent visibility (Task 4 should pick these up).

### XML well-formedness audit (passed)

- ✅ All attribute values double-quoted.
- ✅ Root tag opens `<{root_tag} ...>` and closes `</{root_tag}>` with matching `root_tag` value.
- ✅ `<hit>` opens and `</hit>` closes when `include_content=True`; self-closing `<hit ... />` when `False`.
- ✅ `<content>` opens, raw text, `</content>` closes — no stray tags inside.
- ✅ `<ranked_hits>` opens and `</ranked_hits>` closes.
- ✅ `dist` always written (4-decimal); `score` conditional on rerank — both formatted as quoted attributes.
- ✅ `rank="1"` ... `rank="N"` — 1-indexed per brief.

### Code quality observations

- Variable naming (`file_path`, `chunk_index`, `total_chunks`, `line_start`, `line_end`, `scope`, `doc_id`) is direct and readable — no opaque `ci`/`tc`/`ls`/`le`/`src` abbreviations from the old prose form.
- `str(meta.get("total_chunks", "?"))` etc. ensures non-string metadata values don't break f-string attribute rendering — good defensive coercion without over-engineering.
- Inline comment `# 根标签属性` (L313) is minimal and helpful; matches project's bilingual comment style seen elsewhere.
- Diff is +39/-29 — proportional to scope, no opportunistic refactoring.

---

## Summary

**Spec compliance:** ✅ — every Step 1-8 requirement met, no gaps, no extras.
**Task quality:** Approved — no blocking findings; 3 informational notes all confirmed as in-scope design decisions or correctly-deferred-to-later-task items.

Implementation is ready to proceed to Task 4.
