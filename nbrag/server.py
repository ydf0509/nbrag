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
    在调用其他 nbrag工具之前，必须先确保你曾经已经过调用nbrag_help,以便知道如何对nbrag的一系列工具正确的配合使用打组合拳。

 nbrag 是 agentic rag，由llm主动调用主动根据上下文构造向量检索语句和bm25检索语句,不是那种传统一轮rag。
 nbrag 使llm能根据chunk块，自动以及llm自主扩大阅读范围，吊打任何传统rag，可以完成横跨多个文件的多跳检索的极端复杂任务推理。

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

Call it so subsequent retrieval uses the right tool and handles correctly,
avoiding common errors such as treating bm25_query as a semantic question,
using line_start as chunk_index, or treating a truncated chunk as full source.

MANDATORY bootstrap with session-aware reuse:

Before the first nbrag operation whose nbrag tool usage guide is not already available
in the current conversation context, call nbrag_help() proactively.

A successful nbrag_help() response makes this guidance reusable for all later
nbrag retrieval questions in the same conversation. A new user question does
not by itself require another nbrag_help() call.

Before calling nbrag_help(), check whether the current conversation already
contains a successful nbrag_help() result:

- If it does, reuse the nbrag tool usage guide and proceed directly to the appropriate tool.
- If it does not, the result is unavailable after context compaction, or you
  are uncertain, call nbrag_help() before using other nbrag tools.
- Call it again if the tool usage guide/workflow version has changed.

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
    query: str = Field(description="Main semantic query used by vector retrieval and reranking. Keep it as a natural-language question or statement that preserves the real retrieval target. Use ongoing dialogue or earlier retrieval results to resolve pronouns, restore omitted entities, fix obvious typos, or sharpen the event/relation/attribute wording once the target is clear. Let query stay semantically complete and readable; use bm25_query separately for lexical anchors.如果知识库内容是英文的，请使用英文语句检索")
    collection_name: str = Field(description="Knowledge base name = collection_name = 知识库名字 (call nbrag_stats first if unknown)")
    top_k: int = Field(default=20, description="Number of ranked hits to return,通常情况下保持默认值就就好了，llm不用擅自修改")
    filter_file_path: str = Field(default="", description="Optional exact full absolute file_path returned by nbrag tools. Basename or relative path is not accepted. When set, retrieval is narrowed to that stored file before ranking. In the current hybrid implementation, this narrows vector retrieval to that file and skips cross-file BM25 fusion. Value comes from the file_path handle returned by nbrag tools.")
    bm25_query: str = Field(default="", description="Optional lexical-anchor query used only by BM25. Omit it or pass an empty string when no grounded lexical anchor is available; the hybrid search still uses query for vector retrieval and reranking. When provided, build it from wording likely to appear literally in the source: exact terms, aliases, article numbers, abbreviations, codes, API/class names, symbol names, titles, place names, event markers, error strings, or short phrases. Compared with query, bm25_query carries more source-facing lexical anchors and can combine multiple grounded anchors only when they target the same knowledge. Do not mix unverified alternatives, unrelated entities, or adjacent provisions merely as a keyword bag. Refine anchors across turns from the user's wording, ongoing dialogue, or earlier hits.如果知识库内容是英文的，请使用英文语句检索")
    include_content: bool = Field(default=True, description="Include chunk content in each hit. Set false for metadata-only lookup when you only need handles like file_path/doc_id/chunk_index. Content is a truncated chunk fragment, not the full source")
    file_path: str = Field(description="Exact full absolute file_path returned by nbrag tools. Basename or relative path is not accepted")
    

