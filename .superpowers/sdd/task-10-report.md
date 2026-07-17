# Task 10 Report: End-to-End XML Format Verification

## Summary

Task 10 is the final verification task in the 10-task SDD refactor of nbrag's MCP tool functions to canonical XML format with canonical handle fields (`file_path`, `doc_id`, `chunk_index`, `total_chunks`, `line_start`, `line_end`).

A self-test script `scripts/test_xml_format.py` was written and executed. It directly imports all 14 `nbrag_*` functions from `nbrag.mcp_tools`, calls them in sequence against real pre-ingested collections, and verifies the return XML format. **All 15 verification steps PASSED (15/15).**

The script is adaptive: it calls `nbrag_stats()` to pick the first collection with chunks > 0, then `nbrag_list()` to discover filenames, and derives query/pattern/keyword values from those filenames. No collection names or queries are hardcoded.

Auxiliary grep scans confirmed that `nbrag/skills/nbrag-workflow/SKILL.md` is clean (0 deprecated field-name hits). The `nbrag/*.py` scan found 28 matches, of which 26 are internal function/variable names (acceptable per brief) and **2 are AI-facing `chunk_index:X` occurrences in `server.py`** (lines 134 and 353) — these are findings for final review.

## Final Script Content (`scripts/test_xml_format.py`)

