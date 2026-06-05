"""
nbrag MCP Server — 12 个 Agentic RAG 工具。

Tools (12):
  1. nbrag_add_document         → Import file/directory into collection
  2. nbrag_search               → Semantic search (vector + rerank)
  3. nbrag_search_and_fetch     → Search + auto-fetch raw source (combo tool)
  4. nbrag_grep                 → Keyword/regex exact search (complements semantic search)
  5. nbrag_find_definition      → Find complete class/function definition by symbol name
  6. nbrag_get_file_chunks      → Paginated chunks with scope/line metadata
  7. nbrag_get_raw_file         → Raw file content without overlap
  8. nbrag_get_adjacent_chunks  → Adjacent chunks by chunk index
  9. nbrag_get_chunks_by_lines  → Chunks covering a line range
  10. nbrag_list                → List imported documents
  11. nbrag_delete              → Delete a document
  12. nbrag_stats               → Collection overview and config

启动方式:
  uvx nbrag                          # stdio (默认)
  uvx nbrag --transport streamable-http --port 9101  # HTTP
"""

from pydantic import Field
from mcp.server.fastmcp import FastMCP
from nbrag.config import get_config
from nbrag.chunker import DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP
from nbrag.core import (
    ingest_path, search, list_documents, delete_document, get_stats,
    get_file_chunks, get_context_chunks, grep_knowledge, find_symbol_definition,
)

mcp = FastMCP("nbrag")


