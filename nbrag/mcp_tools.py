"""MCP 工具实现层：不注册 MCP，只提供可直接测试/调用的函数。"""

from __future__ import annotations

import bisect
import functools
import inspect
import os
import re
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


def _tagged_text(tag: str, fields: list[tuple[str, Any]] | None = None, body: list[str] | None = None, attributes: list[tuple[str, Any]] | None = None) -> str:
    attribute_text = "" if not attributes else " " + " ".join(
        f'{key}="{value}"' for key, value in attributes if value is not None and value != ""
    )
    lines = [f"<{tag}{attribute_text}>"]
    if fields:
        lines.extend(f"{key} = {value}" for key, value in fields if value is not None and value != "")
    if fields and body:
        lines.append("")
    if body:
        lines.extend(body)
    lines.append(f"</{tag}>")
    return "\n".join(lines)


def _request_parameters(parameters: list[tuple[str, Any]]) -> str:
    return _tagged_text("request_parameters", body=[
        _tagged_text("parameter", [("name", name), ("value", value)])
        for name, value in parameters
    ])


def _response_text(
    tool_name: str,
    parameters: list[tuple[str, Any]],
    returned_count_name: str,
    returned_count: int,
    body: list[str] | None = None,
    execution: list[tuple[str, Any]] | None = None,
    outcome: str = "results",
) -> str:
    sections = [_request_parameters(parameters)]
    execution_fields = [("outcome", outcome)]
    if execution:
        execution_fields.extend(execution)
    sections.append(_tagged_text("execution", execution_fields))
    if body:
        sections.extend(body)
    return _tagged_text(
        tool_name,
        body=sections,
        attributes=[("status", "success"), (returned_count_name, returned_count)],
    )


def _error_text(error_type: str, field: str, message: str, recovery: str) -> str:
    error = _tagged_text("error", [
        ("type", error_type),
        ("field", field),
        ("message", message),
        ("recovery", recovery),
    ])
    return error


def _path_error(field_name: str) -> str:
    return _error_text(
        "invalid_file_path",
        field_name,
        f"{field_name} must be a full absolute file_path returned by nbrag tools.",
        "Use nbrag_find_files(pattern, collection_name) when you only know a filename, "
        "or nbrag_list(collection_name) to browse available file_path values.",
    )


def _collection_issue_text(collection_name: str, total: int) -> str:
    if total == 0:
        stats = get_stats()
        avail = list(stats["collections"].keys())
        exists = collection_name in avail
        if not exists:
            return _error_text(
                "missing_collection",
                "collection_name",
                f"collection '{collection_name}' does not exist. Available collections: {avail}",
                "Call nbrag_stats() to inspect valid collection_name values, then retry with the correct prepared knowledge base.",
            )
        return _error_text(
            "empty_collection",
            "collection_name",
            f"collection '{collection_name}' exists but has 0 chunks.",
            "Ingest documents first, or call nbrag_stats() to inspect other collections.",
        )
    return ""


def _collection_presence_issue_text(collection_name: str) -> str:
    stats = get_stats()
    collections = stats.get("collections", {})
    avail = list(collections.keys())
    info = collections.get(collection_name)
    if info is None:
        return _error_text(
            "missing_collection",
            "collection_name",
            f"collection '{collection_name}' does not exist. Available collections: {avail}",
            "Call nbrag_stats() to inspect valid collection_name values, then retry with the correct prepared knowledge base.",
        )

    docs = info.get("docs", info.get("doc_count", 0))
    chunks = info.get("chunks", info.get("chunk_count", 0))
    if not docs and not chunks:
        return _error_text(
            "empty_collection",
            "collection_name",
            f"collection '{collection_name}' exists but has 0 chunks.",
            "Ingest documents first, or call nbrag_stats() to inspect other collections.",
        )
    return ""


