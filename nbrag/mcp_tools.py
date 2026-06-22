"""MCP 工具实现层：不注册 MCP，只提供可直接测试/调用的函数。"""

from __future__ import annotations

import bisect
import os
from typing import Any
from nbrag.config import get_config
from nbrag.defaults import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_FETCH_CONTEXT_CHARS,
    DEFAULT_MATCH_CONTEXT_CHARS,
)
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


def _strip_markdown_frontmatter(text: str) -> str:
    text = text.lstrip("\ufeff")
    if not text.startswith("---"):
        return text.strip()

    lines = text.splitlines()
    if len(lines) >= 3 and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                return "\n".join(lines[index + 1:]).strip()
    return text.strip()


def _load_workflow_skill_text() -> str:
    skill_path = os.path.join(os.path.dirname(__file__), "skills", "nbrag-workflow", "SKILL.md")
    try:
        with open(skill_path, "r", encoding="utf-8") as file_handle:
            return _strip_markdown_frontmatter(file_handle.read())
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


def _line_window_from_context_chars(lines: list[str], offsets: list[int], line_start: int, line_end: int, per_hit_context_chars: int) -> tuple[int, int]:
    """Expand around the matched line range using a total per-hit context budget split before/after."""
    total_lines = len(lines)
    if total_lines == 0:
        return 1, 1

    if line_start <= 0 or line_end <= 0:
        return 1, total_lines

    hit_start = max(1, min(total_lines, line_start))
    hit_end = max(hit_start, min(total_lines, line_end))
    if per_hit_context_chars <= 0:
        return hit_start, hit_end

    before_chars = per_hit_context_chars // 2
    after_chars = per_hit_context_chars - before_chars
    hit_char_start = offsets[hit_start - 1]
    hit_char_end = offsets[hit_end]
    win_char_start = max(0, hit_char_start - before_chars)
    win_char_end = min(offsets[-1], hit_char_end + after_chars)

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


def _path_error(field_name: str) -> str:
    return (
        f"Error: {field_name} must be a full absolute file_path returned by "
        "nbrag_search/nbrag_search_and_fetch/nbrag_find_files/nbrag_list. "
        "Next steps: use nbrag_find_files(pattern, collection_name) when you only know a filename, "
        "or nbrag_list(collection_name) to browse available file_path values."
    )


def _collection_issue_text(collection_name: str, total: int) -> str:
    if total == 0:
        stats = get_stats()
        avail = list(stats["collections"].keys())
        exists = collection_name in avail
        if not exists:
            return (
                f"collection '{collection_name}' does not exist.\n"
                f"Available collections: {avail}\n"
                "Next steps: call nbrag_stats() to inspect valid collection_name values, "
                "then retry with the correct prepared knowledge base."
            )
        return (
            f"collection '{collection_name}' is empty. "
            "Next steps: ask the user to ingest/prepare this knowledge base before searching."
        )
    return ""


def _collection_presence_issue_text(collection_name: str) -> str:
    stats = get_stats()
    collections = stats.get("collections", {})
    avail = list(collections.keys())
    info = collections.get(collection_name)
    if info is None:
        return (
            f"collection '{collection_name}' does not exist.\n"
            f"Available collections: {avail}\n"
            "Next steps: call nbrag_stats() to inspect valid collection_name values, "
            "then retry with the correct prepared knowledge base."
        )

    docs = info.get("docs", info.get("doc_count", 0))
    chunks = info.get("chunks", info.get("chunk_count", 0))
    if not docs and not chunks:
        return (
            f"collection '{collection_name}' is empty. "
            "Next steps: ask the user to ingest/prepare this knowledge base before searching."
        )
    return ""