```python
"""End-to-end XML format verification for nbrag MCP tool functions.

Calls every nbrag_* function via direct import and verifies the return
format matches the canonical XML spec with canonical handle fields
(file_path, doc_id, chunk_index, total_chunks, line_start, line_end).

The script is adaptive: it first calls nbrag_stats() to pick a collection,
then nbrag_list() to discover filenames, and derives query/pattern values
from those filenames instead of hardcoding them.

Run:
    D:/ProgramData/miniconda3/envs/py312/python.exe scripts/test_xml_format.py
"""

import os

# Must be set BEFORE any nbrag import to avoid OpenBLAS memory allocation failures.
os.environ["OPENBLAS_NUM_THREADS"] = "1"

import re
import sys

# Ensure project root (d:/codes/nbrag) is importable so `import my_load_config`
# and `from nbrag...` both resolve when the script is run from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import my_load_config  # noqa: F401  (loads NBRAG_API_KEY from dotenv)
from nbrag.config import load_config

load_config()

from nbrag.mcp_tools import (
    nbrag_help,
    nbrag_stats,
    nbrag_search,
    nbrag_search_and_fetch,
    nbrag_search_only_bm25,
    nbrag_search_only_vector,
    nbrag_grep,
    nbrag_find_definition,
    nbrag_find_files,
    nbrag_list,
    nbrag_get_raw_file,
    nbrag_get_file_chunks,
    nbrag_get_adjacent_chunks,
    nbrag_get_chunks_by_lines,
)


# ---- helpers ---------------------------------------------------------------

_passed = 0
_TOTAL = 15


def _record(step: int, ok: bool, reason: str = "") -> None:
    global _passed
    if ok:
        _passed += 1
        print(f"Step {step:2d}: PASS")
    else:
        detail = f" {reason}" if reason else ""
        print(f"Step {step:2d}: FAIL{detail}")


def _attr(attrs_text: str, name: str):
    """Extract first attribute value from an XML attribute string."""
    m = re.search(rf'{name}="([^"]*)"', attrs_text)
    return m.group(1) if m else None


def _first_tag_attrs(text: str, tag: str):
    """Return the attribute portion (between tag name and closing >) of the
    first ``<tag ...>`` occurrence.  Works for both self-closing and
    content-bearing forms because ``[^>]`` stops at the first ``>``.
    """
    m = re.search(rf'<{tag}\s+([^>]*)>', text)
    return m.group(1) if m else None


def _derive_query(filename: str) -> str:
    """Derive a search query from a filename stem."""
    if not filename:
        return "的"
    stem = os.path.splitext(filename)[0]
    cjk_seqs = re.findall(r"[\u4e00-\u9fff]+", stem)
    if cjk_seqs:
        return max(cjk_seqs, key=len)
    ascii_stem = re.sub(r"^[_\d]+", "", stem)
    return ascii_stem or stem or "def"


def _derive_grep_keyword(filename: str) -> str:
    """Pick a grep keyword likely to appear in source text."""
    if filename and re.search(r"[\u4e00-\u9fff]", filename):
        return "的"
    return "e"


def _derive_pattern(filename: str) -> str:
    """Pick a filename fragment for nbrag_find_files."""
    if not filename:
        return "."
    stem = os.path.splitext(filename)[0]
    cjk_seqs = re.findall(r"[\u4e00-\u9fff]+", stem)
    if cjk_seqs:
        return max(cjk_seqs, key=len)[:5]
    ascii_stem = re.sub(r"^[_\d]+", "", stem)
    return ascii_stem[:10] if ascii_stem else stem[:10]


# ---- shared state ----------------------------------------------------------

S: dict = {}

# ===========================================================================
# Step 1: nbrag_help
# ===========================================================================
try:
    out = nbrag_help()
    ok = (
        "line_start" in out
        and "line_end" in out
        and "line:N-M" not in out
        and "chunk:X/Y" not in out
        and "chunk_index:X" not in out
    )
    _record(1, ok, "" if ok else "help text missing canonical handles or contains deprecated forms")
except Exception as exc:  # noqa: BLE001
    _record(1, False, f"exception: {exc!r}")

# ===========================================================================
# Step 2: nbrag_stats  (also picks collection_name for downstream steps)
# ===========================================================================
try:
    out = nbrag_stats()
    ok = (
        out.startswith("<nbrag_stats>")
        and out.rstrip().endswith("</nbrag_stats>")
        and "<collections>" in out
        and "<collection " in out
    )
    if not ok:
        _record(2, False, "stats XML shape mismatch")
    else:
        coll = None
        for m in re.finditer(r"<collection\s+([^/>]*)/>", out):
            attrs = m.group(1)
            name = _attr(attrs, "collection_name")
            chunks_str = _attr(attrs, "chunks") or "0"
            try:
                chunks = int(chunks_str)
            except ValueError:
                chunks = 0
            if name and chunks > 0:
                coll = name
                break
        if coll:
            S["collection_name"] = coll
            _record(2, True)
        else:
            _record(2, False, "no collection with chunks > 0 found")
except Exception as exc:  # noqa: BLE001
    _record(2, False, f"exception: {exc!r}")

# ---- early nbrag_list for adaptation (output reused in Step 10) -----------

_list_out = None
_list_file_path = None
_list_doc_id = None
_list_filename = None
if "collection_name" in S:
    try:
        _list_out = nbrag_list(S["collection_name"])
        doc_attrs = _first_tag_attrs(_list_out, "document")
        if doc_attrs:
            _list_file_path = _attr(doc_attrs, "file_path")
            _list_doc_id = _attr(doc_attrs, "doc_id")
            _list_filename = _attr(doc_attrs, "filename")
    except Exception:  # noqa: BLE001
        pass

_query = _derive_query(_list_filename or "")
_bm25_query = _query
_grep_keyword = _derive_grep_keyword(_list_filename or "")
_find_files_pattern = _derive_pattern(_list_filename or "")
_symbol = "main"

# Guard: if no collection, fail remaining steps with a clear reason.
if "collection_name" not in S:
    for _step in range(3, _TOTAL + 1):
        _record(_step, False, "no collection_name available from step 2")
else:
    _coll = S["collection_name"]

    # =======================================================================
    # Step 3: nbrag_search_and_fetch  (extract 5 handles from first <hit>)
    # =======================================================================
    try:
        out = nbrag_search_and_fetch(
            query=_query, collection_name=_coll, bm25_query=_bm25_query
        )
        ok = (
            "<nbrag_search_and_fetch" in out
            and "<ranked_hits>" in out
            and "<hit " in out
            and "<fetched_raw>" in out
        )
        if not ok:
            _record(3, False, f"XML shape mismatch; output head: {out[:200]!r}")
        else:
            hit_attrs = _first_tag_attrs(out, "hit")
            if not hit_attrs:
                _record(3, False, "no <hit> tag attributes found")
            else:
                S["hit_file_path"] = _attr(hit_attrs, "file_path")
                S["hit_doc_id"] = _attr(hit_attrs, "doc_id")
                S["hit_chunk_index"] = _attr(hit_attrs, "chunk_index")
                S["hit_line_start"] = _attr(hit_attrs, "line_start")
                S["hit_line_end"] = _attr(hit_attrs, "line_end")
                missing = [
                    k for k in ("hit_file_path", "hit_doc_id", "hit_chunk_index",
                                "hit_line_start", "hit_line_end") if S[k] is None
                ]
                _record(3, not missing, "" if not missing else f"missing handles: {missing}")
    except Exception as exc:  # noqa: BLE001
        _record(3, False, f"exception: {exc!r}")

    # =======================================================================
    # Step 4: nbrag_search with include_content=False  (self-closing <hit/>)
    # =======================================================================
    try:
        out = nbrag_search(
            query=_query, collection_name=_coll,
            include_content=False, bm25_query=_bm25_query,
        )
        ok = (
            "<nbrag_search" in out
            and "<ranked_hits>" in out
            and "<hit " in out
            and "<content>" not in out
        )
        _record(4, ok, "" if ok else f"XML shape mismatch; output head: {out[:200]!r}")
    except Exception as exc:  # noqa: BLE001
        _record(4, False, f"exception: {exc!r}")

    # =======================================================================
    # Step 5: nbrag_search_only_bm25
    # =======================================================================
    try:
        out = nbrag_search_only_bm25(bm25_query=_bm25_query, collection_name=_coll)
        ok = "<nbrag_search_only_bm25" in out
        _record(5, ok, "" if ok else f"XML shape mismatch; output head: {out[:200]!r}")
    except Exception as exc:  # noqa: BLE001
        _record(5, False, f"exception: {exc!r}")

    # =======================================================================
    # Step 6: nbrag_search_only_vector
    # =======================================================================
    try:
        out = nbrag_search_only_vector(query=_query, collection_name=_coll)
        ok = "<nbrag_search_only_vector" in out
        _record(6, ok, "" if ok else f"XML shape mismatch; output head: {out[:200]!r}")
    except Exception as exc:  # noqa: BLE001
        _record(6, False, f"exception: {exc!r}")

    # =======================================================================
    # Step 7: nbrag_grep  (extract handles from first <match>)
    # =======================================================================
    try:
        out = nbrag_grep(keyword=_grep_keyword, collection_name=_coll)
        ok = (
            "<nbrag_grep" in out
            and "<matches>" in out
            and "<match " in out
        )
        if not ok:
            _record(7, False, f"XML shape mismatch; output head: {out[:200]!r}")
        else:
            match_attrs = _first_tag_attrs(out, "match")
            if not match_attrs:
                _record(7, False, "no <match> tag attributes found")
            else:
                S["grep_file_path"] = _attr(match_attrs, "file_path")
                S["grep_doc_id"] = _attr(match_attrs, "doc_id")
                S["grep_line_start"] = _attr(match_attrs, "line_start")
                S["grep_line_end"] = _attr(match_attrs, "line_end")
                missing = [
                    k for k in ("grep_file_path", "grep_doc_id",
                                "grep_line_start", "grep_line_end") if S[k] is None
                ]
                _record(7, not missing, "" if not missing else f"missing handles: {missing}")
    except Exception as exc:  # noqa: BLE001
        _record(7, False, f"exception: {exc!r}")

    # =======================================================================
    # Step 8: nbrag_find_definition  (tolerant: error types count as PASS)
    # =======================================================================
    try:
        out = nbrag_find_definition(symbol=_symbol, collection_name=_coll)
        if out.startswith("<nbrag_find_definition"):
            ok = "<definitions>" in out and "<definition " in out
            _record(8, ok, "" if ok else "XML shape mismatch (no <definitions>/<definition)")
        elif out.startswith("<error"):
            ok = (
                'type="not_found"' in out
                or 'type="no_results"' in out
                or 'type="missing_collection"' in out
                or 'type="empty_collection"' in out
            )
            _record(8, ok, "" if ok else f"unexpected error type; output head: {out[:200]!r}")
        else:
            _record(8, False, f"malformed output; head: {out[:100]!r}")
    except Exception as exc:  # noqa: BLE001
        _record(8, False, f"exception: {exc!r}")

    # =======================================================================
    # Step 9: nbrag_find_files  (<file> must have total_chunks, not chunk_count)
    # =======================================================================
    try:
        out = nbrag_find_files(pattern=_find_files_pattern, collection_name=_coll)
        ok = (
            "<nbrag_find_files" in out
            and "<files>" in out
            and "<file " in out
        )
        if not ok:
            _record(9, False, f"XML shape mismatch; output head: {out[:200]!r}")
        else:
            file_attrs = _first_tag_attrs(out, "file")
            if not file_attrs:
                _record(9, False, "no <file> tag attributes found")
            else:
                has_total = _attr(file_attrs, "total_chunks") is not None
                has_count = _attr(file_attrs, "chunk_count") is not None
                ok = has_total and not has_count
                _record(9, ok, "" if ok else "<file> must use total_chunks, not chunk_count")
    except Exception as exc:  # noqa: BLE001
        _record(9, False, f"exception: {exc!r}")

    # =======================================================================
    # Step 10: nbrag_list  (<document> must have doc_id, file_path, total_chunks)
    # =======================================================================
    try:
        out = _list_out if _list_out is not None else nbrag_list(_coll)
        ok = (
            "<nbrag_list" in out
            and "<documents>" in out
            and "<document " in out
        )
        if not ok:
            _record(10, False, f"XML shape mismatch; output head: {out[:200]!r}")
        else:
            doc_attrs = _first_tag_attrs(out, "document")
            if not doc_attrs:
                _record(10, False, "no <document> tag attributes found")
            else:
                has_doc_id = _attr(doc_attrs, "doc_id") is not None
                has_file_path = _attr(doc_attrs, "file_path") is not None
                has_total = _attr(doc_attrs, "total_chunks") is not None
                has_count = _attr(doc_attrs, "chunk_count") is not None
                ok = has_doc_id and has_file_path and has_total and not has_count
                _record(10, ok, "" if ok else "<document> must use doc_id/file_path/total_chunks")
    except Exception as exc:  # noqa: BLE001
        _record(10, False, f"exception: {exc!r}")

    # =======================================================================
    # Step 11: nbrag_get_raw_file  (use file_path from step 3 or 7 or list)
    # =======================================================================
    _raw_file_path = (
        S.get("hit_file_path")
        or S.get("grep_file_path")
        or _list_file_path
    )
    try:
        if not _raw_file_path:
            _record(11, False, "no file_path available from earlier steps")
        else:
            out = nbrag_get_raw_file(file_path=_raw_file_path, collection_name=_coll)
            ok = "<nbrag_get_raw_file" in out and "<content>" in out
            _record(11, ok, "" if ok else f"XML shape mismatch; output head: {out[:200]!r}")
    except Exception as exc:  # noqa: BLE001
        _record(11, False, f"exception: {exc!r}")

    # =======================================================================
    # Step 12: nbrag_get_file_chunks  (<chunk> must have chunk_index/line_start/line_end)
    # =======================================================================
    try:
        if not _raw_file_path:
            _record(12, False, "no file_path available from earlier steps")
        else:
            out = nbrag_get_file_chunks(file_path=_raw_file_path, collection_name=_coll)
            ok = (
                "<nbrag_get_file_chunks" in out
                and "<chunks>" in out
                and "<chunk " in out
            )
            if not ok:
                _record(12, False, f"XML shape mismatch; output head: {out[:200]!r}")
            else:
                chunk_attrs = _first_tag_attrs(out, "chunk")
                if not chunk_attrs:
                    _record(12, False, "no <chunk> tag attributes found")
                else:
                    has_ci = _attr(chunk_attrs, "chunk_index") is not None
                    has_ls = _attr(chunk_attrs, "line_start") is not None
                    has_le = _attr(chunk_attrs, "line_end") is not None
                    ok = has_ci and has_ls and has_le
                    _record(12, ok, "" if ok else "<chunk> missing chunk_index/line_start/line_end")
    except Exception as exc:  # noqa: BLE001
        _record(12, False, f"exception: {exc!r}")

    # =======================================================================
    # Step 13: nbrag_get_adjacent_chunks  (uses doc_id + chunk_index from step 3)
    # =======================================================================
    try:
        _doc_id = S.get("hit_doc_id")
        _ci_str = S.get("hit_chunk_index")
        if not _doc_id or not _ci_str:
            _record(13, False, "no doc_id/chunk_index available from step 3")
        else:
            try:
                _ci = int(_ci_str)
            except ValueError:
                _record(13, False, f"chunk_index not int: {_ci_str!r}")
            else:
                out = nbrag_get_adjacent_chunks(
                    doc_id=_doc_id, chunk_index=_ci, collection_name=_coll
                )
                ok = (
                    "<nbrag_get_adjacent_chunks" in out
                    and "anchor_chunk_index=" in out
                    and "<chunks>" in out
                )
                _record(13, ok, "" if ok else f"XML shape mismatch; output head: {out[:200]!r}")
    except Exception as exc:  # noqa: BLE001
        _record(13, False, f"exception: {exc!r}")

    # =======================================================================
    # Step 14: nbrag_get_chunks_by_lines  (uses doc_id + line_start/end from step 3)
    # =======================================================================
    try:
        _doc_id = S.get("hit_doc_id")
        _ls_str = S.get("hit_line_start")
        _le_str = S.get("hit_line_end")
        if not _doc_id or not _ls_str or not _le_str:
            _record(14, False, "no doc_id/line_start/line_end available from step 3")
        else:
            try:
                _ls = int(_ls_str)
                _le = int(_le_str)
            except ValueError:
                _record(14, False, f"line_start/line_end not int: {_ls_str!r}, {_le_str!r}")
            else:
                out = nbrag_get_chunks_by_lines(
                    doc_id=_doc_id, line_start=_ls, line_end=_le, collection_name=_coll
                )
                ok = (
                    "<nbrag_get_chunks_by_lines" in out
                    and "requested_line_start=" in out
                    and "requested_line_end=" in out
                )
                _record(14, ok, "" if ok else f"XML shape mismatch; output head: {out[:200]!r}")
    except Exception as exc:  # noqa: BLE001
        _record(14, False, f"exception: {exc!r}")

    # =======================================================================
    # Step 15: nbrag_get_raw_file with invalid file_path  (must return error XML)
    # =======================================================================
    try:
        out = nbrag_get_raw_file(file_path="INVALID_PATH", collection_name=_coll)
        ok = '<error type="invalid_file_path" field="file_path">' in out
        _record(15, ok, "" if ok else f"expected invalid_file_path error; output head: {out[:200]!r}")
    except Exception as exc:  # noqa: BLE001
        _record(15, False, f"exception: {exc!r}")

# ---- summary ---------------------------------------------------------------

print()
print(f"{_passed}/{_TOTAL} passed")
```

