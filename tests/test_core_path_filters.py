"""Regression tests for path-scoped retrieval helpers."""

import shutil
from pathlib import Path

from nbrag import core


def _empty_result():
    return {"ids": [], "documents": [], "metadatas": []}


def _chunk_result(source, filename="config.py", doc_id="doc1", ranges=None):
    ranges = ranges or [(10, 20), (21, 30)]
    ids = []
    documents = []
    metadatas = []
    for index, (line_start, line_end) in enumerate(ranges):
        ids.append(f"{doc_id}_c{index}")
        documents.append(f"chunk {index}")
        metadatas.append({
            "source": source,
            "filename": filename,
            "doc_id": doc_id,
            "chunk_index": index,
            "total_chunks": len(ranges),
            "line_start": line_start,
            "line_end": line_end,
            "scope": "",
        })
    return {"ids": ids, "documents": documents, "metadatas": metadatas}


def _doc(filename, source, chunk_count=1, total_chunks=None):
    return {
        "filename": filename,
        "source": core._normalize_path(source),
        "chunk_count": chunk_count,
        "total_chunks": total_chunks or chunk_count,
    }


class FakeGetCollection:
    def __init__(self, responses):
        self.responses = responses
        self.queries = []

    def count(self):
        return 1

    def get(self, where=None, include=None, ids=None):
        self.queries.append({"where": where, "include": include, "ids": ids})
        if where:
            key, value = next(iter(where.items()))
            return self.responses.get((key, value), _empty_result())
        return _empty_result()


class FakeSearchCollection:
    def __init__(self, source):
        self.source = source
        self.where = None

    def count(self):
        return 1

    def query(self, query_embeddings, n_results, where=None, include=None):
        self.where = where
        return {
            "ids": [["doc1_c0"]],
            "documents": [["matched chunk"]],
            "metadatas": [[{
                "source": self.source,
                "filename": "config.py",
                "doc_id": "doc1",
                "chunk_index": 0,
                "total_chunks": 1,
                "line_start": 1,
                "line_end": 5,
                "scope": "",
            }]],
            "distances": [[0.123]],
        }


def test_get_context_chunks_line_range_is_inclusive(monkeypatch):
    source = core._normalize_path("D:/repo/pkg/config.py")
    collection = FakeGetCollection({("doc_id", "doc1"): _chunk_result(source)})
    monkeypatch.setattr(core, "_get_existing_collection", lambda name: collection)

    result = core.get_context_chunks(
        "doc1",
        collection_name="test",
        line_start=20,
        line_end=20,
    )

    assert result["found"] is True
    assert [chunk["index"] for chunk in result["chunks"]] == [0]


def test_file_lookup_rejects_short_filename_even_if_basename_matches():
    source = core._normalize_path("D:/repo/pkg/config.py")
    collection = FakeGetCollection({("filename", "config.py"): _chunk_result(source)})

    result = core._query_file_by_identifier(collection, "config.py")

    assert result == _empty_result()
    assert all(query["where"] != {"filename": "config.py"} for query in collection.queries)


def test_get_file_chunks_rejects_relative_path(monkeypatch):
    source = core._normalize_path("D:/repo/pkg/config.py")
    collection = FakeGetCollection({("source", source): _chunk_result(source)})
    monkeypatch.setattr(core, "_get_existing_collection", lambda name: collection)

    result = core.get_file_chunks("pkg/config.py", collection_name="test")

    assert result["found"] is False
    assert "Full absolute file_path is required" in result["error"]
    assert collection.queries == []


def test_file_lookup_does_not_fallback_from_full_path_to_basename():
    source = core._normalize_path("D:/repo/pkg/config.py")
    missing_source = core._normalize_path("D:/repo/other/config.py")
    collection = FakeGetCollection({("filename", "config.py"): _chunk_result(source)})

    result = core._query_file_by_identifier(collection, missing_source)

    assert result == _empty_result()
    assert collection.queries == [{
        "where": {"source": missing_source},
        "include": ["documents", "metadatas"],
        "ids": None,
    }]


def test_search_filter_file_path_uses_source_metadata(monkeypatch):
    source = core._normalize_path("D:/repo/pkg/config.py")
    collection = FakeSearchCollection(source)
    monkeypatch.setattr(core, "_get_existing_collection", lambda name: collection)
    monkeypatch.setattr(core, "embed", lambda texts: [[0.1, 0.2]])

    documents, metadatas, distances, rerank_used, total, rerank_scores = core.search(
        "config settings",
        collection_name="test",
        use_bm25=True,
        use_rerank=False,
        filter_file_path="D:/repo/pkg/config.py",
    )

    assert collection.where == {"source": source}
    assert documents == ["matched chunk"]
    assert metadatas[0]["source"] == source
    assert distances == [0.123]
    assert rerank_used is False
    assert total == 1
    assert rerank_scores == []