@mcp.tool()
def nbrag_add_document(
    path: str = Field(description="Absolute path to a file or directory. Directory imports all text files recursively"),
    collection_name: str = Field(description="Collection name (required, auto-created if not exists. Use nbrag_stats to see existing)"),
    chunk_size: int = Field(default=DEFAULT_CHUNK_SIZE, description="Chunk size in chars, default 1500, recommended 1000-2000"),
    chunk_overlap: int = Field(default=DEFAULT_CHUNK_OVERLAP, description="Chunk overlap in chars, default 200"),
    file_extensions: str = Field(default="", description="Comma-separated file extensions to include (e.g. 'py,md,html'). Empty = all text files"),
) -> str:
    """Ingest file or directory into RAG collection (chunking + embedding + indexing). Auto-creates collection if not exists.
    Each chunk is enriched with file path, line numbers, and Python class/function scope.
    Use nbrag_search to retrieve ingested content.
    Note: This tool is typically called manually by users via scripts for one-time batch ingestion,
    not by AI during conversations. AI should focus on nbrag_search/nbrag_grep for retrieval."""
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
def nbrag_search(
    query: str = Field(description="Search query (natural language question or keywords)"),
    collection_name: str = Field(description="Collection name (required, use nbrag_stats to see available collections),collection_name对应你的中文就是知识库名字"),
    top_k: int = Field(default=5, description="Number of results to return"),
    use_rerank: bool = Field(default=True, description="Enable reranker for better accuracy (recommended)"),
    filter_filename: str = Field(default="", description="Optional: filter by filename only (e.g. 'constant.py', not full path)"),
) -> str:
    """Semantic search in RAG collection. Vector recall + Rerank. Call nbrag_stats first to see available collections.

    Each result contains: file_path (full path), chunk:X/Y, line:N-M, scope, doc_id, dist (cosine distance, lower=more similar).

    Recommended deep-analysis workflow (use multiple tools, not just search):
      1. nbrag_search → find relevant files and rough location
      2. nbrag_grep → pinpoint exact class/method/constant names (what semantic search may miss)
      3. nbrag_find_definition → get complete class/function source with inheritance chain
      4. nbrag_get_raw_file → read full source code to verify details
      5. Cross-file tracing: when you see unknown symbols in code, repeat steps 2-4 to trace references

    Follow-up tools — use result fields directly as parameters:
      - nbrag_find_definition(symbol, collection_name) → complete class/function definition + methods summary
      - nbrag_get_raw_file(file_path, collection_name) → full source code without overlap
      - nbrag_get_file_chunks(file_path, collection_name) → paginated chunks with scope metadata
      - nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name) → expand context around a result
      - nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name) → chunks covering line range"""
    cfg = get_config()
    fname_filter = filter_filename if filter_filename else None
    documents, metadatas, distances, rerank_used, total = search(
        query, collection_name, top_k, use_rerank,
        filter_filename=fname_filter,
    )

    if total == 0:
        stats = get_stats()
        avail = list(stats["collections"].keys())
        exists = collection_name in avail
        if not exists:
            return (f"collection '{collection_name}' does not exist.\n"
                    f"Available collections: {avail}\n"
                    f"Use nbrag_add_document to create and import docs.")
        return (f"collection '{collection_name}' is empty. "
                f"Use nbrag_add_document to import docs first.")

    if not documents:
        return f"No results (collection has {total} chunks, filter: {filter_filename or 'none'})"

    rerank_str = cfg.rerank.model if rerank_used else "off"
    header = f"[{collection_name}] {total} chunks | rerank: {rerank_str}"
    if filter_filename:
        header += f" | filter: {filter_filename}"
    lines = [header, ""]

    preview_limit = min(8000, 40000 // max(len(documents), 1))
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

        lines.append(f"[{i + 1}/{len(documents)}] {meta.get('filename', '?')} {' '.join(meta_parts)}")
        lines.append(f"file_path: {src}")
        preview = doc[:preview_limit] + ("..." if len(doc) > preview_limit else "")
        lines.append(preview)
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def nbrag_search_and_fetch(
    query: str = Field(description="Search query (natural language question or keywords)"),
    collection_name: str = Field(description="Collection name (required, use nbrag_stats to see available collections)"),
    top_k: int = Field(default=5, description="Number of search results to return"),
    fetch_top_n_raw: int = Field(default=3, description="Auto-fetch raw source for top N results (0 to skip fetching)"),
    context_lines: int = Field(default=100, description="Lines of context around matched chunk. Small files (≤2x this) are fetched fully"),
) -> str:
    """Search + auto-fetch raw source code for top results in one call (combo tool).
    Saves a round-trip vs calling nbrag_search then nbrag_get_raw_file separately.
    Same doc_id appearing in multiple results is fetched only once with merged line range."""
    cfg = get_config()
    fname_filter = None
    documents, metadatas, distances, rerank_used, total = search(
        query, collection_name, top_k, True, filter_filename=fname_filter,
    )

    if total == 0:
        stats = get_stats()
        avail = list(stats["collections"].keys())
        exists = collection_name in avail
        if not exists:
            return (f"collection '{collection_name}' does not exist.\n"
                    f"Available collections: {avail}\n"
                    f"Use nbrag_add_document to create and import docs.")
        return (f"collection '{collection_name}' is empty. "
                f"Use nbrag_add_document to import docs first.")

    if not documents:
        return f"No results (collection has {total} chunks)"

    rerank_str = cfg.rerank.model if rerank_used else "off"
    lines = [f"[{collection_name}] {total} chunks | rerank: {rerank_str}", ""]

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

        lines.append(f"[{i + 1}/{len(documents)}] {meta.get('filename', '?')} {' '.join(meta_parts)}")
        lines.append(f"file_path: {src}")
        preview = doc[:preview_limit] + ("..." if len(doc) > preview_limit else "")
        lines.append(preview)
        lines.append("")

        if i < fetch_top_n_raw and doc_id != "?" and src != "?":
            if doc_id not in fetch_targets:
                fetch_targets[doc_id] = {"src": str(src), "line_min": ls, "line_max": le}
            else:
                t = fetch_targets[doc_id]
                if ls:
                    t["line_min"] = min(t["line_min"], ls) if t["line_min"] else ls
                if le:
                    t["line_max"] = max(t["line_max"], le) if t["line_max"] else le

    if fetch_targets:
        lines.append("=" * 40)
        lines.append(f"Auto-fetched raw source ({len(fetch_targets)} file(s)):")
        lines.append("")

    for doc_id, target in fetch_targets.items():
        center_start = target["line_min"] or 1
        center_end = target["line_max"] or center_start
        center = (center_start + center_end) // 2
        half = context_lines

        raw_result = get_file_chunks(
            target["src"], collection_name, 0, 0,
            raw=True, line_start=-1, line_end=-1,
        )

        if not raw_result.get("found"):
            lines.append(f"[{target['src']}] raw cache not available")
            lines.append("")
            continue

        tl = raw_result["total_lines"]
        if tl <= context_lines * 2:
            lines.append(_format_raw_result(raw_result))
        else:
            fetch_start = max(1, center - half)
            fetch_end = min(tl, center + half)
            excerpt = get_file_chunks(
                target["src"], collection_name, 0, 0,
                raw=True, line_start=fetch_start, line_end=fetch_end,
            )
            if excerpt.get("found"):
                lines.append(_format_raw_result(excerpt))
            else:
                lines.append(f"[{target['src']}] excerpt failed")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def nbrag_grep(
    keyword: str = Field(description="Keyword or regex pattern (e.g. class name 'UserService', method 'get_by_id', constant 'MAX_RETRIES')"),
    collection_name: str = Field(description="Collection name (required, use nbrag_stats to see available collections)"),
    max_results: int = Field(default=10, description="Maximum number of matches to return"),
    case_sensitive: bool = Field(default=False, description="Case-sensitive matching"),
    filter_filename: str = Field(default="", description="Optional: filter by filename only (e.g. 'booster.py', not full path)"),
    context_lines: int = Field(default=10, description="Lines of context before and after each match (default 10, use 20+ for seeing full function/class headers)"),
) -> str:
    """Keyword/regex exact search in cached raw files. Complements nbrag_search (semantic search).

    Use cases where nbrag_search falls short:
      - Find class/function/variable names: 'UserService', 'get_by_id'
      - Find config keys/constants: 'MAX_RETRIES', 'DEFAULT_TIMEOUT'
      - Find import statements: 'from myproject.core'
      - Find string literals: 'error_handler'

    Tip: use context_lines=15 to see class headers + inheritance chain around the match.
    For complete definitions, use nbrag_find_definition instead.
    Typical workflow: nbrag_search (find direction) → nbrag_grep (pinpoint symbols) → nbrag_find_definition (full definition)"""
    fname_filter = filter_filename if filter_filename else None
    results = grep_knowledge(
        keyword, collection_name, max_results, case_sensitive,
        filter_filename=fname_filter, context_lines=context_lines,
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
    symbol: str = Field(description="Symbol name to find (class name like 'UserService', function name like 'get_by_id', or qualified name like 'MyClass.__init__')"),
    collection_name: str = Field(description="Collection name (required, use nbrag_stats to see available collections)"),
    max_results: int = Field(default=5, description="Maximum number of definitions to return"),
) -> str:
    """Find the complete definition of a class/function/method by symbol name.
    Uses AST parsing to extract exact boundaries — returns the FULL source code of the definition.
    For classes, also returns a methods summary (all method signatures).

    Best for cross-file tracing: when you see an unknown symbol in code, use this to get its complete definition.
    Much more efficient than grep + raw_file for understanding class hierarchy and implementation."""
    results = find_symbol_definition(symbol, collection_name, max_results)

    if not results:
        return f"No definition found for '{symbol}' (collection: {collection_name}). Try nbrag_grep for a broader search."

    lines = [f"definition: '{symbol}' | collection_name: {collection_name} | {len(results)} found", ""]
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

        if r.get("methods_summary"):
            lines.append("methods:")
            lines.append(r["methods_summary"])

        lines.append("---")
        lines.append(r["definition"])
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
def nbrag_get_file_chunks(
    file_path: str = Field(description="Full absolute path (use 'file_path' value from nbrag_search results)"),
    collection_name: str = Field(description="Collection name (use nbrag_stats to see available collections)"),
    start_chunk: int = Field(default=0, description="Start chunk index (0-based), use for pagination"),
    max_chunks: int = Field(default=10, description="Max chunks to return (use for pagination)"),
) -> str:
    """Paginated view of file chunks with scope and line metadata. Use start_chunk to paginate.
    Note: adjacent chunks have overlap. For clean source code without overlap, use nbrag_get_raw_file instead."""
    result = get_file_chunks(
        file_path, collection_name, start_chunk, max_chunks,
        raw=False,
    )

    if not result.get("found"):
        return result.get("error", f"File not found: '{file_path}'")

    return _format_chunks_result(result)


@mcp.tool()
def nbrag_get_raw_file(
    file_path: str = Field(description="Full absolute path (use 'file_path' value from nbrag_search results)"),
    collection_name: str = Field(description="Collection name (use nbrag_stats to see available collections)"),
    line_start: int = Field(default=-1, description="Start line (1-based), -1 for beginning"),
    line_end: int = Field(default=-1, description="End line (inclusive), -1 for end of file"),
) -> str:
    """Get cached raw file content without chunk overlap. Recommended for viewing full source code.
    Supports line_start/line_end for extracting specific line ranges.
    Only available for files imported with raw cache (re-import older files if needed)."""
    result = get_file_chunks(
        file_path, collection_name, 0, 0,
        raw=True, line_start=line_start, line_end=line_end,
    )

    if not result.get("found"):
        return result.get("error", f"File not found: '{file_path}'")

    return _format_raw_result(result)


def _format_raw_result(result):
    """Format raw file result in compact English."""
    ls = result["line_start"]
    le = result["line_end"]
    tl = result["total_lines"]
    shown = le - ls + 1
    range_info = f"line:{ls}-{le}" + (f" ({shown}/{tl} lines)" if shown < tl else " (full)")
    lines = [
        f"raw_file: {result['filename']} | doc_id:{result['doc_id']} | {tl} lines | {result['total_chunks']} chunks",
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
    doc_id: str = Field(description="Document ID (use 'doc_id' value from nbrag_search/nbrag_grep results)"),
    chunk_index: int = Field(description="Target chunk index (0-based, the X from 'chunk:X/Y' in nbrag_search results)"),
    collection_name: str = Field(description="Collection name (use nbrag_stats to see available collections)"),
    window: int = Field(default=3, description="Context window: returns chunk_index ± window chunks"),
) -> str:
    """Get adjacent chunks around a specific chunk index, for expanding context of a search result.
    Requires doc_id and chunk_index from nbrag_search results (not file_path).
    Example: doc_id="abc123", chunk_index=3, window=2 → returns chunks 1-5"""
    result = get_context_chunks(
        doc_id, collection_name,
        chunk_index=chunk_index, window=window,
    )
    return _format_context_result(result, doc_id)


@mcp.tool()
def nbrag_get_chunks_by_lines(
    doc_id: str = Field(description="Document ID (use 'doc_id' value from nbrag_search/nbrag_grep results)"),
    line_start: int = Field(description="Start line number (1-based, from 'line:N-M' in search results)"),
    line_end: int = Field(description="End line number (inclusive, from 'line:N-M' in search results)"),
    collection_name: str = Field(description="Collection name (use nbrag_stats to see available collections)"),
) -> str:
    """Get all chunks covering a line range, with scope metadata.
    vs nbrag_get_raw_file: this returns chunks (with scope but has overlap),
    nbrag_get_raw_file returns raw code (no overlap but no scope).
    Example: doc_id="abc123", line_start=80, line_end=200"""
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
    collection_name: str = Field(description="Collection name (required, use nbrag_stats to see available collections)"),
) -> str:
    """List all documents in a collection (filename, path, chunk count, doc_id).
    Use returned doc_id with nbrag_delete to remove documents."""
    docs = list_documents(collection_name)

    if not docs:
        return f"collection '{collection_name}' is empty."

    total_chunks = sum(info["chunk_count"] for info in docs.values())
    lines = [f"[{collection_name}] {len(docs)} docs, {total_chunks} chunks\n"]
    for did, info in docs.items():
        lines.append(f"  {info['filename']} | file_path: {info['source']} | {info['chunk_count']} chunks | doc_id:{did}")

    return "\n".join(lines)


