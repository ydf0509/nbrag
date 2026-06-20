#coding=utf-8
"""检查 nbrag.mcp_tools 每个 MCP 函数的返回内容是否对 AI 友好、字段是否可继续调用。

这个脚本直接调用实现层，不走 MCP/HTTP。它不是性能 benchmark，而是返回契约巡检：
- 是否有 file_path/doc_id/chunk/line 等可复制字段
- 失败分支是否给 Next steps
- 默认入口、能力模型、collection 提示是否清楚
- 每个 MCP 函数是否能返回非空字符串，且格式适合 AI 继续链式调用

注意：详细输出会同步写入同名 `.txt` 文件，避免终端输出过长时被 agent 截断。
"""

from __future__ import annotations

import builtins
import os
import sys
import textwrap
import time
from dataclasses import dataclass
from typing import Callable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import my_load_config  # noqa: F401

from nbrag import mcp_tools


WORKER_RIGHTS = {
    "collection_name": "worker_rights",
    "search_query": "1年劳动合同试用期期限上限",
    "semantic_question": "1年劳动合同试用期最长能约定几个月，违法后怎么赔偿",
    "grep_keyword": "试用期",
    "find_file_pattern": "劳动合同法.md",
    "file_path": "D:/codes/nbrag/scripts/ingest_ex3_worker_rights/劳动合同法.md",
    "doc_id": "",
    "chunk_index": 1,
    "line_start": 45,
    "line_end": 52,
}

FUNBOOST = {
    "collection_name": "funboost",
    "search_query": "funboost 多进程消费 is_using_multiprocessing concurrent_num process pool 使用方法",
    "grep_keyword": "multi_process_consume",
    "find_file_pattern": "c8.md",
    "file_path": "D:/codes/funboost_docs/source/articles/c8.md",
    "symbol": "BoosterParams",
}

LANGCHAIN = {
    "collection_name": "langchain_ai_codes_and_docs",
    "search_query": "RunnableWithMessageHistory session_id configurable chat history example usage",
    "grep_keyword": "RunnableWithMessageHistory",
    "find_file_pattern": "history.py",
    "file_path": "D:/ProgramData/miniconda3/envs/py312/Lib/site-packages/langchain_core/runnables/history.py",
    "symbol": "RunnableWithMessageHistory",
}

PREVIEW = 500
OUTPUT_TXT_PATH = os.path.splitext(__file__)[0] + ".txt"


class _DualWriter:
    def __init__(self, *streams) -> None:
        self._streams = streams

    def write(self, text: str) -> int:
        for stream in self._streams:
            stream.write(text)
        return len(text)

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()


def print_save_file(text: str = "", *, end: str = "\n") -> None:
    builtins.print(text, end=end)


@dataclass
class CheckCase:
    name: str
    question: str
    fn: Callable[..., str]
    kwargs: dict
    must_contain: list[str]
    nice_to_have: list[str] | None = None
    allow_error: bool = False


def shorten(text: str, limit: int = PREVIEW) -> str:
    text = text.replace("\r\n", "\n").strip()
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return text[:limit] + ("..." if len(text) > limit else "")


