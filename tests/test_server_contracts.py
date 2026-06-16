"""MCP wrapper contract tests that do not require a running server."""

import inspect
from types import SimpleNamespace
from pathlib import Path

from nbrag import server


def _field_default(func, parameter):
    default = inspect.signature(func).parameters[parameter].default
    return default.default


def test_find_definition_default_max_results_is_three():
    assert _field_default(server.nbrag_find_definition, "max_results") == 3


def test_help_is_exposed_as_mcp_tool():
    source = Path(server.__file__).read_text(encoding="utf-8-sig")

    assert source.count("@mcp.tool()") == 12
    assert "@mcp.tool()\ndef nbrag_help(" in source


def test_help_returns_compact_workflow_without_manual_maintenance_tools():
    output = server.nbrag_help()

    required = [
        "nbrag_stats",
        "nbrag_search_and_fetch",
        "nbrag_grep",
        "nbrag_find_definition",
        "nbrag_find_files",
        "nbrag_get_raw_file",
        "nbrag_get_adjacent_chunks",
        "file_path",
        "full absolute",
    ]
    for text in required:
        assert text in output

    forbidden = [
        "nbrag_add_document",
        "nbrag_delete",
        "raw cache",
        "raw_cache",
        "re-import",
    ]
    for text in forbidden:
        assert text not in output


def test_project_metadata_and_docs_frame_nbrag_as_general_text_rag():
    root = Path(server.__file__).resolve().parents[1]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")

    assert "code retrieval" not in pyproject
    assert any(token in pyproject for token in ("knowledge-base", "document-search", "text-search", "legal-search"))
    assert "通用知识场景" in readme
    assert "代码场景" in readme
    assert readme.index("通用知识场景") < readme.index("代码场景")


