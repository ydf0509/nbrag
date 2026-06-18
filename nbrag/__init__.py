"""nbrag — 通用知识库 Agentic RAG MCP Server."""

from nbrag.bm25_index import build_bm25_index, invalidate_bm25_cache
from nbrag.collection_profiles import (
    get_collection_profile,
    list_collection_profiles,
    set_collection_profile,
)
from nbrag.embeddings import embed, rerank
from nbrag.ingest import batch_ingest, ingest_file, ingest_path, prepare_file_no_embed
from nbrag.retrieval import (
    delete_document,
    find_files,
    find_symbol_definition,
    get_context_chunks,
    get_file_chunks,
    get_raw_file,
    get_stats,
    grep_knowledge,
    list_documents,
    search,
)
from nbrag.storage import delete_collection, get_collection, list_collections
from nbrag.symbol_index import build_symbol_index, invalidate_symbol_cache

__version__ = "0.7.0"

__all__ = [
    "batch_ingest",
    "ingest_file",
    "ingest_path",
    "prepare_file_no_embed",
    "search",
    "list_documents",
    "delete_document",
    "get_stats",
    "get_file_chunks",
    "get_raw_file",
    "get_context_chunks",
    "grep_knowledge",
    "find_symbol_definition",
    "find_files",
    "get_collection",
    "delete_collection",
    "list_collections",
    "set_collection_profile",
    "get_collection_profile",
    "list_collection_profiles",
    "embed",
    "rerank",
    "build_bm25_index",
    "invalidate_bm25_cache",
    "build_symbol_index",
    "invalidate_symbol_cache",
]
