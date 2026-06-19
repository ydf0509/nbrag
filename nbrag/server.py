"""
nbrag MCP Server — 11 个 Agentic RAG MCP 检索工具 + 1 个导航工具。

MCP tools (12 total):
  0. nbrag_help                 → Short workflow guide for AI agents
  1. nbrag_search               → Semantic search (vector + rerank)
  2. nbrag_search_and_fetch     → Search + auto-fetch original file content (combo tool)
  3. nbrag_grep                 → Keyword/regex exact search (complements semantic search)
  4. nbrag_find_definition      → Find Python class/function definition by symbol name
  5. nbrag_find_files           → Find full file_path by filename/path pattern
  6. nbrag_get_file_chunks      → Paginated chunks with scope/line metadata
  7. nbrag_get_raw_file         → Original file content without overlap
  8. nbrag_get_adjacent_chunks  → Adjacent chunks by chunk index
  9. nbrag_get_chunks_by_lines  → Chunks covering a line range
  10. nbrag_list                → List imported documents
  11. nbrag_stats               → Collection overview and config

启动方式:
  uvx nbrag                          # stdio (默认)
  uvx nbrag --transport streamable-http --port 9101  # HTTP
"""

import os

from pydantic import Field
from mcp.server.fastmcp import FastMCP
from nbrag.config import get_config
from nbrag.chunker import DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP
from nbrag import (
    ingest_path, search, list_documents, delete_document, get_stats,
    get_file_chunks, get_context_chunks, grep_knowledge, find_symbol_definition,
    find_files,
)

mcp = FastMCP("nbrag")


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
    path: str = Field(description="Absolute path to a file or directory. Directory imports all text files recursively"),
    collection_name: str = Field(description="Collection name (required, auto-created if not exists. Use nbrag_stats to see existing)"),
    chunk_size: int = Field(default=DEFAULT_CHUNK_SIZE, description="Chunk size in chars, default 1500, recommended 1000-2000"),
    chunk_overlap: int = Field(default=DEFAULT_CHUNK_OVERLAP, description="Chunk overlap in chars, default 200"),
    file_extensions: str = Field(default="", description="Comma-separated file extensions to include (e.g. 'py,md,html'). Empty = all text files"),
) -> str:
    """Ingest file or directory into knowledge base (chunking + embedding + indexing). Auto-creates collection if not exists.
    Supports any text file: code, docs, law, articles, manuals, etc. Python files get extra class/function scope enrichment.
    Use scripts or Python APIs for batch ingestion workflows."""
    cfg = get_config()
    ext_list = [e.strip() for e in file_extensions.split(",") if e.strip()] if file_extensions else None
    results, errors, skipped_count = ingest_path(path, collection_name, chunk_size, chunk_overlap, file_extensions=ext_list)

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


@mcp.tool()
def nbrag_help() -> str:
    """Short workflow guide for AI agents using nbrag without an external Skill.

    Call this when you are unsure which nbrag tool to use or how to chain tools.
    It returns the recommended retrieval workflow, path rules, and follow-up tools."""
    return "\n".join([
        "nbrag help: Agentic RAG workflow",
        "",
        "Important:",
        "- Use the actual exposed tool/function name you received from the host, not just the bare nbrag_* name.",
        "- Tool names may be prefixed in other agent frameworks, for example xxx_nbrag_search or mcp__xxx__nbrag_search.",
        "",
        "Default workflow:",
        "1. Unknown collection_name? call nbrag_stats.",
        "2. Knowledge/docs/law/manual/usage question? call nbrag_search_and_fetch first.",
        "3. Exact law articles, document headings, terms, phrases, API names, or constants? call nbrag_grep.",
        "4. Python source symbol body? call nbrag_find_definition (Python-only special case).",
        "5. Only have filename/path fragment? call nbrag_find_files to get full absolute file_path.",
        "6. Need more context? call nbrag_get_raw_file, nbrag_get_adjacent_chunks, or nbrag_get_chunks_by_lines.",
        "",
        "Python source workflow:",
        "- Use nbrag_search_and_fetch for concepts/examples; .py chunks include AST scope/signature metadata.",
        "- Use nbrag_grep for exact names/imports/constants/decorators/error strings.",
        "- Use nbrag_find_definition for complete Python .py symbols, then nbrag_get_raw_file for full source context.",
        "",
        "Rules:",
        "- Rewrite long user questions into focused search terms; try several terms before giving up.",
        "- file_path and filter_file_path must be full absolute paths returned by nbrag tools.",
        "- Collections are prepared by the user. If missing or empty, ask for the correct prepared collection_name.",
    ])