def _no_search_results_text(total: int) -> str:
    return _error_text(
        "no_results",
        "query",
        f"No results (collection has {total} chunks).",
        "Verify collection_name, minimally normalize the natural-language query without changing intent, "
        "provide a bm25_query as lexical anchors, try nbrag_grep for exact terms, "
        "or use nbrag_find_files + filter_file_path to narrow to a known file.",
    )


def _extract_tag_body(text: str, tag: str) -> str:
    match = re.fullmatch(rf"<{re.escape(tag)}(?:\s[^>]*)?>\n?(.*?)\n?</{re.escape(tag)}>", text.strip(), re.DOTALL)
    return match.group(1) if match else text.strip()


def _extract_error_fields(text: str) -> list[tuple[str, str]]:
    body = _extract_tag_body(text, "error")
    fields = []
    for line in body.splitlines():
        if " = " in line:
            key, value = line.split(" = ", 1)
            fields.append((key, value))
    return fields


def _finalize_tool_response(tool_name: str, parameters: list[tuple[str, Any]], returned_count_name: str, result_tag: str | None, raw_text: str) -> str:
    error_match = re.fullmatch(r"<(?P<tag>error|nbrag_error)>\n?(?P<body>.*?)\n?</(?P=tag)>", raw_text.strip(), re.DOTALL)
    if error_match:
        error_fields = _extract_error_fields(raw_text)
        error_type = next((value for key, value in error_fields if key == "type"), "unknown")
        if error_type == "no_results":
            return _response_text(tool_name, parameters, returned_count_name, 0, outcome="no_results")
        return _tagged_text(
            tool_name,
            body=[_request_parameters(parameters), _tagged_text("error", error_fields)],
            attributes=[("status", "error")],
        )

    content = _extract_tag_body(raw_text, tool_name)
    returned_count = len(re.findall(rf"(?m)^<{re.escape(result_tag)}>\s*$", raw_text)) if result_tag else 1
    return _response_text(
        tool_name,
        parameters,
        returned_count_name,
        returned_count,
        body=[content] if content else [],
    )


def _contract_tool(returned_count_name: str, result_tag: str | None):
    def decorate(function):
        signature = inspect.signature(function)

        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            parameters = list(bound.arguments.items())
            raw_text = function(*args, **kwargs)
            return _finalize_tool_response(function.__name__, parameters, returned_count_name, result_tag, raw_text)

        return wrapped
    return decorate


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


def _search_and_fetch_follow_up_guidance() -> str:
    return _tagged_text("nbrag_follow_up", body=[
        "Evidence boundaries:",
        "- `<nbrag_chunk_content>` is exactly one RAG chunk; its original-text context stops at the chunk boundaries.",
        "- `<nbrag_original_text_excerpt>` is an overlap-free stored-original-text excerpt with file_path, doc_id, line_start, and line_end; its `<nbrag_original_text_content>` is bounded by fetch_context_chars, not the complete stored file.",
        "",
        "Do not treat either bounded result as complete source context. When the answer, quotation, or verification depends on text outside the shown chunk or original-text excerpt, choose the matching expansion route below.",
        "",
        "Expansion routes using returned handles:",
        "- file_path -> nbrag_read_more_original_text(file_path, collection_name, line_start, line_end): read wider overlap-free original text.",
        "- doc_id + chunk_index -> nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name): read nearby chunk structure.",
        "- doc_id + line_start + line_end -> nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name): read chunk structure covering a known line range.",
        "- 如果某个 ranked hit 对回答有用，就复用该 hit 的 file_path、line_start、line_end 调用 nbrag_read_more_original_text，并将读取窗设为以 hit 的 line_start 为锚点前 200 行到后 400 行：line_start=max(1, line_start-200)，line_end=line_start+400。",
        "- 如果首次扩读后仍缺少回答所需的上下文，就根据缺失内容相对于当前阅读窗的位置，继续扩大读取范围。",
    ])