def test_search_filter_file_path_rejects_relative_path(monkeypatch):
    source = core._normalize_path("D:/repo/pkg/config.py")
    collection = FakeSearchCollection(source)
    monkeypatch.setattr(core, "_get_existing_collection", lambda name: collection)
    monkeypatch.setattr(core, "embed", lambda texts: [[0.1, 0.2]])

    documents, metadatas, distances, rerank_used, total, rerank_scores = core.search(
        "config settings",
        collection_name="test",
        filter_file_path="pkg/config.py",
    )

    assert collection.where is None
    assert documents == []
    assert metadatas == []
    assert distances == []
    assert rerank_used is False
    assert total == 1
    assert rerank_scores == []


def test_grep_filter_file_path_matches_source_metadata(monkeypatch):
    raw_root = Path("tests/.tmp_core_path_filters")
    shutil.rmtree(raw_root, ignore_errors=True)
    try:
        collection_dir = raw_root / "test"
        collection_dir.mkdir(parents=True)
        (collection_dir / "doc1.py").write_text("needle\n", encoding="utf-8")
        (collection_dir / "doc2.py").write_text("needle\n", encoding="utf-8")

        source1 = core._normalize_path("D:/repo/pkg/a.py")
        source2 = core._normalize_path("D:/repo/pkg/b.py")
        monkeypatch.setattr(core, "_raw_files_dir", lambda: str(raw_root))
        monkeypatch.setattr(core, "_get_doc_id_map", lambda collection_name: {
            "doc1": {"filename": "a.py", "source": source1},
            "doc2": {"filename": "b.py", "source": source2},
        })

        results = core.grep_knowledge(
            "needle",
            collection_name="test",
            filter_file_path="D:/repo/pkg/b.py",
        )

        assert len(results) == 1
        assert results[0]["source"] == source2
    finally:
        shutil.rmtree(raw_root, ignore_errors=True)


def test_grep_filter_file_path_rejects_relative_path(monkeypatch):
    raw_root = Path("tests/.tmp_core_path_filters")
    shutil.rmtree(raw_root, ignore_errors=True)
    try:
        collection_dir = raw_root / "test"
        collection_dir.mkdir(parents=True)
        (collection_dir / "doc1.py").write_text("needle\n", encoding="utf-8")

        monkeypatch.setattr(core, "_raw_files_dir", lambda: str(raw_root))
        monkeypatch.setattr(core, "_get_doc_id_map", lambda collection_name: {
            "doc1": {"filename": "a.py", "source": core._normalize_path("D:/repo/pkg/a.py")},
        })

        results = core.grep_knowledge(
            "needle",
            collection_name="test",
            filter_file_path="pkg/a.py",
        )

        assert results == []
    finally:
        shutil.rmtree(raw_root, ignore_errors=True)


def test_find_files_matches_short_filename_and_returns_full_paths(monkeypatch):
    monkeypatch.setattr(core, "list_documents", lambda collection_name: {
        "doc1": _doc("history.py", "D:/repo/langchain_core/runnables/history.py", 20),
        "doc2": _doc("chat_history.py", "D:/repo/langchain_core/chat_history.py", 3),
        "doc3": _doc("other.py", "D:/repo/other.py", 1),
    })

    results = core.find_files("history.py", collection_name="test", max_results=10)

    assert [r["doc_id"] for r in results] == ["doc1", "doc2"]
    assert results[0]["match"] == "filename"
    assert results[0]["file_path"] == "D:/repo/langchain_core/runnables/history.py"
    assert results[0]["chunk_count"] == 20


def test_find_files_supports_regex_and_case_sensitive(monkeypatch):
    monkeypatch.setattr(core, "list_documents", lambda collection_name: {
        "doc1": _doc("History.py", "D:/repo/History.py"),
        "doc2": _doc("history.py", "D:/repo/history.py"),
    })

    insensitive = core.find_files(r"^history\.py$", collection_name="test", case_sensitive=False)
    sensitive = core.find_files(r"^history\.py$", collection_name="test", case_sensitive=True)

    assert [r["doc_id"] for r in insensitive] == ["doc1", "doc2"]
    assert [r["doc_id"] for r in sensitive] == ["doc2"]