def _no_search_results_text(total: int) -> str:
    return (
        f"No results (collection has {total} chunks).\n"
        "Possible adjustments: verify collection_name, minimally normalize the natural-language query without changing intent, "
        "provide a bm25_query as lexical anchors for BM25 (not a keyword list — use exact terms/article numbers/symbols from user wording or context), "
        "try nbrag_grep for exact terms/article numbers/symbols, or use nbrag_find_files + filter_file_path to narrow to a known file."
    )


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
    skeleton = [
        "nbrag help: Agentic RAG knowledge-base MCP workflow guide",
        "",
        "Core strategy (use the actual exposed tool names, which may have prefixes such as xxx_nbrag_search):",
        "- Use nbrag_stats() when collection_name is unknown.",
        "- Use nbrag_search_and_fetch() as the default one-call retrieval entry for most questions.",
        "- Use nbrag_search() when you need retrieval controls or metadata-only output.",
        "- Use nbrag_grep() for exact wording in stored original text.",
        "- Use nbrag_find_definition() only for Python .py symbol definitions.",
        "- Use nbrag_get_raw_file() for overlap-free original text.",
        "- Use nbrag_find_files() when exact file_path is still unknown.",
        "",
        "Stable follow-up fields: file_path, doc_id, chunk_index, line:N-M.",
    ]
    if skill_text:
        skeleton.extend(["", "nbrag workflow skill:", skill_text])
    return "\n".join(skeleton)


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
    cfg = get_config()
    top_k = _int_param(top_k, 5)
    use_rerank = _bool_param(use_rerank, True)
    use_bm25 = _bool_param(use_bm25, True)
    use_vector = _bool_param(use_vector, True)
    filter_file_path = _str_param(filter_file_path)
    include_content = _bool_param(include_content, True)
    bm25_query = _str_param(bm25_query)
    path_filter = filter_file_path if filter_file_path else None
    if path_filter and not _is_absolute_file_path(path_filter):
        return _path_error("filter_file_path")

    documents, metadatas, distances, rerank_used, total, rerank_scores = search(
        query, collection_name, top_k, use_rerank, use_bm25,
        filter_file_path=path_filter, use_vector=use_vector,
        bm25_query=(bm25_query or None),
    )

    collection_issue = _collection_issue_text(collection_name, total)
    if collection_issue:
        return collection_issue

    if not documents:
        return _no_search_results_text(total)

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


def nbrag_search(
    query: str,
    collection_name: str,
    top_k: int = 5,
    use_rerank: bool = True,
    use_bm25: bool = True,
    filter_file_path: str = "",
    include_content: bool = True,
    bm25_query: str = "",
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
        bm25_query=bm25_query,
    )


def nbrag_search_only_bm25(
    bm25_query: str,
    collection_name: str,
    top_k: int = 5,
    filter_file_path: str = "",
    include_content: bool = True,
) -> str:
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