## Step 2: Script Run Output

Command:
```
D:/ProgramData/miniconda3/envs/py312/python.exe scripts/test_xml_format.py
```

Full output:
```
D:\ProgramData\miniconda3\envs\py312\Lib\site-packages\jieba\_compat.py:18: UserWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html. The pkg_resources package is slated for removal as early as 2025-11-30. Refrain from using this package or pin to Setuptools<81.
  import pkg_resources
Building prefix dict from the default dictionary ...
Loading model from cache C:\Users\ydf6\AppData\Local\Temp\jieba.cache
Loading model cost 0.637 seconds.
Prefix dict has been built successfully.
Step  1: PASS
Step  2: PASS
Step  3: PASS
Step  4: PASS
Step  5: PASS
Step  6: PASS
Step  7: PASS
Step  8: PASS
Step  9: PASS
Step 10: PASS
Step 11: PASS
Step 12: PASS
Step 13: PASS
Step 14: PASS
Step 15: PASS

15/15 passed
```

## Step 3: Grep Scan Results

### Scan 1: `nbrag/` directory, `*.py` files

Pattern: `line:N-M|chunk:X/Y|chunk_index:X|matched_line|line_range`

Result: **28 matches** across 6 files.

**Classification:**

| Category | Count | Files | Verdict |
|---|---|---|---|
| Internal function/variable names containing `line_range` substring | 26 | `chunker.py`, `ingest.py`, `mcp_tools.py`, `retrieval.py`, `symbol_index.py` | Acceptable per brief (internal, not AI-facing) |
| AI-facing `chunk_index:X` in `server.py` | 2 | `server.py` lines 134, 353 | **Finding — deprecated form in AI-facing surface** |

