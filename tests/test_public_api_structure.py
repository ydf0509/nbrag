import importlib
import inspect

import nbrag


def test_package_exports_primary_public_api():
    expected = [
        "batch_ingest",
        "ingest_path",
        "set_collection_profile",
        "get_collection_profile",
        "list_collection_profiles",
        "search",
        "list_documents",
        "delete_document",
        "get_stats",
        "get_file_chunks",
        "get_context_chunks",
        "grep_knowledge",
        "find_symbol_definition",
        "find_files",
    ]

    missing = [name for name in expected if not hasattr(nbrag, name)]

    assert missing == []


def test_core_implementation_is_split_into_focused_modules():
    modules = [
        "nbrag.runtime",
        "nbrag.storage",
        "nbrag.collection_profiles",
        "nbrag.embeddings",
        "nbrag.bm25_index",
        "nbrag.symbol_index",
        "nbrag.ingest",
        "nbrag.retrieval",
    ]

    for module_name in modules:
        importlib.import_module(module_name)

    assert not hasattr(nbrag, "core")
