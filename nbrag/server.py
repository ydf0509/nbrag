"""
nbrag MCP Server — 面向 AI 的通用知识库 Agentic RAG MCP。

Exposed MCP tools:
  - nbrag_help                 → Workflow guide + follow-up-handle reminder for AI agents
  - nbrag_search               → Hybrid search with fine-grained controls
  - nbrag_search_and_fetch     → Search + auto-fetch stored original content
  - nbrag_search_only_bm25     → BM25-only diagnostic search
  - nbrag_search_only_vector   → Vector-only diagnostic search
  - nbrag_grep                 → Line-by-line literal text / regex matching
  - nbrag_find_definition      → Find Python class/function definition by symbol name
  - nbrag_find_files           → Find exact full file_path by filename/path pattern
  - nbrag_get_file_chunks      → Paginated chunks with scope/line metadata
  - nbrag_get_raw_file         → Stored original file content without chunk overlap
  - nbrag_get_adjacent_chunks  → Adjacent chunks around a known hit
  - nbrag_get_chunks_by_lines  → Chunks covering a line range
  - nbrag_list                 → List imported documents in a collection
  - nbrag_stats                → Collection overview and routing hints

Design goals for AI agents:
  - prefer plain-text outputs with stable reusable handles
  - teach when to call each tool, not just what it does
  - make follow-up chaining explicit: file_path / doc_id / chunk_index / line ranges

启动方式:
  uvx nbrag
  uvx nbrag --transport streamable-http --port 9101
"""

from pydantic import Field
from mcp.server.fastmcp import FastMCP

from nbrag import mcp_tools
from nbrag.defaults import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_FETCH_CONTEXT_CHARS,
    DEFAULT_MATCH_CONTEXT_CHARS,
)

mcp = FastMCP("nbrag")


@mcp.tool()
def nbrag_help() -> str:
    """Workflow guide for AI agents using nbrag.

    Before calling any nbrag tool, this help function must be called first to know the usage strategy of nbrag.
    If you already know the best way to use nbrag, do not call this help function again.

    The returned text explains path rules, retrieval branching, and reusable follow-up handles
    such as file_path, doc_id, chunk_index, and line ranges.
    """
    return mcp_tools.nbrag_help()

# nbrag_add_document 暂时不暴露为 MCP 函数，向量化一般由人工批量导入，而不是实时导入。
def nbrag_add_document(
    path: str = Field(description="Absolute path to a file or directory. Directory imports all text files recursively"),
    collection_name: str = Field(description="Collection name (required, auto-created if not exists. Use nbrag_stats to see existing)"),
    chunk_size: int = Field(default=DEFAULT_CHUNK_SIZE, description=f"Chunk size in chars, default {DEFAULT_CHUNK_SIZE}, recommended 1000-2000"),
    chunk_overlap: int = Field(default=DEFAULT_CHUNK_OVERLAP, description=f"Chunk overlap in chars, default {DEFAULT_CHUNK_OVERLAP}"),
    file_extensions: str = Field(default="", description="Comma-separated file extensions to include (e.g. 'py,md,html'). Empty = all text files"),
) -> str:
    """Ingest file or directory into knowledge base (chunking + embedding + indexing). Auto-creates collection if not exists.
    Supports any text file: code, docs, law, articles, manuals, etc. Python files get extra class/function scope enrichment.
    Use scripts or Python APIs for batch ingestion workflows."""
    return mcp_tools.nbrag_add_document(path, collection_name, chunk_size, chunk_overlap, file_extensions)



class FuncFields:
    query: str = Field(description="Natural-language semantic query for vector retrieval and reranking. Use the user's wording, clarified from conversation context when needed; keep it a question or statement, not a keyword list. For lexical BM25 anchors, use bm25_query separately.")
    collection_name: str = Field(description="Knowledge base name = collection_name = 知识库名字 (call nbrag_stats first if unknown)")
    top_k: int = Field(default=5, description="Number of ranked hits to return")
    filter_file_path: str = Field(default="", description="Optional exact full absolute file_path returned by nbrag tools. Basename or relative path is not accepted. When set, retrieval is narrowed to that stored file before ranking. In the current hybrid implementation, this narrows vector retrieval to that file and skips cross-file BM25 fusion.")
    bm25_query: str = Field(default="", description="Short keyword version of the query for BM25. Typically pass the user's key terms as space-separated anchors. Does not affect vector retrieval or reranking.")
    include_content: bool = Field(default=True, description="Include chunk content in each hit. Set false for metadata-only lookup when you only need handles like file_path/doc_id/chunk_index")
    file_path: str = Field(description="Exact full absolute file_path returned by nbrag tools. Basename or relative path is not accepted")
    