@_contract_tool("returned_guidance_count", None)
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
        "- Use nbrag_read_more_original_text() for stored original text without chunk overlap.",
        "- Use nbrag_get_file_chunks(), nbrag_get_adjacent_chunks(), or nbrag_get_chunks_by_lines() when you need chunk boundaries, scope metadata, or local chunk context.",
        "- Use nbrag_find_files() when you only know a filename fragment and do not yet have the exact full absolute file_path.",
        "",
        "Step 4: reuse handles from result entities",
        "Each result entity exposes the handles applicable to that result as `key = value` lines:",
        "- `<nbrag_ranked_hit>` → file_path, doc_id, chunk_index, line_start, line_end",
        "- `<nbrag_match>` / `<nbrag_definition>` → file_path, doc_id, line_start, line_end (no chunk_index)",
        "- `<nbrag_file>` / `<nbrag_document>` → file_path, doc_id",
        "- `<nbrag_chunk>` → chunk_index, line_start, line_end; file-level handles remain on the containing result",
        "",
        "`<nbrag_original_text_content>` takes its range semantics from its outer entity: under `<nbrag_match>` it is bounded by match_context_chars; under `<nbrag_original_text_excerpt>` it is bounded by fetch_context_chars; under `<nbrag_original_text>` it is the explicitly requested stored-original-text reading window. Python `<nbrag_definition_content>` is an AST-aware definition body when symbol_type is class/function/method; regex_fallback is only a candidate text match.",
        "",
        "Stable follow-up fields: file_path, doc_id, chunk_index, line_start, line_end.",
        "",
        "search_and_fetch result guidance:",
        _search_and_fetch_follow_up_guidance(),
    ]
    if skill_text:
        skeleton.extend(["", "nbrag workflow skill:", skill_text])
    return _tagged_text("nbrag_help", body=skeleton)


def _format_hit_xml(meta: dict, rank: int, dist: float, rerank_score: float | None, include_content: bool, doc: str = "") -> str:
    file_path = _meta_file_path(meta)
    fields = [
        ("rank", rank),
        ("file_path", file_path),
        ("doc_id", meta.get("doc_id", "?")),
        ("chunk_index", _meta_chunk_index(meta)),
        ("total_chunks", meta.get("total_chunks", "?")),
        ("line_start", meta.get("line_start", "?")),
        ("line_end", meta.get("line_end", "?")),
        ("scope", meta.get("scope", "")),
        ("dist", f"{dist:.4f}"),
    ]
    if rerank_score is not None:
        fields.append(("score", f"{rerank_score:.4f}"))
    body = [_tagged_text("nbrag_chunk_content", body=[doc])] if include_content else None
    return _tagged_text("nbrag_ranked_hit", fields, body)


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

    lines = [f"<{root_tag}>"]

    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
        if meta is None:
            meta = {}
        rerank_score = rerank_scores[i] if rerank_scores and i < len(rerank_scores) else None
        if i > 0:
            lines.extend(["", "", ""])
        lines.append(_format_hit_xml(meta, i + 1, dist, rerank_score, include_content, doc=doc))

    lines.append(f"</{root_tag}>")
    return "\n".join(lines)


@_contract_tool("returned_hit_count", "nbrag_ranked_hit")
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


@_contract_tool("returned_hit_count", "nbrag_ranked_hit")
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


@_contract_tool("returned_hit_count", "nbrag_ranked_hit")
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


