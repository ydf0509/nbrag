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


def _meta_file_path(meta: dict) -> str:
    """Map retrieval.py's source key to canonical file_path handle.

    Returns str directly — file_path is a string at the retrieval layer,
    so callers can use it in f-strings and XML attributes without conversion.
    """
    return str(meta.get("source", "?"))


def _meta_chunk_index(meta: dict) -> int:
    """Map retrieval.py's index key to canonical chunk_index handle.

    Returns int — chunk_index is an integer at the retrieval layer
    (retrieval.py stores it as meta.get("chunk_index", 0)). Callers must
    str() it when interpolating into XML attribute values or prose blocks.
    """
    raw = meta.get("chunk_index", meta.get("index", 0))
    if isinstance(raw, bool):  # bool is subclass of int, guard against accidental flags
        return 0
    if isinstance(raw, int):
        return raw
    if isinstance(raw, (float, str)):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0
    return 0


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
        f"<error type=\"invalid_file_path\" field=\"{field_name}\">\n"
        f"{field_name} must be a full absolute file_path returned by nbrag tools.\n"
        f"Recovery: use nbrag_find_files(pattern, collection_name) when you only know a filename, "
        f"or nbrag_list(collection_name) to browse available file_path values.\n"
        f"</error>"
    )


def _collection_issue_text(collection_name: str, total: int) -> str:
    if total == 0:
        stats = get_stats()
        avail = list(stats["collections"].keys())
        exists = collection_name in avail
        if not exists:
            return (
                f"<error type=\"missing_collection\" field=\"collection_name\">\n"
                f"collection '{collection_name}' does not exist.\n"
                f"Available collections: {avail}\n"
                f"Recovery: call nbrag_stats() to inspect valid collection_name values, "
                f"then retry with the correct prepared knowledge base.\n"
                f"</error>"
            )
        return (
            f"<error type=\"empty_collection\" field=\"collection_name\">\n"
            f"collection '{collection_name}' exists but has 0 chunks.\n"
            f"Recovery: ingest documents first, or call nbrag_stats() to inspect other collections.\n"
            f"</error>"
        )
    return ""


def _collection_presence_issue_text(collection_name: str) -> str:
    stats = get_stats()
    collections = stats.get("collections", {})
    avail = list(collections.keys())
    info = collections.get(collection_name)
    if info is None:
        return (
            f"<error type=\"missing_collection\" field=\"collection_name\">\n"
            f"collection '{collection_name}' does not exist.\n"
            f"Available collections: {avail}\n"
            f"Recovery: call nbrag_stats() to inspect valid collection_name values, "
            f"then retry with the correct prepared knowledge base.\n"
            f"</error>"
        )

    docs = info.get("docs", info.get("doc_count", 0))
    chunks = info.get("chunks", info.get("chunk_count", 0))
    if not docs and not chunks:
        return (
            f"<error type=\"empty_collection\" field=\"collection_name\">\n"
            f"collection '{collection_name}' exists but has 0 chunks.\n"
            f"Recovery: ingest documents first, or call nbrag_stats() to inspect other collections.\n"
            f"</error>"
        )
    return ""