@mcp.tool()
def nbrag_search(
    query: str = FuncFields.query,
    collection_name: str = FuncFields.collection_name,
    top_k: int = FuncFields.top_k,
    use_rerank: bool = Field(default=True, description="Enable reranker for better top-hit ordering (recommended)"),
    use_bm25: bool = Field(default=True, description="Enable multi-channel BM25 keyword matching + Weighted RRF fusion (recommended for precise names, Chinese terms, codes, article numbers)"),
    filter_file_path: str = FuncFields.filter_file_path,
    include_content: bool = FuncFields.include_content,
    bm25_query: str = FuncFields.bm25_query,
) -> str:
    """Search a knowledge base for relevant chunks from docs, laws, manuals, articles, source code, or any imported text.

    IMPORTANT:
    - If you do not know the collection_name, call nbrag_stats() first.
    - For most knowledge / usage / evidence questions, prefer nbrag_search_and_fetch() because it also returns stored original-file context.
    - Use nbrag_search() when you need fine-grained retrieval controls or metadata-only lookup.

    Query guidance:
    - Filling bm25_query does not disable vector retrieval or reranking; it only changes the lexical wording used by BM25.
    - If filter_file_path is set, current behavior narrows vector retrieval to that file and does not run cross-file BM25 fusion.

    Returned text is plain text but intentionally structured for follow-up calls.
    Each hit includes reusable markers such as:
    - chunk:X/Y
    - chunk_index:X
    - total_chunks:Y
    - line:N-M
    - doc_id:...
    - file_path:...
    and often score/dist/scope metadata.

    Typical follow-up tools:
    - nbrag_get_raw_file(file_path, collection_name) for overlap-free source text
    - nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name) to expand around a hit
    - nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name) when line:N-M is already known
    - nbrag_grep(keyword, collection_name) for exact literal text / regex evidence
    - nbrag_find_definition(symbol, collection_name) for Python .py definitions

    Python source workflow: use this for concepts/examples and first evidence, then use
    nbrag_grep for exact names/imports/constants/decorators, nbrag_find_definition for complete
    Python .py symbols, and nbrag_get_raw_file for full source context."""
    return mcp_tools.nbrag_search(
        query,
        collection_name,
        top_k,
        use_rerank,
        use_bm25,
        filter_file_path,
        include_content,
        bm25_query,
    )


@mcp.tool()
def nbrag_search_only_bm25(
    bm25_query: str = FuncFields.bm25_query,
    collection_name: str = FuncFields.collection_name,
    top_k: int = FuncFields.top_k,
    filter_file_path: str = FuncFields.filter_file_path,
    include_content: bool = FuncFields.include_content,
    ) -> str:
    """BM25-only lexical retrieval (fixes use_bm25=True, use_rerank=False, use_vector=False).

    Pick this when you want to isolate keyword-based recall for exact terminology,
    Chinese phrases, article numbers, abbreviations, error codes, or other precise strings.
    This is still ranked retrieval, not literal line matching.

    Switch instead to:
    - nbrag_grep() when the wording itself must appear literally in the stored text
    - nbrag_search_only_vector() when you want intent/meaning retrieval instead of exact lexical overlap
    - nbrag_search() or nbrag_search_and_fetch() for the normal mixed pipeline"""
    return mcp_tools.nbrag_search_only_bm25(
        bm25_query,
        collection_name,
        top_k,
        filter_file_path,
        include_content,
    )


