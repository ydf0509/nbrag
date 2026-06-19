"""MCP wrapper contract tests that do not require a running server."""

import inspect
from types import SimpleNamespace
from pathlib import Path

from nbrag import server, state
import nbrag.mcp_tools as mcp_tools
import nbrag.retrieval as retrieval


def _field_default(func, parameter):
    default = inspect.signature(func).parameters[parameter].default
    return default.default


def test_find_definition_default_max_results_is_three():
    assert _field_default(server.nbrag_find_definition, "max_results") == 3


def test_grep_raw_text_cache_loads_markdown_files(tmp_path, monkeypatch):
    raw_root = tmp_path / "raw_files"
    collection_dir = raw_root / "docs"
    collection_dir.mkdir(parents=True)
    (collection_dir / "doc1.md").write_text("第一行\n试用期不得超过一个月\n", encoding="utf-8")

    monkeypatch.setattr(retrieval, "_raw_files_dir", lambda: str(raw_root))
    monkeypatch.setattr(
        retrieval,
        "_get_doc_id_map",
        lambda collection_name: {
            "doc1": {"filename": "劳动合同法.md", "source": "D:/repo/劳动合同法.md"}
        },
    )
    state._raw_text_cache = None
    state._raw_text_cache_ts = 0.0

    output = mcp_tools.nbrag_grep(keyword="试用期", collection_name="docs", max_results=1)

    assert "file_path: D:/repo/劳动合同法.md" in output
    assert "matched_line: 2" in output
    assert "line_range: line:2-2" in output


def test_help_is_exposed_as_mcp_tool():
    source = Path(server.__file__).read_text(encoding="utf-8-sig")

    assert source.count("@mcp.tool()") == 12
    assert "@mcp.tool()\ndef nbrag_help(" in source


def test_help_embeds_workflow_skill_and_keeps_short_guidance():
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
        "Embedded nbrag workflow guide:",
        "Common guidance:",
        "常见调用路径（不是固定流程）",
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