def _no_search_results_text(total: int) -> str:
    return (
        f"<error type=\"no_results\" field=\"query\">\n"
        f"No results (collection has {total} chunks).\n"
        f"Recovery: verify collection_name, minimally normalize the natural-language query without changing intent, "
        f"provide a bm25_query as lexical anchors, try nbrag_grep for exact terms, "
        f"or use nbrag_find_files + filter_file_path to narrow to a known file.\n"
        f"</error>"
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
        "nbrag help: routing guide for AI agents using nbrag",
        "",
        "Use the actual exposed tool names you received from the MCP host. They may include prefixes such as xxx_nbrag_search.",
        "",
        "Purpose: nbrag_help establishes how to choose retrieval tools, keep query and bm25_query in distinct roles, distinguish chunk text from stored original text, and reuse follow-up handles safely.",
        "",
        "MANDATORY bootstrap with session-aware reuse:",
        "- Before the first nbrag operation whose routing guidance is not already available in the current conversation context, call nbrag_help() proactively.",
        "- A successful nbrag_help() response is reusable for all later nbrag retrieval questions in the same conversation. A new user question does not by itself require another call.",
        "- If the prior result is unavailable after context compaction, or you are uncertain whether it exists, call nbrag_help() again before using other nbrag tools.",
        "- When routing guidance is already available, proceed directly with the chosen tool. Do not repeat nbrag_help() before normal follow-up calls.",
        "",
        "Step 1: decide the collection",
        "- If collection_name is unknown, call nbrag_stats() next.",
        "",
        "Step 2: choose the retrieval path",
        "- Use nbrag_search_and_fetch() for most questions about meaning, explanation, usage, examples, or source-backed evidence after collection routing is already clear.",
        "- Use nbrag_search() when you need ranked retrieval with finer controls or metadata-only output.",
        "- Use nbrag_grep() when exact wording matters in stored original text: article numbers, exact phrases, identifiers, headings, constants, imports, decorators, or error strings.",
        "- Use nbrag_find_definition() only for Python .py symbol definitions.",
        "",
        "Step 3: choose the follow-up reading tool",
        "- Use nbrag_get_raw_file() for stored original text without chunk overlap.",
        "- Use nbrag_get_file_chunks(), nbrag_get_adjacent_chunks(), or nbrag_get_chunks_by_lines() when you need chunk boundaries, scope metadata, or local chunk context.",
        "- Use nbrag_find_files() when you only know a filename fragment and do not yet have the exact full absolute file_path.",
        "",
        "Step 4: top-result surfacing — which tools expose ready-to-use handle blocks",
        "Retrieval and lookup tools surface the TOP result's handles as `key = value` lines at the top of the returned text, plus an `Unlocks:` line listing candidate follow-up tools:",
        "- nbrag_search, nbrag_search_only_bm25, nbrag_search_only_vector, nbrag_search_and_fetch  → file_path, doc_id, chunk_index, line_start, line_end",
        "- nbrag_grep, nbrag_find_definition  → file_path, doc_id, line_start, line_end (no chunk_index)",
        "- nbrag_find_files, nbrag_list  → file_path, doc_id only",
        "Chunk-view reading tools do NOT surface a top-result handle block — scan their `<chunk>` XML attributes directly:",
        "- nbrag_get_file_chunks, nbrag_get_adjacent_chunks, nbrag_get_chunks_by_lines",
        "nbrag_get_raw_file puts handles as XML attributes on the root tag, not as a `key = value` surfacing block.",
        "Only the TOP result is surfaced via `key = value` lines; for non-top results, always scan the corresponding `<hit>`/`<match>`/`<definition>`/`<file>`/`<document>` XML attributes.",
        "",
        "IMPORTANT output boundaries: `<hit>` and `<chunk>` content are RAG chunks and may be cut at chunk boundaries. `<match>` content is a stored-original-text context excerpt bounded by match_context_chars. Python `<definition>` content is an AST-aware definition body when symbol_type is class/function/method; regex_fallback is only a candidate text match. `<fetched_raw>` content is a stored-original-text excerpt bounded by fetch_context_chars. Use nbrag_get_raw_file for overlap-free original text; only line_start=-1 and line_end=-1 return the whole stored file.",
        "",
        "Stable follow-up fields: file_path, doc_id, chunk_index, line_start, line_end.",
    ]
    if skill_text:
        skeleton.extend(["", "nbrag workflow skill:", skill_text])
    return "\n".join(skeleton)


def _format_hit_xml(meta: dict, rank: int, dist: float, rerank_score: float | None, include_content: bool, doc: str = "") -> str:
    """Format one ranked hit as `<hit>` XML. Shared by _format_search_results and nbrag_search_and_fetch."""
    file_path = _meta_file_path(meta)
    chunk_index = str(_meta_chunk_index(meta))
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


