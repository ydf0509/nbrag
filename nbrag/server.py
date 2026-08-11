"""
nbrag MCP Server — 面向 AI 的通用知识库 Agentic RAG MCP。

Exposed MCP tools:
  - nbrag_help                 → Workflow guide + follow-up-handle reminder for AI agents
  - nbrag_retrieve             → Default retrieval: hybrid search + auto-expand original-text context
  - nbrag_retrieve_no_expand   → Hybrid search with fine-grained controls, no auto-expand
  - nbrag_retrieve_only_bm25   → BM25-only diagnostic retrieval
  - nbrag_retrieve_only_vector → Vector-only diagnostic retrieval
  - nbrag_grep                 → Line-by-line literal text / regex matching
  - nbrag_find_definition      → Find Python class/function definition by symbol name
  - nbrag_find_files           → Find exact full file_path by filename/path pattern
  - nbrag_get_file_chunks      → Paginated chunks with scope/line metadata
  - nbrag_read_more_original_text         → Stored original file content without chunk overlap
  - nbrag_get_adjacent_chunks  → Adjacent chunks around a known hit
  - nbrag_get_chunks_by_lines  → Chunks covering a line range
  - nbrag_list                 → List imported documents in a collection
  - nbrag_stats                → Collection overview and routing hints

Design goals for AI agents:
  - return XML-structured text with stable reusable handles and plain-text handle surfacing
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
    """
nbrag tool usage guide for AI agents.
在调用其他 nbrag工具之前，必须先确保你曾经已经调用nbrag_help获取了使用指南，以便知道如何对nbrag的一系列工具正确的配合使用。

nbrag 是 agentic rag，由llm主动调用主动根据上下文构造向量检索语句和bm25检索语句，多轮检索,不是那种传统一轮rag。
nbrag 使llm能根据chunk块，自动以及llm自主扩大阅读范围，吊打任何传统rag，可以完成横跨多个文件的多跳检索的极端复杂任务推理。
所以你必须先调用nbrag_help获取使用指南，才能正确使用nbrag的一系列工具。

说明：
nbrag_help 返回的静态内容，是提供给ai的使用指南，返回不会发生变化，所以你只需要调用一次即可。

nbrag_help() explains how to use nbrag as a knowledge-retrieval workflow rather
than a one-shot search tool. It establishes:

- which tool fits the goal: semantic search, exact grep, Python definition
  lookup, raw-file reading, or chunk expansion;
- the distinct roles of query (semantic intent) and bm25_query (source-facing
  lexical anchors);
- the boundary between truncated RAG chunks, auto-fetched original-text excerpts,
  and complete stored original text;
- safe reuse of follow-up handles: file_path, doc_id, chunk_index, line_start,
  and line_end.

When in doubt, call nbrag_help().
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
    query: str = Field(description="主语义查询，用于向量检索和重排序。写成完整的自然语言问句，不要堆关键词；语义越完整召回越准。精确关键词匹配交给 bm25_query。")
    collection_name: str = Field(description="Knowledge base name = collection_name = 知识库名字 (call nbrag_stats() first if unknown)")
    top_k: int = Field(default=20, description="返回的命中数量。通常保持默认值即可，无需修改。")
    filter_file_path: str = Field(default="", description="Optional exact full absolute file_path returned by nbrag tools. Basename or relative path is not accepted. When set, retrieval is narrowed to that stored file before ranking. Value comes from the file_path handle returned by nbrag tools.")
    bm25_query: str = Field(description="可选的精确关键词查询，仅用于 BM25 检索。提供时填原知识库中可能原样出现的核心关键词：术语、别名、编号、缩写、API/类名、标题等。bm25_query可以传递多个核心关键词 用空格隔开，以提高召回相关性")
    include_content: bool = Field(default=True, description="Include chunk content in each hit. Set false for metadata-only lookup when you only need handles like file_path/doc_id/chunk_index.")
    file_path: str = Field(description="Exact full absolute file_path returned by nbrag tools. Basename or relative path is not accepted")
    

