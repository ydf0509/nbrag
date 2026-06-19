"""MCP 工具实现层：不注册 MCP，只提供可直接测试/调用的函数。"""

from __future__ import annotations

import os
from typing import Any
from nbrag.config import get_config
from nbrag.chunker import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from nbrag import (
    delete_document,
    find_files,
    find_symbol_definition,
    get_context_chunks,
    get_file_chunks,
    get_stats,
    grep_knowledge,
    ingest_path,
    list_documents,
    search,
)


def _load_workflow_skill_text() -> str:
    skill_path = os.path.join(os.path.dirname(__file__), "skills", "nbrag-workflow", "SKILL.md")
    try:
        with open(skill_path, "r", encoding="utf-8") as file_handle:
            return file_handle.read().strip()
    except OSError:
        return ""


def _is_absolute_file_path(path: str) -> bool:
    """Return True only for full absolute file paths."""
    if not path:
        return False
    p = str(path).strip()
    if os.path.isabs(p):
        return True
    return len(p) >= 3 and p[1] == ":" and p[2] in ("/", "\\")


def _str_param(value, default: str = "") -> str:
    """Normalize Field(...) defaults when MCP wrappers are called directly in tests."""
    return value if isinstance(value, str) else default


def _int_param(value, default: int) -> int:
    """Normalize Field(...) defaults when MCP wrappers are called directly in tests."""
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _bool_param(value, default: bool) -> bool:
    """Normalize Field(...) defaults when MCP wrappers are called directly in tests."""
    return value if isinstance(value, bool) else default


def nbrag_add_document(
    path: str,
    collection_name: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    file_extensions: str = "",
) -> str:
    cfg = get_config()
    ext_list = [e.strip() for e in file_extensions.split(",") if e.strip()] if file_extensions else None
    results, errors, skipped_count = ingest_path(
        path, collection_name, chunk_size, chunk_overlap, file_extensions=ext_list
    )

    total_chunks = sum(r["chunks"] for r in results)
    total_chars = sum(r["chars"] for r in results)

    skip_str = f", {skipped_count} skipped" if skipped_count else ""
    lines = [f"Import done: {len(results)} ok, {len(errors)} failed{skip_str}"]
    lines.append(f"collection: {collection_name} | chars: {total_chars} | chunks: {total_chunks}")
    lines.append(f"chunk_size={chunk_size} overlap={chunk_overlap} | embed: {cfg.embedding.model}")

    if len(results) <= 10:
        lines.append("")
        for r in results:
            lines.append(f"  {r['filename']} ({r['chunks']} chunks, {r['chars']} chars, doc_id:{r['doc_id']})")
    else:
        lines.append(f"\n{len(results)} files imported (too many to list)")

    if errors:
        lines.append(f"\nFailed ({len(errors)}):")
        for e in errors[:10]:
            lines.append(f"  {e}")

    return "\n".join(lines)