@mcp.tool()
def nbrag_delete(
    doc_id: str = Field(description="Document ID to delete (use 'doc_id' value from nbrag_list results)"),
    collection_name: str = Field(description="Collection name (use nbrag_stats to see available collections)"),
) -> str:
    """Delete a document's vectors and cached files from the collection. Get doc_id from nbrag_list."""
    deleted, filename = delete_document(doc_id, collection_name)

    if deleted == 0:
        return f"Error: doc_id '{doc_id}' not found. Use nbrag_list to see available doc_ids."

    return f"Deleted: {filename} | {deleted} chunks | doc_id:{doc_id}"


@mcp.tool()
def nbrag_stats() -> str:
    """
    nbrag_stats 获取所有知识库的统计信息，英文术语`collection` 就是中文的`知识库`
    Get RAG overview: all collection names, doc/chunk counts, and config.
    Call this FIRST to discover available collection_name values for other tools.
    Glossary: collection = knowledge base, doc = imported file, chunk = vector-embedded text segment."""
    cfg = get_config()
    stats = get_stats()

    lines = [
        "RAG Stats",
        f"embed: {stats['embedding_model']} | rerank: {stats['rerank_model']}",
        f"data_dir: {stats['data_dir']}",
        f"chunk: size={cfg.chunking.chunk_size} overlap={cfg.chunking.chunk_overlap} | collections: {stats['collection_count']}",
        "",
    ]

    if not stats["collections"]:
        lines.append("(no collections yet, use nbrag_add_document to import)")
        return "\n".join(lines)

    for name, info in stats["collections"].items():
        if "error" in info:
            lines.append(f"  [{name}] error: {info['error']}")
        elif info["chunk_count"] > 0:
            lines.append(f"  [{name}] {info['doc_count']} docs, {info['chunk_count']} chunks")
        else:
            lines.append(f"  [{name}] empty")

    return "\n".join(lines)


def main():
    """CLI entry point for uvx / python -m nbrag."""
    import argparse
    parser = argparse.ArgumentParser(
        description="nbrag — Agentic RAG MCP Server with 12 tools",
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
