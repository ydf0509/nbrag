# Runtime Cache Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a conservative locked 300-second runtime cache refresh for long-running nbrag MCP processes.

**Architecture:** Implement a process-local runtime guard in `nbrag/core.py`. Public core operations enter a shared `threading.RLock`, lazily clear memory-only caches when the refresh interval has elapsed, and then run their existing logic.

**Tech Stack:** Python 3.11, pytest, ChromaDB PersistentClient, bm25s, FastMCP wrappers.

---

## File Structure

- Create: `docs/superpowers/specs/2026-06-17-runtime-cache-refresh-design.md`
- Create: `docs/superpowers/plans/2026-06-17-runtime-cache-refresh.md`
- Create: `tests/test_runtime_cache_refresh.py`
- Modify: `nbrag/core.py`

## Task 1: Runtime Refresh Unit Tests

**Files:**
- Create: `tests/test_runtime_cache_refresh.py`
- Modify: `nbrag/core.py`

- [ ] **Step 1: Write the failing test for memory-only refresh**

```python
import os

from nbrag import core


def test_periodic_refresh_clears_memory_caches_without_deleting_disk_indexes(tmp_path, monkeypatch):
    monkeypatch.setattr(core, "_cfg", lambda: type("Cfg", (), {
        "storage": type("Storage", (), {"db_path": str(tmp_path), "raw_files_path": str(tmp_path / "raw_files")})()
    })())
    bm25_dir = tmp_path / "bm25_index_v2" / "civil_code"
    symbol_dir = tmp_path / "symbol_index" / "civil_code"
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

    core._refresh_runtime_caches_if_due_locked()

    assert core._chroma_client is None
    assert core._doc_id_cache == {}
    assert core._doc_id_cache_ts == {}
    assert core._bm25_cache == {}
    assert core._symbol_cache == {}
    assert (bm25_dir / "keep.txt").exists()
    assert (symbol_dir / "symbols.json").exists()
    assert core._last_runtime_cache_refresh_ts == 301
```

- [ ] **Step 2: Run test to verify it fails**

Run: `D:/ProgramData/miniconda3/envs/py312/python.exe -m pytest tests/test_runtime_cache_refresh.py::test_periodic_refresh_clears_memory_caches_without_deleting_disk_indexes -q`

Expected: FAIL because `_runtime_clock` or `_refresh_runtime_caches_if_due_locked` does not exist.

- [ ] **Step 3: Implement minimal refresh globals and helper**

Add near the existing cache globals in `nbrag/core.py`:

```python
import threading
import time as _runtime_clock

_runtime_cache_lock = threading.RLock()
_last_runtime_cache_refresh_ts = 0.0
_RUNTIME_CACHE_REFRESH_INTERVAL = 300.0


def _refresh_runtime_caches_if_due_locked():
    global _chroma_client, _last_runtime_cache_refresh_ts
    now = _runtime_clock.monotonic()
    if now - _last_runtime_cache_refresh_ts < _RUNTIME_CACHE_REFRESH_INTERVAL:
        return False
    _chroma_client = None
    _doc_id_cache.clear()
    _doc_id_cache_ts.clear()
    _bm25_cache.clear()
    _symbol_cache.clear()
    _last_runtime_cache_refresh_ts = now
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `D:/ProgramData/miniconda3/envs/py312/python.exe -m pytest tests/test_runtime_cache_refresh.py::test_periodic_refresh_clears_memory_caches_without_deleting_disk_indexes -q`

Expected: PASS.

## Task 2: Locking and Skip-Refresh Tests

**Files:**
- Modify: `tests/test_runtime_cache_refresh.py`
- Modify: `nbrag/core.py`

- [ ] **Step 1: Write failing tests for interval skip and operation guard**

```python
def test_periodic_refresh_skips_before_interval(monkeypatch):
    core._chroma_client = object()
    core._doc_id_cache["x"] = {}
    core._last_runtime_cache_refresh_ts = 100
    monkeypatch.setattr(core._runtime_clock, "monotonic", lambda: 399)

    refreshed = core._refresh_runtime_caches_if_due_locked()

    assert refreshed is False
    assert core._chroma_client is not None
    assert "x" in core._doc_id_cache
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `D:/ProgramData/miniconda3/envs/py312/python.exe -m pytest tests/test_runtime_cache_refresh.py -q`