def _surfacing_block(title: str, handles: list[tuple[str, str]], unlocks: str) -> list[str]:
    """Build an AI-facing top-result handle surfacing block + Unlocks menu.

    Uses `key = value` (spaced equals) so the prose block is visually distinct
    from XML `key="value"` attributes and introduces zero `<tag>` literals that
    could collide with data tags.
    """
    lines = [f"{title}"]
    for key, value in handles:
        lines.append(f"  {key} = {value}")
    if unlocks:
        lines.append(unlocks)
    return lines


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

    root_attrs = [f'collection_name="{collection_name}"', f'total_chunks="{total}"', f'bm25="{bm25_str}"', f'rerank="{rerank_str}"']
    if path_filter:
        root_attrs.append(f'filter_file_path="{path_filter}"')
    lines = [f"<{root_tag} {' '.join(root_attrs)}>"]
    top_meta = metadatas[0] or {}
    top_handles = [
        ("file_path", _meta_file_path(top_meta)),
        ("doc_id", str(top_meta.get("doc_id", "?"))),
        ("chunk_index", str(_meta_chunk_index(top_meta))),
        ("line_start", str(top_meta.get("line_start", "?"))),
        ("line_end", str(top_meta.get("line_end", "?"))),
    ]
    unlocks = (
        "Available follow-up tools when you need to expand, quote, or verify: "
        "nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name) | "
        "nbrag_get_raw_file(file_path, collection_name, line_start, line_end) | "
        "nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name)"
    )
    lines.extend(_surfacing_block("Top result handles — reuse these values in the next call:", top_handles, unlocks))
    lines.append("")
    lines.append("`<hit>` 中的 `<content>` 是可能在 chunk 边界截断的 RAG chunk，不是完整原文。可使用上一行工具读取原始文本、扩大上下文或完成验证。")
    lines.append("")
    lines.append("<ranked_hits>")

    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
        if meta is None:
            meta = {}
        rerank_score = rerank_scores[i] if rerank_scores and i < len(rerank_scores) else None
        if i > 0:
            lines.extend(["", "", ""])
        lines.append(_format_hit_xml(meta, i + 1, dist, rerank_score, include_content, doc=doc))

    lines.append("</ranked_hits>")
    lines.append("")
    lines.append(f"</{root_tag}>")
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
        root_tag="nbrag_search",
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
        root_tag="nbrag_search_only_bm25",
    )


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

    fetch_targets: dict[str, dict[str, Any]] = {}
    lines_hits = []
    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
        if meta is None:
            meta = {}
        rerank_score = rerank_scores[i] if rerank_scores and i < len(rerank_scores) else None
        if i > 0:
            lines_hits.append("")
        lines_hits.append(_format_hit_xml(meta, i + 1, dist, rerank_score, include_content=True, doc=doc))

        src = _meta_file_path(meta)
        doc_id = str(meta.get("doc_id", "?"))
        _ls = meta.get("line_start", 0)
        _le = meta.get("line_end", 0)
        ls = int(_ls) if isinstance(_ls, (int, float)) else 0
        le = int(_le) if isinstance(_le, (int, float)) else 0
        if i < fetch_top_n_raw and doc_id != "?" and src != "?":
            if doc_id not in fetch_targets:
                fetch_targets[doc_id] = {"src": str(src), "ranges": []}
            fetch_targets[doc_id]["ranges"].append((ls, le))

    lines_fetched = []
    if fetch_top_n_raw > 0 and fetch_targets:
        for doc_id, info in fetch_targets.items():
            src = str(info["src"])
            ranges = info["ranges"]
            if not ranges:
                continue

            raw_data = get_file_chunks(src, collection_name, 0, 0, raw=True)
            if not raw_data.get("found"):
                continue

            raw_content = str(raw_data.get("content", ""))
            raw_lines, offsets = _build_line_char_index(raw_content)
            expanded_ranges = [
                _line_window_from_context_chars(raw_lines, offsets, ls, le, fetch_context_chars)
                for ls, le in ranges
            ]
            merged_ranges = _merge_line_ranges(expanded_ranges)

            for start, end in merged_ranges:
                excerpt = "".join(raw_lines[start - 1:end]) if raw_lines else raw_content
                if lines_fetched:
                    lines_fetched.extend(["", "", ""])
                lines_fetched.append(
                    f'<raw file_path="{src}" doc_id="{doc_id}" line_start="{start}" line_end="{end}">\n'
                    f'<content>\n{excerpt}\n</content>\n</raw>'
                )

    root_attrs = [f'collection_name="{collection_name}"', f'total_chunks="{total}"', f'bm25="{bm25_str}"', f'rerank="{rerank_str}"']
    if path_filter:
        root_attrs.append(f'filter_file_path="{path_filter}"')

    lines = [f"<nbrag_search_and_fetch {' '.join(root_attrs)}>"]
    top_meta = metadatas[0] or {}
    top_handles = [
        ("file_path", _meta_file_path(top_meta)),
        ("doc_id", str(top_meta.get("doc_id", "?"))),
        ("chunk_index", str(_meta_chunk_index(top_meta))),
        ("line_start", str(top_meta.get("line_start", "?"))),
        ("line_end", str(top_meta.get("line_end", "?"))),
    ]
    unlocks = (
        "Available follow-up tools when you need to expand, quote, or verify: "
        "nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name) | "
        "nbrag_get_raw_file(file_path, collection_name, line_start, line_end) | "
        "nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name)"
    )
    lines.extend(_surfacing_block("Top result handles — reuse these values in the next call:", top_handles, unlocks))
    lines.append("")
    lines.append("`<hit>` 中的 `<content>` 是 RAG chunk，可能在 chunk 边界截断。`<fetched_raw>` 中 `<raw>` 的 `<content>` 是围绕命中位置扩展的、无 chunk overlap 的原始文件快照摘录，不是 RAG chunk；但它仍受 fetch_context_chars 限制，并非完整文件。需要更大或精确行范围时，调用 nbrag_get_raw_file(file_path, collection_name, line_start, line_end)。")
    lines.append("")
    lines.append("<ranked_hits>")
    lines.extend(lines_hits)
    lines.append("</ranked_hits>")
    lines.append("")
    if lines_fetched:
        lines.append("<fetched_raw>")
        lines.append("Raw excerpts below come from the stored original-file snapshot without chunk overlap. Their line_start/line_end are expanded context ranges, not the original hit range. To widen an excerpt or read an exact line range, pass file_path + these line ranges to nbrag_get_raw_file. For the original hit range, read line_start/line_end from `<hit>` above.")
        lines.extend(lines_fetched)
        lines.append("</fetched_raw>")
        lines.append("")
    lines.append("</nbrag_search_and_fetch>")
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
            '<error type="no_results" field="keyword">\n'
            'No grep matches.\n'
            'Recovery: check exact wording/case, escape regex metacharacters if you intended literal matching, '
            'try regex if appropriate, or switch to nbrag_search_and_fetch for semantic discovery '
            'when this is a concept, alias, or paraphrase rather than exact source wording.\n'
            '</error>'
        )

    root_attrs = [f'case_sensitive="{"true" if case_sensitive else "false"}"']
    if path_filter:
        root_attrs.append(f'filter_file_path="{path_filter}"')
    top_item = results[0] or {}
    top_ln = str(top_item.get("line_number", "?"))
    top_handles = [
        ("file_path", str(top_item.get("source", "?"))),
        ("doc_id", str(top_item.get("doc_id", "?"))),
        ("line_start", top_ln),
        ("line_end", top_ln),
    ]
    unlocks = (
        "Available follow-up tools when you need to expand, quote, or verify: "
        "nbrag_get_raw_file(file_path, collection_name, line_start, line_end) | "
        "nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name) | "
        "nbrag_search_and_fetch(query, collection_name) for nearby semantic context"
    )
    lines = [
        f'<nbrag_grep {" ".join(root_attrs)}>',
    ]
    lines.extend(_surfacing_block("Top match handles — reuse these values in the next call:", top_handles, unlocks))
    lines.append("")
    lines.append("`<match>` 中的 `<content>` 是 stored-original-text context excerpt，不含 chunk overlap，但受 match_context_chars 限制，并非完整文件。可使用上一行工具读取所需原文范围、扩大上下文或完成验证。")
    lines.append("")
    lines.append("<matches>")
    for i, item in enumerate(results):
        if i > 0:
            lines.extend(["", "", ""])
        line_number = item.get("line_number", "?")
        ln = str(line_number)
        file_path = str(item.get("source", "?"))
        doc_id = str(item.get("doc_id", "?"))
        context = str(item.get("context", ""))
        lines.append(f'<match file_path="{file_path}" doc_id="{doc_id}" line_start="{ln}" line_end="{ln}">')
        lines.append('<content>')
        lines.append(context)
        lines.append('</content>')
        lines.append('</match>')
    lines.append('</matches>')
    lines.append('')
    lines.append('</nbrag_grep>')
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
            '<error type="no_results" field="symbol">\n'
            'No definition found. Python source may use a different exact name, or this knowledge base may be non-Python text.\n'
            'Recovery: try nbrag_grep for exact text/regex, use nbrag_search_and_fetch for concept/example discovery, '
            'or verify that this collection actually contains Python .py source files.\n'
            '</error>'
        )

    python_symbol_types = {"class", "function", "method"}
    has_python_definition = any(str(r.get("symbol_type", "")).lower() in python_symbol_types for r in results)
    has_non_python_fallback = any(str(r.get("symbol_type", "")).lower() not in python_symbol_types for r in results)

    top_def = results[0] or {}
    top_handles = [
        ("file_path", str(top_def.get("source", "?"))),
        ("doc_id", str(top_def.get("doc_id", "?"))),
        ("line_start", str(top_def.get("line_start", "?"))),
        ("line_end", str(top_def.get("line_end", "?"))),
    ]
    unlocks = (
        "Available follow-up tools when you need to expand, quote, or verify: "
        "nbrag_get_raw_file(file_path, collection_name, line_start, line_end) | "
        "nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name)"
    )
    lines = ['<nbrag_find_definition>']
    lines.extend(_surfacing_block("Top definition handles — reuse these values in the next call:", top_handles, unlocks))
    lines.append("")
    lines.append("For symbol_type class/function/method, `<definition>` `<content>` is an AST-aware Python definition body; regex_fallback is only a candidate text match. Use the returned line range to verify the source or widen surrounding original text.")
    lines.append("")
    if has_non_python_fallback and not has_python_definition:
        lines.append('Only regex fallback results were found. For non-Python text, use nbrag_grep for exact wording lookup.')
        lines.append('')
    lines.append('<definitions>')
    for i, r in enumerate(results):
        if i > 0:
            lines.extend(["", "", ""])
        symbol_type = str(r.get("symbol_type", "unknown"))
        qualified_name = r.get("qualified_name") or symbol
        file_path = str(r.get("source", "?"))
        line_start = str(r.get("line_start", "?"))
        line_end = str(r.get("line_end", "?"))
        doc_id = str(r.get("doc_id", "?"))
        definition = str(r.get("definition") or r.get("content", ""))
        methods_summary = str(r.get("methods_summary", ""))
        display_symbol_type = symbol_type if symbol_type.lower() in python_symbol_types else "regex_fallback"

        lines.append(f'<definition symbol_type="{display_symbol_type}" qualified_name="{qualified_name}" file_path="{file_path}" doc_id="{doc_id}" line_start="{line_start}" line_end="{line_end}">')
        lines.append('<content>')
        lines.append(definition)
        lines.append('</content>')
        if methods_summary:
            lines.append('<methods_summary>')
            lines.append(methods_summary)
            lines.append('</methods_summary>')
        lines.append('</definition>')
    lines.append('</definitions>')
    lines.append('')
    lines.append('</nbrag_find_definition>')
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
            '<error type="no_results" field="pattern">\n'
            'No files matched.\n'
            'Recovery: try a shorter filename fragment, a different suffix, a regex pattern, '
            'or first use nbrag_search_and_fetch/nbrag_grep to discover candidate files.\n'
            '</error>'
        )

    top_file = files[0] or {}
    top_handles = [
        ("file_path", str(top_file.get("source", top_file.get("file_path", "?")))),
        ("doc_id", str(top_file.get("doc_id", "?"))),
    ]
    unlocks = (
        "Unlocks: "
        "nbrag_get_raw_file(file_path, collection_name) | "
        "nbrag_get_file_chunks(file_path, collection_name, start_chunk) | "
        "nbrag_search_and_fetch(query, collection_name, filter_file_path=file_path)"
    )
    lines = ['<nbrag_find_files>']
    lines.extend(_surfacing_block("Top file handle — reuse this value in the next call:", top_handles, unlocks))
    lines.append("")
    lines.append("<files>")
    for i, item in enumerate(files):
        if i > 0:
            lines.extend(["", ""])
        file_path = str(item.get("source", item.get("file_path", "?")))
        doc_id = str(item.get("doc_id", "?"))
        filename = str(item.get("filename", "?"))
        total_chunks = str(item.get("total_chunks", item.get("chunk_count", "?")))
        match = str(item.get("match", "?"))
        lines.append(
            f'<file file_path="{file_path}" doc_id="{doc_id}" filename="{filename}" '
            f'total_chunks="{total_chunks}" match="{match}"/>'
        )
    lines.append('</files>')
    lines.append('')
    lines.append('</nbrag_find_files>')
    return "\n".join(lines)