**Internal function/variable names (acceptable):**
- `chunker.py`: `compute_line_ranges`, `get_ast_definition_line_range`
- `ingest.py`: `line_ranges` (variable)
- `mcp_tools.py`: `_merge_line_ranges` (explicitly mentioned in brief as acceptable)
- `retrieval.py`: `_char_window_to_line_range`, `chunk_line_ranges`
- `symbol_index.py`: `get_ast_definition_line_range`

**AI-facing findings in `server.py` (concern):**

Line 134 (docstring of `nbrag_search_and_fetch` showing returned field examples):
```
    - chunk_index:X
```

Line 353 (Field description for `nbrag_get_adjacent_chunks` `chunk_index` parameter):
```
    chunk_index: int = Field(description="Target chunk index from a search/search_and_fetch result field like chunk_index + total_chunks or chunk_index:X"),
```

Both use the deprecated `chunk_index:X` colon-form instead of the canonical `chunk_index="..."` XML attribute form. These are AI-facing surfaces (docstrings and Field descriptions are visible to MCP clients and LLM agents). Tasks 1-9 appear to have missed these two spots in `server.py`.

### Scan 2: `nbrag/skills/nbrag-workflow/SKILL.md`

Pattern: `line:N-M|chunk:X/Y|chunk_index:X|matched_line|line_range|chunk_count`

