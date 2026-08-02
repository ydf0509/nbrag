from __future__ import annotations

import math
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nbrag import bm25_index, retrieval


class _FakeArray:
    def __init__(self, values):
        self._values = values

    def __getitem__(self, index):
        return self._values[index]


class _FakeRetriever:
    def retrieve(self, queries, k, show_progress):
        return _FakeArray([[0, 1, 2]]), _FakeArray([[3.0, 0.0, -1.0]])


class _FakeCollection:
    def __init__(self):
        self.n_results = None

    def count(self):
        return 3

    def query(self, query_embeddings, n_results, where, include):
        self.n_results = n_results
        return {
            "ids": [["chunk-1"]],
            "documents": [["content"]],
            "metadatas": [[{"doc_id": "doc-1"}]],
            "distances": [[0.1]],
        }


class RetrievalAuditFixTests(unittest.TestCase):
    def test_search_clamps_non_positive_top_k_before_retrieval(self) -> None:
        collection = _FakeCollection()
        config = SimpleNamespace(rerank=SimpleNamespace(model=""))

        with patch("nbrag.retrieval._get_existing_collection", return_value=collection), \
             patch("nbrag.retrieval.embed", return_value=[[0.5]]), \
             patch("nbrag.retrieval._cfg", return_value=config):
            documents, _, _, _, _, _ = retrieval.search(
                "query", "kb", top_k=0, use_rerank=False, use_bm25=False
            )

        self.assertEqual(collection.n_results, 1)
        self.assertEqual(documents, ["content"])

    def test_search_replaces_non_finite_top_k_with_default(self) -> None:
        collection = _FakeCollection()
        config = SimpleNamespace(rerank=SimpleNamespace(model=""))

        with patch("nbrag.retrieval._get_existing_collection", return_value=collection), \
             patch("nbrag.retrieval.embed", return_value=[[0.5]]), \
             patch("nbrag.retrieval._cfg", return_value=config):
            retrieval.search(
                "query", "kb", top_k=math.inf, use_rerank=False, use_bm25=False
            )

        self.assertEqual(collection.n_results, 3)

    def test_bm25_channel_excludes_zero_and_negative_scores(self) -> None:
        with patch(
            "nbrag.bm25_index._load_bm25_index",
            return_value=(_FakeRetriever(), ["positive", "zero", "negative"]),
        ):
            results = bm25_index._bm25_search_channel(["term"], "kb", "word", 3)

        self.assertEqual(results, ["positive"])

    def test_non_python_definition_range_matches_returned_context_via_index(self) -> None:
        content = "\n".join(f"line {i}" for i in range(1, 31))
        content = content.replace("line 10", "line 10 target")
        cache = {
            "kb": {
                "doc-1": {
                    "filename": "notes.md",
                    "source": "D:/docs/notes.md",
                    "content": content,
                }
            }
        }

        with patch("nbrag.retrieval._query_symbol_index", return_value=[]), \
             patch("nbrag.retrieval._load_all_raw_texts_cached", return_value=cache):
            results = retrieval._find_definition_via_index("target", "kb", {}, "unused", 1)

        result = results[0]
        self.assertEqual((result["line_start"], result["line_end"]), (7, 29))
        self.assertEqual(len(result["definition"].splitlines()), 23)
        self.assertTrue(result["definition"].startswith("line 7\n"))

    def test_non_python_definition_range_matches_returned_context_full_scan(self) -> None:
        content = "\n".join(f"line {i}" for i in range(1, 31))
        content = content.replace("line 10", "line 10 target")
        cache = {
            "kb": {
                "doc-1": {
                    "filename": "notes.md",
                    "source": "D:/docs/notes.md",
                    "content": content,
                }
            }
        }

        with tempfile.TemporaryDirectory() as raw_dir, \
             patch("nbrag.retrieval._get_doc_id_map", return_value={}), \
             patch("nbrag.retrieval._load_all_raw_texts_cached", return_value=cache):
            results = retrieval._find_definition_full_scan("target", "kb", raw_dir, 1)

        result = results[0]
        self.assertEqual((result["line_start"], result["line_end"]), (7, 29))
        self.assertEqual(len(result["definition"].splitlines()), 23)
        self.assertTrue(result["definition"].startswith("line 7\n"))


if __name__ == "__main__":
    unittest.main()