@mcp.tool()
def nbrag_search_only_vector(
    query: str = FuncFields.query,
    collection_name: str = FuncFields.collection_name,
    top_k: int = FuncFields.top_k,
    filter_file_path: str = FuncFields.filter_file_path,
    include_content: bool = FuncFields.include_content,
) -> str:
    """Vector-only semantic retrieval (fixes use_bm25=False, use_rerank=False).

    Pick this when you want to isolate embedding-based recall for intent, meaning,
    paraphrases, or natural-language questions that may not share exact wording with the source.

    Switch instead to:
    - nbrag_search_only_bm25() for exact terms / article numbers / abbreviations
    - nbrag_grep() for literal line-by-line evidence
    - nbrag_search() or nbrag_search_and_fetch() for the normal mixed pipeline"""
    return mcp_tools.nbrag_search_only_vector(
        query,
        collection_name,
        top_k,
        filter_file_path,
        include_content,
    )


@mcp.tool()
def nbrag_search_and_fetch(
    query: str = FuncFields.query,
    collection_name: str = FuncFields.collection_name,
    top_k: int = FuncFields.top_k,
    fetch_top_n_raw: int = Field(default=3, description="Auto-fetch stored original content for the top N ranked hits. 0 disables fetching"),
    fetch_context_chars: int = Field(default=DEFAULT_FETCH_CONTEXT_CHARS, description=f"Per ranked hit: approximate total context chars around the matched line range, split about half before and half after. This is per result, not a total cap across all results. Default {DEFAULT_FETCH_CONTEXT_CHARS} means roughly {DEFAULT_FETCH_CONTEXT_CHARS // 2} chars before and {DEFAULT_FETCH_CONTEXT_CHARS // 2} chars after each hit"),
    filter_file_path: str = FuncFields.filter_file_path,
    bm25_query: str = FuncFields.bm25_query,
) -> str:
    """Default entry point for most user questions: hybrid retrieval + auto-fetched stored original content in one call.

    Prefer this over nbrag_search() when the user asks how to do something, wants examples,
    wants evidence, or when you need both ranked discovery and original-file context immediately.

    Query guidance:
    - Filling bm25_query does not disable vector retrieval or reranking; it only changes the lexical wording used by BM25.
    - If filter_file_path is set, current behavior narrows vector retrieval to that file and does not run cross-file BM25 fusion.

    The returned text has two AI-friendly sections:
    1. Ranked search results
    2. Auto-fetched original content

    Key follow-up handles are preserved in the ranked section: file_path, doc_id, chunk_index, and line:N-M.
    Auto-fetched raw snippets are grouped by file/doc_id, and overlapping windows are merged, so the number of fetched files may be smaller than fetch_top_n_raw.
    fetch_context_chars is a per-hit total context budget split about half before and half after, not a final total response budget. For example, top_k=10 with fetch_context_chars=10000 can request roughly 10000 chars around each hit before merging, so avoid oversized values unless the user explicitly needs very large context.

    Use nbrag_search() instead only when you need fine-grained retrieval switches or metadata-only output.

    Python source workflow: use this for concepts/examples and first evidence, then use
    nbrag_grep for exact names/imports/constants/decorators, nbrag_find_definition for complete
    Python .py symbols, and nbrag_get_raw_file for full source context."""
    return mcp_tools.nbrag_search_and_fetch(
        query=query,
        collection_name=collection_name,
        top_k=top_k,
        fetch_top_n_raw=fetch_top_n_raw,
        fetch_context_chars=fetch_context_chars,
        filter_file_path=filter_file_path,
        bm25_query=bm25_query,
    )