def test_docs_present_help_as_optional_navigation_not_required_skill():
    root = Path(server.__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    skill = (root / "nbrag" / "skills" / "nbrag-workflow" / "SKILL.md").read_text(encoding="utf-8")

    assert "nbrag_help" in readme
    assert "不复制 Skill" in readme
    assert "nbrag_help" in skill


def test_mcp_docstrings_lead_with_general_text_before_python_source():
    grep_doc = inspect.getdoc(server.nbrag_grep)
    find_doc = inspect.getdoc(server.nbrag_find_definition)

    assert grep_doc is not None
    assert find_doc is not None
    assert "Law/docs/manuals" in grep_doc
    assert "Code:" in grep_doc
    assert grep_doc.index("Law/docs/manuals") < grep_doc.index("Code:")
    assert "Python .py files" in find_doc
    assert "For law/docs/manuals, use nbrag_grep" in find_doc


def test_find_definition_non_python_result_guides_to_grep(monkeypatch):
    monkeypatch.setattr(
        server,
        "find_symbol_definition",
        lambda symbol, collection_name, max_results: [{
            "symbol_type": "text",
            "qualified_name": "第十九条",
            "line_start": 45,
            "line_end": 48,
            "doc_id": "doc1",
            "source": "D:/docs/labor_law/劳动合同法.md",
            "definition": "第十九条 劳动合同期限三个月以上不满一年的...",
        }],
    )

    output = server.nbrag_find_definition(
        symbol="第十九条",
        collection_name="worker_rights",
    )

    assert "For law/docs/manuals, use nbrag_grep" in output
    assert "第十九条 劳动合同期限" in output


def test_search_can_return_metadata_only(monkeypatch):
    monkeypatch.setattr(
        server,
        "get_config",
        lambda: SimpleNamespace(rerank=SimpleNamespace(model="rerank-model")),
    )
    monkeypatch.setattr(
        server,
        "search",
        lambda *args, **kwargs: (
            ["secret content that should not appear"],
            [{
                "source": "D:/repo/history.py",
                "filename": "history.py",
                "chunk_index": 1,
                "total_chunks": 3,
                "line_start": 10,
                "line_end": 20,
                "scope": "RunnableWithMessageHistory",
                "doc_id": "doc1",
            }],
            [0.1234],
            True,
            3,
            [0.9876],
        ),
    )

    output = server.nbrag_search(
        query="history",
        collection_name="test",
        include_content=False,
    )

    assert "secret content" not in output
    assert "content omitted" in output
    assert "file_path: D:/repo/history.py" in output
    assert "doc_id:doc1" in output


def test_search_preview_chars_limits_content(monkeypatch):
    monkeypatch.setattr(
        server,
        "get_config",
        lambda: SimpleNamespace(rerank=SimpleNamespace(model="off")),
    )
    monkeypatch.setattr(
        server,
        "search",
        lambda *args, **kwargs: (
            ["abcdefghijklmnopqrstuvwxyz"],
            [{
                "source": "D:/repo/history.py",
                "filename": "history.py",
                "chunk_index": 1,
                "total_chunks": 3,
                "line_start": 10,
                "line_end": 20,
                "scope": "",
                "doc_id": "doc1",
            }],
            [0.1234],
            False,
            3,
            [],
        ),
    )

    output = server.nbrag_search(
        query="history",
        collection_name="test",
        preview_chars=5,
    )

    assert "abcde..." in output
    assert "abcdef" not in output


def test_find_files_wrapper_normalizes_defaults(monkeypatch):
    captured = {}

    def fake_find_files(pattern, collection_name, max_results, case_sensitive):
        captured.update({
            "pattern": pattern,
            "collection_name": collection_name,
            "max_results": max_results,
            "case_sensitive": case_sensitive,
        })
        return [{
            "doc_id": "doc1",
            "filename": "history.py",
            "file_path": "D:/repo/langchain_core/runnables/history.py",
            "source": "D:/repo/langchain_core/runnables/history.py",
            "chunk_count": 20,
            "total_chunks": 20,
            "match": "filename",
        }]

    monkeypatch.setattr(server, "find_files", fake_find_files)

    output = server.nbrag_find_files(pattern="history.py", collection_name="test")

    assert captured == {
        "pattern": "history.py",
        "collection_name": "test",
        "max_results": 20,
        "case_sensitive": False,
    }
    assert "file_path: D:/repo/langchain_core/runnables/history.py" in output


def test_search_and_fetch_wrapper_normalizes_defaults(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        server,
        "get_config",
        lambda: SimpleNamespace(rerank=SimpleNamespace(model="rerank-model")),
    )

    def fake_search(query, collection_name, top_k, use_rerank, use_bm25=True, filter_file_path=None):
        captured.update({
            "query": query,
            "collection_name": collection_name,
            "top_k": top_k,
            "use_rerank": use_rerank,
            "use_bm25": use_bm25,
            "filter_file_path": filter_file_path,
        })
        return (
            ["matched chunk"],
            [{
                "source": "D:/repo/history.py",
                "filename": "history.py",
                "chunk_index": 0,
                "total_chunks": 1,
                "line_start": 1,
                "line_end": 5,
                "scope": "",
                "doc_id": "doc1",
            }],
            [0.1234],
            True,
            1,
            [0.9876],
        )

    def fake_get_file_chunks(file_path, collection_name, start_chunk, max_chunks, raw=False, line_start=-1, line_end=-1):
        assert file_path == "D:/repo/history.py"
        assert collection_name == "test"
        assert raw is True
        return {
            "found": True,
            "filename": "history.py",
            "doc_id": "doc1",
            "source": file_path,
            "total_lines": 5,
            "total_chunks": 1,
            "line_start": 1,
            "line_end": 5,
            "content": "original content",
        }

    monkeypatch.setattr(server, "search", fake_search)
    monkeypatch.setattr(server, "get_file_chunks", fake_get_file_chunks)

    output = server.nbrag_search_and_fetch(query="history", collection_name="test")

    assert captured == {
        "query": "history",
        "collection_name": "test",
        "top_k": 5,
        "use_rerank": True,
        "use_bm25": True,
        "filter_file_path": None,
    }
    assert "Auto-fetched original content (1 file(s))" in output
    assert "original_file: history.py" in output
