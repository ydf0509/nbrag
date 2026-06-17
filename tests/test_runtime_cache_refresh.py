import shutil
from pathlib import Path

from nbrag import core


def _runtime_tmp_dir(name):
    root = Path("tests/.tmp_runtime_cache_refresh") / name
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    return root


def test_periodic_refresh_clears_memory_caches_without_deleting_disk_indexes(monkeypatch):
    tmp_dir = _runtime_tmp_dir("memory_only")
    try:
        monkeypatch.setattr(core, "_cfg", lambda: type("Cfg", (), {
            "storage": type("Storage", (), {
                "db_path": str(tmp_dir),
                "raw_files_path": str(tmp_dir / "raw_files"),
            })()
        })())
        bm25_dir = tmp_dir / "bm25_index_v2" / "civil_code"
        symbol_dir = tmp_dir / "symbol_index" / "civil_code"
        bm25_dir.mkdir(parents=True)
        symbol_dir.mkdir(parents=True)
        (bm25_dir / "keep.txt").write_text("keep", encoding="utf-8")
        (symbol_dir / "symbols.json").write_text("{}", encoding="utf-8")

        core._chroma_client = object()
        core._doc_id_cache["civil_code"] = {"doc": {"filename": "民法典.md", "source": "D:/x.md"}}
        core._doc_id_cache_ts["civil_code"] = 1
        core._bm25_cache["civil_code"] = {"word": ("retriever", ["id"])}
        core._symbol_cache["civil_code"] = {"Foo": []}
        core._last_runtime_cache_refresh_ts = 0
        monkeypatch.setattr(core._runtime_clock, "monotonic", lambda: 301)

        refreshed = core._refresh_runtime_caches_if_due_locked()

        assert refreshed is True
        assert core._chroma_client is None
        assert core._doc_id_cache == {}
        assert core._doc_id_cache_ts == {}
        assert core._bm25_cache == {}
        assert core._symbol_cache == {}
        assert (bm25_dir / "keep.txt").exists()
        assert (symbol_dir / "symbols.json").exists()
        assert core._last_runtime_cache_refresh_ts == 301
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_periodic_refresh_skips_before_interval(monkeypatch):
    core._chroma_client = object()
    core._doc_id_cache.clear()
    core._doc_id_cache["civil_code"] = {}
    core._last_runtime_cache_refresh_ts = 100
    monkeypatch.setattr(core._runtime_clock, "monotonic", lambda: 399)

    refreshed = core._refresh_runtime_caches_if_due_locked()

    assert refreshed is False
    assert core._chroma_client is not None
    assert "civil_code" in core._doc_id_cache
    assert core._last_runtime_cache_refresh_ts == 100


def test_runtime_guard_holds_lock_and_refreshes_before_operation(monkeypatch):
    events = []

    class FakeLock:
        def __enter__(self):
            events.append("lock-enter")

        def __exit__(self, exc_type, exc, tb):
            events.append("lock-exit")

    monkeypatch.setattr(core, "_runtime_cache_lock", FakeLock())
    monkeypatch.setattr(core, "_refresh_runtime_caches_if_due_locked", lambda: events.append("refresh"))

    def operation():
        events.append("operation")
        return "ok"

    assert core._with_runtime_cache_refresh(operation) == "ok"
    assert events == ["lock-enter", "refresh", "operation", "lock-exit"]


def test_search_runs_under_runtime_guard(monkeypatch):
    calls = []
    monkeypatch.setattr(core, "_refresh_runtime_caches_if_due_locked", lambda: calls.append("refresh"))
    monkeypatch.setattr(core, "_get_existing_collection", lambda name: None)

    result = core.search("anything", collection_name="missing")

    assert calls == ["refresh"]
    assert result == ([], [], [], False, 0, [])


def test_public_core_entry_points_are_runtime_guarded():
    guarded_names = [
        "get_collection",
        "delete_collection",
        "list_collections",
        "check_file_cache",
        "search",
        "get_file_chunks",
        "get_context_chunks",
        "grep_knowledge",
        "find_symbol_definition",
        "list_documents",
        "find_files",
        "delete_document",
        "get_stats",
    ]

    missing = [
        name for name in guarded_names
        if not hasattr(getattr(core, name), "__wrapped__")
    ]

    assert missing == []