@mcp.tool()
def nbrag_retrieve_no_expand(
    query: str = FuncFields.query,
    collection_name: str = FuncFields.collection_name,
    top_k: int = FuncFields.top_k,
    use_rerank: bool = Field(default=True, description="Enable rag reranker for better top-hit ordering (recommended)"),
    use_bm25: bool = Field(default=True, description="Enable multi-channel BM25 lexical retrieval + Weighted RRF fusion (recommended for precise names, aliases, Chinese terms, codes, article numbers, titles, and other exact-wording anchors)"),
    filter_file_path: str = FuncFields.filter_file_path,
    include_content: bool = FuncFields.include_content,
    bm25_query: str = FuncFields.bm25_query,
) -> str:
    """
    使用这个工具之前，请确保调用过 nbrag_help 获取了使用指南，请确保调用过 nbrag_stats 获取了有哪些知识库名字(collection_name)，以便你知道如传参。
    """
    return mcp_tools.nbrag_retrieve_no_expand(
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
def nbrag_retrieve_only_bm25(
    bm25_query: str = FuncFields.bm25_query,
    collection_name: str = FuncFields.collection_name,
    top_k: int = FuncFields.top_k,
    filter_file_path: str = FuncFields.filter_file_path,
    include_content: bool = FuncFields.include_content,
) -> str:
    """BM25-only ranked retrieval.
    如果用户是为了验证bm25检索和向量语义检索哪个召回质量更好，要求你使用bm25检索时候，就用这个工具。
    """
    return mcp_tools.nbrag_retrieve_only_bm25(
        bm25_query,
        collection_name,
        top_k,
        filter_file_path,
        include_content,
    )


@mcp.tool()
def nbrag_retrieve_only_vector(
    query: str = FuncFields.query,
    collection_name: str = FuncFields.collection_name,
    top_k: int = FuncFields.top_k,
    filter_file_path: str = FuncFields.filter_file_path,
    include_content: bool = FuncFields.include_content,
) -> str:
    """Vector-only ranked retrieval.
    如果用户是为了验证bm25检索和向量语义检索哪个召回质量更好，要求你使用rag语义向量检索时候，就用这个工具。
    """
    return mcp_tools.nbrag_retrieve_only_vector(
        query,
        collection_name,
        top_k,
        filter_file_path,
        include_content,
    )


@mcp.tool()
def nbrag_retrieve(
    query: str = FuncFields.query,
    collection_name: str = FuncFields.collection_name,
    top_k: int = FuncFields.top_k,
    expand_top_n: int = Field(default=5, description="自动对前 expand_top_n 个最相关的 ranked hit 的前后文字内容进行扩展"),
    expand_context_chars: int = Field(default=DEFAULT_FETCH_CONTEXT_CHARS, description=f"Per ranked hit: approximate original-text context-character budget around the matched line range, split roughly 1:2 before and after (1 part before, 2 parts after). This is per eligible hit, not a total response cap."),
    filter_file_path: str = FuncFields.filter_file_path,
    bm25_query: str = FuncFields.bm25_query,
) -> str:
    """nbrag的默认检索工具，适用于大多数问题的默认键检索工具，是最核心工具。
    使用这个工具之前，请确保调用过 nbrag_help 获取了使用指南，请确保调用过 nbrag_stats 获取了有哪些知识库名字(collection_name)，以便你知道如传参。

    Returned text has two sections:
    1. ranked retrieval results
    2. auto-expanded stored original-text context blocks

    `<nbrag_follow_up>` appears before the result data. `<nbrag_ranked_hit>` contains one `<nbrag_chunk_content>` RAG chunk whose original-text context stops at chunk boundaries. Each `<nbrag_original_text_expand>` contains a bounded, overlap-free auto-expanded original-text block in `<nbrag_original_text_content>` and carries file_path, doc_id, line_start, and line_end. Neither entity is a complete file.

    如果某个 ranked hit 对回答有用，就把它的 line_start 记作 hit_line_start，再用 file_path 调用 nbrag_read_more_original_text，读取 line_start=max(1, hit_line_start-200) 到 line_end=hit_line_start+400 的连续原文。如果缺少前文，就减小 line_start；如果缺少后文，就增大 line_end。

    大文件和大范围内容也使用 nbrag_read_more_original_text 按连续 line ranges 阅读。

    expand_context_chars 是对前 expand_top_n 个最相关的 ranked hit 的前后内容的扩展字符数量。

    Use nbrag_retrieve_no_expand() instead when you need fine-grained retrieval switches or metadata-only output.
    """
    return mcp_tools.nbrag_retrieve(
        query=query,
        collection_name=collection_name,
        top_k=top_k,
        expand_top_n=expand_top_n,
        expand_context_chars=expand_context_chars,
        filter_file_path=filter_file_path,
        bm25_query=bm25_query,
    )


@mcp.tool()
def nbrag_grep(
    keyword: str = Field(description="Plain text or regex pattern to search in stored original text lines. This is line-by-line literal/regex matching, not semantic search. Plain text only matches wording that literally appears in the source text. If you pass a valid regex, regex rules apply. If you need literal matching for regex metacharacters, escape them first. When unsure about exact wording, use nbrag_retrieve instead"),
    collection_name: str = FuncFields.collection_name,
    max_results: int = Field(default=10, description="Maximum number of matches to return"),
    case_sensitive: bool = Field(default=False, description="Case-sensitive matching"),
    filter_file_path: str = FuncFields.filter_file_path,
    match_context_chars: int = Field(default=DEFAULT_MATCH_CONTEXT_CHARS, description=f"Per match: approximate total context chars around the matched line range, split roughly 1:2 before and after (1 part before, 2 parts after). This is per match, not a total cap across all matches."),
) -> str:
    """Literal text or regex search over stored original text, matched line by line.

    Use this when exact wording matters: article numbers, headings, exact phrases, API names, class/function names, constants, imports, error strings, or other precise text.
    This is for literal/regex matching after you already know or suspect the wording to target; it is not the tool for semantic discovery.
    Use nbrag_retrieve() for concept, synonym, or paraphrase retrieval.

    Each `<nbrag_match>` exposes file_path, doc_id, line_start, and line_end as XML attributes
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
    Each `<nbrag_definition>` exposes doc_id, file_path, and line bounds as XML attributes. `<nbrag_definition_content>` is an AST-aware Python definition body; regex_fallback is only a candidate text match.
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

    Each `<nbrag_file>` exposes matched file_path, filename, doc_id, and total_chunks as XML attributes.
    """
    return mcp_tools.nbrag_find_files(pattern, collection_name, max_results, case_sensitive)





@mcp.tool()
def nbrag_read_more_original_text(
    file_path: str = FuncFields.file_path,
    collection_name: str = FuncFields.collection_name,
    line_start: int | None = Field(default=None, description="Optional start line (1-based) of the stored-original-text reading window. For a useful ranked hit, reuse its line_start as line_start=max(1, hit line_start-200). Omit it to start at the beginning of the stored file."),
    line_end: int | None = Field(default=None, description="Optional end line (1-based, inclusive) of the stored-original-text reading window. For a useful ranked hit, set line_end=hit line_start+400. Omit it to end at the last line of the stored file."),
) -> str:
    """
    根据文件名和行号范围获取某个文件的原始内容。
    如果某个 ranked hit 对回答有用，就把它的 line_start 记作 hit_line_start，再读取 line_start=max(1, hit_line_start-200) 到 line_end=hit_line_start+400 的连续原文。
    如果缺少前文，就减小 line_start；如果缺少后文，就增大 line_end。大文件和大范围内容也按连续 line ranges 读取。
    这个是 nbrag工具中仅次于 nbrag_retrieve 的第二重要的工具，用于获取文件的原始内容。 
    因为rag知识库的chunk是截断的，并且每个相邻chunk之间有重叠的文字内容，所以这个比 `nbrag_get_file_chunks` 和 `nbrag_get_adjacent_chunks` `nbrag_get_chunks_by_lines` 更适合阅读某个hit chunk的前后范围的原文。

    This reads the stored original text snapshot captured in the knowledge base at ingestion time; it is not a live filesystem refresh.
    Returned text includes file_path, doc_id, total_lines, line_start, and line_end as XML attributes, with original text under `<nbrag_original_text_content>`.
    Unlike chunk-based tools, this returns overlap-free stored original text snapshot, not a truncated chunk.
    
    """
    return mcp_tools.nbrag_read_more_original_text(file_path, collection_name, line_start, line_end)

@mcp.tool()
def nbrag_get_file_chunks(
    file_path: str = FuncFields.file_path,
    collection_name: str = FuncFields.collection_name,
    start_chunk: int = Field(default=0, description="Start chunk index (0-based) for pagination; same value space as the chunk_index handle. Use it as a cursor: to read the next page, pass the last chunk_index seen + 1."),
    max_chunks: int = Field(default=10, description="Maximum chunks to return for this page"),
) -> str:
    """Paginated chunk view for a stored file.

    Use this for paginated inspection of chunk boundaries, scope metadata, overlap, or chunking quality.
    Use nbrag_read_more_original_text() for continuous original text, large files, and wider source context.
    Adjacent chunks in this view overlap by the ingestion overlap configuration.

    Returned text exposes pagination metadata on the root and `<pagination>` tags, plus one `<nbrag_chunk>` per chunk with reusable handles as XML attributes. Each `<nbrag_chunk_content>` always contains one RAG chunk, bounded by that chunk's boundaries rather than complete original text.
    """
    return mcp_tools.nbrag_get_file_chunks(file_path, collection_name, start_chunk, max_chunks)

@mcp.tool()
def nbrag_get_adjacent_chunks(
    doc_id: str = Field(description="Document ID returned by nbrag tools such as retrieve/retrieve_no_expand/grep/list"),
    chunk_index: int = Field(description="Target chunk index from a prior `<nbrag_ranked_hit>` or `<nbrag_chunk>` metadata block. Use the chunk_index attribute returned by those entities."),
    collection_name: str = FuncFields.collection_name,
    window: int = Field(default=3, description="Return chunk_index ± window chunks"),
) -> str:
    """Inspect chunk structure around a known ranked hit.
    Use nbrag_read_more_original_text() for wider source context and large files.
    """
    return mcp_tools.nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name, window)


