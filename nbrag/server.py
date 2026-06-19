"""
nbrag MCP Server — 10+ 个 Agentic RAG MCP 检索工具 + 1 个导航工具。

MCP tools (10+ retrieval/reading tools + help):
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

from pydantic import Field
from mcp.server.fastmcp import FastMCP

from nbrag import mcp_tools
from nbrag.chunker import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE

mcp = FastMCP("nbrag")


# nbrag_add_document 暂时不暴露为 MCP 函数，向量化一般由人工批量导入，而不是实时导入。
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
    return mcp_tools.nbrag_add_document(path, collection_name, chunk_size, chunk_overlap, file_extensions)


@mcp.tool()
def nbrag_help() -> str:
    """Short workflow guide for AI agents using nbrag without an external Skill.

    Call this when you are unsure which nbrag tool to use or how to chain tools.
    It returns the recommended retrieval workflow, path rules, and follow-up tools."""
    return mcp_tools.nbrag_help()


@mcp.tool()
def nbrag_search(
    query: str = Field(description="Focused search query: short natural-language query or concise phrase; do not mechanically split into space-separated keywords"),
    collection_name: str = Field(description="Knowledge base name = collection_name = 知识库名字 (call nbrag_stats if unknown)"),
    top_k: int = Field(default=5, description="Number of results to return"),
    use_rerank: bool = Field(default=True, description="Enable reranker for better accuracy (recommended)"),
    use_bm25: bool = Field(default=True, description="Enable multi-channel BM25 keyword matching + Weighted RRF fusion (recommended for precise names, Chinese terms, codes, article numbers)"),
    filter_file_path: str = Field(default="", description="Optional exact full absolute file_path returned by nbrag_search/search_and_fetch/find_files/list. Basename is not accepted. BM25 auto-disabled when set"),
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

    TIP: Prefer a focused query over a raw long question. Rewrite into a short natural-language
    query that keeps the core subject, constraints, and terminology.
    Do not mechanically convert the question into a space-separated keyword list.
    e.g. user asks "试用期干了5个月不转正，1年合同合法吗" → query="1年劳动合同试用期期限上限"
    Then do a second search: query="违法约定试用期赔偿金" to find penalty clauses.

    Result format: [1/5] filename chunk:X/Y line:N-M scope:xxx doc_id:xxx dist:0.1234 score:0.9876
    Key fields for follow-up: file_path (for nbrag_get_raw_file), doc_id + chunk_index (for nbrag_get_adjacent_chunks).

    Possible follow-up tools when the result suggests you need more evidence:
      - nbrag_grep(keyword, collection_name) → exact keyword/regex search (legal terms, article numbers, headings, API names)
      - nbrag_find_definition(symbol, collection_name) → Python source definition lookup (Python .py files ONLY)
      - nbrag_find_files(pattern, collection_name) → find the exact full file_path before path-filtered reads
      - nbrag_get_raw_file(file_path, collection_name) → full file content without chunk overlap
      - nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name) → expand context around a result

    If first search misses, consider changing the query, using exact-term grep, or checking collection_name."""
    return mcp_tools.nbrag_search(
        query,
        collection_name,
        top_k,
        use_rerank,
        use_bm25,
        filter_file_path,
        include_content,
        preview_chars,
    )