def nbrag_get_adjacent_chunks(doc_id: str, chunk_index: int, collection_name: str, window: int = 3) -> str:
    chunk_index = _int_param(chunk_index, 0)
    window = _int_param(window, 3)
    data = get_context_chunks(doc_id, collection_name=collection_name, chunk_index=chunk_index, window=window)
    if not data.get("found"):
        detail = data.get("error") or data.get("message") or ""
        suffix = f" Detail: {detail}." if detail else ""
        return (
            f'<error type="not_found" field="doc_id">\n'
            f"No adjacent chunks found. Check that doc_id is valid and chunk_index came from a search result.{suffix}\n"
            f"Recovery: copy doc_id and chunk_index from a prior nbrag_search / nbrag_search_and_fetch `<hit>`, "
            f"or use nbrag_get_raw_file if you only need original text without chunk boundaries.\n"
            f'</error>'
        )

    chunks = data.get("chunks", [])
    if not chunks:
        detail = data.get("message") or data.get("error") or ""
        suffix = f" Detail: {detail}." if detail else ""
        return (
            f'<error type="not_found" field="doc_id">\n'
            f"No adjacent chunks found. Check that doc_id is valid and chunk_index came from a search result.{suffix}\n"
            f"Recovery: copy doc_id and chunk_index from a prior nbrag_search / nbrag_search_and_fetch `<hit>`, "
            f"or use nbrag_get_raw_file if you only need original text without chunk boundaries.\n"
            f'</error>'
        )

    file_path = str(data.get("source", "?"))
    total_chunks = str(data.get("total_chunks", "?"))
    doc_id_str = str(data.get("doc_id", doc_id))

    lines = [
        f'<nbrag_get_adjacent_chunks file_path="{file_path}" doc_id="{doc_id_str}" total_chunks="{total_chunks}" window="{window}" anchor_chunk_index="{chunk_index}">',
        "Input chunk_index echoed above as anchor_chunk_index. Returned chunk handles below: chunk_index, line_start, line_end.",
        "",
        "`<chunk>` 中的 `<content>` 是可能在 chunk 边界截断的 RAG chunk，不是完整原文。可调用 nbrag_get_raw_file 读取无重叠的原始文本、扩大上下文或完成验证。",
        "",
        "<chunks>",
    ]
    for i, chunk in enumerate(chunks):
        if i > 0:
            lines.extend(["", "", ""])
        ci = str(_meta_chunk_index(chunk))
        ls = str(chunk.get("line_start", "?"))
        le = str(chunk.get("line_end", "?"))
        scope = str(chunk.get("scope", ""))
        attrs = [
            f'chunk_index="{ci}"',
            f'total_chunks="{total_chunks}"',
            f'line_start="{ls}"',
            f'line_end="{le}"',
        ]
        if scope:
            attrs.append(f'scope="{scope}"')
        content = str(chunk.get("content", ""))
        lines.append(f'<chunk {" ".join(attrs)}>')
        lines.append("<content>")
        lines.append(content)
        lines.append("</content>")
        lines.append("</chunk>")
    lines.append("</chunks>")
    lines.append("")
    lines.append("</nbrag_get_adjacent_chunks>")
    return "\n".join(lines)


