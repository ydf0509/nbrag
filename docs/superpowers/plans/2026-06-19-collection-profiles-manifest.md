# Collection Profiles Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local JSON manifest for knowledge base profiles so AI can route by display name, description, and aliases without touching Chroma collection metadata.

**Architecture:** Keep Chroma collection names as stable ASCII identifiers. Store human-readable collection profiles in `rag_db/collection_profiles.json`, read them through a small `nbrag.collection_profiles` module, and merge them into `get_stats()` / `nbrag_stats()` output. Existing search and ingest flows stay unchanged except for optional profile writes in helper scripts.

**Tech Stack:** Python 3.11, JSON files, existing `nbrag.config`, `nbrag.storage`, `nbrag.retrieval`, `nbrag.server`, pytest.

---

### Task 1: Add collection profile storage and round-trip tests

**Files:**
- Create: `tests/test_collection_profiles.py`
- Create: `nbrag/collection_profiles.py`

- [ ] **Step 1: Write the failing test**

```python
def test_collection_profile_round_trip(tmp_path, monkeypatch):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `D:/ProgramData/miniconda3/envs/py312/python.exe -m pytest tests/test_collection_profiles.py -q`
Expected: FAIL because `nbrag.collection_profiles` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Implement JSON load/save helpers plus `set_collection_profile()`, `get_collection_profile()`, and `list_collection_profiles()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `D:/ProgramData/miniconda3/envs/py312/python.exe -m pytest tests/test_collection_profiles.py -q`
Expected: PASS.

### Task 2: Merge profiles into stats output

**Files:**
- Modify: `nbrag/retrieval.py`
- Modify: `nbrag/server.py`
- Modify: `tests/test_server_contracts.py`

- [ ] **Step 1: Write the failing test**

Add assertions that `get_stats()` and `nbrag_stats()` include `display_name`, `description`, and `aliases` when a profile exists.

- [ ] **Step 2: Run test to verify it fails**

Run: `D:/ProgramData/miniconda3/envs/py312/python.exe -m pytest tests/test_server_contracts.py tests/test_collection_profiles.py -q`
Expected: FAIL because stats do not render profile data yet.

- [ ] **Step 3: Write minimal implementation**

Merge manifest fields into `get_stats()` collection entries and format them in `nbrag_stats()` output.

- [ ] **Step 4: Run test to verify it passes**

Run: `D:/ProgramData/miniconda3/envs/py312/python.exe -m pytest tests/test_server_contracts.py tests/test_collection_profiles.py -q`
Expected: PASS.

### Task 3: Export profile helpers from package root

**Files:**
- Modify: `nbrag/__init__.py`
- Modify: `tests/test_public_api_structure.py`

- [ ] **Step 1: Write the failing test**

Assert that `nbrag` exports `set_collection_profile`, `get_collection_profile`, and `list_collection_profiles`.

- [ ] **Step 2: Run test to verify it fails**

Run: `D:/ProgramData/miniconda3/envs/py312/python.exe -m pytest tests/test_public_api_structure.py -q`
Expected: FAIL because the new exports are missing.

- [ ] **Step 3: Write minimal implementation**

Re-export the profile helpers from the package root.

- [ ] **Step 4: Run test to verify it passes**

Run: `D:/ProgramData/miniconda3/envs/py312/python.exe -m pytest tests/test_public_api_structure.py -q`
Expected: PASS.

### Task 4: Seed current knowledge bases and verify MCP output

**Files:**
- Create or modify: `rag_db/collection_profiles.json`
- Modify: `README.md`
- Modify: `README.zh-CN.md`

- [ ] **Step 1: Seed a few real profiles**

Add profiles for the existing collections so `nbrag_stats()` shows useful Chinese descriptions immediately.

- [ ] **Step 2: Run the focused tests**

Run: `D:/ProgramData/miniconda3/envs/py312/python.exe -m pytest tests/test_collection_profiles.py tests/test_server_contracts.py tests/test_public_api_structure.py -q`
Expected: PASS.

- [ ] **Step 3: Restart and check MCP**

Run the local HTTP MCP service restart command and call `nbrag_stats()` again.

- [ ] **Step 4: Commit**

Stage the manifest, code, tests, and docs together with a message describing the profile manifest feature.