def nbrag_help() -> str:
    skill_text = _load_workflow_skill_text()
    parts = [
        "nbrag help: Agentic RAG knowledge-base MCP workflow",
        "",
        "Capability model:",
        "- nbrag is not a plain file search tool; it is an Agentic RAG retrieval toolkit for prepared knowledge bases (知识库 = collection).",
        "- It combines semantic vector search, multi-channel BM25 lexical search, Weighted RRF fusion, rerank, raw original-file evidence reading, and Python AST symbol lookup.",
        "- Use it as a workflow: discover relevant evidence → pinpoint exact terms/symbols → fetch original content → expand context.",
        "",
        "Important:",
        "- Use the actual exposed tool/function name you received from the host, not just the bare nbrag_* name.",
        "- Tool names may be prefixed in other agent frameworks, for example xxx_nbrag_search or mcp__xxx__nbrag_search.",
        "",
        "Common guidance:",
        "- Unknown collection_name? call nbrag_stats.",
        "- Knowledge/docs/law/manual/usage question? usually start with nbrag_search_and_fetch.",
        "- Exact law articles, document headings, terms, phrases, API names, or constants? use nbrag_grep.",
        "  ⚠️ grep does byte-for-byte literal matching — '空城计' will NOT match if the file says '焚香操琴' instead.",
        "  When unsure about exact wording, prefer nbrag_search_and_fetch (semantic search).",
        "- Python source symbol body? use nbrag_find_definition (Python-only special case).",
        "- Only have filename/path fragment? use nbrag_find_files to get full absolute file_path.",
        "- Need more context? use nbrag_get_raw_file, nbrag_get_adjacent_chunks, or nbrag_get_chunks_by_lines.",
        "",
        "Python source workflow:",
        "- Use nbrag_search_and_fetch for concepts/examples; .py chunks include AST scope/signature metadata.",
        "- Use nbrag_grep for exact names/imports/constants/decorators/error strings.",
        "- Use nbrag_find_definition for complete Python .py symbols, then nbrag_get_raw_file for full source context.",
        "",
        "Rules:",
        "- Rewrite long user questions into short natural-language search queries; do not mechanically split them into space-separated keywords.",
        "- file_path and filter_file_path must be full absolute paths returned by nbrag tools.",
        "- Collections are prepared by the user. If missing or empty, ask for the correct prepared collection_name.",
    ]
    if skill_text:
        parts.extend(["", "Embedded nbrag workflow guide:", skill_text])
    return "\n".join(parts)


