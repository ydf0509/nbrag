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
    nbrag_retrieve_no_expand,
    nbrag_retrieve,
    nbrag_retrieve_only_bm25,
    nbrag_retrieve_only_vector,
    nbrag_grep,
    nbrag_find_definition,
    nbrag_find_files,
    nbrag_list,
    nbrag_read_more_original_text,
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


def _first_tag_fields(text: str, tag: str):
    m = re.search(rf"<{tag}>\n(.*?)\n</{tag}>", text, re.DOTALL)
    if not m:
        return None
    fields = {}
    for line in m.group(1).splitlines():
        if " = " in line:
            key, value = line.split(" = ", 1)
            fields[key] = value
    return fields


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
        out.startswith("<nbrag_stats status=\"success\"")
        and out.rstrip().endswith("</nbrag_stats>")
        and "<nbrag_collection>" in out
    )
    if not ok:
        _record(2, False, "stats XML shape mismatch")
    else:
        coll = None
        for fields in re.findall(r"<nbrag_collection>\n(.*?)\n</nbrag_collection>", out, re.DOTALL):
            values = dict(line.split(" = ", 1) for line in fields.splitlines() if " = " in line)
            name = values.get("collection_name")
            chunks_str = values.get("chunks", "0")
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
        doc_attrs = _first_tag_fields(_list_out, "nbrag_document")
        if doc_attrs:
            _list_file_path = doc_attrs.get("file_path")
            _list_doc_id = doc_attrs.get("doc_id")
            _list_filename = doc_attrs.get("filename")
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
    # Step 3: nbrag_retrieve  (extract 5 handles from first ranked hit)
    # =======================================================================
    try:
        out = nbrag_retrieve(
            query=_query, collection_name=_coll, bm25_query=_bm25_query
        )
        ok = (
            "<nbrag_retrieve" in out
            and "<nbrag_ranked_hit>" in out
            and "<nbrag_original_text_expand>" in out
        )
        if not ok:
            _record(3, False, f"XML shape mismatch; output head: {out[:200]!r}")
        else:
            hit_attrs = _first_tag_fields(out, "nbrag_ranked_hit")
            if not hit_attrs:
                _record(3, False, "no <nbrag_ranked_hit> tag attributes found")
            else:
                S["hit_file_path"] = hit_attrs.get("file_path")
                S["hit_doc_id"] = hit_attrs.get("doc_id")
                S["hit_chunk_index"] = hit_attrs.get("chunk_index")
                S["hit_line_start"] = hit_attrs.get("line_start")
                S["hit_line_end"] = hit_attrs.get("line_end")
                missing = [
                    k for k in ("hit_file_path", "hit_doc_id", "hit_chunk_index",
                                "hit_line_start", "hit_line_end") if S[k] is None
                ]
                _record(3, not missing, "" if not missing else f"missing handles: {missing}")
    except Exception as exc:  # noqa: BLE001
        _record(3, False, f"exception: {exc!r}")

    # =======================================================================
    # Step 4: nbrag_retrieve_no_expand with include_content=False
    # =======================================================================
    try:
        out = nbrag_retrieve_no_expand(
            query=_query, collection_name=_coll,
            include_content=False, bm25_query=_bm25_query,
        )
        ok = (
            "<nbrag_retrieve_no_expand" in out
            and "<nbrag_ranked_hit>" in out
            and "<nbrag_chunk_content>" not in out
        )
        _record(4, ok, "" if ok else f"XML shape mismatch; output head: {out[:200]!r}")
    except Exception as exc:  # noqa: BLE001
        _record(4, False, f"exception: {exc!r}")

    # =======================================================================
    # Step 5: nbrag_retrieve_only_bm25
    # =======================================================================
    try:
        out = nbrag_retrieve_only_bm25(bm25_query=_bm25_query, collection_name=_coll)
        ok = "<nbrag_retrieve_only_bm25" in out
        _record(5, ok, "" if ok else f"XML shape mismatch; output head: {out[:200]!r}")
    except Exception as exc:  # noqa: BLE001
        _record(5, False, f"exception: {exc!r}")

    # =======================================================================
    # Step 6: nbrag_retrieve_only_vector
    # =======================================================================
    try:
        out = nbrag_retrieve_only_vector(query=_query, collection_name=_coll)
        ok = "<nbrag_retrieve_only_vector" in out
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
            and "<nbrag_match>" in out
        )
        if not ok:
            _record(7, False, f"XML shape mismatch; output head: {out[:200]!r}")
        else:
            match_attrs = _first_tag_fields(out, "nbrag_match")
            if not match_attrs:
                _record(7, False, "no <nbrag_match> tag attributes found")
            else:
                S["grep_file_path"] = match_attrs.get("file_path")
                S["grep_doc_id"] = match_attrs.get("doc_id")
                S["grep_line_start"] = match_attrs.get("line_start")
                S["grep_line_end"] = match_attrs.get("line_end")
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
            has_definition = "<nbrag_definition>" in out
            no_results = 'outcome = no_results' in out
            ok = has_definition or no_results
            _record(8, ok, "" if ok else "XML shape mismatch (no <nbrag_definition> or no-results outcome)")
        elif out.startswith("<nbrag_find_definition status=\"error\">"):
            ok = (
                'type = not_found' in out
                or 'type = no_results' in out
                or 'type = missing_collection' in out
                or 'type = empty_collection' in out
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
            and "<nbrag_file>" in out
        )
        if not ok:
            _record(9, False, f"XML shape mismatch; output head: {out[:200]!r}")
        else:
            file_attrs = _first_tag_fields(out, "nbrag_file")
            if not file_attrs:
                _record(9, False, "no <nbrag_file> tag attributes found")
            else:
                has_total = file_attrs.get("total_chunks") is not None
                has_count = file_attrs.get("chunk_count") is not None
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
            and "<nbrag_document>" in out
        )
        if not ok:
            _record(10, False, f"XML shape mismatch; output head: {out[:200]!r}")
        else:
            doc_attrs = _first_tag_fields(out, "nbrag_document")
            if not doc_attrs:
                _record(10, False, "no <nbrag_document> tag attributes found")
            else:
                has_doc_id = doc_attrs.get("doc_id") is not None
                has_file_path = doc_attrs.get("file_path") is not None
                has_total = doc_attrs.get("total_chunks") is not None
                has_count = doc_attrs.get("chunk_count") is not None
                ok = has_doc_id and has_file_path and has_total and not has_count
                _record(10, ok, "" if ok else "<document> must use doc_id/file_path/total_chunks")
    except Exception as exc:  # noqa: BLE001
        _record(10, False, f"exception: {exc!r}")

    # =======================================================================
    # Step 11: nbrag_read_more_original_text  (use file_path from step 3 or 7 or list)
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
            out = nbrag_read_more_original_text(file_path=_raw_file_path, collection_name=_coll)
            ok = "<nbrag_read_more_original_text" in out and "<nbrag_original_text_content>" in out
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
                and "<nbrag_chunk>" in out
            )
            if not ok:
                _record(12, False, f"XML shape mismatch; output head: {out[:200]!r}")
            else:
                chunk_attrs = _first_tag_fields(out, "nbrag_chunk")
                if not chunk_attrs:
                    _record(12, False, "no <nbrag_chunk> tag attributes found")
                else:
                    has_ci = chunk_attrs.get("chunk_index") is not None
                    has_ls = chunk_attrs.get("line_start") is not None
                    has_le = chunk_attrs.get("line_end") is not None
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
                    and "<nbrag_chunk>" in out
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
                    and "<nbrag_chunk>" in out
                )
                _record(14, ok, "" if ok else f"XML shape mismatch; output head: {out[:200]!r}")
    except Exception as exc:  # noqa: BLE001
        _record(14, False, f"exception: {exc!r}")

    # =======================================================================
    # Step 15: nbrag_read_more_original_text with invalid file_path  (must return error XML)
    # =======================================================================
    try:
        out = nbrag_read_more_original_text(file_path="INVALID_PATH", collection_name=_coll)
        ok = '<nbrag_read_more_original_text status="error">' in out and 'type = invalid_file_path' in out and 'field = file_path' in out
        _record(15, ok, "" if ok else f"expected invalid_file_path error; output head: {out[:200]!r}")
    except Exception as exc:  # noqa: BLE001
        _record(15, False, f"exception: {exc!r}")

# ---- summary ---------------------------------------------------------------

print()
print(f"{_passed}/{_TOTAL} passed")