Expected: first test may pass after Task 1; second fails because `_with_runtime_cache_refresh` does not exist.

- [ ] **Step 3: Implement the operation guard**

Add to `nbrag/core.py`:

```python
def _with_runtime_cache_refresh(func, *args, **kwargs):
    with _runtime_cache_lock:
        _refresh_runtime_caches_if_due_locked()
        return func(*args, **kwargs)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `D:/ProgramData/miniconda3/envs/py312/python.exe -m pytest tests/test_runtime_cache_refresh.py -q`

Expected: PASS.

## Task 3: Wrap Public Core Entry Points

**Files:**
- Modify: `nbrag/core.py`
- Modify: `tests/test_runtime_cache_refresh.py`

- [ ] **Step 1: Add a failing test that `search` enters the guard**

```python
def test_search_runs_under_runtime_guard(monkeypatch):
    calls = []
    monkeypatch.setattr(core, "_refresh_runtime_caches_if_due_locked", lambda: calls.append("refresh"))
    monkeypatch.setattr(core, "_get_existing_collection", lambda name: None)

    result = core.search("anything", collection_name="missing")

    assert calls == ["refresh"]
    assert result == ([], [], [], False, 0, [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `D:/ProgramData/miniconda3/envs/py312/python.exe -m pytest tests/test_runtime_cache_refresh.py::test_search_runs_under_runtime_guard -q`

Expected: FAIL because `search` has not been wrapped yet.

- [ ] **Step 3: Wrap `search` with a private implementation function**

Rename existing `search(...)` body to `_search_impl(...)`, then define:

```python
def search(query, collection_name="default", top_k=5, use_rerank=True,
           use_bm25=True, filter_file_path=None):
    """混合检索：Vector + BM25 → RRF 融合 → Reranker 精排。"""
    return _with_runtime_cache_refresh(
        _search_impl, query, collection_name, top_k, use_rerank, use_bm25, filter_file_path,
    )
```

- [ ] **Step 4: Run search guard test**

Run: `D:/ProgramData/miniconda3/envs/py312/python.exe -m pytest tests/test_runtime_cache_refresh.py::test_search_runs_under_runtime_guard -q`

Expected: PASS.

- [ ] **Step 5: Wrap the remaining public core functions**

Apply the same wrapper pattern to:

```text
get_file_chunks
get_context_chunks
grep_knowledge
find_symbol_definition
list_documents
find_files
get_stats
delete_collection
delete_document
check_file_cache
get_collection
list_collections
```

Keep internal helper names simple, such as `_get_file_chunks_impl`.

- [ ] **Step 6: Run focused tests**

Run: `D:/ProgramData/miniconda3/envs/py312/python.exe -m pytest tests/test_runtime_cache_refresh.py tests/test_core_path_filters.py tests/test_server_contracts.py -q`

Expected: all tests pass.

## Task 4: Verification

**Files:**
- `nbrag/core.py`
- `tests/test_runtime_cache_refresh.py`

- [ ] **Step 1: Syntax check**

Run:

```powershell
$env:PYTHONPYCACHEPREFIX='D:\codes\nbrag\tmp\pycache'
D:/ProgramData/miniconda3/envs/py312/python.exe -m py_compile nbrag/core.py tests/test_runtime_cache_refresh.py
```

Expected: exit code 0.

- [ ] **Step 2: Regression tests**

Run: `D:/ProgramData/miniconda3/envs/py312/python.exe -m pytest tests/test_runtime_cache_refresh.py tests/test_core_path_filters.py tests/test_server_contracts.py -q`

Expected: all selected tests pass.

- [ ] **Step 3: Manual MCP follow-up**

After restarting MCP, query `civil_code` with:

```text
民法典 合同违约 违约金 定金 损害赔偿 继续履行
```

Expected: no stale HNSW reader error after restart; if an external ingest later occurs, the next operation after the refresh interval clears process-local caches before querying.
