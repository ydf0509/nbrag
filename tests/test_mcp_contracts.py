from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nbrag import chunker, ingest, mcp_tools, retrieval, server


class McpContractTests(unittest.TestCase):
    def test_server_search_only_vector_uses_dedicated_helper(self) -> None:
        with patch("nbrag.server.mcp_tools.nbrag_search_only_vector", return_value="VECTOR") as mock_vector, \
             patch("nbrag.server.mcp_tools.nbrag_search") as mock_search:
            result = server.nbrag_search_only_vector(
                query="semantic intent",
                collection_name="kb",
                top_k=2,
                filter_file_path="D:/docs/file.md",
                include_content=False,
            )

        self.assertEqual(result, "VECTOR")
        mock_vector.assert_called_once_with("semantic intent", "kb", 2, "D:/docs/file.md", False)
        mock_search.assert_not_called()

    def test_delete_reports_deleted_count_and_filename(self) -> None:
        with patch("nbrag.mcp_tools.delete_document", return_value=(3, "劳动合同法.md")):
            result = mcp_tools.nbrag_delete("doc-1", "worker_rights")

        self.assertEqual(result, "Deleted 3 chunk(s) for filename: 劳动合同法.md | doc_id: doc-1")

    def test_grep_returns_collection_issue_for_missing_collection(self) -> None:
        with patch("nbrag.mcp_tools.grep_knowledge", return_value=[]), \
             patch("nbrag.mcp_tools.get_stats", return_value={"collections": {"worker_rights": {"docs": 1, "chunks": 1}}}):
            result = mcp_tools.nbrag_grep("第十九条", "missing_collection")

        self.assertIn("collection 'missing_collection' does not exist.", result)
        self.assertIn("Available collections: ['worker_rights']", result)

    def test_search_output_includes_handles_and_filter_note(self) -> None:
        fake_config = SimpleNamespace(rerank=SimpleNamespace(model="reranker-v2"))
        fake_search_result = (
            ["matched text"],
            [{
                "filename": "劳动合同法.md",
                "source": "D:/docs/labor_law/劳动合同法.md",
                "chunk_index": 3,
                "total_chunks": 9,
                "line_start": 10,
                "line_end": 20,
                "scope": "劳动合同法.试用期",
                "doc_id": "doc-1",
            }],
            [0.1234],
            True,
            9,
            [0.9876],
        )
        with patch("nbrag.mcp_tools.search", return_value=fake_search_result), \
             patch("nbrag.mcp_tools.get_config", return_value=fake_config):
            result = mcp_tools.nbrag_search(
                query="trial period",
                collection_name="worker_rights",
                top_k=1,
                use_rerank=True,
                use_bm25=True,
                filter_file_path="D:/docs/labor_law/劳动合同法.md",
                include_content=False,
                bm25_query="试用期",
            )

        self.assertIn("[worker_rights] 9 chunks | bm25: off | rerank: reranker-v2 | filter_file_path: D:/docs/labor_law/劳动合同法.md", result)
        self.assertIn("Returned handle fields for follow-up: file_path, doc_id, chunk_index, line range.", result)
        self.assertIn("query remains the semantic question for vector retrieval/rerank; bm25_query only changes BM25 wording when BM25 is active.", result)
        self.assertIn("Behavior note: with filter_file_path set, current hybrid behavior narrows vector retrieval to that single file and does not run cross-file BM25 fusion.", result)
        self.assertIn("content omitted", result)

    def test_search_and_fetch_auto_fetches_original_content(self) -> None:
        fake_config = SimpleNamespace(rerank=SimpleNamespace(model="reranker-v2"))
        fake_search_result = (
            ["ranked text"],
            [{
                "filename": "劳动合同法.md",
                "source": "D:/docs/labor_law/劳动合同法.md",
                "chunk_index": 1,
                "total_chunks": 5,
                "line_start": 2,
                "line_end": 2,
                "scope": "劳动合同法.试用期",
                "doc_id": "doc-1",
            }],
            [0.2222],
            True,
            5,
            [0.8888],
        )
        raw_file_data = {
            "found": True,
            "raw": True,
            "source": "D:/docs/labor_law/劳动合同法.md",
            "filename": "劳动合同法.md",
            "doc_id": "doc-1",
            "total_chunks": 5,
            "total_lines": 3,
            "line_start": 1,
            "line_end": 3,
            "content": "第一行\n第二行\n第三行\n",
        }
        with patch("nbrag.mcp_tools.search", return_value=fake_search_result), \
             patch("nbrag.mcp_tools.get_config", return_value=fake_config), \
             patch("nbrag.mcp_tools.get_file_chunks", return_value=raw_file_data) as mock_get_file_chunks:
            result = mcp_tools.nbrag_search_and_fetch(
                query="trial period",
                collection_name="worker_rights",
                top_k=1,
                fetch_top_n_raw=1,
                fetch_context_chars=200,
                filter_file_path="",
                bm25_query="试用期",
            )

        mock_get_file_chunks.assert_called_once_with("D:/docs/labor_law/劳动合同法.md", "worker_rights", 0, 0, raw=True)
        self.assertIn("Ranked search results:", result)
        self.assertIn("Auto-fetched original content (1 file(s)):", result)
        self.assertIn("original_file: 劳动合同法.md | file_path: D:/docs/labor_law/劳动合同法.md | doc_id: doc-1 | range: line:", result)
        self.assertIn("第二行", result)

    def test_grep_handles_crlf_line_boundaries(self) -> None:
        raw_cache = {
            "kb": {
                "doc-1": {
                    "content": "first\r\nmatch\r\nthird\r\n",
                    "source": "D:/docs/file.txt",
                    "filename": "file.txt",
                }
            }
        }
        with patch("nbrag.retrieval._load_all_raw_texts_cached", return_value=raw_cache):
            results = retrieval.grep_knowledge("match", "kb", max_results=5, case_sensitive=False, filter_file_path=None, match_context_chars=40)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["line_number"], 2)
        self.assertIn(">>>     2| match", results[0]["context"])
        self.assertIn("    1| first", results[0]["context"])
        self.assertIn("    3| third", results[0]["context"])

    def test_collect_files_excludes_paths_with_mixed_separators(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            tests_dir = root / "tests"
            tests_old_dir = root / "tests_old"
            dist_dir = root / "dist"
            src_dir = root / "src"
            for directory in (tests_dir, tests_old_dir, dist_dir, src_dir):
                directory.mkdir(parents=True, exist_ok=True)

            keep_file = src_dir / "main.py"
            tests_file = tests_dir / "test_main.py"
            tests_old_file = tests_old_dir / "test_old.py"
            dist_file = dist_dir / "bundle.py"
            readme_file = root / "README.md"
            for file_path in (keep_file, tests_file, tests_old_file, dist_file, readme_file):
                file_path.write_text("content", encoding="utf-8")

            excluded_tests = str(tests_dir).replace("/", "\\")
            excluded_dist = str(dist_dir).replace("\\", "/")
            excluded_readme = str(readme_file)

            files = chunker.collect_files(
                str(root),
                file_extensions=[".py", ".md"],
                excluded_paths=[excluded_tests, excluded_dist, excluded_readme],
            )
            normalized = {Path(path).resolve() for path in files}

            self.assertIn(keep_file.resolve(), normalized)
            self.assertIn(tests_old_file.resolve(), normalized)
            self.assertNotIn(tests_file.resolve(), normalized)
            self.assertNotIn(dist_file.resolve(), normalized)
            self.assertNotIn(readme_file.resolve(), normalized)

    def test_batch_ingest_auto_excludes_git_for_directory_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            git_dir = root / ".git"
            src_dir = root / "src"
            root.mkdir(parents=True, exist_ok=True)
            git_dir.mkdir(parents=True, exist_ok=True)
            src_dir.mkdir(parents=True, exist_ok=True)
            (git_dir / "HEAD").write_text("ref: refs/heads/main", encoding="utf-8")
            (src_dir / "main.py").write_text("print('ok')", encoding="utf-8")

            captured = {}

            def fake_check_file_cache(fp, collection_name):
                return False, None

            def fake_prepare_file_no_embed(fp, chunk_size, chunk_overlap):
                captured.setdefault("files", []).append(fp)
                return {
                    "ok": True,
                    "filename": Path(fp).name,
                    "source": fp,
                    "content": "x",
                    "chunks": 1,
                    "char_count": 1,
                }

            def fake_batch_embed_prepared(prepared_list, sleep_interval=0.0, verbose=False):
                return prepared_list

            def fake_write_to_db(prepared, collection_name):
                return {"ok": True, "chunks": prepared["chunks"], "chars": prepared["char_count"]}

            def fake_get_collection(collection_name):
                return object()

            def fake_batch_get(col, include=None):
                return {"documents": [], "ids": []}

            with patch("nbrag.ingest.check_file_cache", side_effect=fake_check_file_cache), \
                 patch("nbrag.ingest.prepare_file_no_embed", side_effect=fake_prepare_file_no_embed), \
                 patch("nbrag.ingest.batch_embed_prepared", side_effect=fake_batch_embed_prepared), \
                 patch("nbrag.ingest._write_to_db", side_effect=fake_write_to_db), \
                 patch("nbrag.ingest.get_collection", side_effect=fake_get_collection), \
                 patch("nbrag.ingest._batch_get", side_effect=fake_batch_get), \
                 patch("nbrag.ingest.build_bm25_index"), \
                 patch("nbrag.ingest.build_symbol_index", return_value={}), \
                 patch("nbrag.ingest.set_collection_profile"):
                ingest.batch_ingest(
                    paths=[str(root)],
                    collection_name="kb",
                    file_extensions=[".py", ".md"],
                    delete_first=False,
                    verbose=False,
                    max_workers=1,
                    use_cache=False,
                )

            processed = {Path(path).resolve() for path in captured.get("files", [])}
            self.assertIn((src_dir / "main.py").resolve(), processed)
            self.assertNotIn((git_dir / "HEAD").resolve(), processed)

    def test_python_ast_definition_range_includes_decorators(self) -> None:
        source = """\
@outer
@inner(x=1)
class Demo:
    @classmethod
    @retry(times=3)
    async def fetch(cls):
        return 1
"""
        tree = chunker.ast.parse(source)
        cls = tree.body[0]
        method = cls.body[0]

        self.assertEqual(chunker.get_ast_definition_line_range(cls), (1, 7))
        self.assertEqual(chunker.get_ast_definition_line_range(method), (4, 7))

        scope_map = chunker._build_python_scope_map(source)
        class_entry = next(entry for entry in scope_map if entry[2] == "Demo")
        method_entry = next(entry for entry in scope_map if entry[2] == "Demo.fetch")
        self.assertEqual(class_entry[:2], (1, 7))
        self.assertEqual(method_entry[:2], (4, 7))


if __name__ == "__main__":
    unittest.main()
