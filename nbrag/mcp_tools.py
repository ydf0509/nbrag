"""MCP 工具实现层：不注册 MCP，只提供可直接测试/调用的函数。"""

from __future__ import annotations

import bisect
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


def _build_line_char_index(content: str) -> tuple[list[str], list[int]]:
    """Return raw lines (with line endings) and cumulative char offsets."""
    lines = content.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    return lines, offsets


def _line_window_from_chars(lines: list[str], offsets: list[int], line_start: int, line_end: int, fetch_chars: int) -> tuple[int, int]:
    """Expand around the matched line range using an approximate symmetric char budget."""
    total_lines = len(lines)
    if total_lines == 0:
        return 1, 1

    if line_start <= 0 or line_end <= 0:
        return 1, total_lines

    hit_start = max(1, min(total_lines, line_start))
    hit_end = max(hit_start, min(total_lines, line_end))
    if fetch_chars <= 0:
        return hit_start, hit_end

    hit_char_start = offsets[hit_start - 1]
    hit_char_end = offsets[hit_end]
    hit_len = hit_char_end - hit_char_start
    if hit_len >= fetch_chars:
        return hit_start, hit_end

    extra = fetch_chars - hit_len
    extra_before = extra // 2
    extra_after = extra - extra_before
    win_char_start = max(0, hit_char_start - extra_before)
    win_char_end = min(offsets[-1], hit_char_end + extra_after)

    window_start = max(1, min(total_lines, bisect.bisect_right(offsets, win_char_start)))
    window_end = max(window_start, min(total_lines, bisect.bisect_left(offsets, win_char_end)))
    return window_start, window_end