def nbrag_get_file_chunks(file_path: str, collection_name: str, start_chunk: int = 0, max_chunks: int = 10) -> str:
    start_chunk = _int_param(start_chunk, 0)
    max_chunks = _int_param(max_chunks, 10)
    if not _is_absolute_file_path(file_path):
        return _path_error("file_path")

    data = get_file_chunks(file_path, collection_name, start_chunk, max_chunks, raw=False)
    if not data.get("found"):
        detail = data.get("error") or ""
        suffix = f" Detail: {detail}." if detail else ""
        return (
            f'<error type="not_found" field="file_path">\n'
            f"File chunks not found.{suffix}\n"
            f"Recovery: copy file_path from prior nbrag results, "
            f"or use nbrag_find_files / nbrag_list to get the exact full file_path.\n"
            f'</error>'
        )

    chunks = data.get("chunks", [])
    file_path_str = str(data.get("source", file_path))
    doc_id_str = str(data.get("doc_id", "?"))
    total_chunks = str(data.get("total_chunks", "?"))
    total_lines = str(data.get("total_lines", "?"))
    has_more = str((data.get("end_chunk") or 0) < (data.get("total_chunks") or 0) - 1).lower()

    lines = [
        f'<nbrag_get_file_chunks file_path="{file_path_str}" doc_id="{doc_id_str}" total_chunks="{total_chunks}" total_lines="{total_lines}" start_chunk="{start_chunk}" max_chunks="{max_chunks}" has_more="{has_more}">',
        "Input start_chunk echoed above (pagination cursor, value-compatible with chunk_index but not a chunk handle). Returned chunk handles below: chunk_index, line_start, line_end.",
        "",
        "`<chunk>` 中的 `<content>` 是可能在 chunk 边界截断的 RAG chunk，不是完整原文。可调用 nbrag_get_raw_file 读取无重叠的原始文本、扩大上下文或完成验证。",
        "",
        "<chunks>",
    ]
    for i, chunk in enumerate(chunks):
        if i > 0:
            lines.extend(["", "", ""])
        ci = str(_meta_chunk_index(chunk))
        ls = str(chunk.get("line_start", "?"))
        le = str(chunk.get("line_end", "?"))
        scope = str(chunk.get("scope", ""))
        attrs = [
            f'chunk_index="{ci}"',
            f'total_chunks="{total_chunks}"',
            f'line_start="{ls}"',
            f'line_end="{le}"',
        ]
        if scope:
            attrs.append(f'scope="{scope}"')
        content = str(chunk.get("content", ""))
        lines.append(f'<chunk {" ".join(attrs)}>')
        lines.append("<content>")
        lines.append(content)
        lines.append("</content>")
        lines.append("</chunk>")
    lines.append("</chunks>")
    lines.append("")
    if has_more == "true":
        last_ci = _meta_chunk_index(chunks[-1]) if chunks else start_chunk
        lines.append(f"Next page: nbrag_get_file_chunks(file_path, collection_name, start_chunk={last_ci + 1}).")
        lines.append("")
    lines.append("</nbrag_get_file_chunks>")
    return "\n".join(lines)