def nbrag_search_and_fetch(
    query: str,
    collection_name: str,
    top_k: int = 5,
    fetch_top_n_raw: int = 3,
    fetch_context_chars: int = DEFAULT_FETCH_CONTEXT_CHARS,
    filter_file_path: str = "",
    bm25_query: str = "",
) -> str:
    cfg = get_config()
    top_k = _int_param(top_k, 5)
    fetch_top_n_raw = _int_param(fetch_top_n_raw, 3)
    fetch_context_chars = max(0, _int_param(fetch_context_chars, DEFAULT_FETCH_CONTEXT_CHARS))
    filter_file_path = _str_param(filter_file_path)
    bm25_query = _str_param(bm25_query)
    path_filter = filter_file_path if filter_file_path else None
    if path_filter and not _is_absolute_file_path(path_filter):
        return _path_error("filter_file_path")

    documents, metadatas, distances, rerank_used, total, rerank_scores = search(
        query, collection_name, top_k, True, use_bm25=True, filter_file_path=path_filter,
        bm25_query=(bm25_query or None),
    )

    collection_issue = _collection_issue_text(collection_name, total)
    if collection_issue:
        return collection_issue

    if not documents:
        return _no_search_results_text(total)

    rerank_str = cfg.rerank.model if rerank_used else "off"
    bm25_str = "off" if path_filter else "on"
    header = f"[{collection_name}] {total} chunks | bm25: {bm25_str} | rerank: {rerank_str}"
    if filter_file_path:
        header += f" | filter_file_path: {filter_file_path}"
    lines = [
        header,
        "",
        "This tool returns both ranked hits and auto-fetched stored original content.",
        "query is the main semantic query used by vector retrieval and reranking. bm25_query, when provided, is the lexical-anchor query used only by BM25.",
        "fetch_context_chars is per ranked hit: roughly N total context chars split half before and half after, not a total response cap.",
        "Reused follow-up handles in ranked hits: file_path, doc_id, chunk_index, line:N-M.",
        "",
    ]
    if path_filter:
        lines.extend([
            "Behavior note: with filter_file_path set, current hybrid behavior narrows vector retrieval to that single file and does not run cross-file BM25 fusion.",
            "",
        ])
    lines.extend([
        "Ranked search results:",
        "",
    ])

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
        lines.append(doc)
        lines.append("")

        if i < fetch_top_n_raw and doc_id != "?" and src != "?":
            if doc_id not in fetch_targets:
                fetch_targets[doc_id] = {"src": str(src), "ranges": []}
            fetch_targets[doc_id]["ranges"].append((ls, le))

    if fetch_top_n_raw > 0 and fetch_targets:
        lines.append(f"Auto-fetched original content ({len(fetch_targets)} file(s)):")
        lines.append("Returned raw snippets come from the stored original-file snapshot captured at ingestion time.")
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
                _line_window_from_context_chars(raw_lines, offsets, ls, le, fetch_context_chars)
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
    match_context_chars: int = DEFAULT_MATCH_CONTEXT_CHARS,
) -> str:
    max_results = _int_param(max_results, 10)
    case_sensitive = _bool_param(case_sensitive, False)
    filter_file_path = _str_param(filter_file_path)
    match_context_chars = max(0, _int_param(match_context_chars, DEFAULT_MATCH_CONTEXT_CHARS))
    path_filter = filter_file_path if filter_file_path else None
    if path_filter and not _is_absolute_file_path(path_filter):
        return _path_error("filter_file_path")

    results = grep_knowledge(
        keyword,
        collection_name,
        max_results,
        case_sensitive,
        filter_file_path=path_filter,
        match_context_chars=match_context_chars,
    )
    if not results:
        collection_issue = _collection_presence_issue_text(collection_name)
        if collection_issue:
            return collection_issue
        return (
            "No grep matches. Possible adjustments: check exact wording/case, escape regex metacharacters if you intended literal matching, "
            "try regex if appropriate, or switch to nbrag_search_and_fetch for semantic discovery when this is a concept, alias, or paraphrase rather than exact source wording."
        )

    lines = [
        f"grep matches: {len(results)}",
        "",
        "match_context_chars is per grep match: roughly N total context chars split half before and half after, not a total response cap.",
        "Returned handle fields for follow-up: file_path, doc_id, matched_line, line_range.",
        "",
    ]
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
        collection_issue = _collection_presence_issue_text(collection_name)
        if collection_issue:
            return collection_issue
        return (
            "No definition found. Python source may use a different exact name, or this knowledge base may be non-Python text. "
            "Possible adjustments: try nbrag_grep for exact text/regex, use nbrag_search_and_fetch for concept/example discovery, "
            "or verify that this collection actually contains Python .py source files."
        )

    python_symbol_types = {"class", "function", "method"}
    has_python_definition = any(str(r.get("symbol_type", "")).lower() in python_symbol_types for r in results)
    has_non_python_fallback = any(str(r.get("symbol_type", "")).lower() not in python_symbol_types for r in results)

    lines = [
        f"definitions: {len(results)}",
        "",
        "Returned handle fields for follow-up: file_path, doc_id, line range.",
        "",
    ]
    if has_non_python_fallback and not has_python_definition:
        lines.append("Only regex fallback results were found. For law/docs/manuals, use nbrag_grep for exact text / article lookup.")
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
        collection_issue = _collection_presence_issue_text(collection_name)
        if collection_issue:
            return collection_issue
        return (
            "No files matched. Possible adjustments: try a shorter filename fragment, a different suffix, a regex pattern, "
            "or first use nbrag_search_and_fetch/nbrag_grep to discover candidate files."
        )

    lines = [
        f"matched files: {len(files)}",
        "",
        "Returned handle field for follow-up: file_path.",
        "",
    ]
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