@_contract_tool("returned_hit_count", "nbrag_ranked_hit")
def nbrag_search_and_fetch(
    query: str,
    collection_name: str,
    top_k: int = 5,
    fetch_top_n_original_text_excerpt: int = 3,
    fetch_context_chars: int = DEFAULT_FETCH_CONTEXT_CHARS,
    filter_file_path: str = "",
    bm25_query: str = "",
) -> str:
    top_k = _int_param(top_k, 5)
    fetch_top_n_original_text_excerpt = _int_param(fetch_top_n_original_text_excerpt, 3)
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
        if i < fetch_top_n_original_text_excerpt and doc_id != "?" and src != "?":
            if doc_id not in fetch_targets:
                fetch_targets[doc_id] = {"src": str(src), "ranges": []}
            fetch_targets[doc_id]["ranges"].append((ls, le))

    lines_fetched = []
    if fetch_top_n_original_text_excerpt > 0 and fetch_targets:
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
                lines_fetched.append(_tagged_text("nbrag_original_text_excerpt", [
                    ("file_path", src),
                    ("doc_id", doc_id),
                    ("line_start", start),
                    ("line_end", end),
                ], [_tagged_text("nbrag_original_text_content", body=[excerpt])]))

    lines = ["<nbrag_search_and_fetch>", _search_and_fetch_follow_up_guidance(), ""]
    lines.extend(lines_hits)
    lines.append("")
    if lines_fetched:
        lines.extend(lines_fetched)
        lines.append("")
    lines.append("</nbrag_search_and_fetch>")
    return "\n".join(lines)


@_contract_tool("returned_match_count", "nbrag_match")
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
        return _error_text(
            "no_results",
            "keyword",
            "No grep matches.",
            "Check exact wording/case, escape regex metacharacters if you intended literal matching, "
            "try regex if appropriate, or switch to nbrag_search_and_fetch for semantic discovery "
            "when this is a concept, alias, or paraphrase rather than exact source wording.",
        )

    lines = ["<nbrag_grep>"]
    for i, item in enumerate(results):
        if i > 0:
            lines.extend(["", "", ""])
        line_number = item.get("line_number", "?")
        ln = str(line_number)
        file_path = str(item.get("source", "?"))
        doc_id = str(item.get("doc_id", "?"))
        context = str(item.get("context", ""))
        lines.append(_tagged_text("nbrag_match", [
            ("file_path", file_path),
            ("doc_id", doc_id),
            ("line_start", ln),
            ("line_end", ln),
        ], [_tagged_text("nbrag_original_text_content", body=[context])]))
    lines.append('')
    lines.append('</nbrag_grep>')
    return "\n".join(lines)


@_contract_tool("returned_definition_count", "nbrag_definition")
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
        return _error_text(
            "no_results",
            "symbol",
            "No definition found. Python source may use a different exact name, or this knowledge base may be non-Python text.",
            "Try nbrag_grep for exact text/regex, use nbrag_search_and_fetch for concept/example discovery, "
            "or verify that this collection actually contains Python .py source files.",
        )

    python_symbol_types = {"class", "function", "method"}
    lines = ['<nbrag_find_definition>']
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

        body = [_tagged_text("nbrag_definition_content", body=[definition])]
        if methods_summary:
            body.append(_tagged_text("nbrag_methods_summary", body=[methods_summary]))
        lines.append(_tagged_text("nbrag_definition", [
            ("symbol_type", display_symbol_type),
            ("qualified_name", qualified_name),
            ("file_path", file_path),
            ("doc_id", doc_id),
            ("line_start", line_start),
            ("line_end", line_end),
        ], body))
    lines.append('')
    lines.append('</nbrag_find_definition>')
    return "\n".join(lines)


@_contract_tool("returned_file_count", "nbrag_file")
def nbrag_find_files(pattern: str, collection_name: str, max_results: int = 20, case_sensitive: bool = False) -> str:
    max_results = _int_param(max_results, 20)
    case_sensitive = _bool_param(case_sensitive, False)
    files = find_files(pattern, collection_name, max_results, case_sensitive)
    if not files:
        collection_issue = _collection_presence_issue_text(collection_name)
        if collection_issue:
            return collection_issue
        return _error_text(
            "no_results",
            "pattern",
            "No files matched.",
            "Try a shorter filename fragment, a different suffix, a regex pattern, "
            "or first use nbrag_search_and_fetch/nbrag_grep to discover candidate files.",
        )

    lines = ['<nbrag_find_files>']
    for i, item in enumerate(files):
        if i > 0:
            lines.extend(["", ""])
        file_path = str(item.get("source", item.get("file_path", "?")))
        doc_id = str(item.get("doc_id", "?"))
        filename = str(item.get("filename", "?"))
        total_chunks = str(item.get("total_chunks", item.get("chunk_count", "?")))
        match = str(item.get("match", "?"))
        lines.append(_tagged_text("nbrag_file", [
            ("file_path", file_path),
            ("doc_id", doc_id),
            ("filename", filename),
            ("total_chunks", total_chunks),
            ("match", match),
        ]))
    lines.append('')
    lines.append('</nbrag_find_files>')
    return "\n".join(lines)