def test_python_source_workflow_is_visible_without_copying_the_skill():
    root = Path(server.__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    skill = (root / "nbrag" / "skills" / "nbrag-workflow" / "SKILL.md").read_text(encoding="utf-8")
    help_text = server.nbrag_help()
    search_doc = inspect.getdoc(server.nbrag_search)
    fetch_doc = inspect.getdoc(server.nbrag_search_and_fetch)

    required = [
        "Python source workflow",
        "nbrag_grep",
        "nbrag_find_definition",
        "nbrag_get_raw_file",
    ]

    for text in (readme, skill, help_text, search_doc or "", fetch_doc or ""):
        for needle in required:
            assert needle in text


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
        mcp_tools,
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


def test_find_definition_mixed_results_do_not_label_python_ast_as_fallback(monkeypatch):
    monkeypatch.setattr(
        mcp_tools,
        "find_symbol_definition",
        lambda symbol, collection_name, max_results: [
            {
                "symbol_type": "class",
                "qualified_name": "BoosterParams",
                "line_start": 61,
                "line_end": 330,
                "doc_id": "py1",
                "source": "D:/repo/funboost/core/func_params_model.py",
                "definition": "class BoosterParams(BaseModel):\n    pass",
                "methods_summary": "  def __init__(self, **data)",
            },
            {
                "symbol_type": "unknown",
                "qualified_name": "BoosterParams",
                "line_start": 10,
                "line_end": 20,
                "doc_id": "md1",
                "source": "D:/repo/docs/usage.md",
                "definition": "`BoosterParams` is used in examples.",
                "methods_summary": "",
            },
        ],
    )

    output = server.nbrag_find_definition(
        symbol="BoosterParams",
        collection_name="funboost",
        max_results=3,
    )

    header = output.split("\n\n", 1)[0]
    assert "non-Python regex fallback" not in header
    assert "[1/2] class BoosterParams" in output
    assert "Regex fallback in non-Python file" in output


def test_search_can_return_metadata_only(monkeypatch):
    monkeypatch.setattr(
        mcp_tools,
        "get_config",
        lambda: SimpleNamespace(rerank=SimpleNamespace(model="rerank-model")),
    )
    monkeypatch.setattr(
        mcp_tools,
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
        mcp_tools,
        "get_config",
        lambda: SimpleNamespace(rerank=SimpleNamespace(model="off")),
    )
    monkeypatch.setattr(
        mcp_tools,
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

    monkeypatch.setattr(mcp_tools, "find_files", fake_find_files)

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
        mcp_tools,
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

    monkeypatch.setattr(mcp_tools, "search", fake_search)
    monkeypatch.setattr(mcp_tools, "get_file_chunks", fake_get_file_chunks)

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


def test_search_and_fetch_uses_ranked_windows_for_same_doc(monkeypatch):
    monkeypatch.setattr(
        mcp_tools,
        "get_config",
        lambda: SimpleNamespace(rerank=SimpleNamespace(model="rerank-model")),
    )

    monkeypatch.setattr(
        mcp_tools,
        "search",
        lambda *args, **kwargs: (
            ["top chunk", "second chunk"],
            [
                {
                    "source": "D:/repo/manual.md",
                    "filename": "manual.md",
                    "chunk_index": 1,
                    "total_chunks": 10,
                    "line_start": 100,
                    "line_end": 120,
                    "scope": "",
                    "doc_id": "doc1",
                },
                {
                    "source": "D:/repo/manual.md",
                    "filename": "manual.md",
                    "chunk_index": 8,
                    "total_chunks": 10,
                    "line_start": 300,
                    "line_end": 320,
                    "scope": "",
                    "doc_id": "doc1",
                },
            ],
            [0.1, 0.2],
            True,
            10,
            [0.99, 0.88],
        ),
    )

    excerpt_calls = []

    def fake_get_file_chunks(file_path, collection_name, start_chunk, max_chunks, raw=False, line_start=-1, line_end=-1):
        assert file_path == "D:/repo/manual.md"
        assert collection_name == "docs"
        assert raw is True
        if line_start == -1 and line_end == -1:
            return {
                "found": True,
                "filename": "manual.md",
                "doc_id": "doc1",
                "source": file_path,
                "total_lines": 400,
                "total_chunks": 10,
                "line_start": 1,
                "line_end": 400,
                "content": "full manual",
            }

        excerpt_calls.append((line_start, line_end))
        return {
            "found": True,
            "filename": "manual.md",
            "doc_id": "doc1",
            "source": file_path,
            "total_lines": 400,
            "total_chunks": 10,
            "line_start": line_start,
            "line_end": line_end,
            "content": f"excerpt {line_start}-{line_end}",
        }

    monkeypatch.setattr(mcp_tools, "get_file_chunks", fake_get_file_chunks)

    output = server.nbrag_search_and_fetch(
        query="manual",
        collection_name="docs",
        fetch_top_n_raw=2,
        context_lines=5,
    )

    assert (95, 125) in excerpt_calls
    assert (295, 325) in excerpt_calls
    assert "range: line:95-125" in output
    assert "range: line:295-325" in output


def test_list_wrapper_passes_limit_and_offset_by_name(monkeypatch):
    captured = {}

    def fake_list(collection_name, offset=0, limit=200):
        captured.update({
            "collection_name": collection_name,
            "offset": offset,
            "limit": limit,
        })
        return "listed"

    monkeypatch.setattr(mcp_tools, "nbrag_list", fake_list)

    output = server.nbrag_list(collection_name="docs", limit=5, offset=10)

    assert output == "listed"
    assert captured == {"collection_name": "docs", "offset": 10, "limit": 5}


def test_grep_result_exposes_machine_readable_line_range(monkeypatch):
    monkeypatch.setattr(
        mcp_tools,
        "grep_knowledge",
        lambda *args, **kwargs: [{
            "filename": "manual.md",
            "source": "D:/repo/manual.md",
            "doc_id": "doc1",
            "line_number": 42,
            "context": "40: before\n42: matched\n44: after",
        }],
    )

    output = server.nbrag_grep(keyword="matched", collection_name="docs")

    assert "line_range: line:42-42" in output
    assert "matched_line: 42" in output


def test_adjacent_chunks_include_line_ranges_for_follow_up(monkeypatch):
    monkeypatch.setattr(
        mcp_tools,
        "get_context_chunks",
        lambda *args, **kwargs: {
            "found": True,
            "source": "D:/repo/manual.md",
            "doc_id": "doc1",
            "total_chunks": 5,
            "chunks": [{
                "index": 2,
                "line_start": 20,
                "line_end": 35,
                "content": "chunk body",
            }],
        },
    )

    output = server.nbrag_get_adjacent_chunks(doc_id="doc1", chunk_index=2, collection_name="docs")

    assert "line:20-35" in output
    assert "file_path: D:/repo/manual.md" in output


def test_search_and_fetch_docstring_declares_default_entrypoint():
    doc = inspect.getdoc(server.nbrag_search_and_fetch) or ""

    assert "Default entry point" in doc
    assert "most user questions" in doc


def test_server_routes_delegate_to_mcp_tools(monkeypatch):
    calls = {}

    def fake_search_and_fetch(**kwargs):
        calls.update(kwargs)
        return "delegated"

    monkeypatch.setattr(mcp_tools, "nbrag_search_and_fetch", fake_search_and_fetch)

    output = server.nbrag_search_and_fetch(
        query="history",
        collection_name="docs",
        top_k=7,
        fetch_top_n_raw=2,
        context_lines=15,
        filter_file_path="D:/repo/history.py",
    )

    assert output == "delegated"
    assert calls == {
        "query": "history",
        "collection_name": "docs",
        "top_k": 7,
        "fetch_top_n_raw": 2,
        "context_lines": 15,
        "filter_file_path": "D:/repo/history.py",
    }