def nbrag_get_adjacent_chunks(doc_id: str, chunk_index: int, collection_name: str, window: int = 3) -> str:
    chunk_index = _int_param(chunk_index, 0)
    window = _int_param(window, 3)
    data = get_context_chunks(doc_id, collection_name=collection_name, chunk_index=chunk_index, window=window)
    if not data.get("found"):
        detail = data.get("error") or data.get("message") or ""
        suffix = f" Detail: {detail}" if detail else ""
        return (
            "No adjacent chunks found. Check that doc_id is valid and chunk_index came from a search/search_and_fetch result field like chunk:X/Y or chunk_index:X."
            f"{suffix}"
        )

    chunks = data.get("chunks", [])
    if not chunks:
        detail = data.get("message") or data.get("error") or ""
        suffix = f" Detail: {detail}" if detail else ""
        return (
            "No adjacent chunks found. Check that doc_id is valid and chunk_index came from a search/search_and_fetch result field like chunk:X/Y or chunk_index:X."
            f"{suffix}"
        )

    lines = [
        f"adjacent chunks: {len(chunks)} | file_path: {data.get('source', '?')} | doc_id: {doc_id} | total_chunks: {data.get('total_chunks', '?')}",
        "",
        "Returned context is chunk-level and may overlap. Use file_path with nbrag_get_raw_file for overlap-free source text.",
        "",
    ]
    for chunk in chunks:
        lines.append(f"chunk:{chunk.get('index', '?')} | line:{chunk.get('line_start', '?')}-{chunk.get('line_end', '?')}")
        lines.append(str(chunk.get("content", "")))
        lines.append("")
    return "\n".join(lines)