@_contract_tool("returned_chunk_count", "nbrag_chunk")
def nbrag_get_adjacent_chunks(doc_id: str, chunk_index: int, collection_name: str, window: int = 3) -> str:
    chunk_index = _int_param(chunk_index, 0)
    window = _int_param(window, 3)
    data = get_context_chunks(doc_id, collection_name=collection_name, chunk_index=chunk_index, window=window)
    if not data.get("found"):
        detail = data.get("error") or data.get("message") or ""
        suffix = f" Detail: {detail}." if detail else ""
        return _error_text(
            "not_found",
            "doc_id",
            f"No adjacent chunks found. Check that doc_id is valid and chunk_index came from a search result.{suffix}",
            "Copy doc_id and chunk_index from a prior nbrag_search / nbrag_search_and_fetch `<nbrag_ranked_hit>`, "
            "or use nbrag_read_more_original_text if you only need original text without chunk boundaries.",
        )

    chunks = data.get("chunks", [])
    if not chunks:
        detail = data.get("message") or data.get("error") or ""
        suffix = f" Detail: {detail}." if detail else ""
        return _error_text(
            "not_found",
            "doc_id",
            f"No adjacent chunks found. Check that doc_id is valid and chunk_index came from a search result.{suffix}",
            "Copy doc_id and chunk_index from a prior nbrag_search / nbrag_search_and_fetch `<nbrag_ranked_hit>`, "
            "or use nbrag_read_more_original_text if you only need original text without chunk boundaries.",
        )

    file_path = str(data.get("source", "?"))
    total_chunks = str(data.get("total_chunks", "?"))
    doc_id_str = str(data.get("doc_id", doc_id))

    lines = ['<nbrag_get_adjacent_chunks>']
    for i, chunk in enumerate(chunks):
        if i > 0:
            lines.extend(["", "", ""])
        ci = str(_meta_chunk_index(chunk))
        ls = str(chunk.get("line_start", "?"))
        le = str(chunk.get("line_end", "?"))
        scope = str(chunk.get("scope", ""))
        content = str(chunk.get("content", ""))
        lines.append(_tagged_text("nbrag_chunk", [
            ("file_path", file_path),
            ("doc_id", doc_id_str),
            ("chunk_index", ci),
            ("total_chunks", total_chunks),
            ("line_start", ls),
            ("line_end", le),
            ("scope", scope),
        ], [_tagged_text("nbrag_chunk_content", body=[content])]))
    lines.append("")
    lines.append("</nbrag_get_adjacent_chunks>")
    return "\n".join(lines)