def _merge_line_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping or adjacent inclusive line ranges."""
    merged = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


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
        "Common guidance:",
        "- Unknown collection_name? call nbrag_stats.",
        "- Most knowledge / usage / evidence questions: usually start with nbrag_search_and_fetch.",
        "- Need retrieval controls or strategy isolation: use nbrag_search / nbrag_search_only_bm25 / nbrag_search_only_vector.",
        "- Exact wording / article number / API name / constant: use nbrag_grep.",
        "- Python .py exact symbol body: use nbrag_find_definition.",
        "- Need exact full file_path first: use nbrag_find_files.",
        "",
        "Path rules:",
        "- file_path and filter_file_path must be full absolute paths returned by nbrag tools.",
        "- Use the actual exposed tool name from the host; other frameworks may add prefixes.",
        "",
        "See the embedded workflow guide below for detailed strategy selection, multi-round retrieval, and follow-up patterns.",
    ]
    if skill_text:
        parts.extend(["", "Embedded nbrag workflow guide:", skill_text])
    return "\n".join(parts)


def _format_search_results(
    query: str,
    collection_name: str,
    top_k: int = 5,
    use_rerank: bool = True,
    use_bm25: bool = True,
    use_vector: bool = True,
    filter_file_path: str = "",
    include_content: bool = True,
    preview_chars: int = -1,
) -> str:
    cfg = get_config()
    top_k = _int_param(top_k, 5)
    use_rerank = _bool_param(use_rerank, True)
    use_bm25 = _bool_param(use_bm25, True)
    use_vector = _bool_param(use_vector, True)
    filter_file_path = _str_param(filter_file_path)
    include_content = _bool_param(include_content, True)
    preview_chars = _int_param(preview_chars, -1)
    path_filter = filter_file_path if filter_file_path else None
    if path_filter and not _is_absolute_file_path(path_filter):
        return "Error: filter_file_path must be a full absolute file_path returned by nbrag_search/nbrag_search_and_fetch/nbrag_find_files/nbrag_list."

    documents, metadatas, distances, rerank_used, total, rerank_scores = search(
        query, collection_name, top_k, use_rerank, use_bm25,
        filter_file_path=path_filter, use_vector=use_vector,
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
    bm25_str = "off" if path_filter and use_vector else ("on" if use_bm25 else "off")
    lines = [f"[{collection_name}] {total} chunks | bm25: {bm25_str} | rerank: {rerank_str}", ""]

    auto_limit = min(2000, 24000 // max(len(documents), 1))
    if preview_chars < 0:
        preview_limit = auto_limit
    else:
        preview_limit = max(0, preview_chars)

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

        if include_content and preview_limit != 0:
            preview = doc[:preview_limit] + ("..." if len(doc) > preview_limit else "")
            lines.append(preview)
        elif not include_content:
            lines.append("content omitted")
        lines.append("")

    return "\n".join(lines)


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
    return _format_search_results(
        query=query,
        collection_name=collection_name,
        top_k=top_k,
        use_rerank=use_rerank,
        use_bm25=use_bm25,
        use_vector=True,
        filter_file_path=filter_file_path,
        include_content=include_content,
        preview_chars=preview_chars,
    )


def nbrag_search_only_bm25(
    query: str,
    collection_name: str,
    top_k: int = 5,
    filter_file_path: str = "",
    include_content: bool = True,
    preview_chars: int = -1,
) -> str:
    return _format_search_results(
        query=query,
        collection_name=collection_name,
        top_k=top_k,
        use_rerank=False,
        use_bm25=True,
        use_vector=False,
        filter_file_path=filter_file_path,
        include_content=include_content,
        preview_chars=preview_chars,
    )


def nbrag_search_only_vector(
    query: str,
    collection_name: str,
    top_k: int = 5,
    filter_file_path: str = "",
    include_content: bool = True,
    preview_chars: int = -1,
) -> str:
    return nbrag_search(
        query=query,
        collection_name=collection_name,
        top_k=top_k,
        use_rerank=False,
        use_bm25=False,
        filter_file_path=filter_file_path,
        include_content=include_content,
        preview_chars=preview_chars,
    )


def nbrag_search_and_fetch(
    query: str,
    collection_name: str,
    top_k: int = 5,
    fetch_top_n_raw: int = 3,
    fetch_chars: int = 4000,
    filter_file_path: str = "",
) -> str:
    cfg = get_config()
    top_k = _int_param(top_k, 5)
    fetch_top_n_raw = _int_param(fetch_top_n_raw, 3)
    fetch_chars = max(0, _int_param(fetch_chars, 4000))
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
    header = f"[{collection_name}] {total} chunks | bm25: {bm25_str} | rerank: {rerank_str}"
    if filter_file_path:
        header += f" | filter_file_path: {filter_file_path}"
    lines = [header, "", "Ranked search results:", ""]

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

        meta_parts = [f"chunk:{ci}/{tc}", f"chunk_index:{ci}", f"total_chunks:{tc}"]
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

    if fetch_top_n_raw > 0 and fetch_targets:
        lines.append(f"Auto-fetched original content ({len(fetch_targets)} file(s)):")
        lines.append("")
        for doc_id, info in fetch_targets.items():
            src = str(info["src"])
            ranges = info["ranges"]
            if not ranges:
                continue

            raw_data = get_file_chunks(src, collection_name, 0, 0, raw=True)
            if not raw_data.get("found"):
                continue

            filename = os.path.basename(src)
            raw_content = str(raw_data.get("content", ""))
            raw_lines, offsets = _build_line_char_index(raw_content)
            expanded_ranges = [
                _line_window_from_chars(raw_lines, offsets, ls, le, fetch_chars)
                for ls, le in ranges
            ]
            merged_ranges = _merge_line_ranges(expanded_ranges)

            for start, end in merged_ranges:
                excerpt = "".join(raw_lines[start - 1:end]) if raw_lines else raw_content
                lines.append(f"original_file: {filename} | file_path: {src} | doc_id: {doc_id} | range: line:{start}-{end}")
                lines.append(excerpt)
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
        keyword,
        collection_name,
        max_results,
        case_sensitive,
        filter_file_path=path_filter,
        context_lines=context_lines,
    )
    if not results:
        return ("No grep matches. Possible adjustments: check exact wording/case, try regex if appropriate, "
                "or switch to nbrag_search_and_fetch for semantic discovery if this is a concept, alias, or paraphrase rather than exact source wording.")

    lines = [f"grep matches: {len(results)}", ""]
    for item in results:
        line_number = item.get("line_number", "?")
        lines.append(f"{item.get('filename', '?')} | matched_line: {line_number} | line_range: line:{line_number}-{line_number} | doc_id: {item.get('doc_id', '?')}")
        lines.append(f"file_path: {item.get('source', '?')}")
        lines.append(str(item.get("context", "")))
        lines.append("")
    return "\n".join(lines)


def nbrag_find_definition(
    symbol: str,
    collection_name: str,
    max_results: int = 3,
) -> str:
    max_results = _int_param(max_results, 3)
    results = find_symbol_definition(symbol, collection_name, max_results)
    if not results:
        return ("No definition found. Python source may use a different exact name, or this knowledge base may be non-Python text. "
                "Try nbrag_grep for exact text/regex, or nbrag_search_and_fetch for concept/example discovery. For law/docs/manuals, use nbrag_grep.")

    python_symbol_types = {"class", "function", "method"}
    has_python_definition = any(str(r.get("symbol_type", "")).lower() in python_symbol_types for r in results)
    has_non_python_fallback = any(str(r.get("symbol_type", "")).lower() not in python_symbol_types for r in results)

    lines = [f"definitions: {len(results)}", ""]
    if has_non_python_fallback and not has_python_definition:
        lines.append("For law/docs/manuals, use nbrag_grep for exact text / article lookup.")
        lines.append("")

    for index, r in enumerate(results, 1):
        symbol_type = str(r.get("symbol_type", "unknown"))
        qualified_name = r.get("qualified_name") or symbol
        source = r.get("source", "?")
        line_start = r.get("line_start", "?")
        line_end = r.get("line_end", "?")
        doc_id = r.get("doc_id", "?")
        definition = r.get("definition") or r.get("content", "")
        methods_summary = r.get("methods_summary", "")
        filename = os.path.basename(str(source)) if source not in (None, "") else "?"

        display_symbol_type = symbol_type if symbol_type.lower() in python_symbol_types else "regex_fallback"
        lines.append(f"[{index}/{len(results)}] {display_symbol_type} {qualified_name} | line:{line_start}-{line_end} | doc_id:{doc_id}")
        lines.append(f"file_path: {source}")
        if symbol_type.lower() not in python_symbol_types:
            lines.append("Regex fallback in non-Python file")
        if methods_summary:
            lines.append(str(methods_summary))
        lines.append(str(definition))
        lines.append("")
    return "\n".join(lines)


def nbrag_find_files(pattern: str, collection_name: str, max_results: int = 20, case_sensitive: bool = False) -> str:
    max_results = _int_param(max_results, 20)
    case_sensitive = _bool_param(case_sensitive, False)
    files = find_files(pattern, collection_name, max_results, case_sensitive)
    if not files:
        return ("No files matched. Try a shorter filename fragment, a different suffix, or first use nbrag_search_and_fetch/nbrag_grep to discover candidate files.")

    lines = [f"matched files: {len(files)}", ""]
    for item in files:
        chunk_count = item.get("chunk_count", item.get("total_chunks", "?"))
        total_chunks = item.get("total_chunks", chunk_count)
        match = item.get("match", "?")
        lines.append(
            f"filename: {item.get('filename', '?')} | doc_id: {item.get('doc_id', '?')} | "
            f"chunk_count: {chunk_count} | total_chunks: {total_chunks} | match: {match}"
        )
        lines.append(f"file_path: {item.get('source', item.get('file_path', '?'))}")
        lines.append("")
    return "\n".join(lines)


def nbrag_get_adjacent_chunks(doc_id: str, chunk_index: int, collection_name: str, window: int = 2) -> str:
    chunk_index = _int_param(chunk_index, 0)
    window = _int_param(window, 2)
    data = get_context_chunks(doc_id, collection_name=collection_name, chunk_index=chunk_index, window=window)
    if not data.get("found"):
        detail = data.get("error") or data.get("message") or ""
        suffix = f" Detail: {detail}" if detail else ""
        return f"No adjacent chunks found. Check doc_id/chunk_index from search results.{suffix}"

    chunks = data.get("chunks", [])
    lines = [f"adjacent chunks: {len(chunks)} | file_path: {data.get('source', '?')} | doc_id: {doc_id} | total_chunks: {data.get('total_chunks', '?')}", ""]
    for chunk in chunks:
        lines.append(f"chunk:{chunk.get('index', '?')} | line:{chunk.get('line_start', '?')}-{chunk.get('line_end', '?')}")
        lines.append(str(chunk.get("content", "")))
        lines.append("")
    return "\n".join(lines)


def nbrag_get_file_chunks(file_path: str, collection_name: str, start_chunk: int = 0, max_chunks: int = 10) -> str:
    start_chunk = _int_param(start_chunk, 0)
    max_chunks = _int_param(max_chunks, 10)
    if not _is_absolute_file_path(file_path):
        return ("Error: file_path must be a full absolute file_path returned by "
                "nbrag_search/nbrag_search_and_fetch/nbrag_find_files/nbrag_list. "
                "Next steps: use nbrag_find_files(pattern, collection_name) when you only know a filename, "
                "or nbrag_list(collection_name) to browse available file_path values.")

    data = get_file_chunks(file_path, collection_name, start_chunk, max_chunks, raw=False)
    if not data.get("found"):
        detail = data.get("error") or ""
        suffix = f" Detail: {detail}" if detail else ""
        return ("File chunks not found. Check file_path from prior nbrag results, "
                "or use nbrag_find_files/nbrag_list to get the exact full file_path."
                f"{suffix}")

    chunks = data.get("chunks", [])
    if chunks:
        range_start = chunks[0].get("index", data.get("start_chunk", "?"))
        range_end = chunks[-1].get("index", data.get("end_chunk", "?"))
    else:
        range_start = data.get("start_chunk", "?")
        range_end = data.get("end_chunk", "?")
    lines = [
        f"file chunks: {len(chunks)} | filename: {data.get('filename', '?')} | doc_id: {data.get('doc_id', '?')}",
        f"file_path: {data.get('source', '?')} | total_chunks: {data.get('total_chunks', '?')} | total_lines: {data.get('total_lines', '?')}",
        f"range: chunk:{range_start}-{range_end}",
        "",
    ]
    for chunk in chunks:
        scope = str(chunk.get("scope", ""))
        chunk_meta = f"chunk:{chunk.get('index', '?')} | line:{chunk.get('line_start', '?')}-{chunk.get('line_end', '?')}"
        if scope:
            chunk_meta += f" | scope:{scope}"
        lines.append(chunk_meta)
        lines.append(str(chunk.get("content", "")))
        lines.append("")
    return "\n".join(lines)


def nbrag_get_chunks_by_lines(doc_id: str, line_start: int, line_end: int, collection_name: str) -> str:
    line_start = _int_param(line_start, 1)
    line_end = _int_param(line_end, line_start)
    data = get_context_chunks(doc_id, collection_name=collection_name, line_start=line_start, line_end=line_end)
    if not data.get("found"):
        return "No chunks found for that doc_id/line range."

    chunks = data.get("chunks", [])
    lines = [
        f"chunks by lines: {len(chunks)} | doc_id: {doc_id} | total_chunks: {data.get('total_chunks', '?')}",
        f"file_path: {data.get('source', '?')} | line_range: line:{line_start}-{line_end}",
        "",
    ]
    for chunk in chunks:
        scope = str(chunk.get("scope", ""))
        chunk_meta = f"chunk:{chunk.get('index', '?')} | line:{chunk.get('line_start', '?')}-{chunk.get('line_end', '?')}"
        if scope:
            chunk_meta += f" | scope:{scope}"
        lines.append(chunk_meta)
        lines.append(str(chunk.get("content", "")))
        lines.append("")
    return "\n".join(lines)


def nbrag_get_raw_file(file_path: str, collection_name: str, line_start: int = -1, line_end: int = -1) -> str:
    line_start = _int_param(line_start, -1)
    line_end = _int_param(line_end, -1)
    if not _is_absolute_file_path(file_path):
        return ("Error: file_path must be a full absolute file_path returned by "
                "nbrag_search/nbrag_search_and_fetch/nbrag_find_files/nbrag_list. "
                "Next steps: use nbrag_find_files(pattern, collection_name) when you only know a filename, "
                "or nbrag_list(collection_name) to browse available file_path values.")

    data = get_file_chunks(file_path, collection_name, 0, 0, raw=True, line_start=line_start, line_end=line_end)
    if not data.get("found"):
        detail = data.get("error") or ""
        suffix = f" Detail: {detail}" if detail else ""
        return ("Raw file not found. Check file_path from prior nbrag results, "
                "or use nbrag_find_files/nbrag_list to get the exact full file_path."
                f"{suffix}")

    lines = [
        f"original_file: {data.get('filename', '?')} | file_path: {data.get('source', '?')} | doc_id: {data.get('doc_id', '?')}",
        f"total_lines: {data.get('total_lines', '?')} | range: line:{data.get('line_start', '?')}-{data.get('line_end', '?')}",
        str(data.get("content", "")),
    ]
    return "\n".join(lines)


def nbrag_list(collection_name: str, offset: int = 0, limit: int = 200) -> str:
    offset = _int_param(offset, 0)
    limit = _int_param(limit, 200)
    rows = list_documents(collection_name, offset=offset, limit=limit)
    if not rows:
        return "No documents in this collection."

    lines = [f"documents returned: {len(rows)} | offset: {offset} | limit: {limit}", ""]
    for doc_id, row in rows.items():
        chunk_count = row.get("chunk_count", row.get("total_chunks", 0))
        lines.append(f"doc_id: {doc_id} | filename: {row.get('filename', '?')} | chunk_count: {chunk_count} | total_chunks: {row.get('total_chunks', chunk_count)}")
        lines.append(f"file_path: {row.get('source', '?')}")
        lines.append("")
    return "\n".join(lines)


def nbrag_stats() -> str:
    stats = get_stats()
    collections = stats.get("collections", {})
    if not collections:
        return "No collections found. Ask the user to prepare/import a knowledge base first."

    lines = ["collections:", ""]
    for name, info in collections.items():
        docs = info.get("docs", info.get("doc_count", 0))
        chunks = info.get("chunks", info.get("chunk_count", 0))
        lines.append(f"- {name}: docs={docs} chunks={chunks}")
        display_name = info.get("display_name")
        description = info.get("description")
        aliases = info.get("aliases") or []
        tags = info.get("tags") or []
        if display_name:
            lines.append(f"  display_name: {display_name}")
        if description:
            lines.append(f"  description: {description}")
        if aliases:
            lines.append(f"  aliases: {', '.join(str(item) for item in aliases)}")
        if tags:
            lines.append(f"  tags: {', '.join(str(item) for item in tags)}")
        lines.append("")
    return "\n".join(lines)


def nbrag_delete(doc_id: str, collection_name: str) -> str:
    ok = delete_document(doc_id, collection_name)
    return "Deleted" if ok else "Delete failed or doc_id not found."