@mcp.tool()
def nbrag_grep(
    keyword: str = Field(description="Plain text or regex pattern to search in stored original text lines. This is line-by-line literal/regex matching, not semantic search. Plain text only matches wording that literally appears in the source text. If you pass a valid regex, regex rules apply. If you need literal matching for regex metacharacters, escape them first. When unsure about exact wording, use nbrag_search_and_fetch instead"),
    collection_name: str = FuncFields.collection_name,
    max_results: int = Field(default=10, description="Maximum number of matches to return"),
    case_sensitive: bool = Field(default=False, description="Case-sensitive matching"),
    filter_file_path: str = FuncFields.filter_file_path,
    match_context_chars: int = Field(default=DEFAULT_MATCH_CONTEXT_CHARS, description=f"Per match: approximate total context chars around the matched line range, split about half before and half after. This is per match, not a total cap across all matches. Default {DEFAULT_MATCH_CONTEXT_CHARS} means roughly {DEFAULT_MATCH_CONTEXT_CHARS // 2} chars before and {DEFAULT_MATCH_CONTEXT_CHARS // 2} chars after each match"),
) -> str:
    """Literal text / regex search in stored original text, matched line by line.

    Use this for exact wording in general text before treating it as a code tool:
    - Law/docs/manuals: article numbers, headings, exact terms, dates, codes.
    - Code: API names, class/function names, constants, imports, decorators, exact error strings.

    Do not use it for concept search, synonym search, or paraphrase search.

    match_context_chars is a per-match total context budget split about half before and half after, not a final total response budget. For example,
    max_results=10 with match_context_chars=10000 can request roughly 10000 chars around each match, so avoid oversized values unless the user explicitly needs very large context.

    Returned text includes reusable markers such as matched_line, line_range, doc_id, and file_path.
    If no matches are found, the tool returns adjustment hints that usually point you back to semantic search
    or to refining the literal pattern."""
    return mcp_tools.nbrag_grep(keyword, collection_name, max_results, case_sensitive, filter_file_path, match_context_chars)


@mcp.tool()
def nbrag_find_definition(
    symbol: str = Field(description="Python symbol name such as 'UserService', 'get_by_id', or 'MyClass.__init__'"),
    collection_name: str = FuncFields.collection_name,
    max_results: int = Field(default=3, description="Maximum number of candidate definitions to return"),
) -> str:
    """Specialized Python source tool: find complete class/function/method definitions by symbol name.

    Python .py files use AST-aware boundaries when possible. Non-Python files may return a clearly labeled regex fallback,
    which is weaker and should be verified with grep/raw file context.

    Use this after search or grep has already narrowed down the symbol name.
    For law/docs/manuals, use nbrag_grep or nbrag_search_and_fetch instead.
    Returned text includes line ranges, doc_id, file_path, and the definition body itself."""
    return mcp_tools.nbrag_find_definition(symbol, collection_name, max_results)


@mcp.tool()
def nbrag_find_files(
    pattern: str = Field(description="Filename fragment or regex over filename/full path to discover the exact stored file_path (e.g. '劳动合同法.md', 'manuals/install.md', 'history.py')"),
    collection_name: str = FuncFields.collection_name,
    max_results: int = Field(default=20, description="Maximum number of matching files to return"),
    case_sensitive: bool = Field(default=False, description="Case-sensitive filename/path matching"),
) -> str:
    """Find imported files by filename or path pattern.

    Use this when you only know a file name/path fragment and need the exact full absolute file_path
    before calling nbrag_get_raw_file(), nbrag_get_file_chunks(), or using filter_file_path in retrieval tools.

    Returned text lists filename, doc_id, chunk counts, a short match summary, and the exact file_path to reuse."""
    return mcp_tools.nbrag_find_files(pattern, collection_name, max_results, case_sensitive)


@mcp.tool()
def nbrag_get_file_chunks(
    file_path: str = FuncFields.file_path,
    collection_name: str = FuncFields.collection_name,
    start_chunk: int = Field(default=0, description="Start chunk index (0-based) for pagination"),
    max_chunks: int = Field(default=10, description="Maximum chunks to return for this page"),
) -> str:
    """Paginated chunk view for a stored file.

    Use this when you want chunk-by-chunk browsing with scope and line metadata.
    Chunks may overlap. For clean original text without overlap, use nbrag_get_raw_file() instead.

    Returned text includes filename, doc_id, file_path, total_chunks, total_lines,
    a chunk range summary, and per-chunk line/scope markers."""
    return mcp_tools.nbrag_get_file_chunks(file_path, collection_name, start_chunk, max_chunks)