@_contract_tool("returned_chunk_count", "nbrag_chunk")
def nbrag_get_file_chunks(file_path: str, collection_name: str, start_chunk: int = 0, max_chunks: int = 10) -> str:
    start_chunk = _int_param(start_chunk, 0)
    max_chunks = _int_param(max_chunks, 10)
    if not _is_absolute_file_path(file_path):
        return _path_error("file_path")

    data = get_file_chunks(file_path, collection_name, start_chunk, max_chunks, raw=False)
    if not data.get("found"):
        detail = data.get("error") or ""
        suffix = f" Detail: {detail}." if detail else ""
        return _error_text(
            "not_found",
            "file_path",
            f"File chunks not found.{suffix}",
            "Copy file_path from prior nbrag results, or use nbrag_find_files / nbrag_list to get the exact full file_path.",
        )

    chunks = data.get("chunks", [])
    file_path_str = str(data.get("source", file_path))
    doc_id_str = str(data.get("doc_id", "?"))
    total_chunks = str(data.get("total_chunks", "?"))
    total_lines = str(data.get("total_lines", "?"))
    has_more = str((data.get("end_chunk") or 0) < (data.get("total_chunks") or 0) - 1).lower()

    lines = ['<nbrag_get_file_chunks>']
    for i, chunk in enumerate(chunks):
        if i > 0:
            lines.extend(["", "", ""])
        ci = str(_meta_chunk_index(chunk))
        ls = str(chunk.get("line_start", "?"))
        le = str(chunk.get("line_end", "?"))
        scope = str(chunk.get("scope", ""))
        content = str(chunk.get("content", ""))
        lines.append(_tagged_text("nbrag_chunk", [
            ("file_path", file_path_str),
            ("doc_id", doc_id_str),
            ("chunk_index", ci),
            ("total_chunks", total_chunks),
            ("line_start", ls),
            ("line_end", le),
            ("scope", scope),
        ], [_tagged_text("nbrag_chunk_content", body=[content])]))
    lines.append("")
    lines.append("</nbrag_get_file_chunks>")
    return "\n".join(lines)


@_contract_tool("returned_chunk_count", "nbrag_chunk")
def nbrag_get_chunks_by_lines(doc_id: str, line_start: int, line_end: int, collection_name: str) -> str:
    line_start = _int_param(line_start, 1)
    line_end = _int_param(line_end, line_start)
    data = get_context_chunks(doc_id, collection_name=collection_name, line_start=line_start, line_end=line_end)
    if not data.get("found"):
        return _error_text(
            "not_found",
            "doc_id",
            "No chunks found for that doc_id / line range.",
            "Verify doc_id, copy line_start / line_end from a prior `<nbrag_chunk>` metadata block, "
            "or use nbrag_read_more_original_text if you only need original text rather than chunk-level scope metadata.",
        )

    chunks = data.get("chunks", [])
    if not chunks:
        detail = data.get("message") or data.get("error") or ""
        suffix = f" Detail: {detail}." if detail else ""
        return _error_text(
            "not_found",
            "doc_id",
            f"No chunks found for that doc_id / line range.{suffix}",
            "Verify doc_id, copy line_start / line_end from a prior `<nbrag_chunk>` metadata block, "
            "or use nbrag_read_more_original_text if you only need original text rather than chunk-level scope metadata.",
        )

    file_path = str(data.get("source", "?"))
    doc_id_str = str(data.get("doc_id", doc_id))
    total_chunks = str(data.get("total_chunks", "?"))

    lines = ['<nbrag_get_chunks_by_lines>']
    for i, chunk in enumerate(chunks):
        if i > 0:
            lines.extend(["", "", ""])
        ci = str(_meta_chunk_index(chunk))
        ls = str(chunk.get("line_start", "?"))
        le = str(chunk.get("line_end", "?"))
        scope = str(chunk.get("scope", ""))
        content = str(chunk.get("content", ""))
        lines.append(_tagged_text("nbrag_chunk", [
            ("file_path", file_path),
            ("doc_id", doc_id_str),
            ("chunk_index", ci),
            ("total_chunks", total_chunks),
            ("line_start", ls),
            ("line_end", le),
            ("scope", scope),
        ], [_tagged_text("nbrag_chunk_content", body=[content])]))
    lines.append("")
    lines.append("</nbrag_get_chunks_by_lines>")
    return "\n".join(lines)