Result: **0 matches** — clean.

## Pass/Fail Count

**15/15 passed**

## Steps that FAILed

None. All 15 steps PASSED.

## Final Commit Hash

```
b369994522aaf70591cff9a6337f3b73cf890def
```

(Short: `b369994`, on branch `optimize_ret_for_llm`, parent: `8a48948`)

## Concerns and Deviations

### Concern 1: `server.py` still has 2 AI-facing `chunk_index:X` occurrences

The grep scan found two AI-facing surfaces in `nbrag/server.py` that still use the deprecated `chunk_index:X` colon-form:

1. **Line 134** — in the `nbrag_search_and_fetch` docstring, listed as an example of returned fields:
   ```
   - chunk_index:X
   ```
   This should be updated to reflect the canonical XML attribute form (e.g., `chunk_index="..."`).

2. **Line 353** — in the `Field(description=...)` for the `chunk_index` parameter of `nbrag_get_adjacent_chunks`:
   ```
   chunk_index: int = Field(description="Target chunk index from a search/search_and_fetch result field like chunk_index + total_chunks or chunk_index:X"),
   ```
   The `chunk_index:X` substring should be removed or replaced with the canonical form.

These do NOT affect the 15-step test script (which tests `mcp_tools.py` function return values, not `server.py` docstrings/Field descriptions), so the test passes 15/15. However, they are AI-facing surfaces that MCP clients and LLM agents can see, so they should be cleaned up in a follow-up.