def nbrag_get_chunks_by_lines(doc_id: str, line_start: int, line_end: int, collection_name: str) -> str:
    line_start = _int_param(line_start, 1)
    line_end = _int_param(line_end, line_start)
    data = get_context_chunks(doc_id, collection_name=collection_name, line_start=line_start, line_end=line_end)
    if not data.get("found"):
        return (
            f'<error type="not_found" field="doc_id">\n'
            f"No chunks found for that doc_id / line range.\n"
            f"Recovery: verify doc_id, copy line_start / line_end from a prior `<chunk>` handle, "
            f"or use nbrag_get_raw_file if you only need original text rather than chunk-level scope metadata.\n"
            f'</error>'
        )

    chunks = data.get("chunks", [])
    if not chunks:
        detail = data.get("message") or data.get("error") or ""
        suffix = f" Detail: {detail}." if detail else ""
        return (
            f'<error type="not_found" field="doc_id">\n'
            f"No chunks found for that doc_id / line range.{suffix}\n"
            f"Recovery: verify doc_id, copy line_start / line_end from a prior `<chunk>` handle, "
            f"or use nbrag_get_raw_file if you only need original text rather than chunk-level scope metadata.\n"
            f'</error>'
        )

    file_path = str(data.get("source", "?"))
    doc_id_str = str(data.get("doc_id", doc_id))
    total_chunks = str(data.get("total_chunks", "?"))

    lines = [
        f'<nbrag_get_chunks_by_lines doc_id="{doc_id_str}" file_path="{file_path}" total_chunks="{total_chunks}" requested_line_start="{line_start}" requested_line_end="{line_end}">',
        "Input line_start/line_end echoed above as requested_line_start/requested_line_end. Returned chunk handles below: chunk_index, line_start, line_end (actual chunk coverage may differ from requested range).",
        "",
        "`<chunk>` 中的 `<content>` 是可能在 chunk 边界截断的 RAG chunk，不是完整原文。可调用 nbrag_get_raw_file 读取无重叠的原始文本、扩大上下文或完成验证。",
        "",
        "<chunks>",
    ]
    for i, chunk in enumerate(chunks):
        if i > 0:
            lines.extend(["", "", ""])
        ci = str(_meta_chunk_index(chunk))
        ls = str(chunk.get("line_start", "?"))
        le = str(chunk.get("line_end", "?"))
        scope = str(chunk.get("scope", ""))
        attrs = [
            f'chunk_index="{ci}"',
            f'total_chunks="{total_chunks}"',
            f'line_start="{ls}"',
            f'line_end="{le}"',
        ]
        if scope:
            attrs.append(f'scope="{scope}"')
        content = str(chunk.get("content", ""))
        lines.append(f'<chunk {" ".join(attrs)}>')
        lines.append("<content>")
        lines.append(content)
        lines.append("</content>")
        lines.append("</chunk>")
    lines.append("</chunks>")
    lines.append("")
    lines.append("</nbrag_get_chunks_by_lines>")
    return "\n".join(lines)