@mcp.tool()
def nbrag_search_and_fetch(
    query: str = Field(description="Focused search query: short natural-language query or concise phrase; do not mechanically split into space-separated keywords"),
    collection_name: str = Field(description="Knowledge base name = collection_name = 知识库名字 (call nbrag_stats if unknown)"),
    top_k: int = Field(default=5, description="Number of search results to return"),
    fetch_top_n_raw: int = Field(default=3, description="Auto-fetch original file content for top N results (0 to skip)"),
    context_lines: int = Field(default=100, description="Lines of context around matched chunk"),
    filter_file_path: str = Field(default="", description="Optional exact full absolute file_path returned by nbrag_search/search_and_fetch/find_files/list. Basename is not accepted"),
) -> str:
    """
    Default entry point for most user questions: search + auto-fetch stored original content for top results in one call.

    **PREFER this over nbrag_search** when:
    - User asks 'how to do X', 'show me examples of X', 'what is X usage', or any knowledge/usage question.
    - You need both a quick answer AND the original file content/evidence backing it.
    - You want to avoid fragmented chunks and get complete file context immediately.

    **Use nbrag_search** only when:
    - You need fine-grained control (disable BM25, different chunk counts).
    - You only want metadata/summary, not full original content.

    Query guidance: prefer a focused short natural-language query or concise phrase over a raw long question.
    Keep the core subject, constraints, and terminology; do not mechanically convert to space-separated keywords.

    Uses Vector + BM25 + RRF + rerank by default. When filter_file_path is set,
    BM25 is skipped and ChromaDB source-path filtering is used before rerank.
    Same doc_id results are grouped by file; distant ranked hits are fetched as separate line windows.

    Python source workflow: use this for concepts/examples and first evidence, then call nbrag_grep
    for exact names/imports/constants/decorators, nbrag_find_definition for complete Python .py
    symbols, and nbrag_get_raw_file for full source context.
    """
    return mcp_tools.nbrag_search_and_fetch(
        query=query,
        collection_name=collection_name,
        top_k=top_k,
        fetch_top_n_raw=fetch_top_n_raw,
        context_lines=context_lines,
        filter_file_path=filter_file_path,
    )


@mcp.tool()
def nbrag_grep(
    keyword: str = Field(description="Literal string or regex to search for in the original file content. This does byte-for-byte exact matching — NOT semantic/concept search. The text must appear verbatim (e.g. '第四十二条' finds the article number, but '试用期' will NOT match if the file says '见习期' instead). If in doubt, use nbrag_search_and_fetch instead (it understands concepts). Examples: '第四十二条', 'MAX_RETRIES', 'UserService', 'Article 42'"),
    collection_name: str = Field(description="Knowledge base name = collection_name = 知识库名字 (call nbrag_stats if unknown)"),
    max_results: int = Field(default=10, description="Maximum number of matches to return"),
    case_sensitive: bool = Field(default=False, description="Case-sensitive matching"),
    filter_file_path: str = Field(default="", description="Optional exact full absolute file_path returned by nbrag_search/search_and_fetch/find_files/list. Basename is not accepted"),
    context_lines: int = Field(default=10, description="Context lines before/after each match (use 20+ for long clauses/sections or class headers)"),
) -> str:
    """Literal string / regex exact search in stored original files. Performs byte-level matching (re.search) on raw file content — NOT semantic or concept search.

    ⚠️ CRITICAL: This tool only matches text that literally appears in the file. It does NOT understand concepts or paraphrases.
    For example, searching '空城计' will find NOTHING if the original text says '焚香操琴' and '大开四门' but never uses the exact word '空城计'.
    When in doubt about exact wording, use nbrag_search_and_fetch (semantic search) instead.

    Best for exact known strings:
      - 法律条文号 ('第四十二条'), 标题 headings, 专业术语 exact terms, 日期 dates, 编号 codes
      - Code: class/function names ('UserService'), constants ('MAX_RETRIES'), imports ('from myproject'), error strings

    NOT suitable for (use nbrag_search_and_fetch instead):
      - Conceptual queries ('劳动法对试用期有什么规定' → search, not grep)
      - Summarized plot points ('空城计', '草船借箭' — these may not appear verbatim)
      - Paraphrased or vague terms

    Python source workflow: after nbrag_search_and_fetch discovers relevant files, use nbrag_grep for exact
    names/imports/constants/decorators/error strings, then nbrag_find_definition for complete Python .py symbols,
    and nbrag_get_raw_file for full source context.

    Tip: use context_lines=15 to see surrounding context around the match.
    Common pattern when extra evidence is needed: semantic discovery → exact-term grep → raw file context."""
    return mcp_tools.nbrag_grep(keyword, collection_name, max_results, case_sensitive, filter_file_path, context_lines)