@mcp.tool()
def nbrag_get_raw_file(
    file_path: str = FuncFields.file_path,
    collection_name: str = FuncFields.collection_name,
    line_start: int = Field(default=-1, description="Start line (1-based). Use -1 for the beginning"),
    line_end: int = Field(default=-1, description="End line (inclusive). Use -1 for the end of file"),
) -> str:
    """Return the stored original-file snapshot without chunk overlap.

    This reads the original text captured in the knowledge base at ingestion time; it is not a live filesystem refresh.
    Use it when you need clean quoting, broader source context, or a specific line range.

    Returned text includes original_file, file_path, doc_id, total_lines, and the returned line range."""
    return mcp_tools.nbrag_get_raw_file(file_path, collection_name, line_start, line_end)


@mcp.tool()
def nbrag_get_adjacent_chunks(
    doc_id: str = Field(description="Document ID returned by nbrag tools such as search/search_and_fetch/grep/list"),
    chunk_index: int = Field(description="Target chunk index from a search/search_and_fetch result field like chunk:X/Y or chunk_index:X"),
    collection_name: str = FuncFields.collection_name,
    window: int = Field(default=3, description="Return chunk_index ± window chunks"),
) -> str:
    """Expand chunk context around a known ranked hit.

    Use this when nbrag_search() or nbrag_search_and_fetch() already gave you doc_id + chunk_index
    and you want nearby chunks. grep results may provide doc_id, but grep alone does not provide chunk_index,
    so grep output is not sufficient by itself for this tool.

    Returned text includes file_path, total_chunks, and the adjacent chunks with line markers."""
    return mcp_tools.nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name, window)


@mcp.tool()
def nbrag_get_chunks_by_lines(
    doc_id: str = Field(description="Document ID returned by nbrag tools such as search/search_and_fetch/grep/list"),
    line_start: int = Field(description="Start line (1-based), usually copied from a prior line:N-M style result"),
    line_end: int = Field(description="End line (inclusive), usually copied from a prior line:N-M style result"),
    collection_name: str = FuncFields.collection_name,
) -> str:
    """Return all chunks covering a line range.

    Use this when you already know a line range and want chunk-level context with scope metadata.
    Compared with nbrag_get_raw_file(), this keeps chunk/scope structure but may contain overlap.

    Returned text includes doc_id, file_path, requested line_range, and all overlapping chunks."""
    return mcp_tools.nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name)


@mcp.tool()
def nbrag_list(
    collection_name: str = FuncFields.collection_name ,
    limit: int = Field(default=100, description="Maximum documents to return for this page (default 100, usually keep <= 500)"),
    offset: int = Field(default=0, description="Skip the first N documents for pagination"),
) -> str:
    """List imported documents in a collection.

    Use this when the user explicitly wants to browse imported documents,
    or when you need inventory handles such as doc_id and file_path before a follow-up read.

    Returned text includes per-document doc_id, filename, chunk_count, total_chunks, and file_path."""
    return mcp_tools.nbrag_list(collection_name=collection_name, offset=offset, limit=limit)


# 删除文档：人工维护入口，不注册为 MCP tool。
def nbrag_delete(
    doc_id: str = Field(description="Document ID to delete (from nbrag_list results)"),
    collection_name: str = FuncFields.collection_name,
    ) -> str:
    """Delete a document's vectors and cached files from the collection. Get doc_id from nbrag_list."""
    return mcp_tools.nbrag_delete(doc_id, collection_name)


@mcp.tool()
def nbrag_stats() -> str:
    """List available knowledge bases . CALL THIS when collection_name is unknown.
    
    Before calling the nbrag_stats tool, it is necessary to ensure that the nbrag_help tool has been called in order to know the usage policy guidelines for nbrag

    Returned text includes each collection's stable name plus docs/chunks counts,
    and may also include display_name, description, aliases, tags, chunk_size, chunk_overlap, and last_ingested_at.
    Use these fields to choose the right collection before retrieval.

    """
    return mcp_tools.nbrag_stats()


def main():
    """CLI entry point for uvx / python -m nbrag."""
    import argparse
    parser = argparse.ArgumentParser(
        description="nbrag — Agentic RAG MCP Server with retrieval tools + help",
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