@mcp.tool()
def nbrag_search(
    query: str = Field(description="Search query (natural language question or keywords)"),
    collection_name: str = Field(description="Knowledge base name, i.e. 知识库名字 (use nbrag_stats to see available names)"),
    top_k: int = Field(default=5, description="Number of results to return"),
    use_rerank: bool = Field(default=True, description="Enable reranker for better accuracy (recommended)"),
    use_bm25: bool = Field(default=True, description="Enable multi-channel BM25 keyword matching + Weighted RRF fusion (recommended for precise names, Chinese terms, codes, article numbers)"),
    filter_file_path: str = Field(default="", description="Filter by full absolute file_path from search/list results. Basename is not accepted. BM25 auto-disabled when set"),
    include_content: bool = Field(default=True, description="Include chunk preview content. Set false for metadata-only lookup"),
    preview_chars: int = Field(default=-1, description="Max preview chars per result. -1 = generous auto limit, 0 = metadata only"),
) -> str:
    """Search knowledge base (知识库) for relevant content. Works for docs, law, manuals, articles, source code, or any imported text.

    IMPORTANT: If you don't know the collection_name, call nbrag_stats() first to see all available knowledge bases.
    collection_name = knowledge base name = 知识库名字 (e.g. user says "查项目文档知识库" → collection_name="project_docs").

    **PREFER nbrag_search_and_fetch** when the user asks 'how to do X', 'show me examples of X',
    or any knowledge/usage question — it auto-fetches complete file context and avoids fragmented chunks.
    **Use nbrag_search** only when you need fine-grained control (disable BM25/rerank),
    metadata-only lookup (include_content=False), or custom preview length.

    Python source workflow: .py chunks include AST scope/signature metadata, so source-code questions
    often need several tools. Use nbrag_search_and_fetch for concepts/examples, nbrag_grep for exact
    names/imports/constants/decorators/error strings, nbrag_find_definition for complete Python .py
    symbols, and nbrag_get_raw_file for full source context.

    TIP: Don't pass the user's raw long question directly. Rewrite it into focused search terms.
    e.g. user asks "试用期干了5个月不转正，1年合同合法吗" → query="试用期 最长期限 1年合同"
    Then do a second search: query="违法约定试用期 赔偿" to find penalty clauses.

    Result format: [1/5] filename chunk:X/Y line:N-M scope:xxx doc_id:xxx dist:0.1234 score:0.9876
    Key fields for follow-up: file_path (for nbrag_get_raw_file), doc_id + chunk_index (for nbrag_get_adjacent_chunks).

    After search, use these follow-up tools to dig deeper:
      - nbrag_grep(keyword, collection_name) → exact keyword/regex search (legal terms, article numbers, headings, API names)
      - nbrag_find_definition(symbol, collection_name) → Python source definition lookup (Python .py files ONLY)
      - nbrag_find_files(pattern, collection_name) → find the exact full file_path before path-filtered reads
      - nbrag_get_raw_file(file_path, collection_name) → full file content without chunk overlap
      - nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name) → expand context around a result

    If first search misses, try different keywords or use nbrag_grep for exact term matching."""
    cfg = get_config()
    top_k = _int_param(top_k, 5)
    use_rerank = _bool_param(use_rerank, True)
    use_bm25 = _bool_param(use_bm25, True)
    filter_file_path = _str_param(filter_file_path)
    include_content = _bool_param(include_content, True)
    preview_chars = _int_param(preview_chars, -1)
    path_filter = filter_file_path if filter_file_path else None
    if path_filter and not _is_absolute_file_path(path_filter):
        return "Error: filter_file_path must be a full absolute file_path returned by search/list tools."
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
        return f"No results (collection has {total} chunks, filter_file_path: {filter_file_path or 'none'})"

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