@mcp.tool()
def nbrag_find_definition(
    symbol: str = Field(description="Python symbol name (e.g. 'UserService', 'get_by_id', 'MyClass.__init__')"),
    collection_name: str = Field(description="Knowledge base name = collection_name = 知识库名字 (call nbrag_stats if unknown)"),
    max_results: int = Field(default=3, description="Maximum number of definitions to return"),
) -> str:
    """Specialized Python source tool: find complete class/function/method definition by symbol name.
    Python .py files: AST parsing for exact boundaries + methods summary. Non-Python: regex fallback (limited).
    IMPORTANT: Only works on imported .py files. Code snippets inside .md/.txt docs cannot be AST-parsed.
    Default max_results=3 gives enough alternatives without flooding context. For common names in large libraries,
    start with max_results=1. For law/docs/manuals, use nbrag_grep; other non-Python text is not a good fit for this tool.
    Python source workflow: first use nbrag_search_and_fetch or nbrag_grep to discover exact symbols,
    then use this tool for the complete definition and nbrag_get_raw_file for full source context."""
    return mcp_tools.nbrag_find_definition(symbol, collection_name, max_results)


@mcp.tool()
def nbrag_find_files(
    pattern: str = Field(description="Filename or full-path regex/keyword to find exact file_path (e.g. '劳动合同法.md', 'manuals/install.md', 'history.py')"),
    collection_name: str = Field(description="Knowledge base name = collection_name = 知识库名字 (call nbrag_stats if unknown)"),
    max_results: int = Field(default=20, description="Maximum number of matching files to return"),
    case_sensitive: bool = Field(default=False, description="Case-sensitive filename/path matching"),
) -> str:
    """Find imported files by filename or full file_path pattern.

    Works for documents, laws, manuals, articles, and source files. Use this when
    the user mentions a file name/path fragment and you need the exact
    full file_path before calling nbrag_get_raw_file, nbrag_get_file_chunks, or filter_file_path.
    This tool only lists matching files; it does not read file content.
    Next step: pass the returned file_path to nbrag_get_raw_file for original content,
    or to filter_file_path in nbrag_search/nbrag_search_and_fetch/nbrag_grep to narrow retrieval."""
    return mcp_tools.nbrag_find_files(pattern, collection_name, max_results, case_sensitive)


@mcp.tool()
def nbrag_get_file_chunks(
    file_path: str = Field(description="Exact full absolute file_path returned by nbrag_search/search_and_fetch/find_files/list. Basename or relative path is not accepted"),
    collection_name: str = Field(description="Knowledge base name = collection_name = 知识库名字 (call nbrag_stats if unknown)"),
    start_chunk: int = Field(default=0, description="Start chunk index (0-based) for pagination"),
    max_chunks: int = Field(default=10, description="Max chunks to return"),
) -> str:
    """Paginated view of file chunks with scope and line metadata.
    Requires the exact full file_path returned by nbrag_search/search_and_fetch/nbrag_find_files/nbrag_list.
    Note: chunks have overlap. For clean original content without overlap, use nbrag_get_raw_file instead.
    Next step: use nbrag_get_raw_file when quoting source evidence, or increase start_chunk for pagination."""
    return mcp_tools.nbrag_get_file_chunks(file_path, collection_name, start_chunk, max_chunks)


@mcp.tool()
def nbrag_get_raw_file(
    file_path: str = Field(description="Exact full absolute file_path returned by nbrag_search/search_and_fetch/find_files/list. Basename or relative path is not accepted"),
    collection_name: str = Field(description="Knowledge base name = collection_name = 知识库名字 (call nbrag_stats if unknown)"),
    line_start: int = Field(default=-1, description="Start line (1-based), -1 for beginning"),
    line_end: int = Field(default=-1, description="End line (inclusive), -1 for end of file"),
) -> str:
    """Get stored original file content without chunk overlap. Recommended for viewing full file content.
    Requires the exact full file_path returned by nbrag_search/search_and_fetch/nbrag_find_files/nbrag_list.
    Supports line_start/line_end for extracting specific line ranges.
    Next step: use returned file_path/doc_id with nbrag_grep or nbrag_get_adjacent_chunks if more surrounding context is needed."""
    return mcp_tools.nbrag_get_raw_file(file_path, collection_name, line_start, line_end)