def nbrag_get_file_chunks(file_path: str, collection_name: str, start_chunk: int = 0, max_chunks: int = 10) -> str:
    start_chunk = _int_param(start_chunk, 0)
    max_chunks = _int_param(max_chunks, 10)
    if not _is_absolute_file_path(file_path):
        return _path_error("file_path")

    data = get_file_chunks(file_path, collection_name, start_chunk, max_chunks, raw=False)
    if not data.get("found"):
        detail = data.get("error") or ""
        suffix = f" Detail: {detail}" if detail else ""
        return (
            "File chunks not found. Check file_path from prior nbrag results, "
            "or use nbrag_find_files/nbrag_list to get the exact full file_path."
            f"{suffix}"
        )

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
        "This view keeps chunk/scope structure and may contain overlap. Use nbrag_get_raw_file for overlap-free source text.",
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
        return (
            "No chunks found for that doc_id/line range. Possible adjustments: verify doc_id, copy line_start/line_end from a prior line:N-M result, "
            "or use nbrag_get_raw_file if you only need original text rather than chunk-level scope metadata."
        )

    chunks = data.get("chunks", [])
    if not chunks:
        detail = data.get("message") or data.get("error") or ""
        suffix = f" Detail: {detail}" if detail else ""
        return (
            "No chunks found for that doc_id/line range. Possible adjustments: verify doc_id, copy line_start/line_end from a prior line:N-M result, "
            "or use nbrag_get_raw_file if you only need original text rather than chunk-level scope metadata."
            f"{suffix}"
        )

    lines = [
        f"chunks by lines: {len(chunks)} | doc_id: {doc_id} | total_chunks: {data.get('total_chunks', '?')}",
        f"file_path: {data.get('source', '?')} | line_range: line:{line_start}-{line_end}",
        "This view preserves chunk/scope structure and may overlap with neighboring chunks.",
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
        return _path_error("file_path")

    data = get_file_chunks(file_path, collection_name, 0, 0, raw=True, line_start=line_start, line_end=line_end)
    if not data.get("found"):
        detail = data.get("error") or ""
        suffix = f" Detail: {detail}" if detail else ""
        return (
            "Raw file not found. Check file_path from prior nbrag results, "
            "or use nbrag_find_files/nbrag_list to get the exact full file_path."
            f"{suffix}"
        )

    lines = [
        f"original_file: {data.get('filename', '?')} | file_path: {data.get('source', '?')} | doc_id: {data.get('doc_id', '?')}",
        f"total_lines: {data.get('total_lines', '?')} | range: line:{data.get('line_start', '?')}-{data.get('line_end', '?')}",
        "Content source: stored original-file snapshot captured at ingestion time.",
        str(data.get("content", "")),
    ]
    return "\n".join(lines)


def nbrag_list(collection_name: str, offset: int = 0, limit: int = 100) -> str:
    offset = _int_param(offset, 0)
    limit = _int_param(limit, 100)
    rows = list_documents(collection_name, offset=offset, limit=limit)
    if not rows:
        collection_issue = _collection_presence_issue_text(collection_name)
        if collection_issue:
            return collection_issue
        return (
            "No documents in this collection. Possible adjustments: verify collection_name with nbrag_stats(), "
            "or ask the user whether this knowledge base has been prepared/ingested."
        )

    lines = [
        f"documents returned: {len(rows)} | offset: {offset} | limit: {limit}",
        "Returned handle fields for follow-up: doc_id, file_path.",
        "",
    ]
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

    lines = [
        "collections:",
        "Use collection_name(知识库名字) exactly as shown below when calling retrieval tools.",
       
        "",
    ]
    for name, info in collections.items():
        docs = info.get("docs", info.get("doc_count", 0))
        chunks = info.get("chunks", info.get("chunk_count", 0))
        lines.append(f"- {name}: docs={docs} chunks={chunks}")
        lines.append(f"  collection_name(知识库名字): {name}")
        display_name = info.get("display_name")
        description = info.get("description")
        aliases = info.get("aliases") or []
        tags = info.get("tags") or []
        chunk_size = info.get("chunk_size")
        chunk_overlap = info.get("chunk_overlap")
        last_ingested_at = info.get("last_ingested_at")
        if display_name:
            lines.append(f"  display_name: {display_name}")
        if description:
            lines.append(f"  description: {description}")
        if aliases:
            lines.append(f"  aliases: {', '.join(str(item) for item in aliases)}")
        if tags:
            lines.append(f"  tags: {', '.join(str(item) for item in tags)}")
        if chunk_size:
            lines.append(f"  chunk_size: {chunk_size}")
        if chunk_overlap:
            lines.append(f"  chunk_overlap: {chunk_overlap}")
        if last_ingested_at:
            lines.append(f"  last_ingested_at: {last_ingested_at}")
        lines.append("")
    nbrag_help_notice = ' It is necessary to ensure that the nbrag_help tool has been called in order to know the usage policy guidelines for nbrag'
    lines.append(f'\n\n {nbrag_help_notice}')
    return "\n".join(lines)


def nbrag_delete(doc_id: str, collection_name: str) -> str:
    deleted_count, filename = delete_document(doc_id, collection_name)
    if deleted_count:
        return f"Deleted {deleted_count} chunk(s) for filename: {filename} | doc_id: {doc_id}"
    collection_issue = _collection_presence_issue_text(collection_name)
    if collection_issue:
        return collection_issue
    return "Delete failed or doc_id not found."