def nbrag_search(
    query: str,
    collection_name: str,
    top_k: int = 5,
    use_rerank: bool = True,
    use_bm25: bool = True,
    filter_file_path: str = "",
    include_content: bool = True,
    preview_chars: int = -1,
) -> str:
    cfg = get_config()
    top_k = _int_param(top_k, 5)
    use_rerank = _bool_param(use_rerank, True)
    use_bm25 = _bool_param(use_bm25, True)
    filter_file_path = _str_param(filter_file_path)
    include_content = _bool_param(include_content, True)
    preview_chars = _int_param(preview_chars, -1)
    path_filter = filter_file_path if filter_file_path else None
    if path_filter and not _is_absolute_file_path(path_filter):
        return "Error: filter_file_path must be a full absolute file_path returned by nbrag_search/nbrag_search_and_fetch/nbrag_find_files/nbrag_list."

    documents, metadatas, distances, rerank_used, total, rerank_scores = search(
        query, collection_name, top_k, use_rerank,
        use_bm25=use_bm25,
        filter_file_path=path_filter,
    )

    if total == 0:
        stats = get_stats()
        avail = list(stats["collections"].keys())
        exists = collection_name in avail
        if not exists:
            return (f"collection '{collection_name}' does not exist.\n"
                    f"Available collections: {avail}\n"
                    f"Ask the user for the correct prepared collection_name.")
        return (f"collection '{collection_name}' is empty. "
                f"Ask the user to prepare this knowledge base before searching.")

    if not documents:
        return (f"No results (collection has {total} chunks, filter_file_path: {filter_file_path or 'none'}).\n"
                "Possible adjustments: rewrite the query as a focused short phrase, use nbrag_grep for exact terms/article numbers/symbols, "
                "or call nbrag_stats if collection_name may be wrong.")

    rerank_str = cfg.rerank.model if rerank_used else "off"
    bm25_str = "on" if (use_bm25 and not path_filter) else "off"
    header = f"[{collection_name}] {total} chunks | hybrid(bm25+vector): {bm25_str} | rerank: {rerank_str}"
    if filter_file_path:
        header += f" | filter_file_path: {filter_file_path}"
    lines = [header, ""]

    if preview_chars > 0:
        preview_limit = preview_chars
    else:
        preview_limit = min(8000, 40000 // max(len(documents), 1))
    show_content = include_content and preview_chars != 0
    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
        if meta is None:
            meta = {}
        src = meta.get("source", meta.get("filename", "?"))
        ci = meta.get("chunk_index", "?")
        tc = meta.get("total_chunks", "?")
        ls = meta.get("line_start", 0)
        le = meta.get("line_end", 0)
        scope = meta.get("scope", "")
        doc_id = meta.get("doc_id", "?")

        meta_parts = [f"chunk:{ci}/{tc}"]
        if ls and le:
            meta_parts.append(f"line:{ls}-{le}")
        if scope:
            meta_parts.append(f"scope:{scope}")
        meta_parts.append(f"doc_id:{doc_id}")
        meta_parts.append(f"dist:{dist:.4f}")
        if rerank_scores and i < len(rerank_scores):
            meta_parts.append(f"score:{rerank_scores[i]:.4f}")

        lines.append(f"[{i + 1}/{len(documents)}] {meta.get('filename', '?')} {' '.join(meta_parts)}")
        lines.append(f"file_path: {src}")
        if show_content:
            preview = doc[:preview_limit] + ("..." if len(doc) > preview_limit else "")
            lines.append(preview)
        else:
            lines.append("(content omitted; use include_content=True or nbrag_get_raw_file for original content)")
        lines.append("")

    return "\n".join(lines)


def nbrag_search_and_fetch(
    query: str,
    collection_name: str,
    top_k: int = 5,
    fetch_top_n_raw: int = 3,
    context_lines: int = 100,
    filter_file_path: str = "",
) -> str:
    cfg = get_config()
    top_k = _int_param(top_k, 5)
    fetch_top_n_raw = _int_param(fetch_top_n_raw, 3)
    context_lines = max(0, _int_param(context_lines, 100))
    filter_file_path = _str_param(filter_file_path)
    path_filter = filter_file_path if filter_file_path else None
    if path_filter and not _is_absolute_file_path(path_filter):
        return "Error: filter_file_path must be a full absolute file_path returned by nbrag_search/nbrag_search_and_fetch/nbrag_find_files/nbrag_list."

    documents, metadatas, distances, rerank_used, total, rerank_scores = search(
        query, collection_name, top_k, True, use_bm25=True, filter_file_path=path_filter,
    )

    if total == 0:
        stats = get_stats()
        avail = list(stats["collections"].keys())
        exists = collection_name in avail
        if not exists:
            return (f"collection '{collection_name}' does not exist.\n"
                    f"Available collections: {avail}\n"
                    f"Ask the user for the correct prepared collection_name.")
        return (f"collection '{collection_name}' is empty. "
                f"Ask the user to prepare this knowledge base before searching.")

    if not documents:
        return (f"No results (collection has {total} chunks).\n"
                "Possible adjustments: rewrite the query as a focused short phrase, use nbrag_grep for exact terms/article numbers/symbols, "
                "or call nbrag_stats if collection_name may be wrong.")

    rerank_str = cfg.rerank.model if rerank_used else "off"
    bm25_str = "off" if path_filter else "on"
    header = f"[{collection_name}] {total} chunks | hybrid(bm25+vector): {bm25_str} | rerank: {rerank_str}"
    if filter_file_path:
        header += f" | filter_file_path: {filter_file_path}"
    lines = [header, ""]

    preview_limit = min(8000, 40000 // max(len(documents), 1))
    fetch_targets: dict[str, dict[str, Any]] = {}
    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
        if meta is None:
            meta = {}
        src = meta.get("source", meta.get("filename", "?"))
        ci = meta.get("chunk_index", "?")
        tc = meta.get("total_chunks", "?")
        _ls = meta.get("line_start", 0)
        _le = meta.get("line_end", 0)
        ls = int(_ls) if isinstance(_ls, (int, float)) else 0
        le = int(_le) if isinstance(_le, (int, float)) else 0
        scope = str(meta.get("scope", ""))
        doc_id = str(meta.get("doc_id", "?"))

        meta_parts = [f"chunk:{ci}/{tc}"]
        if ls and le:
            meta_parts.append(f"line:{ls}-{le}")
        if scope:
            meta_parts.append(f"scope:{scope}")
        meta_parts.append(f"doc_id:{doc_id}")
        meta_parts.append(f"dist:{dist:.4f}")
        if rerank_scores and i < len(rerank_scores):
            meta_parts.append(f"score:{rerank_scores[i]:.4f}")

        lines.append(f"[{i + 1}/{len(documents)}] {meta.get('filename', '?')} {' '.join(meta_parts)}")
        lines.append(f"file_path: {src}")
        preview = doc[:preview_limit] + ("..." if len(doc) > preview_limit else "")
        lines.append(preview)
        lines.append("")

        if i < fetch_top_n_raw and doc_id != "?" and src != "?":
            if doc_id not in fetch_targets:
                fetch_targets[doc_id] = {"src": str(src), "ranges": []}
            fetch_targets[doc_id]["ranges"].append((ls, le))

    if fetch_targets:
        lines.append("=" * 40)
        lines.append(f"Auto-fetched original content ({len(fetch_targets)} file(s)):")
        lines.append("")

    for doc_id, target in fetch_targets.items():
        raw_result = get_file_chunks(
            target["src"], collection_name, 0, 0,
            raw=True, line_start=-1, line_end=-1,
        )

        if not raw_result.get("found"):
            lines.append(f"[{target['src']}] {raw_result.get('error', 'raw content unavailable')}")
            lines.append("")
            continue

        tl = raw_result["total_lines"]
        if tl <= context_lines * 2:
            lines.append(_format_raw_result(raw_result))
        else:
            windows = []
            for ls, le in target.get("ranges", []):
                start_line = ls or le or 1
                end_line = le or start_line
                if end_line < start_line:
                    start_line, end_line = end_line, start_line
                fetch_start = max(1, start_line - context_lines)
                fetch_end = min(tl, end_line + context_lines)

                for window in windows:
                    if fetch_start <= window["end"] + 1 and fetch_end >= window["start"] - 1:
                        window["start"] = min(window["start"], fetch_start)
                        window["end"] = max(window["end"], fetch_end)
                        break
                else:
                    windows.append({"start": fetch_start, "end": fetch_end})

            if not windows:
                windows.append({"start": 1, "end": min(tl, 1 + context_lines * 2)})

            for window in windows:
                excerpt = get_file_chunks(
                    target["src"], collection_name, 0, 0,
                    raw=True, line_start=window["start"], line_end=window["end"],
                )
                if excerpt.get("found"):
                    lines.append(_format_raw_result(excerpt))
                else:
                    lines.append(f"[{target['src']}] excerpt failed")
                lines.append("")

    return "\n".join(lines)


def nbrag_grep(
    keyword: str,
    collection_name: str,
    max_results: int = 10,
    case_sensitive: bool = False,
    filter_file_path: str = "",
    context_lines: int = 10,
) -> str:
    max_results = _int_param(max_results, 10)
    case_sensitive = _bool_param(case_sensitive, False)
    filter_file_path = _str_param(filter_file_path)
    context_lines = _int_param(context_lines, 10)
    path_filter = filter_file_path if filter_file_path else None
    if path_filter and not _is_absolute_file_path(path_filter):
        return "Error: filter_file_path must be a full absolute file_path returned by nbrag_search/nbrag_search_and_fetch/nbrag_find_files/nbrag_list."
    results = grep_knowledge(
        keyword, collection_name, max_results, case_sensitive,
        filter_file_path=path_filter, context_lines=context_lines,
    )

    if not results:
        return (f"No matches for '{keyword}' (collection: {collection_name}).\n"
                "Possible adjustments: use a simpler exact term, check spelling/article number, remove regex anchors, "
                "or switch to nbrag_search_and_fetch for semantic discovery.")

    lines = [f"grep: '{keyword}' | collection_name: {collection_name} | {len(results)} match(es)", ""]
    for i, r in enumerate(results):
        matched_line = r["line_number"]
        lines.append(f"[{i + 1}/{len(results)}] {r['filename']} line:{matched_line} doc_id:{r['doc_id']}")
        lines.append(f"file_path: {r['source']}")
        lines.append(f"matched_line: {matched_line}")
        lines.append(f"line_range: line:{matched_line}-{matched_line}")
        lines.append(r["context"])
        lines.append("")

    return "\n".join(lines)


def nbrag_find_definition(symbol: str, collection_name: str, max_results: int = 3) -> str:
    max_results = _int_param(max_results, 3)
    results = find_symbol_definition(symbol, collection_name, max_results)

    if not results:
        return (f"No definition found for '{symbol}' (collection: {collection_name}).\n"
                "Next steps: use nbrag_grep to discover the exact Python symbol spelling, or use "
                "nbrag_search_and_fetch for concept/example discovery. Non-Python text should use nbrag_grep.")

    has_python_result = any(str(r.get("source", "")).lower().endswith(".py") for r in results)
    has_non_python_result = any(not str(r.get("source", "")).lower().endswith(".py") for r in results)

    lines = [f"definition: '{symbol}' | collection_name: {collection_name} | {len(results)} found"]
    if has_non_python_result and not has_python_result:
        lines.append("Note: non-Python regex fallback result. For law/docs/manuals, use nbrag_grep for exact text search.")
    lines.append("")
    for i, r in enumerate(results):
        header_parts = [
            f"[{i + 1}/{len(results)}]",
            f"{r['symbol_type']}",
            f"{r['qualified_name']}",
            f"line:{r['line_start']}-{r['line_end']}",
            f"doc_id:{r['doc_id']}",
        ]
        lines.append(" ".join(header_parts))
        lines.append(f"file_path: {r['source']}")
        if not str(r.get("source", "")).lower().endswith(".py"):
            lines.append("Regex fallback in non-Python file")
        if r.get("methods_summary"):
            lines.append("methods:")
            lines.append(r["methods_summary"])
        lines.append(r["definition"])
        lines.append("")

    return "\n".join(lines)


def nbrag_find_files(pattern: str, collection_name: str, max_results: int = 20, case_sensitive: bool = False) -> str:
    max_results = _int_param(max_results, 20)
    case_sensitive = _bool_param(case_sensitive, False)
    results = find_files(pattern, collection_name, max_results, case_sensitive)

    if not results:
        return (f"No files matched '{pattern}' (collection: {collection_name}).\n"
                "Next steps: try a shorter filename/path fragment, remove directory prefixes, or use nbrag_list to inspect available documents.")

    lines = [f"files: '{pattern}' | collection_name: {collection_name} | {len(results)} match(es)",
             "Returned file_path values can be copied into file_path/filter_file_path parameters.", ""]
    for i, r in enumerate(results):
        lines.append(f"[{i + 1}/{len(results)}] {r['filename']}")
        lines.append(f"file_path: {r['source']}")
        lines.append(f"doc_id: {r['doc_id']} | total_chunks: {r['total_chunks']} | chunk_count: {r['chunk_count']}")
        lines.append("")
    return "\n".join(lines)


def _format_raw_result(raw_result: dict[str, Any]) -> str:
    lines = [
        f"original_file: {raw_result['filename']}",
        f"file_path: {raw_result['source']}",
        f"doc_id: {raw_result['doc_id']} | total_chunks: {raw_result['total_chunks']} | total_lines: {raw_result['total_lines']}",
    ]
    if raw_result.get("line_range"):
        lines.append(f"range: {raw_result['line_range']}")
    elif raw_result.get("line_start") and raw_result.get("line_end"):
        lines.append(f"range: line:{raw_result['line_start']}-{raw_result['line_end']}")
    lines.append(raw_result.get("content", ""))
    return "\n".join(lines)


def nbrag_get_raw_file(
    file_path: str,
    collection_name: str,
    line_start: int = -1,
    line_end: int = -1,
) -> str:
    file_path = _str_param(file_path)
    collection_name = _str_param(collection_name)
    line_start = _int_param(line_start, -1)
    line_end = _int_param(line_end, -1)

    if not _is_absolute_file_path(file_path):
        return "Error: file_path must be a full absolute file_path returned by nbrag_search/nbrag_find_files/nbrag_list."

    raw_result = get_file_chunks(
        file_path,
        collection_name,
        0,
        0,
        raw=True,
        line_start=line_start,
        line_end=line_end,
    )
    if not raw_result.get("found"):
        return raw_result.get("error", f"File not found: {file_path}")
    return _format_raw_result(raw_result)


def nbrag_get_adjacent_chunks(doc_id: str, chunk_index: int, collection_name: str, window: int = 3) -> str:
    doc_id = _str_param(doc_id)
    chunk_index = _int_param(chunk_index, 0)
    window = _int_param(window, 3)
    result = get_context_chunks(doc_id, collection_name=collection_name, chunk_index=chunk_index, window=window)
    if not result.get("found"):
        return (f"No adjacent chunks found for doc_id={doc_id}, chunk_index={chunk_index}.\n"
                "Next steps: confirm doc_id/chunk_index from nbrag_search output, or use nbrag_get_file_chunks for a broader file view.")
    results = result.get("chunks", [])
    if not results:
        return (f"No adjacent chunks found for doc_id={doc_id}, chunk_index={chunk_index}.\n"
                "Next steps: confirm doc_id/chunk_index from nbrag_search output, or use nbrag_get_file_chunks for a broader file view.")

    lines = [f"adjacent chunks | doc_id:{doc_id} | around chunk_index:{chunk_index} | {len(results)} chunk(s)",
             "If you still need broader context, call nbrag_get_raw_file or nbrag_get_file_chunks.", ""]
    for i, r in enumerate(results):
        ci = r.get("index", "?")
        tc = result.get("total_chunks", "?")
        src = result.get("source", "?")
        ls = r.get("line_start", 0)
        le = r.get("line_end", 0)
        header = f"[{i + 1}/{len(results)}] chunk:{ci}/{tc} file_path: {src}"
        if ls and le:
            header += f" line:{ls}-{le}"
        lines.append(header)
        lines.append(r.get("content", ""))
        lines.append("")
    return "\n".join(lines)


def nbrag_get_chunks_by_lines(
    doc_id: str,
    line_start: int,
    line_end: int,
    collection_name: str,
) -> str:
    doc_id = _str_param(doc_id)
    line_start = _int_param(line_start, 1)
    line_end = _int_param(line_end, 1)
    result = get_context_chunks(doc_id, collection_name=collection_name, line_start=line_start, line_end=line_end)
    if not result.get("found"):
        return (f"No chunks overlap line range {line_start}-{line_end} for doc_id={doc_id}.\n"
                "Next steps: confirm doc_id and line numbers from search/raw-file output, or use nbrag_get_raw_file for exact line slices.")
    results = result.get("chunks", [])
    if not results:
        return (f"No chunks overlap line range {line_start}-{line_end} for doc_id={doc_id}.\n"
                "Next steps: confirm doc_id and line numbers from search/raw-file output, or use nbrag_get_raw_file for exact line slices.")

    lines = [f"chunks by lines | doc_id:{doc_id} | line_range:{line_start}-{line_end} | {len(results)} chunk(s)",
             "Use nbrag_get_adjacent_chunks if you need nearby chunk context too.", ""]
    for i, r in enumerate(results):
        ci = r.get("index", "?")
        tc = result.get("total_chunks", "?")
        ls = r.get("line_start", 0)
        le = r.get("line_end", 0)
        src = result.get("source", "?")
        lines.append(f"[{i + 1}/{len(results)}] chunk:{ci}/{tc} line:{ls}-{le} file_path: {src}")
        lines.append(r.get("content", ""))
        lines.append("")
    return "\n".join(lines)


def nbrag_get_file_chunks(
    file_path: str,
    collection_name: str,
    start_chunk: int = 0,
    max_chunks: int = 10,
) -> str:
    file_path = _str_param(file_path)
    collection_name = _str_param(collection_name)
    start_chunk = _int_param(start_chunk, 0)
    max_chunks = _int_param(max_chunks, 10)
    if not _is_absolute_file_path(file_path):
        return "Error: file_path must be a full absolute file_path returned by nbrag_search/nbrag_find_files/nbrag_list."

    result = get_file_chunks(file_path, collection_name, start_chunk, max_chunks)
    if not result.get("found"):
        return result.get("error", f"File not found: {file_path}")

    lines = [
        f"file chunks | {result['filename']} | file_path: {result['source']}",
        f"doc_id: {result['doc_id']} | total_chunks: {result['total_chunks']} | returned: {len(result['chunks'])}",
        "Use returned doc_id/chunk_index with nbrag_get_adjacent_chunks, or use nbrag_get_raw_file for original content.",
        "",
    ]

    for i, chunk in enumerate(result["chunks"]):
        meta = chunk.get("metadata", {}) or {}
        ci = meta.get("chunk_index", "?")
        tc = meta.get("total_chunks", "?")
        ls = meta.get("line_start", 0)
        le = meta.get("line_end", 0)
        scope = meta.get("scope", "")
        header = [f"[{i + 1}/{len(result['chunks'])}] chunk:{ci}/{tc}"]
        if ls and le:
            header.append(f"line:{ls}-{le}")
        if scope:
            header.append(f"scope:{scope}")
        lines.append(" ".join(header))
        lines.append(chunk.get("content", ""))
        lines.append("")

    return "\n".join(lines)


def nbrag_delete_document(doc_id: str, collection_name: str) -> str:
    doc_id = _str_param(doc_id)
    collection_name = _str_param(collection_name)
    deleted_count, filename = delete_document(doc_id, collection_name)
    if deleted_count == 0:
        return (f"No document found for doc_id={doc_id} in collection '{collection_name}'.\n"
                "Use nbrag_list or search output to get the exact doc_id first.")
    return f"Deleted {deleted_count} chunks for {filename} (doc_id:{doc_id}) from collection '{collection_name}'."


def nbrag_list(collection_name: str, offset: int = 0, limit: int = 200) -> str:
    collection_name = _str_param(collection_name)
    offset = _int_param(offset, 0)
    limit = _int_param(limit, 200)
    docs = list_documents(collection_name, offset=offset, limit=limit)

    if not docs:
        stats = get_stats()
        avail = list(stats["collections"].keys())
        if collection_name not in avail:
            return (f"collection '{collection_name}' does not exist.\n"
                    f"Available collections: {avail}\n"
                    f"Ask the user for the correct prepared collection_name.")
        return (f"collection '{collection_name}' is empty.\n"
                "Ask the user to prepare/import documents into this knowledge base first.")

    lines = [f"documents in collection '{collection_name}' (offset={offset}, limit={limit}, returned={len(docs)})",
             "Use the returned file_path in file_path/filter_file_path parameters.", ""]
    for i, (doc_id, info) in enumerate(docs.items()):
        lines.append(f"[{i + 1}/{len(docs)}] {info['filename']}")
        lines.append(f"file_path: {info['source']}")
        lines.append(f"doc_id: {doc_id} | total_chunks: {info['total_chunks']} | chunk_count: {info['chunk_count']}")
        lines.append("")
    return "\n".join(lines)


def nbrag_stats() -> str:
    stats = get_stats()
    if not stats["collections"]:
        return ("No collections found.\n"
                "Capabilities: semantic vector search + multi-channel BM25 + Weighted RRF + rerank + raw original-file evidence + Python AST symbol lookup.\n"
                "Ask the user to prepare/import a knowledge base first, then call nbrag_stats again.")

    lines = [
        f"Data dir: {stats['data_dir']}",
        "Capabilities: semantic vector search + multi-channel BM25 + Weighted RRF + rerank + raw original-file evidence + Python AST symbol lookup.",
        f"Total collections: {len(stats['collections'])}",
        "Use one of the collection names below as collection_name in other nbrag tools.",
        "",
    ]
    for name, info in stats["collections"].items():
        label = name
        if info.get("display_name"):
            label += f" ({info['display_name']})"
        lines.append(f"- {label}: doc_count: {info.get('doc_count', '?')} | chunk_count: {info['chunk_count']}")
        if info.get("description"):
            lines.append(f"  description: {info['description']}")
        if info.get("aliases"):
            lines.append(f"  aliases: {', '.join(info['aliases'])}")
        if info.get("tags"):
            lines.append(f"  tags: {', '.join(info['tags'])}")
    return "\n".join(lines)
