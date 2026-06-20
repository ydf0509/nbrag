#coding=utf-8
"""直接调用 nbrag.mcp_tools 的基准脚本：为每个 MCP 工具函数提供示例调用并统计耗时。"""

from __future__ import annotations

import os
import statistics
import sys
import time
from typing import Any, Callable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import my_load_config

from nbrag import mcp_tools


WORKER_RIGHTS = {
    "collection_name": "worker_rights",
    "search_query": "1年劳动合同试用期期限上限",
    "grep_keyword": "第十九条|第八十三条",
    "find_file_pattern": "劳动合同法.md",
    "file_path": "D:/codes/nbrag/scripts/ingest_ex3_worker_rights/劳动合同法.md",
    "symbol": "第十九条",
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
    "symbol": "create_deep_agent",
}

ROUNDS = 10
PREVIEW = 160


def time_it(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[float, Any]:
    t0 = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = time.perf_counter() - t0
    return elapsed, result


def shorten(text: str, limit: int = PREVIEW) -> str:
    text = text.replace("\n", " ").strip()
    return text[:limit] + ("..." if len(text) > limit else "")


def print_result_preview(result: Any) -> str:
    if isinstance(result, str):
        return shorten(result)
    return shorten(repr(result))


def run_case(label: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[str, float, str]:
    elapsed, result = time_it(fn, *args, **kwargs)
    preview = print_result_preview(result)
    return label, elapsed, preview


def build_dynamic_cases() -> list[tuple[str, Callable[..., Any], tuple[Any, ...], dict[str, Any]]]:
    dynamic_cases: list[tuple[str, Callable[..., Any], tuple[Any, ...], dict[str, Any]]] = []

    worker_docs = mcp_tools.nbrag_list(WORKER_RIGHTS["collection_name"], limit=2, offset=0)
    dynamic_cases.append((
        "nbrag_list(worker_rights)",
        mcp_tools.nbrag_list,
        (WORKER_RIGHTS["collection_name"],),
        {"limit": 2, "offset": 0},
    ))

    worker_search = mcp_tools.nbrag_search(
        query=WORKER_RIGHTS["search_query"],
        collection_name=WORKER_RIGHTS["collection_name"],
        top_k=3,
        include_content=True,
    )
    dynamic_cases.append((
        "nbrag_search(worker_rights)",
        mcp_tools.nbrag_search,
        (),
        {
            "query": WORKER_RIGHTS["search_query"],
            "collection_name": WORKER_RIGHTS["collection_name"],
            "top_k": 3,
            "include_content": True,
        },
    ))

    dynamic_cases.append((
        "nbrag_search_and_fetch(worker_rights)",
        mcp_tools.nbrag_search_and_fetch,
        (),
        {
            "query": WORKER_RIGHTS["search_query"],
            "collection_name": WORKER_RIGHTS["collection_name"],
            "top_k": 3,
            "fetch_top_n_raw": 1,
            "fetch_context_chars": 2000,
        },
    ))

    dynamic_cases.append((
        "nbrag_grep(worker_rights)",
        mcp_tools.nbrag_grep,
        (),
        {
            "keyword": WORKER_RIGHTS["grep_keyword"],
            "collection_name": WORKER_RIGHTS["collection_name"],
            "max_results": 5,
            "match_context_chars": 2000,
        },
    ))

    dynamic_cases.append((
        "nbrag_find_files(worker_rights)",
        mcp_tools.nbrag_find_files,
        (),
        {
            "pattern": WORKER_RIGHTS["find_file_pattern"],
            "collection_name": WORKER_RIGHTS["collection_name"],
            "max_results": 5,
        },
    ))

    dynamic_cases.append((
        "nbrag_get_raw_file(worker_rights)",
        mcp_tools.nbrag_get_raw_file,
        (),
        {
            "file_path": WORKER_RIGHTS["file_path"],
            "collection_name": WORKER_RIGHTS["collection_name"],
            "line_start": 45,
            "line_end": 52,
        },
    ))

    dynamic_cases.append((
        "nbrag_get_file_chunks(worker_rights)",
        mcp_tools.nbrag_get_file_chunks,
        (),
        {
            "file_path": WORKER_RIGHTS["file_path"],
            "collection_name": WORKER_RIGHTS["collection_name"],
            "start_chunk": 0,
            "max_chunks": 2,
        },
    ))

    dynamic_cases.append((
        "nbrag_find_definition(funboost)",
        mcp_tools.nbrag_find_definition,
        (),
        {
            "symbol": FUNBOOST["symbol"],
            "collection_name": FUNBOOST["collection_name"],
            "max_results": 1,
        },
    ))

    dynamic_cases.append((
        "nbrag_search(funboost)",
        mcp_tools.nbrag_search,
        (),
        {
            "query": FUNBOOST["search_query"],
            "collection_name": FUNBOOST["collection_name"],
            "top_k": 3,
        },
    ))

    dynamic_cases.append((
        "nbrag_grep(funboost)",
        mcp_tools.nbrag_grep,
        (),
        {
            "keyword": FUNBOOST["grep_keyword"],
            "collection_name": FUNBOOST["collection_name"],
            "max_results": 5,
            "match_context_chars": 2000,
        },
    ))

    dynamic_cases.append((
        "nbrag_search(langchain)",
        mcp_tools.nbrag_search,
        (),
        {
            "query": LANGCHAIN["search_query"],
            "collection_name": LANGCHAIN["collection_name"],
            "top_k": 3,
        },
    ))

    dynamic_cases.append((
        "nbrag_search_and_fetch(langchain)",
        mcp_tools.nbrag_search_and_fetch,
        (),
        {
            "query": LANGCHAIN["search_query"],
            "collection_name": LANGCHAIN["collection_name"],
            "top_k": 3,
            "fetch_top_n_raw": 1,
            "fetch_context_chars": 2000,
        },
    ))

    dynamic_cases.append((
        "nbrag_grep(langchain)",
        mcp_tools.nbrag_grep,
        (),
        {
            "keyword": LANGCHAIN["grep_keyword"],
            "collection_name": LANGCHAIN["collection_name"],
            "max_results": 5,
            "match_context_chars": 2000,
        },
    ))

    dynamic_cases.append((
        "nbrag_find_files(langchain)",
        mcp_tools.nbrag_find_files,
        (),
        {
            "pattern": LANGCHAIN["find_file_pattern"],
            "collection_name": LANGCHAIN["collection_name"],
            "max_results": 5,
        },
    ))

    dynamic_cases.append((
        "nbrag_find_definition(langchain)",
        mcp_tools.nbrag_find_definition,
        (),
        {
            "symbol": LANGCHAIN["symbol"],
            "collection_name": LANGCHAIN["collection_name"],
            "max_results": 1,
        },
    ))

    dynamic_cases.append((
        "nbrag_get_raw_file(langchain)",
        mcp_tools.nbrag_get_raw_file,
        (),
        {
            "file_path": LANGCHAIN["file_path"],
            "collection_name": LANGCHAIN["collection_name"],
            "line_start": 1,
            "line_end": 40,
        },
    ))

    if "doc_id:" in worker_search and "chunk:" in worker_search:
        doc_id = worker_search.split("doc_id:", 1)[1].split()[0]
        chunk_index = int(worker_search.split("chunk:", 1)[1].split("/", 1)[0])
        line_range = worker_search.split("line:", 1)[1].split()[0]
        line_start, line_end = [int(x) for x in line_range.split("-")]

        dynamic_cases.append((
            "nbrag_get_adjacent_chunks(worker_rights)",
            mcp_tools.nbrag_get_adjacent_chunks,
            (),
            {
                "doc_id": doc_id,
                "chunk_index": chunk_index,
                "collection_name": WORKER_RIGHTS["collection_name"],
                "window": 1,
            },
        ))

        dynamic_cases.append((
            "nbrag_get_chunks_by_lines(worker_rights)",
            mcp_tools.nbrag_get_chunks_by_lines,
            (),
            {
                "doc_id": doc_id,
                "line_start": line_start,
                "line_end": line_end,
                "collection_name": WORKER_RIGHTS["collection_name"],
            },
        ))

    if "empty" not in worker_docs.lower():
        dynamic_cases.append((
            "nbrag_list(worker_rights,page2)",
            mcp_tools.nbrag_list,
            (WORKER_RIGHTS["collection_name"],),
            {"limit": 2, "offset": 2},
        ))

    return dynamic_cases


def main() -> None:
    static_cases: list[tuple[str, Callable[..., Any], tuple[Any, ...], dict[str, Any]]] = [
        ("nbrag_help()", mcp_tools.nbrag_help, (), {}),
        ("nbrag_stats()", mcp_tools.nbrag_stats, (), {}),
    ]

    dynamic_cases = build_dynamic_cases()
    cases = static_cases + dynamic_cases

    print("=" * 88)
    print("nbrag.mcp_tools benchmark — direct function calls")
    print("collections: worker_rights + funboost + langchain_ai_codes_and_docs")
    print("=" * 88)

    all_metrics: dict[str, list[float]] = {}

    for round_idx in range(1, ROUNDS + 1):
        print(f"\n--- Round {round_idx}/{ROUNDS} ---")
        for label, fn, args, kwargs in cases:
            name, elapsed, preview = run_case(label, fn, *args, **kwargs)
            all_metrics.setdefault(name, []).append(elapsed)
            print(f"{name:<44} {elapsed:>8.4f}s | {preview}")

    print("\n" + "=" * 88)
    print("Summary")
    print("=" * 88)
    for name, values in all_metrics.items():
        print(
            f"{name:<44} avg={statistics.mean(values):.4f}s "
            f"min={min(values):.4f}s max={max(values):.4f}s rounds={len(values)}"
        )


if __name__ == "__main__":
    main()