@mcp.tool()
def nbrag_retrieve_no_expand(
    query: str = FuncFields.query,
    collection_name: str = FuncFields.collection_name,
    top_k: int = FuncFields.top_k,
    use_rerank: bool = Field(default=True, description="Enable reranker for better top-hit ordering (recommended)"),
    use_bm25: bool = Field(default=True, description="Enable multi-channel BM25 lexical retrieval + Weighted RRF fusion (recommended for precise names, aliases, Chinese terms, codes, article numbers, titles, and other exact-wording anchors)"),
    filter_file_path: str = FuncFields.filter_file_path,
    include_content: bool = FuncFields.include_content,
    bm25_query: str = FuncFields.bm25_query,
) -> str:
    """Hybrid retrieval without auto-expand. Use nbrag_retrieve() instead for most questions.

    Before using this tool, check whether a successful nbrag_help() response is already
    available in the current conversation context. If it is, reuse that tool usage guide
    and call this tool directly. If it is unavailable, lost after context compaction, or
    uncertain, call nbrag_help() proactively first. A new user question in the same
    conversation does not by itself require another nbrag_help() call.

    If collection_name is still unknown, call nbrag_stats().

    Use this when you need fine-grained control over rerank, BM25, file filtering, or content inclusion,
    and do NOT need the auto-expand of original-text context that nbrag_retrieve() provides.

    Query guidance:
    - query is the main semantic query used by vector retrieval and reranking; keep it as the real question/statement you want answered
    - query may be clarified across turns using ongoing dialogue or earlier hits, for example by restoring omitted entities, resolving pronouns, or sharpening the event/relation/attribute wording once the target is clear
    - bm25_query is the lexical-anchor query used only by BM25
    - compared with query, bm25_query should carry more source-facing lexical anchors and be improved across turns using grounded wording discovered from the conversation or earlier hits
    - a single bm25_query can combine multiple anchors when they all target the same knowledge, such as exact terms, aliases, titles, article numbers, symbol names, place names, event markers, or repeated phrases from earlier results
    - setting bm25_query does not disable vector retrieval or reranking
    - setting filter_file_path narrows retrieval to one stored file; in the current hybrid implementation this also disables cross-file BM25 fusion

    Returned text uses nbrag-specific XML tags. Each `<nbrag_ranked_hit>` carries file_path, doc_id, chunk_index, total_chunks, line_start, line_end, scope, dist, and optional score as XML attributes. Its `<nbrag_chunk_content>` always contains one RAG chunk, bounded by that chunk's boundaries rather than complete original text.

    Follow-up tools:
    - 如果某个 ranked hit 对回答有用，就把它的 line_start 记作 hit_line_start，再用 file_path 调用 nbrag_read_more_original_text，读取 line_start=max(1, hit_line_start-200) 到 line_end=hit_line_start+400 的连续原文。
    - 如果缺少前文，就减小 line_start；如果缺少后文，就增大 line_end。如果需要完整 stored file，就省略两个 line bounds。
    - 大文件和大范围内容也使用 nbrag_read_more_original_text 按连续 line ranges 阅读。只有明确需要 chunk boundaries、scope metadata、overlap 或 chunking inspection 时，才使用 chunk tools。
    - 如果需要精确文本匹配，就调用 nbrag_grep；如果需要 Python .py symbol definition，就调用 nbrag_find_definition。
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

    Use this to isolate lexical recall when exact terms matter: article numbers, abbreviations, error codes, identifiers, exact phrases, titles, aliases, or other high-precision wording.
    This is ranked retrieval, not literal line matching.
    A single bm25_query can combine multiple grounded lexical anchors when you want to test whether BM25 can target the right knowledge by wording alone.

    Each `<nbrag_ranked_hit>` exposes result-specific handles as XML attributes. Each `<nbrag_chunk_content>` always contains one RAG chunk, bounded by that chunk's boundaries rather than complete original text.

    Use instead:
    - nbrag_grep() for literal line-by-line matching in stored original text
    - nbrag_retrieve_only_vector() to inspect semantic recall only
    - nbrag_retrieve_no_expand() or nbrag_retrieve() for the normal mixed retrieval pipeline
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

    Use this to isolate semantic recall when meaning, intent, or paraphrase matters more than exact lexical overlap.
    This is useful for inspecting embedding behavior without BM25 or reranking.
    Keep query semantically clear here. This tool does not accept bm25_query; if you need lexical anchors, switch to nbrag_retrieve_no_expand() or nbrag_retrieve() which expose bm25_query.

    Each `<nbrag_ranked_hit>` exposes result-specific handles as XML attributes. Each `<nbrag_chunk_content>` always contains one RAG chunk, bounded by that chunk's boundaries rather than complete original text.

    Use instead:
    - nbrag_retrieve_only_bm25() for lexical-only inspection
    - nbrag_grep() for literal line-by-line matching
    - nbrag_retrieve_no_expand() or nbrag_retrieve() for the normal mixed retrieval pipeline
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
    expand_top_n: int = Field(default=5, description="Number of top ranked hits eligible for auto-expanding stored original-text context. Hits from the same document can produce merged ranges, so the final <nbrag_original_text_expand> count can be lower. 0 disables auto-expand."),
    expand_context_chars: int = Field(default=DEFAULT_FETCH_CONTEXT_CHARS, description=f"Per ranked hit: approximate original-text context-character budget around the matched line range, split about half before and half after. This is per eligible hit, not a total response cap. Default {DEFAULT_FETCH_CONTEXT_CHARS} means roughly {DEFAULT_FETCH_CONTEXT_CHARS // 2} chars before and {DEFAULT_FETCH_CONTEXT_CHARS // 2} chars after each hit."),
    filter_file_path: str = FuncFields.filter_file_path,
    bm25_query: str = FuncFields.bm25_query,
) -> str:
    """Default one-call retrieval tool for most questions after collection_name is known.

    Before using this tool, check whether a successful nbrag_help() response is already
    available in the current conversation context. That guidance explains query/bm25_query
    roles, original-text-vs-chunk boundaries, result-entity handle reuse, and how to choose follow-up
    tools. If it is available, call this tool directly. If it is unavailable, lost after
    context compaction, or uncertain, call nbrag_help() proactively first. A new user
    question in the same conversation does not by itself require another nbrag_help() call.

    Once collection_name is known, this is the normal default for most source-backed questions.

    Use it for questions about meaning, usage, explanation, examples, or source-backed knowledge.

    Query guidance:
    - query is the main semantic query used by vector retrieval and reranking; keep it as the real question/statement you want answered
    - query may be clarified across turns using ongoing dialogue or earlier hits, for example by restoring omitted entities, resolving pronouns, or sharpening the event/relation/attribute wording once the target is clear
    - bm25_query is the lexical-anchor query used only by BM25
    - compared with query, bm25_query should carry more source-facing lexical anchors and be improved across turns using grounded wording discovered from the conversation or earlier hits
    - a single bm25_query can combine multiple anchors when they all target the same knowledge, such as exact terms, aliases, titles, article numbers, symbol names, place names, event markers, or repeated phrases from earlier results
    - setting bm25_query does not disable vector retrieval or reranking
    - setting filter_file_path narrows retrieval to one stored file; in the current hybrid implementation this also disables cross-file BM25 fusion

    Returned text has two sections:
    1. ranked retrieval results
    2. auto-expanded stored original-text context blocks

    `<nbrag_follow_up>` appears before the result data. `<nbrag_ranked_hit>` contains one `<nbrag_chunk_content>` RAG chunk whose original-text context stops at chunk boundaries. Each `<nbrag_original_text_expand>` contains a bounded, overlap-free auto-expanded original-text block in `<nbrag_original_text_content>` and carries file_path, doc_id, line_start, and line_end. Neither entity is a complete file.

    如果某个 ranked hit 对回答有用，就把它的 line_start 记作 hit_line_start，再用 file_path 调用 nbrag_read_more_original_text，读取 line_start=max(1, hit_line_start-200) 到 line_end=hit_line_start+400 的连续原文。如果缺少前文，就减小 line_start；如果缺少后文，就增大 line_end。

    大文件和大范围内容也使用 nbrag_read_more_original_text 按连续 line ranges 阅读。只有明确需要 chunk boundaries、scope metadata、overlap 或 chunking inspection 时，才使用 chunk tools。

    expand_context_chars is a per-hit original-text context-character budget used during automatic expansion, not a final total response budget.

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
    match_context_chars: int = Field(default=DEFAULT_MATCH_CONTEXT_CHARS, description=f"Per match: approximate total context chars around the matched line range, split about half before and half after. This is per match, not a total cap across all matches. Default {DEFAULT_MATCH_CONTEXT_CHARS} means roughly {DEFAULT_MATCH_CONTEXT_CHARS // 2} chars before and {DEFAULT_MATCH_CONTEXT_CHARS // 2} chars after each match"),
) -> str:
    """Literal text or regex search over stored original text, matched line by line.

    Use this when exact wording matters: article numbers, headings, exact phrases, API names, class/function names, constants, imports, decorators, error strings, or other precise text.
    This is for literal/regex matching after you already know or suspect the wording to target; it is not the tool for semantic discovery.
    Use nbrag_retrieve() for concept, synonym, or paraphrase retrieval.

    Each `<nbrag_match>` exposes file_path, doc_id, line_start, and line_end as XML attributes; single-line matches use equal bounds. `<nbrag_original_text_content>` is a stored-original-text excerpt bounded by match_context_chars.
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
def nbrag_read_more_original_text(
    file_path: str = FuncFields.file_path,
    collection_name: str = FuncFields.collection_name,
    line_start: int | None = Field(default=None, description="Optional start line (1-based) of the stored-original-text reading window. For a useful ranked hit, reuse its line_start as line_start=max(1, hit line_start-200). Omit it to start at the beginning of the stored file."),
    line_end: int | None = Field(default=None, description="Optional end line (1-based, inclusive) of the stored-original-text reading window. For a useful ranked hit, set line_end=hit line_start+400. Omit it to end at the last line of the stored file."),
) -> str:
    """
    获取某个文件的原始内容。
    如果某个 ranked hit 对回答有用，就把它的 line_start 记作 hit_line_start，再读取 line_start=max(1, hit_line_start-200) 到 line_end=hit_line_start+400 的连续原文。
    如果缺少前文，就减小 line_start；如果缺少后文，就增大 line_end。大文件和大范围内容也按连续 line ranges 读取。

    This reads the stored original text snapshot captured in the knowledge base at ingestion time; it is not a live filesystem refresh.
    Use it for clean quoting, broader source context, a specific line range, or a complete stored file. Omit both line bounds to read the complete stored file.

    Returned text includes file_path, doc_id, total_lines, line_start, and line_end as XML attributes, with original text under `<nbrag_original_text_content>`.
    Unlike chunk-based tools, this returns overlap-free stored original text snapshot, not a truncated chunk."""
    return mcp_tools.nbrag_read_more_original_text(file_path, collection_name, line_start, line_end)


@mcp.tool()
def nbrag_get_adjacent_chunks(
    doc_id: str = Field(description="Document ID returned by nbrag tools such as retrieve/retrieve_no_expand/grep/list"),
    chunk_index: int = Field(description="Target chunk index from a prior `<nbrag_ranked_hit>` or `<nbrag_chunk>` metadata block. Use the chunk_index attribute returned by those entities."),
    collection_name: str = FuncFields.collection_name,
    window: int = Field(default=3, description="Return chunk_index ± window chunks"),
) -> str:
    """Inspect chunk structure around a known ranked hit.

    Use this for nearby chunk boundaries, scope metadata, overlap, or chunking inspection.
    Use nbrag_read_more_original_text() for wider source context and large files.
    nbrag_retrieve_no_expand() or nbrag_retrieve() must already have provided doc_id + chunk_index. grep results may provide doc_id, but grep alone does not provide chunk_index,
    so grep output is not sufficient by itself for this tool.

    Returned text includes file_path, total_chunks, and the adjacent chunks with line markers.
    Each `<nbrag_chunk_content>` always contains one RAG chunk; adjacent chunks overlap by the ingestion overlap configuration."""
    return mcp_tools.nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name, window)


@mcp.tool()
def nbrag_get_chunks_by_lines(
    doc_id: str = Field(description="Document ID returned by nbrag tools such as retrieve/retrieve_no_expand/grep/list"),
    line_start: int = Field(description="Start line (1-based), usually copied from a prior nbrag result's line_start key"),
    line_end: int = Field(description="End line (inclusive), usually copied from a prior nbrag result's line_end key"),
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
    limit: int = Field(default=100, description="Maximum documents to return for this page (default 100, usually keep <= 500)"),
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
    """List available knowledge bases and collection routing hints.

    Before using this tool, check whether a successful nbrag_help() response is already
    available in the current conversation context. If it is, reuse that guidance and call
    nbrag_stats() directly. If it is unavailable, lost after context compaction, or
    uncertain, call nbrag_help() proactively first. A new user question in the same
    conversation does not by itself require another nbrag_help() call.

    Use this when collection_name is unknown or when you need to inspect available
    collections before retrieval.

    This tool resolves collection routing only. It helps you choose the correct stable collection_name, but it does not choose the retrieval strategy for you.

    Returned text includes each collection's stable collection_name and document/chunk counts, and may also include display_name, description, aliases, tags, chunk_size, chunk_overlap, and last_ingested_at.
    After reading the collection list, continue with retrieval planning .

    After choosing collection_name:
    - use nbrag_retrieve() for most semantic/source-backed questions
    - use nbrag_retrieve_no_expand() when you need finer retrieval control
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