@mcp.tool()
def nbrag_get_chunks_by_lines(
    doc_id: str = Field(description="Document ID returned by nbrag tools such as retrieve/retrieve_no_expand/grep/list"),
    line_start: int = Field(description="Start line (1-based)"),
    line_end: int = Field(description="End line (inclusive)"),
    collection_name: str = FuncFields.collection_name,
) -> str:
    """Return all chunks covering a line range.

    Use this when you already know a line range and want chunk-level context with scope metadata.
    Compared with nbrag_read_more_original_text(), this keeps chunk/scope structure; adjacent chunks overlap by the ingestion overlap configuration.

    Returned text includes doc_id, file_path, requested line bounds, and one `<nbrag_chunk>` with XML attributes per overlapping chunk. Each `<nbrag_chunk_content>` always contains one RAG chunk, bounded by that chunk's boundaries rather than complete original text."""
    return mcp_tools.nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name)


@mcp.tool()
def nbrag_list(
    collection_name: str = FuncFields.collection_name ,
    limit: int = Field(default=10, description="Maximum documents to return for this page (default 100, usually keep <= 30)"),
    offset: int = Field(default=0, description="Skip the first N documents for pagination"),
) -> str:
    """List imported documents in a collection.

    Use this when the user explicitly wants to browse imported documents,
    or when you need inventory handles such as doc_id and file_path before a follow-up read.
    This provides collection inventory and handle discovery. Use nbrag_retrieve() for semantic question answering.

    The root and `<pagination>` tag expose offset, limit, has_more, and next_offset when another page exists. Each `<nbrag_document>` exposes doc_id, filename, total_chunks, and file_path as XML attributes."""
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
    """List available knowledge bases （collection_name） and the knowledge base detail information.

    什么时候使用：
    如果你不知道已存在哪些知识库，或者不知道用户的问题需要检索哪个知识库，不知道nbrag工具的 collection_name 应该传递什么具体入参时候，必须调用这个nbrag_stats。
    什么时候不使用：
    nbrag_stats是返回有哪些知识库，不会经常变化，所以不需要每一轮回答都频繁调用，返回的内容不会频繁发生变化，除非用户在导入新的知识库后，用户让你主动读取有哪些新的知识库，你才重新调用此工具。

    Returned text includes each collection's stable collection_name and document/chunk counts, and include display_name, description, aliases, tags, chunk_size, chunk_overlap, and last_ingested_at.
    使用此工具前，请检查当前对话上下文中是否已有调用过`nbrag_help()`获取nbrag的使用指南。 
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
  NBRAG_API_KEY=sk-xxx nbrag         # API key via env var""",
    )
    parser.add_argument("--transport", choices=["stdio", "streamable-http", "sse"], default="stdio",
                        help="MCP transport mode (default: stdio)")
    parser.add_argument("--port", type=int, default=9101,
                        help="HTTP port (only for streamable-http/sse, default: 9101)")
    parser.add_argument("--db-path", dest="db_path",
                        help="ChromaDB storage path (default: ./rag_db)")
    parser.add_argument("--config",
                        help="Path to YAML config file")
    args = parser.parse_args()

    from nbrag.config import load_config
    load_config(args)

    from nbrag.cache_watcher import start_cache_watcher
    start_cache_watcher()

    if args.transport != "stdio":
        mcp.settings.port = args.port

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