**Recommendation:** A small follow-up commit to `server.py` to replace the two `chunk_index:X` occurrences with canonical XML attribute form references. This is outside Task 10's scope (Task 10 is verification only), so it's flagged for the final review.

### Deviation from brief: none

The script was implemented exactly as specified in the brief:
- `OPENBLAS_NUM_THREADS=1` set before any nbrag import ✅
- `import my_load_config` before `from nbrag.config import load_config` ✅
- Direct import of all 14 `nbrag_*` functions (not HTTP calls) ✅
- Adaptive: no hardcoded collection_name / query / pattern ✅
- 15 steps matching the brief's table ✅
- No `assert` statements — only `PASS` / `FAIL <reason>` prints ✅
- Final `X/15 passed` summary ✅
- Step 8 tolerant of `not_found` / `no_results` errors ✅
- Step 15 verifies `<error type="invalid_file_path" field="file_path">` ✅
- Handles extracted from step 3 (`<hit>`) and step 7 (`<match>`) and fed into steps 11-14 ✅

### Note: 9109 port MCP server

The 9109 port MCP server was already running (confirmed by the main session via `netstat`). The script does NOT start or connect to the server — it uses direct import of `nbrag.mcp_tools` functions as specified by the brief. The running server confirms that the `mcp_tools` module can be loaded by FastMCP without errors.