@mcp.tool()
def nbrag_get_adjacent_chunks(
    doc_id: str = Field(description="Document ID returned by nbrag_search/search_and_fetch/grep results"),
    chunk_index: int = Field(description="Target chunk index (the X from 'chunk:X/Y' in results)"),
    collection_name: str = Field(description="Knowledge base name = collection_name = 知识库名字 (call nbrag_stats if unknown)"),
    window: int = Field(default=3, description="Returns chunk_index ± window chunks"),
) -> str:
    """Get adjacent chunks around a specific chunk index, for expanding context of a search result.
    Requires doc_id and chunk_index from nbrag_search results (not file_path).
    Example: doc_id="abc123", chunk_index=3, window=2 → returns chunks 1-5
    Next step: use nbrag_get_raw_file with the returned file_path for clean original content without overlap."""
    return mcp_tools.nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name, window)


@mcp.tool()
def nbrag_get_chunks_by_lines(
    doc_id: str = Field(description="Document ID returned by nbrag_search/search_and_fetch/grep results"),
    line_start: int = Field(description="Start line (1-based, from 'line:N-M' in results)"),
    line_end: int = Field(description="End line (inclusive, from 'line:N-M' in results)"),
    collection_name: str = Field(description="Knowledge base name = collection_name = 知识库名字 (call nbrag_stats if unknown)"),
) -> str:
    """Get all chunks covering a line range, with scope metadata.
    Use this when search results give line:N-M and you need all overlapping chunks for that range.
    vs nbrag_get_raw_file: this returns chunks (with scope but has overlap),
    nbrag_get_raw_file returns original content (no overlap but no scope).
    Example: doc_id="abc123", line_start=80, line_end=200
    Next step: use nbrag_get_raw_file with returned file_path for clean source text if quoting evidence."""
    return mcp_tools.nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name)


@mcp.tool()
def nbrag_list(
    collection_name: str = Field(description="Knowledge base name = collection_name = 知识库名字 (call nbrag_stats if unknown)"),
    limit: int = Field(default=100, description="Max docs to return (default 100, max 500)"),
    offset: int = Field(default=0, description="Skip first N docs (default 0). Use with limit for pagination"),
) -> str:
    """List documents in a knowledge base (filename, path, chunk count, doc_id).
    Use only when the user asks to browse/list imported documents, or when you need doc_id/file_path inventory.
    Returns paginated results by default (limit=100). Use offset for next page.
    Next step: pass returned file_path to nbrag_get_raw_file, or doc_id to nbrag_get_adjacent_chunks/get_chunks_by_lines."""
    return mcp_tools.nbrag_list(collection_name=collection_name, offset=offset, limit=limit)


# 删除文档：人工维护入口，不注册为 MCP tool。
def nbrag_delete(
    doc_id: str = Field(description="Document ID to delete (from nbrag_list results)"),
    collection_name: str = Field(description="Knowledge base name = collection_name = 知识库名字 (call nbrag_stats if unknown)"),
) -> str:
    """Delete a document's vectors and cached files from the collection. Get doc_id from nbrag_list."""
    return mcp_tools.nbrag_delete(doc_id, collection_name)


@mcp.tool()
def nbrag_stats() -> str:
    """Get all available knowledge bases (知识库) and their stats. CALL THIS FIRST if you don't know the collection_name.
    Capability model: nbrag is an Agentic RAG MCP retrieval toolkit, not a plain file search tool.
    It combines semantic vector search, multi-channel BM25 lexical search, Weighted RRF fusion, rerank,
    raw original-file evidence reading, and Python AST symbol lookup.
    Returns: all collection names, doc count, chunk count, embedding/rerank model, storage path, and optional collection profiles.
    Glossary: collection_name = knowledge base name = 知识库名字 (e.g. "project_docs", "law_docs").
    When a profile exists, it shows display_name / description / aliases to help AI choose the right collection.
    If you are unsure how to chain tools, call nbrag_help for a compact workflow guide.
    After getting collection names, use nbrag_search_and_fetch for most knowledge/usage questions.
    Use nbrag_search only when you need metadata-only results or fine-grained retrieval controls."""
    return mcp_tools.nbrag_stats()


def main():
    """CLI entry point for uvx / python -m nbrag."""
    import argparse
    parser = argparse.ArgumentParser(
        description="nbrag — Agentic RAG MCP Server with 10+ retrieval tools + help",
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