def ok_mark(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def contains_all(text: str, needles: list[str]) -> tuple[bool, list[str]]:
    missing = [needle for needle in needles if needle not in text]
    return not missing, missing


def run_case(case: CheckCase) -> bool:
    print_save_file("=" * 96)
    print_save_file(f"{case.name}")
    print_save_file(f"模拟用户问题: {case.question}")
    print_save_file(f"调用参数: {case.kwargs}")
    t0 = time.perf_counter()
    try:
        result = case.fn(**case.kwargs)
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        print_save_file(f"结果: FAIL | elapsed={elapsed:.4f}s | exception={type(exc).__name__}: {exc}")
        return False

    elapsed = time.perf_counter() - t0
    if not isinstance(result, str) or not result.strip():
        print_save_file(f"结果: FAIL | elapsed={elapsed:.4f}s | 返回不是非空字符串")
        print_save_file(repr(result))
        return False

    if not case.allow_error and result.startswith("Error:"):
        print_save_file(f"结果: FAIL | elapsed={elapsed:.4f}s | 返回 Error")
        print_save_file(shorten(result))
        return False

    required_ok, missing_required = contains_all(result, case.must_contain)
    nice_to_have = case.nice_to_have or []
    nice_ok, missing_nice = contains_all(result, nice_to_have)

    print_save_file(f"结果: {ok_mark(required_ok)} | elapsed={elapsed:.4f}s | chars={len(result)}")
    if missing_required:
        print_save_file("缺失必需字段:")
        for item in missing_required:
            print_save_file(f"  - {item}")
    if missing_nice:
        print_save_file("缺失建议字段:")
        for item in missing_nice:
            print_save_file(f"  - {item}")

    print_save_file("返回预览:")
    print_save_file(textwrap.indent(shorten(result), "  "))
    return required_ok


def discover_worker_doc_id() -> str:
    output = mcp_tools.nbrag_search(
        query=WORKER_RIGHTS["search_query"],
        collection_name=WORKER_RIGHTS["collection_name"],
        top_k=1,
        include_content=False,
        preview_chars=0,
    )
    for token in output.replace("\n", " ").split():
        if token.startswith("doc_id:"):
            return token.split(":", 1)[1]
    return ""


def build_cases() -> list[CheckCase]:
    worker_doc_id = discover_worker_doc_id()
    WORKER_RIGHTS["doc_id"] = worker_doc_id

    cases = [
        CheckCase(
            name="nbrag_help() 能建立 Agentic RAG 心智模型",
            question="我第一次看到 nbrag 这组 MCP 工具，应该怎么用？",
            fn=mcp_tools.nbrag_help,
            kwargs={},
            must_contain=[
                "Agentic RAG",
                "Common guidance",
                "nbrag_search_and_fetch",
                "nbrag_grep",
                "file_path",
                "Embedded nbrag workflow guide",
            ],
            nice_to_have=["BM25", "semantic", "rerank"],
        ),
        CheckCase(
            name="nbrag_stats() 能告诉 AI 有哪些知识库以及规模",
            question="我不知道 collection_name，先列出所有知识库。",
            fn=mcp_tools.nbrag_stats,
            kwargs={},
            must_contain=[
                "collections:",
                "docs=",
                "chunks=",
            ],
            nice_to_have=[WORKER_RIGHTS["collection_name"], FUNBOOST["collection_name"], LANGCHAIN["collection_name"]],
        ),
        CheckCase(
            name="nbrag_list() 返回 file_path/doc_id，可分页浏览",
            question="列出 worker_rights 知识库前 2 个文档，给我后续可复制的路径。",
            fn=mcp_tools.nbrag_list,
            kwargs={"collection_name": WORKER_RIGHTS["collection_name"], "limit": 2, "offset": 0},
            must_contain=[
                "documents in collection",
                "file_path:",
                "doc_id:",
                "total_chunks:",
                "chunk_count:",
            ],
        ),
        CheckCase(
            name="nbrag_search() 语义检索返回 chunk/doc_id/file_path/line",
            question=WORKER_RIGHTS["semantic_question"],
            fn=mcp_tools.nbrag_search,
            kwargs={
                "query": WORKER_RIGHTS["search_query"],
                "collection_name": WORKER_RIGHTS["collection_name"],
                "top_k": 3,
                "include_content": True,
                "preview_chars": 700,
            },
            must_contain=[
                "bm25:",
                "rerank:",
                "file_path:",
                "chunk:",
                "doc_id:",
                "line:",
            ],
            nice_to_have=["score:", "dist:"],
        ),
        CheckCase(
            name="nbrag_search() metadata-only 模式不污染上下文",
            question="只要检索元数据，不要正文。",
            fn=mcp_tools.nbrag_search,
            kwargs={
                "query": WORKER_RIGHTS["search_query"],
                "collection_name": WORKER_RIGHTS["collection_name"],
                "top_k": 2,
                "include_content": False,
                "preview_chars": 0,
            },
            must_contain=[
                "file_path:",
                "doc_id:",
                "content omitted",
            ],
        ),
        CheckCase(
            name="nbrag_search_only_bm25() 能单独验证词法召回输出格式",
            question="只看 BM25 召回时，返回字段是否还能继续调用。",
            fn=mcp_tools.nbrag_search_only_bm25,
            kwargs={
                "query": WORKER_RIGHTS["grep_keyword"],
                "collection_name": WORKER_RIGHTS["collection_name"],
                "top_k": 2,
                "include_content": False,
                "preview_chars": 0,
            },
            must_contain=[
                "bm25:",
                "rerank: off",
                "file_path:",
                "doc_id:",
                "content omitted",
            ],
        ),
        CheckCase(
            name="nbrag_search_only_vector() 能单独验证语义召回输出格式",
            question="只看向量召回时，返回字段是否还能继续调用。",
            fn=mcp_tools.nbrag_search_only_vector,
            kwargs={
                "query": WORKER_RIGHTS["search_query"],
                "collection_name": WORKER_RIGHTS["collection_name"],
                "top_k": 2,
                "include_content": False,
                "preview_chars": 0,
            },
            must_contain=[
                "bm25: off",
                "rerank: off",
                "file_path:",
                "doc_id:",
                "content omitted",
            ],
        ),
        CheckCase(
            name="nbrag_search_and_fetch() 默认入口能自动抓原文证据",
            question=WORKER_RIGHTS["semantic_question"],
            fn=mcp_tools.nbrag_search_and_fetch,
            kwargs={
                "query": WORKER_RIGHTS["search_query"],
                "collection_name": WORKER_RIGHTS["collection_name"],
                "top_k": 3,
                "fetch_top_n_raw": 1,
                "fetch_chars": 4000,
            },
            must_contain=[
                "bm25:",
                "Auto-fetched original content",
                "original_file:",
                "file_path:",
                "doc_id:",
                "range: line:",
            ],
        ),
        CheckCase(
            name="nbrag_grep() 精确检索返回 matched_line/line_range",
            question="精确查劳动合同法第十九条和第八十三条。",
            fn=mcp_tools.nbrag_grep,
            kwargs={
                "keyword": WORKER_RIGHTS["grep_keyword"],
                "collection_name": WORKER_RIGHTS["collection_name"],
                "max_results": 5,
                "context_lines": 6,
            },
            must_contain=[
                "grep matches:",
                "file_path:",
                "doc_id:",
                "matched_line:",
                "line_range: line:",
            ],
        ),
        CheckCase(
            name="nbrag_find_files() 文件发现返回可复制 file_path",
            question="找到劳动合同法这个文件的完整路径。",
            fn=mcp_tools.nbrag_find_files,
            kwargs={
                "pattern": WORKER_RIGHTS["find_file_pattern"],
                "collection_name": WORKER_RIGHTS["collection_name"],
                "max_results": 5,
            },
            must_contain=[
                "matched files:",
                "file_path:",
                "doc_id:",
            ],
            nice_to_have=["total_chunks:", "chunk_count:"],
        ),
        CheckCase(
            name="nbrag_get_raw_file() 原文读取返回无 overlap 的行范围",
            question="读取劳动合同法 45 到 52 行原文。",
            fn=mcp_tools.nbrag_get_raw_file,
            kwargs={
                "file_path": WORKER_RIGHTS["file_path"],
                "collection_name": WORKER_RIGHTS["collection_name"],
                "line_start": WORKER_RIGHTS["line_start"],
                "line_end": WORKER_RIGHTS["line_end"],
            },
            must_contain=[
                "original_file:",
                "file_path:",
                "doc_id:",
                "total_lines:",
                "range: line:",
            ],
        ),
        CheckCase(
            name="nbrag_get_file_chunks() 分页 chunk 返回 scope/line/doc_id",
            question="按 chunk 看劳动合同法前 2 个块。",
            fn=mcp_tools.nbrag_get_file_chunks,
            kwargs={
                "file_path": WORKER_RIGHTS["file_path"],
                "collection_name": WORKER_RIGHTS["collection_name"],
                "start_chunk": 0,
                "max_chunks": 2,
            },
            must_contain=[
                "file chunks",
                "file_path:",
                "doc_id:",
                "total_chunks:",
                "chunk:",
            ],
            nice_to_have=["line:"],
        ),
        CheckCase(
            name="nbrag_get_adjacent_chunks() 相邻 chunk 返回行号和路径",
            question="围绕刚才搜到的 chunk 扩展上下文。",
            fn=mcp_tools.nbrag_get_adjacent_chunks,
            kwargs={
                "doc_id": worker_doc_id,
                "chunk_index": WORKER_RIGHTS["chunk_index"],
                "collection_name": WORKER_RIGHTS["collection_name"],
                "window": 1,
            },
            must_contain=[
                "doc_id",
                "chunk",
            ],
            nice_to_have=["adjacent chunks:", "file_path:", "line:"],
            allow_error=True,
        ),
        CheckCase(
            name="nbrag_get_chunks_by_lines() 行范围反查 chunks",
            question="根据原文行号找到覆盖这些行的 chunk。",
            fn=mcp_tools.nbrag_get_chunks_by_lines,
            kwargs={
                "doc_id": worker_doc_id,
                "line_start": WORKER_RIGHTS["line_start"],
                "line_end": WORKER_RIGHTS["line_end"],
                "collection_name": WORKER_RIGHTS["collection_name"],
            },
            must_contain=[
                "chunks by lines",
                "doc_id:",
                "line_range:",
                "chunk:",
                "file_path:",
            ],
        ),
        CheckCase(
            name="nbrag_find_definition() Python symbol 返回定义和 file_path",
            question="找到 funboost 的 BoosterParams 定义。",
            fn=mcp_tools.nbrag_find_definition,
            kwargs={
                "symbol": FUNBOOST["symbol"],
                "collection_name": FUNBOOST["collection_name"],
                "max_results": 2,
            },
            must_contain=[
                "definitions:",
                "file_path:",
                "line:",
                "doc_id:",
            ],
            nice_to_have=["def __init__", "Regex fallback in non-Python file"],
        ),
        CheckCase(
            name="错误路径提示能指导 AI 改用 find_files/list",
            question="AI 误把 basename 当 file_path 传入时，工具应该明确纠正。",
            fn=mcp_tools.nbrag_get_raw_file,
            kwargs={
                "file_path": "劳动合同法.md",
                "collection_name": WORKER_RIGHTS["collection_name"],
            },
            must_contain=[
                "Error:",
                "full absolute file_path",
                "nbrag_search",
                "nbrag_find_files",
                "nbrag_list",
            ],
            allow_error=True,
        ),
        CheckCase(
            name="无结果提示能给 Next steps",
            question="查一个不存在的精确词，应该告诉 AI 下一步怎么换工具/换 query。",
            fn=mcp_tools.nbrag_grep,
            kwargs={
                "keyword": "__THIS_SHOULD_NOT_EXIST_NBRAG_RESULT_CHECK__",
                "collection_name": WORKER_RIGHTS["collection_name"],
                "max_results": 3,
            },
            must_contain=[
                "No grep matches",
                "Possible adjustments:",
                "nbrag_search_and_fetch",
            ],
        ),
    ]

    return cases


def main() -> int:
    with open(OUTPUT_TXT_PATH, "w", encoding="utf-8") as output_file:
        original_stdout = sys.stdout
        sys.stdout = _DualWriter(original_stdout, output_file)
        try:
            print_save_file("=" * 96)
            print_save_file("nbrag MCP result friendliness check — direct mcp_tools calls")
            print_save_file("目标: 检查每个 MCP 函数返回是否包含 AI 后续调用所需字段和清晰下一步。")
            print_save_file(f"详细输出已同步保存到: {OUTPUT_TXT_PATH}")
            print_save_file("若 agent 终端输出被截断，请直接读取这个 txt 文件做完整检查。")
            print_save_file("=" * 96)

            cases = build_cases()
            passed = 0
            failed = 0
            failed_names: list[str] = []
            for case in cases:
                if run_case(case):
                    passed += 1
                else:
                    failed += 1
                    failed_names.append(case.name)

            print_save_file("=" * 96)
            print_save_file(f"SUMMARY: passed={passed} failed={failed} total={len(cases)}")
            if failed:
                print_save_file("失败 case:")
                for name in failed_names:
                    print_save_file(f"  - {name}")
                print_save_file("结论: 有返回契约不够友好或调用失败，请查看上面的 FAIL case。")
                return 1
            print_save_file("结论: 所有 MCP 函数返回均满足当前 AI 友好性检查。")
            return 0
        finally:
            sys.stdout = original_stdout


if __name__ == "__main__":
    raise SystemExit(main())
