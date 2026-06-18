import shutil
from pathlib import Path

from nbrag import runtime, state
from nbrag.retrieval import search
from nbrag.storage import get_collection, delete_collection, list_collections
from nbrag.ingest import check_file_cache
from nbrag.retrieval import (
    delete_document,
    find_files,
    find_symbol_definition,
    get_context_chunks,
    get_file_chunks,
    get_stats,
    grep_knowledge,
    list_documents,
)


def _runtime_tmp_dir(name):
    root = Path("tests/.tmp_runtime_cache_refresh") / name
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    return root


def test_periodic_refresh_clears_memory_caches_without_deleting_disk_indexes(monkeypatch):
    tmp_dir = _runtime_tmp_dir("memory_only")
    try:
        bm25_dir = tmp_dir / "bm25_index_v2" / "civil_code"
        symbol_dir = tmp_dir / "symbol_index" / "civil_code"
        bm25_dir.mkdir(parents=True)
        symbol_dir.mkdir(parents=True)
        (bm25_dir / "keep.txt").write_text("keep", encoding="utf-8")
        (symbol_dir / "symbols.json").write_text("{}", encoding="utf-8")

        state._chroma_client = object()
        state._doc_id_cache["civil_code"] = {"doc": {"filename": "民法典.md", "source": "D:/x.md"}}
        state._doc_id_cache_ts["civil_code"] = 1
        state._bm25_cache["civil_code"] = {"word": ("retriever", ["id"])}
        state._symbol_cache["civil_code"] = {"Foo": []}
        state._last_runtime_cache_refresh_ts = 0
        monkeypatch.setattr(state._runtime_clock, "monotonic", lambda: 301)

        refreshed = runtime._refresh_runtime_caches_if_due_locked()

        assert refreshed is True
        assert state._chroma_client is None
        assert state._doc_id_cache == {}
        assert state._doc_id_cache_ts == {}
        assert state._bm25_cache == {}
        assert state._symbol_cache == {}
        assert (bm25_dir / "keep.txt").exists()
        assert (symbol_dir / "symbols.json").exists()
        assert state._last_runtime_cache_refresh_ts == 301
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_periodic_refresh_skips_before_interval(monkeypatch):
    state._chroma_client = object()
    state._doc_id_cache.clear()
    state._doc_id_cache["civil_code"] = {}
    state._last_runtime_cache_refresh_ts = 100
    monkeypatch.setattr(state._runtime_clock, "monotonic", lambda: 399)

    refreshed = runtime._refresh_runtime_caches_if_due_locked()

    assert refreshed is False
    assert state._chroma_client is not None
    assert "civil_code" in state._doc_id_cache
    assert state._last_runtime_cache_refresh_ts == 100


def test_runtime_guard_holds_lock_and_refreshes_before_operation(monkeypatch):
    events = []

    class FakeLock:
        def __enter__(self):
            events.append("lock-enter")

        def __exit__(self, exc_type, exc, tb):
            events.append("lock-exit")

    monkeypatch.setattr(state, "_runtime_cache_lock", FakeLock())
    monkeypatch.setattr(runtime, "_refresh_runtime_caches_if_due_locked", lambda: events.append("refresh"))

    def operation():
        events.append("operation")
        return "ok"

    assert runtime._with_runtime_cache_refresh(operation) == "ok"
    assert events == ["lock-enter", "refresh", "operation", "lock-exit"]


def test_search_runs_under_runtime_guard(monkeypatch):
    calls = []
    monkeypatch.setattr(runtime, "_refresh_runtime_caches_if_due_locked", lambda: calls.append("refresh"))
    monkeypatch.setattr("nbrag.retrieval._get_existing_collection", lambda name: None)

    result = search("anything", collection_name="missing")

    assert calls == ["refresh"]
    assert result == ([], [], [], False, 0, [])


def test_public_core_entry_points_are_runtime_guarded():
    guarded_names = [
        get_collection,
        delete_collection,
        list_collections,
        check_file_cache,
        search,
        get_file_chunks,
        get_context_chunks,
        grep_knowledge,
        find_symbol_definition,
        list_documents,
        find_files,
        delete_document,
        get_stats,
    ]

    missing = [
        func.__name__ for func in guarded_names
        if not hasattr(func, "__wrapped__")
    ]

    assert missing == []