@mcp.tool()
def nbrag_search_and_fetch(
    query: str = Field(description="Search query (natural language question or keywords)"),
    collection_name: str = Field(description="Knowledge base name (use nbrag_stats to see available names)"),
    top_k: int = Field(default=5, description="Number of search results to return"),
    fetch_top_n_raw: int = Field(default=3, description="Auto-fetch original file content for top N results (0 to skip)"),
    context_lines: int = Field(default=100, description="Lines of context around matched chunk"),
    filter_file_path: str = Field(default="", description="Filter by full absolute file_path from search/list results. Basename is not accepted"),
) -> str:
    """Search + auto-fetch stored original content for top results in one call (saves a round-trip).

    **PREFER this over nbrag_search** when:
    - User asks 'how to do X', 'show me examples of X', 'what is X usage', or any knowledge/usage question.
    - You need both a quick answer AND the original file content/evidence backing it.
    - You want to avoid fragmented chunks and get complete file context immediately.

    **Use nbrag_search** only when:
    - You need fine-grained control (disable BM25, different chunk counts).
    - You only want metadata/summary, not full original content.

    Uses Vector + BM25 + RRF + rerank by default. When filter_file_path is set,
    BM25 is skipped and ChromaDB source-path filtering is used before rerank.
    Same doc_id results are grouped by file; distant ranked hits are fetched as separate line windows.

    Python source workflow: use this for concepts/examples and first evidence, then call nbrag_grep
    for exact names/imports/constants/decorators, nbrag_find_definition for complete Python .py
    symbols, and nbrag_get_raw_file for full source context."""
    cfg = get_config()
    top_k = _int_param(top_k, 5)
    fetch_top_n_raw = _int_param(fetch_top_n_raw, 3)
    context_lines = max(0, _int_param(context_lines, 100))
    filter_file_path = _str_param(filter_file_path)
    path_filter = filter_file_path if filter_file_path else None
    if path_filter and not _is_absolute_file_path(path_filter):
        return "Error: filter_file_path must be a full absolute file_path returned by search/list tools."
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
        return f"No results (collection has {total} chunks)"

    rerank_str = cfg.rerank.model if rerank_used else "off"
    bm25_str = "off" if path_filter else "on"
    header = f"[{collection_name}] {total} chunks | hybrid(bm25+vector): {bm25_str} | rerank: {rerank_str}"
    if filter_file_path:
        header += f" | filter_file_path: {filter_file_path}"
    lines = [header, ""]

    preview_limit = min(8000, 40000 // max(len(documents), 1))
    fetch_targets = {}
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


@mcp.tool()
def nbrag_grep(
    keyword: str = Field(description="Keyword or regex (e.g. '第四十二条', '侵权责任', 'Article 42', 'UserService', 'MAX_RETRIES')"),
    collection_name: str = Field(description="Knowledge base name (use nbrag_stats to see available names)"),
    max_results: int = Field(default=10, description="Maximum number of matches to return"),
    case_sensitive: bool = Field(default=False, description="Case-sensitive matching"),
    filter_file_path: str = Field(default="", description="Filter by full absolute file_path from search/list results. Basename is not accepted"),
    context_lines: int = Field(default=10, description="Context lines before/after each match (use 20+ for long clauses/sections or class headers)"),
) -> str:
    """Keyword/regex exact search in stored original files. Complements nbrag_search (semantic search).

    Use cases where nbrag_search falls short:
      - Law/docs/manuals: article numbers ('第四十二条'), legal terms ('侵权责任'), headings, error codes
      - General: specific dates, proper nouns, technical terms, exact phrases
      - Code: class/function names ('UserService'), constants ('MAX_RETRIES'), imports ('from myproject')

    Python source workflow: use nbrag_grep for exact names/imports/constants/decorators/error strings,
    then nbrag_find_definition for complete Python .py symbols and nbrag_get_raw_file for full source context.

    Tip: use context_lines=15 to see surrounding context around the match.
    Typical workflow: nbrag_search_and_fetch (find direction) → nbrag_grep (pinpoint exact terms) → nbrag_get_raw_file (full context)"""
    max_results = _int_param(max_results, 10)
    case_sensitive = _bool_param(case_sensitive, False)
    filter_file_path = _str_param(filter_file_path)
    context_lines = _int_param(context_lines, 10)
    path_filter = filter_file_path if filter_file_path else None
    if path_filter and not _is_absolute_file_path(path_filter):
        return "Error: filter_file_path must be a full absolute file_path returned by search/list tools."
    results = grep_knowledge(
        keyword, collection_name, max_results, case_sensitive,
        filter_file_path=path_filter, context_lines=context_lines,
    )

    if not results:
        return f"No matches for '{keyword}' (collection: {collection_name})"

    lines = [f"grep: '{keyword}' | collection_name: {collection_name} | {len(results)} match(es)", ""]
    for i, r in enumerate(results):
        lines.append(f"[{i + 1}/{len(results)}] {r['filename']} line:{r['line_number']} doc_id:{r['doc_id']}")
        lines.append(f"file_path: {r['source']}")
        lines.append(r["context"])
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def nbrag_find_definition(
    symbol: str = Field(description="Python symbol name (e.g. 'UserService', 'get_by_id', 'MyClass.__init__')"),
    collection_name: str = Field(description="Knowledge base name (use nbrag_stats to see available names)"),
    max_results: int = Field(default=3, description="Maximum number of definitions to return"),
) -> str:
    """Specialized Python source tool: find complete class/function/method definition by symbol name.
    Python .py files: AST parsing for exact boundaries + methods summary. Non-Python: regex fallback (limited).
    IMPORTANT: Only works on imported .py files. Code snippets inside .md/.txt docs cannot be AST-parsed.
    Default max_results=3 gives enough alternatives without flooding context. For common names in large libraries,
    start with max_results=1. For law/docs/manuals, use nbrag_grep instead.
    Python source workflow: first use nbrag_search_and_fetch or nbrag_grep to discover exact symbols,
    then use this tool for the complete definition and nbrag_get_raw_file for full source context."""
    max_results = _int_param(max_results, 3)
    results = find_symbol_definition(symbol, collection_name, max_results)

    if not results:
        return f"No definition found for '{symbol}' (collection: {collection_name}). Try nbrag_grep for a broader search."

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
            lines.append("Note: Regex fallback in non-Python file. For law/docs/manuals, use nbrag_grep for exact text search.")

        if r.get("methods_summary"):
            lines.append("methods:")
            lines.append(r["methods_summary"])

        lines.append("---")
        lines.append(r["definition"])
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def nbrag_find_files(
    pattern: str = Field(description="Filename or full-path regex/keyword to find exact file_path (e.g. '劳动合同法.md', 'manuals/install.md', 'history.py')"),
    collection_name: str = Field(description="Knowledge base name (use nbrag_stats to see available names)"),
    max_results: int = Field(default=20, description="Maximum number of matching files to return"),
    case_sensitive: bool = Field(default=False, description="Case-sensitive filename/path matching"),
) -> str:
    """Find imported files by filename or full file_path pattern.

    Works for documents, laws, manuals, articles, and source files. Use this when
    the user mentions a file name/path fragment and you need the exact
    full file_path before calling nbrag_get_raw_file, nbrag_get_file_chunks, or filter_file_path.
    This tool only lists matching files; it does not read file content."""
    pattern = _str_param(pattern)
    max_results = _int_param(max_results, 20)
    case_sensitive = _bool_param(case_sensitive, False)
    max_results = max(1, min(max_results, 100))
    results = find_files(pattern, collection_name, max_results, case_sensitive)

    if not results:
        return (f"No files match '{pattern}' (collection: {collection_name}). "
                f"Try nbrag_search_and_fetch for semantic discovery.")

    lines = [f"files: '{pattern}' | collection_name: {collection_name} | {len(results)} match(es)", ""]
    for i, r in enumerate(results):
        lines.append(
            f"[{i + 1}/{len(results)}] {r['filename']} | match:{r['match']} "
            f"| chunks:{r['chunk_count']} | doc_id:{r['doc_id']}"
        )
        lines.append(f"file_path: {r['file_path']}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def nbrag_get_file_chunks(
    file_path: str = Field(description="Full absolute file_path from nbrag_search/search_and_fetch/find_files/list results. Basename is not accepted"),
    collection_name: str = Field(description="Knowledge base name (use nbrag_stats to see available names)"),
    start_chunk: int = Field(default=0, description="Start chunk index (0-based) for pagination"),
    max_chunks: int = Field(default=10, description="Max chunks to return"),
) -> str:
    """Paginated view of file chunks with scope and line metadata.
    Requires the exact full file_path returned by nbrag_search/search_and_fetch/nbrag_find_files/nbrag_list.
    Note: chunks have overlap. For clean original content without overlap, use nbrag_get_raw_file instead."""
    start_chunk = _int_param(start_chunk, 0)
    max_chunks = _int_param(max_chunks, 10)
    result = get_file_chunks(
        file_path, collection_name, start_chunk, max_chunks,
        raw=False,
    )

    if not result.get("found"):
        return result.get("error", f"File not found: '{file_path}'")

    return _format_chunks_result(result)


@mcp.tool()
def nbrag_get_raw_file(
    file_path: str = Field(description="Full absolute file_path from nbrag_search/search_and_fetch/find_files/list results. Basename is not accepted"),
    collection_name: str = Field(description="Knowledge base name (use nbrag_stats to see available names)"),
    line_start: int = Field(default=-1, description="Start line (1-based), -1 for beginning"),
    line_end: int = Field(default=-1, description="End line (inclusive), -1 for end of file"),
) -> str:
    """Get stored original file content without chunk overlap. Recommended for viewing full file content.
    Requires the exact full file_path returned by nbrag_search/search_and_fetch/nbrag_find_files/nbrag_list.
    Supports line_start/line_end for extracting specific line ranges."""
    line_start = _int_param(line_start, -1)
    line_end = _int_param(line_end, -1)
    result = get_file_chunks(
        file_path, collection_name, 0, 0,
        raw=True, line_start=line_start, line_end=line_end,
    )

    if not result.get("found"):
        return result.get("error", f"File not found: '{file_path}'")

    return _format_raw_result(result)


def _format_raw_result(result):
    """Format stored original file result in compact English."""
    ls = result["line_start"]
    le = result["line_end"]
    tl = result["total_lines"]
    shown = le - ls + 1
    range_info = f"line:{ls}-{le}" + (f" ({shown}/{tl} lines)" if shown < tl else " (full)")
    lines = [
        f"original_file: {result['filename']} | doc_id:{result['doc_id']} | {tl} lines | {result['total_chunks']} chunks",
        f"file_path: {result['source']}",
        f"range: {range_info}",
        "",
        result["content"],
    ]
    if le < tl:
        lines.append(f"\n({tl - le} lines remaining, use line_start={le + 1} to continue)")
    return "\n".join(lines)


def _format_chunks_result(result):
    """Format chunks result in compact English."""
    tc = result["total_chunks"]
    lines = [
        f"file: {result['filename']} | doc_id:{result['doc_id']} | {tc} chunks | ~{result['total_lines']} lines",
        f"file_path: {result['source']}",
        "chunk_ranges: " + " ".join(f"[{s}-{e}]" for s, e in result["chunk_line_ranges"]),
        "",
    ]

    for chunk in result["chunks"]:
        idx = chunk["index"]
        scope = chunk["scope"]
        scope_str = f" scope:{scope}" if scope else ""
        lines.append(f"-- chunk {idx}/{tc} line:{chunk['line_start']}-{chunk['line_end']}{scope_str} --")
        lines.append(chunk["content"])
        lines.append("")

    sc = result["start_chunk"]
    ec = result["end_chunk"]
    if ec < tc:
        lines.append(f"(showing chunk {sc}-{ec - 1}, {ec - sc}/{tc} total. Use start_chunk={ec} for more)")
    else:
        lines.append(f"(all {tc} chunks shown)")

    return "\n".join(lines)


@mcp.tool()
def nbrag_get_adjacent_chunks(
    doc_id: str = Field(description="Document ID (from nbrag_search/nbrag_grep results)"),
    chunk_index: int = Field(description="Target chunk index (the X from 'chunk:X/Y' in results)"),
    collection_name: str = Field(description="Knowledge base name (use nbrag_stats to see available names)"),
    window: int = Field(default=3, description="Returns chunk_index ± window chunks"),
) -> str:
    """Get adjacent chunks around a specific chunk index, for expanding context of a search result.
    Requires doc_id and chunk_index from nbrag_search results (not file_path).
    Example: doc_id="abc123", chunk_index=3, window=2 → returns chunks 1-5"""
    chunk_index = _int_param(chunk_index, 0)
    window = _int_param(window, 3)
    result = get_context_chunks(
        doc_id, collection_name,
        chunk_index=chunk_index, window=window,
    )
    return _format_context_result(result, doc_id)


@mcp.tool()
def nbrag_get_chunks_by_lines(
    doc_id: str = Field(description="Document ID (from nbrag_search/nbrag_grep results)"),
    line_start: int = Field(description="Start line (1-based, from 'line:N-M' in results)"),
    line_end: int = Field(description="End line (inclusive, from 'line:N-M' in results)"),
    collection_name: str = Field(description="Knowledge base name (use nbrag_stats to see available names)"),
) -> str:
    """Get all chunks covering a line range, with scope metadata.
    vs nbrag_get_raw_file: this returns chunks (with scope but has overlap),
    nbrag_get_raw_file returns original content (no overlap but no scope).
    Example: doc_id="abc123", line_start=80, line_end=200"""
    line_start = _int_param(line_start, 1)
    line_end = _int_param(line_end, line_start)
    result = get_context_chunks(
        doc_id, collection_name,
        line_start=line_start, line_end=line_end,
    )
    return _format_context_result(result, doc_id)


def _format_context_result(result, doc_id):
    """Format context/adjacent chunks result in compact English."""
    if not result.get("found"):
        return result.get("error", f"doc_id '{doc_id}' not found")

    if not result.get("chunks"):
        return result.get("message", "No matching chunks")

    tc = result["total_chunks"]
    lines = [
        f"file: {result.get('filename', '?')} | doc_id:{doc_id} | {tc} chunks",
        f"file_path: {result['source']}",
        "",
    ]

    for chunk in result["chunks"]:
        scope = chunk["scope"]
        scope_str = f" scope:{scope}" if scope else ""
        lines.append(f"-- chunk {chunk['index']}/{tc} line:{chunk['line_start']}-{chunk['line_end']}{scope_str} --")
        lines.append(chunk["content"])
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def nbrag_list(
    collection_name: str = Field(description="Knowledge base name (知识库名字)(use nbrag_stats to see available names)"),
    limit: int = Field(default=100, description="Max docs to return (default 100, max 500)"),
    offset: int = Field(default=0, description="Skip first N docs (default 0). Use with limit for pagination"),
) -> str:
    """List documents in a knowledge base (filename, path, chunk count, doc_id).
    Returns paginated results by default (limit=100). Use offset for next page."""
    limit = _int_param(limit, 100)
    offset = _int_param(offset, 0)
    limit = max(1, min(limit, 500))
    docs = list_documents(collection_name, offset=offset, limit=limit)

    if not docs:
        if offset > 0:
            return f"collection '{collection_name}': no more docs after offset {offset}."
        return f"collection '{collection_name}' is empty."

    # 从 stats 获取总文档数（已缓存计数）
    all_stats = get_stats()
    total_docs = all_stats["collections"].get(collection_name, {}).get("doc_count", 0)
    total_chunks = sum(info["chunk_count"] for info in docs.values())
    shown = len(docs)
    has_more = offset + shown < total_docs

    header = (f"[{collection_name}] {total_docs} total docs, showing {offset + 1}-{offset + shown}"
              f" | {total_chunks} chunks in current page")
    if has_more:
        header += (f"\n  (more available: use offset={offset + limit} for next page, "
                   f"{total_docs - offset - shown} remaining)")
    lines = [header + "\n"]
    for did, info in docs.items():
        lines.append(f"  {info['filename']} | file_path: {info['source']} | {info['chunk_count']} chunks | doc_id:{did}")

    return "\n".join(lines)

# 删除文档：人工维护入口，不注册为 MCP tool。
def nbrag_delete(
    doc_id: str = Field(description="Document ID to delete (from nbrag_list results)"),
    collection_name: str = Field(description="Knowledge base name (use nbrag_stats to see available names)"),
) -> str:
    """Delete a document's vectors and cached files from the collection. Get doc_id from nbrag_list."""
    deleted, filename = delete_document(doc_id, collection_name)

    if deleted == 0:
        return f"Error: doc_id '{doc_id}' not found. Use nbrag_list to see available doc_ids."

    return f"Deleted: {filename} | {deleted} chunks | doc_id:{doc_id}"


@mcp.tool()
def nbrag_stats() -> str:
    """Get all available knowledge bases (知识库) and their stats. CALL THIS FIRST if you don't know the collection_name.
    Returns: all collection names, doc count, chunk count, embedding/rerank model, storage path, and optional collection profiles.
    Glossary: collection_name = knowledge base name = 知识库名字 (e.g. "project_docs", "law_docs").
    When a profile exists, it shows display_name / description / aliases to help AI choose the right collection.
    If you are unsure how to chain tools, call nbrag_help for a compact workflow guide.
    After getting collection names, use nbrag_search_and_fetch for most knowledge/usage questions.
    Use nbrag_search only when you need metadata-only results or fine-grained retrieval controls."""
    cfg = get_config()
    stats = get_stats()

    lines = [
        "RAG Stats",
        f"embed: {stats['embedding_model']} | rerank: {stats['rerank_model']}",
        f"data_dir: {stats['data_dir']}",
        f"chunk: size={cfg.chunking.chunk_size} overlap={cfg.chunking.chunk_overlap} (current config) | collections: {stats['collection_count']}",
        "",
    ]

    if not stats["collections"]:
        lines.append("(no prepared collections yet; ask the user for the correct collection_name)")
        return "\n".join(lines)

    for name, info in stats["collections"].items():
        if "error" in info:
            lines.append(f"- [{name}] error: {info['error']}")
            lines.append("")
        else:
            display_name = info.get("display_name", "")
            header = f"- [{name}] {display_name}" if display_name else f"- [{name}]"
            header += f" {info['doc_count']} docs, {info['chunk_count']} chunks"
            lines.append(header)
            description = info.get("description", "")
            aliases = info.get("aliases", [])
            tags = info.get("tags", [])
            if description:
                lines.append(f"  description: {description}")
            if aliases:
                lines.append(f"  aliases: {', '.join(aliases)}")
            if tags:
                lines.append(f"  tags: {', '.join(tags)}")
            if info["chunk_count"] == 0:
                lines.append("  empty")
            lines.append("")

    if lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


def main():
    """CLI entry point for uvx / python -m nbrag."""
    import argparse
    parser = argparse.ArgumentParser(
        description="nbrag — Agentic RAG MCP Server with 11 retrieval tools + help",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  nbrag                               # stdio transport (default)
  nbrag --transport streamable-http    # HTTP transport on port 9101
  nbrag --api-key sk-xxx              # specify API key directly
  NBRAG_API_KEY=sk-xxx nbrag         # API key via env var""",
    )
    parser.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default="stdio",
                        help="MCP transport mode (default: stdio)")
    parser.add_argument("--port", type=int, default=9101,
                        help="HTTP port (only for streamable-http/sse, default: 9101)")
    parser.add_argument("--api-key", dest="api_key",
                        help="Embedding/Rerank API key (or set NBRAG_API_KEY env var)")
    parser.add_argument("--db-path", dest="db_path",
                        help="ChromaDB storage path (default: ./rag_db)")
    parser.add_argument("--config",
                        help="Path to YAML config file")
    args = parser.parse_args()

    from nbrag.config import load_config
    load_config(args)

    if args.transport != "stdio":
        mcp.settings.port = args.port

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
