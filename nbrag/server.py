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
    """Routing guide for AI agents using nbrag.

    Use this when you are starting with nbrag in the current task and collection/tool routing is not yet clear.
    Call it before retrieval when tool routing is not yet established.

    Typical cases:
    - this is your first nbrag call in the current task and collection/tool routing are still unclear
    - collection_name is still unknown
    - you need to choose between nbrag_stats(), nbrag_search_and_fetch(), nbrag_search(), nbrag_grep(), nbrag_find_definition(), or file/chunk follow-up tools
    - you need to decide whether the task is semantic retrieval, lexical retrieval, raw-text reading, chunk-context reading, or Python symbol-definition lookup
    - a previous retrieval attempt did not answer the question and you need to change strategy

    Usual next step:
    - if collection_name is unknown, call nbrag_stats() next
    - otherwise choose the retrieval or follow-up tool based on the returned routing guidance

    You usually do not need to call nbrag_help() again once the collection and retrieval path are already clear in the current task.

    Returned guidance explains:
    - when to use each nbrag tool
    - how to choose between semantic vs lexical retrieval
    - when to use raw-file vs chunk tools
    - stable follow-up fields such as file_path, doc_id, chunk_index, and line:N-M
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
    """Ingest file or directory into a knowledge base (chunking + embedding + indexing).

    Auto-creates the collection if it does not exist.
    Supports imported text files in general; Python files also get class/function scope enrichment.
    Use scripts or Python APIs for batch ingestion workflows."""
    return mcp_tools.nbrag_add_document(path, collection_name, chunk_size, chunk_overlap, file_extensions)



class FuncFields:
    query: str = Field(description="Main semantic query used by vector retrieval and reranking. Keep it as a natural-language question or statement that preserves the real retrieval target. Use ongoing dialogue or earlier retrieval results to resolve pronouns, restore omitted entities, fix obvious typos, or sharpen the event/relation/attribute wording once the target is clear. Let query stay semantically complete and readable; use bm25_query separately for lexical anchors.")
    collection_name: str = Field(description="Knowledge base name = collection_name = 知识库名字 (call nbrag_stats first if unknown)")
    top_k: int = Field(default=5, description="Number of ranked hits to return")
    filter_file_path: str = Field(default="", description="Optional exact full absolute file_path returned by nbrag tools. Basename or relative path is not accepted. When set, retrieval is narrowed to that stored file before ranking. In the current hybrid implementation, this narrows vector retrieval to that file and skips cross-file BM25 fusion.")
    bm25_query: str = Field(description="Lexical-anchor query used only by BM25. Build it from grounded wording likely to appear literally in the source: exact terms, aliases, article numbers, abbreviations, codes, API/class names, symbol names, titles, place names, event markers, error strings, or short phrases. Compared with query, bm25_query carries more source-facing lexical anchors and can combine multiple grounded anchors refined across turns from the user's wording, ongoing dialogue, or earlier hits. It does not affect vector retrieval or reranking.")
    include_content: bool = Field(default=True, description="Include chunk content in each hit. Set false for metadata-only lookup when you only need handles like file_path/doc_id/chunk_index")
    file_path: str = Field(description="Exact full absolute file_path returned by nbrag tools. Basename or relative path is not accepted")
    

@mcp.tool()
def nbrag_search(
    query: str = FuncFields.query,
    collection_name: str = FuncFields.collection_name,
    top_k: int = FuncFields.top_k,
    use_rerank: bool = Field(default=True, description="Enable reranker for better top-hit ordering (recommended)"),
    use_bm25: bool = Field(default=True, description="Enable multi-channel BM25 lexical retrieval + Weighted RRF fusion (recommended for precise names, aliases, Chinese terms, codes, article numbers, titles, and other exact-wording anchors)"),
    filter_file_path: str = FuncFields.filter_file_path,
    include_content: bool = FuncFields.include_content,
    bm25_query: str = FuncFields.bm25_query,
) -> str:
    """
    Search an imported knowledge base for relevant chunks.

    Use this after collection_name is already known and the retrieval path is already established.
    If this is your first nbrag call in the current task and collection/tool routing are still unclear, consult nbrag_help() first.
    If collection_name is still unknown, call nbrag_stats() first.

    Use this when you need ranked retrieval with fine-grained control over rerank, BM25, file filtering, or content inclusion.

    Query guidance:
    - query is the main semantic query used by vector retrieval and reranking; keep it as the real question/statement you want answered
    - query may be clarified across turns using ongoing dialogue or earlier hits, for example by restoring omitted entities, resolving pronouns, or sharpening the event/relation/attribute wording once the target is clear
    - bm25_query is the lexical-anchor query used only by BM25
    - compared with query, bm25_query should carry more source-facing lexical anchors and be improved across turns using grounded wording discovered from the conversation or earlier hits
    - a single bm25_query can combine multiple anchors when they all target the same evidence, such as exact terms, aliases, titles, article numbers, symbol names, place names, event markers, or repeated phrases from earlier results
    - setting bm25_query does not disable vector retrieval or reranking
    - setting filter_file_path narrows retrieval to one stored file; in the current hybrid implementation this also disables cross-file BM25 fusion

    Returned text is structured for follow-up calls. Each hit includes stable reusable fields such as:
    - chunk:X/Y
    - chunk_index:X
    - total_chunks:Y
    - line:N-M
    - doc_id:...
    - file_path:...

    Typical follow-up tools:
    - nbrag_get_raw_file(file_path, collection_name)
    - nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name)
    - nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name)
    - nbrag_grep(keyword, collection_name)
    - nbrag_find_definition(symbol, collection_name) for Python .py source
    """
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
    """BM25-only ranked retrieval.

    Use this to isolate lexical recall when exact terms matter: article numbers, abbreviations, error codes, identifiers, exact phrases, titles, aliases, or other high-precision wording.
    This is ranked retrieval, not literal line matching.
    A single bm25_query can combine multiple grounded lexical anchors when you want to test whether BM25 can target the right evidence by wording alone.

    Use instead:
    - nbrag_grep() for literal line-by-line matching in stored original text
    - nbrag_search_only_vector() to inspect semantic recall only
    - nbrag_search() or nbrag_search_and_fetch() for the normal mixed retrieval pipeline
    """
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
    """Vector-only ranked retrieval.

    Use this to isolate semantic recall when meaning, intent, or paraphrase matters more than exact lexical overlap.
    This is useful for inspecting embedding behavior without BM25 or reranking.
    Keep query semantically clear here; lexical anchor planning belongs in bm25_query on the mixed retrieval tools.

    Use instead:
    - nbrag_search_only_bm25() for lexical-only inspection
    - nbrag_grep() for literal line-by-line matching
    - nbrag_search() or nbrag_search_and_fetch() for the normal mixed retrieval pipeline
    """
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
    """Default one-call retrieval tool for most questions after routing is established.

    Use this when collection_name is already known and you want both ranked discovery and stored original-text evidence in the same call.
    This is the normal default once collection and retrieval routing are already clear.

    Use it for questions about meaning, usage, explanation, examples, or source-backed evidence.

    Query guidance:
    - query is the main semantic query used by vector retrieval and reranking; keep it as the real question/statement you want answered
    - query may be clarified across turns using ongoing dialogue or earlier hits, for example by restoring omitted entities, resolving pronouns, or sharpening the event/relation/attribute wording once the target is clear
    - bm25_query is the lexical-anchor query used only by BM25
    - compared with query, bm25_query should carry more source-facing lexical anchors and be improved across turns using grounded wording discovered from the conversation or earlier hits
    - a single bm25_query can combine multiple anchors when they all target the same evidence, such as exact terms, aliases, titles, article numbers, symbol names, place names, event markers, or repeated phrases from earlier results
    - setting bm25_query does not disable vector retrieval or reranking
    - setting filter_file_path narrows retrieval to one stored file; in the current hybrid implementation this also disables cross-file BM25 fusion

    Returned text has two sections:
    1. ranked search results
    2. auto-fetched stored original content

    Follow-up fields preserved in ranked hits include file_path, doc_id, chunk_index, and line:N-M.
    fetch_context_chars is a per-hit raw-context budget used during original-text expansion, not a final total response budget.

    Use nbrag_search() instead when you need fine-grained retrieval switches or metadata-only output.
    """
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
    """Literal text or regex search over stored original text, matched line by line.

    Use this when exact wording matters: article numbers, headings, exact phrases, API names, class/function names, constants, imports, decorators, error strings, or other precise text.
    This is for literal/regex matching after you already know or suspect the wording to target; it is not the tool for semantic discovery.
    Do not use it for concept search, synonym search, or paraphrase search.

    Returned text includes reusable follow-up fields such as matched_line, line_range, doc_id, and file_path.
    """
    return mcp_tools.nbrag_grep(keyword, collection_name, max_results, case_sensitive, filter_file_path, match_context_chars)


@mcp.tool()
def nbrag_find_definition(
    symbol: str = Field(description="Python symbol name such as 'UserService', 'get_by_id', or 'MyClass.__init__'"),
    collection_name: str = FuncFields.collection_name,
    max_results: int = Field(default=3, description="Maximum number of candidate definitions to return"),
) -> str:
    """Find complete Python class/function/method definitions by symbol name.

    This tool is specialized for Python .py source. When possible it uses AST-aware symbol boundaries.
    If a result comes from non-Python text, it should be clearly treated as regex fallback rather than as a strong symbol-definition result.

    Use this after search, grep, or prior retrieval context has already narrowed the symbol name.
    Returned text includes doc_id, file_path, line range, and the definition body.
    """
    return mcp_tools.nbrag_find_definition(symbol, collection_name, max_results)


@mcp.tool()
def nbrag_find_files(
    pattern: str = Field(description="Filename fragment or regex over filename/full path to discover the exact stored file_path (e.g. '劳动合同法.md', 'manuals/install.md', 'history.py')"),
    collection_name: str = FuncFields.collection_name,
    max_results: int = Field(default=20, description="Maximum number of matching files to return"),
    case_sensitive: bool = Field(default=False, description="Case-sensitive filename/path matching"),
) -> str:
    """Find the exact full file_path by filename or path fragment.

    Use this when nbrag tools return file info but you only have a partial filename or path.
    Returns the full absolute file_path that other tools require for file_path / filter_file_path parameters.
    This is a handle-discovery step, not a semantic retrieval step.

    Returned text includes matched file_path, filename, and doc_id.
    """
    return mcp_tools.nbrag_find_files(pattern, collection_name, max_results, case_sensitive)


@mcp.tool()
def nbrag_get_file_chunks(
    file_path: str = FuncFields.file_path,
    collection_name: str = FuncFields.collection_name,
    start_chunk: int = Field(default=0, description="Start chunk index (0-based) for pagination"),
    max_chunks: int = Field(default=10, description="Maximum chunks to return for this page"),
) -> str:
    """Paginated chunk view for a stored file.

    Use this when you want chunk-by-chunk browsing together with line and scope metadata.
    This is a chunk-based view and can include overlapping content by design.
    For overlap-free original text, use nbrag_get_raw_file() instead.

    Returned text includes filename, doc_id, file_path, total_chunks, total_lines, and per-chunk line/scope markers.
    """
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
    Compared with nbrag_get_raw_file(), this keeps chunk/scope structure but can include overlapping content by design.

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
    This is for collection inventory and handle discovery, not the default path for semantic question answering.

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
    """List available knowledge bases and collection routing hints.

    Use this when collection_name is still unknown, or when you need to inspect available collections before retrieval.

    This tool resolves collection routing only. It helps you choose the correct stable collection_name, but it does not choose the retrieval strategy for you.

    Returned text includes each collection's stable collection_name and document/chunk counts, and may also include display_name, description, aliases, tags, chunk_size, chunk_overlap, and last_ingested_at.

    After choosing collection_name:
    - use nbrag_search_and_fetch() for most semantic/source-backed questions
    - use nbrag_search() when you need finer retrieval control
    - use nbrag_grep() for exact wording
    - use nbrag_find_definition() only for Python .py symbol definitions
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
