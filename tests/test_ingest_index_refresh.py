from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nbrag import ingest


class _FakeCollection:
    def __init__(self) -> None:
        self.documents = ["old document", "new document"]
        self.ids = ["old_c0", "new_c0"]

    def get(self, include=None):
        return {"documents": list(self.documents), "ids": list(self.ids)}


class IngestIndexRefreshTests(unittest.TestCase):
    def test_ingest_file_refreshes_bm25_and_symbol_disk_indexes(self) -> None:
        collection = _FakeCollection()
        prepared = {"ok": True}
        write_result = {
            "ok": True,
            "filename": "new.py",
            "chars": 20,
            "chunks": 1,
            "doc_id": "new",
        }

        with tempfile.TemporaryDirectory() as tmp:
            index_root = Path(tmp)

            def build_bm25(collection_name, documents, chunk_ids):
                (index_root / f"{collection_name}.bm25").write_text(
                    "|".join(chunk_ids), encoding="utf-8"
                )

            def build_symbol(collection_name):
                (index_root / f"{collection_name}.symbols").write_text(
                    "fresh", encoding="utf-8"
                )
                return {}

            with patch("nbrag.ingest._prepare_file", return_value=prepared), \
                 patch("nbrag.ingest._write_to_db", return_value=write_result), \
                 patch("nbrag.ingest.get_collection", return_value=collection), \
                 patch("nbrag.ingest.build_bm25_index", side_effect=build_bm25), \
                 patch("nbrag.ingest.build_symbol_index", side_effect=build_symbol):
                result = ingest.ingest_file("new.py", "kb", use_cache=False)

            self.assertTrue(result["ok"])
            self.assertEqual((index_root / "kb.bm25").read_text(encoding="utf-8"), "old_c0|new_c0")
            self.assertEqual((index_root / "kb.symbols").read_text(encoding="utf-8"), "fresh")

    def test_ingest_path_refreshes_disk_indexes_once_after_all_files(self) -> None:
        collection = _FakeCollection()
        files = ["first.py", "second.py"]

        def ingest_one(file_path, collection_name, chunk_size, chunk_overlap,
                       sleep_interval=0.0, use_cache=True, verbose=False,
                       refresh_indexes=True):
            return {
                "ok": True,
                "filename": file_path,
                "chars": 10,
                "chunks": 1,
                "doc_id": Path(file_path).stem,
            }

        with patch("nbrag.ingest.os.path.exists", return_value=True), \
             patch("nbrag.ingest.collect_files", return_value=files), \
             patch("nbrag.ingest._ingest_file", side_effect=ingest_one), \
             patch("nbrag.ingest.get_collection", return_value=collection), \
             patch("nbrag.ingest.build_bm25_index") as build_bm25, \
             patch("nbrag.ingest.build_symbol_index", return_value={}) as build_symbol:
            results, errors, skipped = ingest.ingest_path("src", "kb", use_cache=False)

        self.assertEqual(len(results), 2)
        self.assertEqual(errors, [])
        self.assertEqual(skipped, 0)
        build_bm25.assert_called_once_with("kb", collection.documents, collection.ids)
        build_symbol.assert_called_once_with("kb")


if __name__ == "__main__":
    unittest.main()