def nbrag_get_raw_file(file_path: str, collection_name: str, line_start: int = -1, line_end: int = -1) -> str:
    line_start = _int_param(line_start, -1)
    line_end = _int_param(line_end, -1)
    if not _is_absolute_file_path(file_path):
        return _path_error("file_path")

    data = get_file_chunks(file_path, collection_name, 0, 0, raw=True, line_start=line_start, line_end=line_end)
    if not data.get("found"):
        detail = data.get("error") or ""
        suffix = f" Detail: {detail}." if detail else ""
        return (
            f'<error type="not_found" field="file_path">\n'
            f"Raw file not found.{suffix}\n"
            f"Recovery: copy file_path from prior nbrag results, "
            f"or use nbrag_find_files / nbrag_list to get the exact full file_path.\n"
            f'</error>'
        )

    file_path_str = str(data.get("source", file_path))
    doc_id_str = str(data.get("doc_id", "?"))
    total_lines = str(data.get("total_lines", "?"))
    ls = str(data.get("line_start", "?"))
    le = str(data.get("line_end", "?"))
    content = str(data.get("content", ""))

    lines = [
        f'<nbrag_get_raw_file file_path="{file_path_str}" doc_id="{doc_id_str}" total_lines="{total_lines}" line_start="{ls}" line_end="{le}">',
        "<content>",
        content,
        "</content>",
        "",
        "</nbrag_get_raw_file>",
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
            '<error type="no_results" field="collection_name">\n'
            'No documents in this collection.\n'
            'Recovery: verify collection_name with nbrag_stats(), '
            'or ask the user whether this knowledge base has been prepared/ingested.\n'
            '</error>'
        )

    first_doc_id = next(iter(rows), None)
    first_row = rows.get(first_doc_id, {}) if first_doc_id else {}
    top_handles = [
        ("doc_id", str(first_doc_id) if first_doc_id else "?"),
        ("file_path", str(first_row.get("source", first_row.get("file_path", "?")))),
    ]
    unlocks = (
        "Unlocks: nbrag_get_raw_file(file_path, collection_name) | "
        "nbrag_get_file_chunks(file_path, collection_name, start_chunk) | "
        "nbrag_search_and_fetch(query, collection_name, filter_file_path=file_path)"
    )
    lines = [f'<nbrag_list collection_name="{collection_name}" offset="{offset}" limit="{limit}">']
    lines.extend(_surfacing_block("First document handles — reuse these values in the next call:", top_handles, unlocks))
    lines.append("")
    lines.append("<documents>")
    for i, (doc_id, row) in enumerate(rows.items()):
        if i > 0:
            lines.extend(["", ""])
        file_path = str(row.get("source", row.get("file_path", "?")))
        filename = str(row.get("filename", "?"))
        total_chunks = str(row.get("total_chunks", row.get("chunk_count", "?")))
        lines.append(
            f'<document doc_id="{doc_id}" file_path="{file_path}" filename="{filename}" '
            f'total_chunks="{total_chunks}"/>'
        )
    lines.append('</documents>')
    lines.append('')
    lines.append('</nbrag_list>')
    return "\n".join(lines)