@_contract_tool("returned_original_text_count", "nbrag_original_text_content")
def nbrag_read_more_original_text(file_path: str, collection_name: str, line_start: int | None = None, line_end: int | None = None) -> str:
    line_start = line_start if isinstance(line_start, int) and not isinstance(line_start, bool) and line_start > 0 else None
    line_end = line_end if isinstance(line_end, int) and not isinstance(line_end, bool) and line_end > 0 else None
    if not _is_absolute_file_path(file_path):
        return _path_error("file_path")

    data = get_file_chunks(file_path, collection_name, 0, 0, raw=True, line_start=line_start, line_end=line_end)
    if not data.get("found"):
        detail = data.get("error") or ""
        suffix = f" Detail: {detail}." if detail else ""
        return _error_text(
            "not_found",
            "file_path",
            f"Stored original text not found.{suffix}",
            "Copy file_path from prior nbrag results, or use nbrag_find_files / nbrag_list to get the exact full file_path.",
        )

    file_path_str = str(data.get("source", file_path))
    doc_id_str = str(data.get("doc_id", "?"))
    total_lines = str(data.get("total_lines", "?"))
    ls = str(data.get("line_start", "?"))
    le = str(data.get("line_end", "?"))
    content = str(data.get("content", ""))

    original_text = _tagged_text("nbrag_original_text", [
        ("file_path", file_path_str),
        ("doc_id", doc_id_str),
        ("total_lines", total_lines),
        ("line_start", ls),
        ("line_end", le),
    ], [_tagged_text("nbrag_original_text_content", body=[content])])
    return _tagged_text("nbrag_read_more_original_text", body=[original_text])


@_contract_tool("returned_document_count", "nbrag_document")
def nbrag_list(collection_name: str, offset: int = 0, limit: int = 100) -> str:
    offset = _int_param(offset, 0)
    limit = _int_param(limit, 100)
    rows = list_documents(collection_name, offset=offset, limit=limit)
    if not rows:
        collection_issue = _collection_presence_issue_text(collection_name)
        if collection_issue:
            return collection_issue
        return _error_text(
            "no_results",
            "collection_name",
            "No documents in this collection.",
            "Verify collection_name with nbrag_stats(), or ask the user whether this knowledge base has been prepared/ingested.",
        )

    lines = ['<nbrag_list>']
    for i, (doc_id, row) in enumerate(rows.items()):
        if i > 0:
            lines.extend(["", ""])
        file_path = str(row.get("source", row.get("file_path", "?")))
        filename = str(row.get("filename", "?"))
        total_chunks = str(row.get("total_chunks", row.get("chunk_count", "?")))
        lines.append(_tagged_text("nbrag_document", [
            ("doc_id", doc_id),
            ("file_path", file_path),
            ("filename", filename),
            ("total_chunks", total_chunks),
        ]))
    lines.append('')
    lines.append('</nbrag_list>')
    return "\n".join(lines)


@_contract_tool("returned_collection_count", "nbrag_collection")
def nbrag_stats() -> str:
    stats = get_stats()
    collections = stats.get("collections", {})
    if not collections:
        return _error_text(
            "no_results",
            "collection_name",
            "No collections found.",
            "Ask the user to prepare/import a knowledge base first.",
        )

    lines = ['<nbrag_stats>']
    for i, (name, info) in enumerate(collections.items()):
        if i > 0:
            lines.extend(["", ""])
        docs = str(info.get("docs", info.get("doc_count", 0)))
        chunks = str(info.get("chunks", info.get("chunk_count", 0)))
        display_name = info.get("display_name")
        description = info.get("description")
        aliases = info.get("aliases") or []
        tags = info.get("tags") or []
        chunk_size = info.get("chunk_size")
        chunk_overlap = info.get("chunk_overlap")
        last_ingested_at = info.get("last_ingested_at")
        lines.append(_tagged_text("nbrag_collection", [
            ("collection_name", name),
            ("docs", docs),
            ("chunks", chunks),
            ("display_name", display_name),
            ("description", description),
            ("aliases", ", ".join(str(item) for item in aliases)),
            ("tags", ", ".join(str(item) for item in tags)),
            ("chunk_size", chunk_size),
            ("chunk_overlap", chunk_overlap),
            ("last_ingested_at", last_ingested_at),
        ]))
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
