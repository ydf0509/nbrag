from __future__ import annotations

import inspect
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nbrag import chunker, ingest, mcp_tools, retrieval, server


class McpContractTests(unittest.TestCase):
    def test_all_exposed_mcp_tools_use_tagged_text_returns(self) -> None:
        search_result = (
            ["matched text"],
            [{
                "filename": "file.txt",
                "source": "D:/docs/file.txt",
                "chunk_index": 1,
                "total_chunks": 3,
                "line_start": 2,
                "line_end": 4,
                "scope": "Demo.run",
                "doc_id": "doc-1",
            }],
            [0.125],
            False,
            3,
            [],
        )
        chunk_data = {
            "found": True,
            "source": "D:/docs/file.txt",
            "doc_id": "doc-1",
            "total_chunks": 3,
            "total_lines": 8,
            "end_chunk": 1,
            "chunks": [{
                "chunk_index": 1,
                "line_start": 2,
                "line_end": 4,
                "scope": "Demo.run",
                "content": "chunk body",
            }],
        }
        raw_data = {
            "found": True,
            "raw": True,
            "source": "D:/docs/file.txt",
            "doc_id": "doc-1",
            "total_chunks": 3,
            "total_lines": 3,
            "line_start": 1,
            "line_end": 3,
            "content": "raw body\n",
        }
        config = SimpleNamespace(rerank=SimpleNamespace(model="reranker-v2"))

        with patch("nbrag.mcp_tools._load_workflow_skill_text", return_value=""):
            help_result = mcp_tools.nbrag_help()
        with patch("nbrag.mcp_tools.get_stats", return_value={"collections": {"kb": {"docs": 1, "chunks": 3}}}):
            stats_result = mcp_tools.nbrag_stats()
        with patch("nbrag.mcp_tools.search", return_value=search_result), \
             patch("nbrag.mcp_tools.get_config", return_value=config):
            search_result_text = mcp_tools.nbrag_search("query", "kb")
            bm25_result = mcp_tools.nbrag_search_only_bm25("term", "kb")
            vector_result = mcp_tools.nbrag_search_only_vector("query", "kb")
        with patch("nbrag.mcp_tools.search", return_value=search_result), \
             patch("nbrag.mcp_tools.get_config", return_value=config), \
             patch("nbrag.mcp_tools.get_file_chunks", return_value=raw_data):
            fetch_result = mcp_tools.nbrag_search_and_fetch("query", "kb")
        with patch("nbrag.mcp_tools.grep_knowledge", return_value=[{
            "source": "D:/docs/file.txt",
            "doc_id": "doc-1",
            "line_number": 3,
            "context": "exact text",
        }]):
            grep_result = mcp_tools.nbrag_grep("exact", "kb")
        with patch("nbrag.mcp_tools.find_symbol_definition", return_value=[{
            "symbol_type": "function",
            "qualified_name": "demo",
            "source": "D:/docs/file.py",
            "doc_id": "doc-2",
            "line_start": 1,
            "line_end": 2,
            "definition": "def demo():\n    pass",
        }]):
            definition_result = mcp_tools.nbrag_find_definition("demo", "kb")
        with patch("nbrag.mcp_tools.find_files", return_value=[{
            "source": "D:/docs/file.txt",
            "doc_id": "doc-1",
            "filename": "file.txt",
            "total_chunks": 3,
            "match": "filename",
        }]):
            files_result = mcp_tools.nbrag_find_files("file", "kb")
        with patch("nbrag.mcp_tools.get_context_chunks", return_value=chunk_data):
            adjacent_result = mcp_tools.nbrag_get_adjacent_chunks("doc-1", 1, "kb")
            lines_result = mcp_tools.nbrag_get_chunks_by_lines("doc-1", 2, 4, "kb")
        with patch("nbrag.mcp_tools.get_file_chunks", return_value=chunk_data):
            chunks_result = mcp_tools.nbrag_get_file_chunks("D:/docs/file.txt", "kb")
        with patch("nbrag.mcp_tools.get_file_chunks", return_value=raw_data):
            raw_result = mcp_tools.nbrag_get_raw_file("D:/docs/file.txt", "kb")
        with patch("nbrag.mcp_tools.list_documents", return_value={
            "doc-1": {"source": "D:/docs/file.txt", "filename": "file.txt", "total_chunks": 3},
        }):
            list_result = mcp_tools.nbrag_list("kb")

        contracts = [
            (help_result, "nbrag_help", "returned_guidance_count", []),
            (stats_result, "nbrag_stats", "returned_collection_count", ["nbrag_collection"]),
            (search_result_text, "nbrag_search", "returned_hit_count", ["nbrag_ranked_hit", "nbrag_chunk_content"]),
            (bm25_result, "nbrag_search_only_bm25", "returned_hit_count", ["nbrag_ranked_hit", "nbrag_chunk_content"]),
            (vector_result, "nbrag_search_only_vector", "returned_hit_count", ["nbrag_ranked_hit", "nbrag_chunk_content"]),
            (fetch_result, "nbrag_search_and_fetch", "returned_hit_count", ["nbrag_follow_up", "nbrag_ranked_hit", "nbrag_chunk_content", "nbrag_raw_excerpt", "nbrag_raw_content"]),
            (grep_result, "nbrag_grep", "returned_match_count", ["nbrag_match", "nbrag_original_text_content"]),
            (definition_result, "nbrag_find_definition", "returned_definition_count", ["nbrag_definition", "nbrag_definition_content"]),
            (files_result, "nbrag_find_files", "returned_file_count", ["nbrag_file"]),
            (chunks_result, "nbrag_get_file_chunks", "returned_chunk_count", ["nbrag_chunk", "nbrag_chunk_content"]),
            (raw_result, "nbrag_get_raw_file", "returned_raw_count", ["nbrag_raw_content"]),
            (adjacent_result, "nbrag_get_adjacent_chunks", "returned_chunk_count", ["nbrag_chunk", "nbrag_chunk_content"]),
            (lines_result, "nbrag_get_chunks_by_lines", "returned_chunk_count", ["nbrag_chunk", "nbrag_chunk_content"]),
            (list_result, "nbrag_list", "returned_document_count", ["nbrag_document"]),
        ]
        for result, root, count_name, child_tags in contracts:
            with self.subTest(root=root):
                self.assertTrue(result.startswith(f'<{root} status="success" {count_name}="'), result[:200])
                self.assertTrue(result.rstrip().endswith(f"</{root}>"), result[-200:])
                self.assertIn("<request_parameters>", result)
                self.assertIn("<execution>", result)
                self.assertNotIn("<top_result_handles>", result)
                self.assertNotIn("<guidance>", result)
                for child_tag in child_tags:
                    self.assertIn(f"<{child_tag}>", result)
                    self.assertIn(f"</{child_tag}>", result)

        self.assertIn("file_path = D:/docs/file.txt", search_result_text)
        self.assertIn("chunk_index = 1", search_result_text)
        self.assertIn("line_start = 3\nline_end = 3", grep_result)
        path_error = mcp_tools.nbrag_get_raw_file("file.txt", "kb")
        self.assertTrue(path_error.startswith('<nbrag_get_raw_file status="error">'))
        self.assertIn("<error>\ntype = invalid_file_path\nfield = file_path", path_error)

    def test_no_results_is_success_with_zero_count(self) -> None:
        with patch("nbrag.mcp_tools.grep_knowledge", return_value=[]), \
             patch("nbrag.mcp_tools.get_stats", return_value={"collections": {"kb": {"docs": 1, "chunks": 3}}}):
            result = mcp_tools.nbrag_grep("missing", "kb")

        self.assertTrue(result.startswith('<nbrag_grep status="success" returned_match_count="0">'))
        self.assertIn("<execution>\noutcome = no_results", result)
        self.assertNotIn("<error>", result)

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

    def test_help_distinguishes_chunk_and_original_text_outputs(self) -> None:
        with patch("nbrag.mcp_tools._load_workflow_skill_text", return_value=""):
            result = mcp_tools.nbrag_help()

        self.assertIn("<nbrag_follow_up>", result)
        self.assertIn("`<nbrag_chunk_content>` is exactly one RAG chunk", result)
        self.assertIn("When the answer, quotation, or verification depends on text outside the shown chunk or raw excerpt", result)
        self.assertIn("`<nbrag_original_text_content>` is a stored-original-text context excerpt", result)
        self.assertIn("Omit both line bounds only when you intentionally need the complete stored file", result)

    def test_routing_guidance_is_reused_within_a_conversation(self) -> None:
        with patch("nbrag.mcp_tools._load_workflow_skill_text", return_value=""):
            help_result = mcp_tools.nbrag_help()

        self.assertIn("current conversation context", help_result)
        self.assertIn("reusable for all later nbrag retrieval questions", help_result)
        self.assertNotIn("new retrieval task", help_result)
        for tool in (server.nbrag_search, server.nbrag_search_and_fetch, server.nbrag_stats):
            self.assertIn("current conversation context", tool.__doc__)
            self.assertNotIn("new retrieval task", tool.__doc__)

    def test_grep_keeps_handles_on_match_entity_only(self) -> None:
        fake_results = [{
            "source": "D:/docs/file.txt",
            "doc_id": "doc-1",
            "line_number": 4,
            "context": "    4| exact phrase",
        }]
        with patch("nbrag.mcp_tools.grep_knowledge", return_value=fake_results):
            result = mcp_tools.nbrag_grep("exact phrase", "kb")

        self.assertIn("<nbrag_match>\nfile_path = D:/docs/file.txt\ndoc_id = doc-1\nline_start = 4\nline_end = 4", result)
        self.assertNotIn("Top match handles", result)
        self.assertNotIn("guidance", result)

    def test_definition_keeps_handles_on_definition_entity_only(self) -> None:
        fake_results = [{
            "symbol_type": "function",
            "qualified_name": "demo",
            "source": "D:/docs/demo.py",
            "doc_id": "doc-1",
            "line_start": 2,
            "line_end": 3,
            "definition": "def demo():\n    return 1",
        }]
        with patch("nbrag.mcp_tools.find_symbol_definition", return_value=fake_results):
            result = mcp_tools.nbrag_find_definition("demo", "kb")

        self.assertIn("<nbrag_definition>\nsymbol_type = function\nqualified_name = demo\nfile_path = D:/docs/demo.py\ndoc_id = doc-1\nline_start = 2\nline_end = 3", result)
        self.assertNotIn("Top definition handles", result)
        self.assertNotIn("guidance", result)

    def test_list_exposes_handles_only_on_document_entities(self) -> None:
        fake_rows = {"doc-1": {"source": "D:/docs/file.txt", "filename": "file.txt", "total_chunks": 2}}
        with patch("nbrag.mcp_tools.list_documents", return_value=fake_rows):
            result = mcp_tools.nbrag_list("kb")

        self.assertIn("<nbrag_document>\ndoc_id = doc-1\nfile_path = D:/docs/file.txt", result)
        self.assertNotIn("Unlocks:", result)

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

        self.assertTrue(result.startswith('<nbrag_search status="success" returned_hit_count="1">'))
        self.assertIn("name = collection_name\nvalue = worker_rights", result)
        self.assertIn("name = filter_file_path\nvalue = D:/docs/labor_law/劳动合同法.md", result)
        self.assertNotIn("bm25 = off", result)
        self.assertNotIn("rerank = reranker-v2", result)
        self.assertIn("file_path = D:/docs/labor_law/劳动合同法.md", result)
        self.assertIn("total_chunks = 9", result)
        self.assertIn("chunk_index = 3", result)
        self.assertNotIn("Available follow-up tools when you need to expand, quote, or verify:", result)
        self.assertIn("<nbrag_ranked_hit>\nrank = 1", result)
        self.assertIn("score = 0.9876", result)

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
        self.assertIn("<nbrag_follow_up>", result)
        self.assertLess(result.index("<nbrag_follow_up>"), result.index("<nbrag_ranked_hit>"))
        self.assertIn("Do not treat either bounded result as complete source context.", result)
        self.assertIn("file_path -> nbrag_get_raw_file(file_path, collection_name, line_start, line_end)", result)
        self.assertIn("doc_id + chunk_index -> nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name)", result)
        self.assertIn("doc_id + line_start + line_end -> nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name)", result)
        self.assertIn("<nbrag_ranked_hit>", result)
        self.assertIn("<nbrag_raw_excerpt>", result)
        self.assertIn("file_path = D:/docs/labor_law/劳动合同法.md\ndoc_id = doc-1\nline_start = 1\nline_end = 3", result)
        self.assertIn("第二行", result)

    def test_get_raw_file_uses_none_for_omitted_line_bounds(self) -> None:
        raw_file_data = {
            "found": True,
            "raw": True,
            "source": "D:/docs/file.txt",
            "filename": "file.txt",
            "doc_id": "doc-1",
            "total_chunks": 1,
            "total_lines": 2,
            "line_start": 1,
            "line_end": 2,
            "content": "first\nsecond\n",
        }
        with patch("nbrag.mcp_tools.get_file_chunks", return_value=raw_file_data) as mock_get_file_chunks:
            result = mcp_tools.nbrag_get_raw_file("D:/docs/file.txt", "kb")

        mock_get_file_chunks.assert_called_once_with(
            "D:/docs/file.txt", "kb", 0, 0, raw=True, line_start=None, line_end=None,
        )
        self.assertIn("line_start = 1\nline_end = 2", result)

    def test_raw_file_description_prefers_a_broad_500_line_window(self) -> None:
        signature = inspect.signature(server.nbrag_get_raw_file)
        line_start_description = signature.parameters["line_start"].default.description
        line_end_description = signature.parameters["line_end"].default.description

        self.assertIn("line_end = line_start + 500", line_end_description)
        self.assertIn("DEFAULT BOUNDED READ POLICY", server.nbrag_get_raw_file.__doc__)
        self.assertIn("line_end = line_start + 500", server.nbrag_get_raw_file.__doc__)
        self.assertIn("Do not copy a short range", server.nbrag_get_raw_file.__doc__)

    def test_get_raw_file_returns_full_content_when_line_bounds_are_none(self) -> None:
        with patch("nbrag.retrieval._get_existing_collection", return_value=SimpleNamespace(count=lambda: 1)), \
             patch("nbrag.retrieval._query_file_by_identifier", return_value={
                 "ids": ["chunk-1"],
                 "documents": ["chunk"],
                 "metadatas": [{
                     "chunk_index": 0,
                     "line_end": 3,
                     "doc_id": "doc-1",
                     "source": "D:/docs/file.txt",
                     "filename": "file.txt",
                 }],
             }), \
             patch("nbrag.retrieval._get_cached_raw_doc", return_value={"content": "first\nsecond\nthird\n"}):
            result = retrieval.get_raw_file("D:/docs/file.txt", "kb")

        self.assertTrue(result["found"])
        self.assertEqual(result["line_start"], 1)
        self.assertEqual(result["line_end"], 3)
        self.assertEqual(result["content"], "first\nsecond\nthird\n")

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