def nbrag_stats() -> str:
    stats = get_stats()
    collections = stats.get("collections", {})
    if not collections:
        return (
            '<error type="no_results" field="collection_name">\n'
            'No collections found.\n'
            'Recovery: ask the user to prepare/import a knowledge base first.\n'
            '</error>'
        )

    lines = [
        '<nbrag_stats>',
        'Use collection_name exactly as shown below when calling retrieval tools.',
        '',
        '<collections>',
    ]
    for i, (name, info) in enumerate(collections.items()):
        if i > 0:
            lines.extend(["", ""])
        docs = str(info.get("docs", info.get("doc_count", 0)))
        chunks = str(info.get("chunks", info.get("chunk_count", 0)))
        attrs = [f'collection_name="{name}"', f'docs="{docs}"', f'chunks="{chunks}"']
        display_name = info.get("display_name")
        description = info.get("description")
        aliases = info.get("aliases") or []
        tags = info.get("tags") or []
        chunk_size = info.get("chunk_size")
        chunk_overlap = info.get("chunk_overlap")
        last_ingested_at = info.get("last_ingested_at")
        if display_name:
            attrs.append(f'display_name="{display_name}"')
        if description:
            attrs.append(f'description="{description}"')
        if aliases:
            attrs.append(f'aliases="{", ".join(str(item) for item in aliases)}"')
        if tags:
            attrs.append(f'tags="{", ".join(str(item) for item in tags)}"')
        if chunk_size:
            attrs.append(f'chunk_size="{chunk_size}"')
        if chunk_overlap:
            attrs.append(f'chunk_overlap="{chunk_overlap}"')
        if last_ingested_at:
            attrs.append(f'last_ingested_at="{last_ingested_at}"')
        lines.append(f'<collection {" ".join(attrs)}/>')
    lines.append('</collections>')
    lines.append('')
    lines.append('After choosing collection_name, continue with nbrag_search_and_fetch for most questions.')
    lines.append('')
    lines.append('</nbrag_stats>')
    return "\n".join(lines)


def nbrag_delete(doc_id: str, collection_name: str) -> str:
    deleted_count, filename = delete_document(doc_id, collection_name)
    if deleted_count:
        return f"Deleted {deleted_count} chunk(s) for filename: {filename} | doc_id: {doc_id}"
    collection_issue = _collection_presence_issue_text(collection_name)
    if collection_issue:
        return collection_issue
    return "Delete failed or doc_id not found."
