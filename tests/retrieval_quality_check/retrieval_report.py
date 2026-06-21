#coding=utf-8
"""如实验证 nbrag MCP 工具集——逐个调用、把函数名+入参+完整返回写进同名 .txt（通过 HTTP 端口 9101）。

不做任何质量判定（不 pass/fail、不 must_contain、不截断）。
只负责记录每个 MCP 工具在固定入参下的真实返回，供读取 txt 的 AI 自己判断。
"""

from __future__ import annotations

import builtins
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS_DIR)

from _mcp_request import call_mcp_tool  # noqa: E402


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


def section(title: str) -> None:
    print_save_file("=" * 96)
    print_save_file(title)
    print_save_file("=" * 96)


def record(fn_name: str, tool_name: str, kwargs: dict | None = None) -> None:
    """通过 MCP HTTP 调用并记录完整返回。"""
    print_save_file("-" * 96)
    print_save_file(f"调用函数: {fn_name}")
    print_save_file(f"入参: {kwargs or {}}")
    print_save_file("-" * 96)
    try:
        result = call_mcp_tool(tool_name, kwargs or {})
    except Exception as exc:
        print_save_file(f"[调用抛出异常] {type(exc).__name__}: {exc}")
        print_save_file()
        return
    if isinstance(result, str):
        print_save_file(result)
    else:
        print_save_file(f"[返回非字符串] {type(result).__name__}: {result!r}")
    print_save_file()


def main() -> int:
    with open(OUTPUT_TXT_PATH, "w", encoding="utf-8") as output_file:
        original_stdout = sys.stdout
        sys.stdout = _DualWriter(original_stdout, output_file)
        try:
            section("nbrag MCP 检索函数返回证据报告（HTTP 端口 9101）")
            print_save_file("说明: 本脚本只如实记录每个 MCP 工具的调用入参和返回结果，不做任何质量判定。")
            print_save_file("质量判断完全交给读取本 txt 的 AI。")
            print_save_file(f"输出文件: {OUTPUT_TXT_PATH}")
            print_save_file()

            # ---- 导航类 ----
            record("nbrag_help()", "nbrag_help")
            record("nbrag_stats()", "nbrag_stats")
            record("nbrag_list(limit=2, offset=0)", "nbrag_list",
                   {"collection_name": "worker_rights", "limit": 2, "offset": 0})

            # ---- 检索类 ----
            record("nbrag_search(query, bm25_query, top_k=3, include_content=True)", "nbrag_search",
                   {"query": "1年劳动合同试用期期限上限", "bm25_query": "试用期 一年劳动合同", "collection_name": "worker_rights",
                    "top_k": 3, "include_content": True})
            record("nbrag_search(metadata-only: include_content=False)", "nbrag_search",
                   {"query": "1年劳动合同试用期期限上限", "bm25_query": "试用期 一年劳动合同", "collection_name": "worker_rights",
                    "top_k": 2, "include_content": False})
            record("nbrag_search_only_bm25(query='试用期', include_content=False)", "nbrag_search_only_bm25",
                   {"query": "试用期", "collection_name": "worker_rights",
                    "top_k": 2, "include_content": False})
            record("nbrag_search_only_vector(query, include_content=False)", "nbrag_search_only_vector",
                   {"query": "1年劳动合同试用期期限上限", "collection_name": "worker_rights",
                    "top_k": 2, "include_content": False})
            record("nbrag_search_and_fetch(query, bm25_query, top_k=3, fetch_top_n_raw=1, fetch_context_chars=4000)", "nbrag_search_and_fetch",
                   {"query": "1年劳动合同试用期期限上限", "bm25_query": "试用期 一年劳动合同", "collection_name": "worker_rights",
                    "top_k": 3, "fetch_top_n_raw": 1, "fetch_context_chars": 4000})

            # ---- 精确/词法类 ----
            record("nbrag_grep(keyword='试用期', max_results=5)", "nbrag_grep",
                   {"keyword": "试用期", "collection_name": "worker_rights",
                    "max_results": 5, "match_context_chars": 2000})
            record("nbrag_grep(无结果路径)", "nbrag_grep",
                   {"keyword": "__THIS_SHOULD_NOT_EXIST_NBRAG_REPORT__",
                    "collection_name": "worker_rights", "max_results": 3})

            # ---- 发现类 ----
            record("nbrag_find_files(pattern='劳动合同法.md')", "nbrag_find_files",
                   {"pattern": "劳动合同法.md", "collection_name": "worker_rights", "max_results": 5})
            record("nbrag_find_definition(symbol='BoosterParams')", "nbrag_find_definition",
                   {"symbol": "BoosterParams", "collection_name": "funboost", "max_results": 2})

            # ---- 深入读取类 ----
            record("nbrag_get_raw_file(line_start=45, line_end=52)", "nbrag_get_raw_file",
                   {"file_path": "D:/codes/nbrag/scripts/ingest_ex3_worker_rights/劳动合同法.md",
                    "collection_name": "worker_rights", "line_start": 45, "line_end": 52})
            record("nbrag_get_raw_file(basename误传=错误路径)", "nbrag_get_raw_file",
                   {"file_path": "劳动合同法.md", "collection_name": "worker_rights"})
            record("nbrag_get_file_chunks(start_chunk=0, max_chunks=2)", "nbrag_get_file_chunks",
                   {"file_path": "D:/codes/nbrag/scripts/ingest_ex3_worker_rights/劳动合同法.md",
                    "collection_name": "worker_rights", "start_chunk": 0, "max_chunks": 2})

            # ---- 需要 doc_id 的工具 ----
            print_save_file("[前置] 通过 nbrag_search 获取真实 doc_id")
            search_output = call_mcp_tool("nbrag_search", {
                "query": "试用期", "collection_name": "worker_rights",
                "top_k": 1, "include_content": False,
            })
            worker_doc_id = ""
            for token in search_output.replace("\n", " ").split():
                if token.startswith("doc_id:"):
                    worker_doc_id = token.split(":", 1)[1]
            print_save_file(f"解析到 worker_doc_id = {worker_doc_id!r}")
            print_save_file()

            if worker_doc_id:
                record("nbrag_get_adjacent_chunks(doc_id=<前置>, chunk_index=1, window=1)", "nbrag_get_adjacent_chunks",
                       {"doc_id": worker_doc_id, "chunk_index": 1, "collection_name": "worker_rights", "window": 1})
                record("nbrag_get_chunks_by_lines(doc_id=<前置>, line_start=45, line_end=52)", "nbrag_get_chunks_by_lines",
                       {"doc_id": worker_doc_id, "line_start": 45, "line_end": 52, "collection_name": "worker_rights"})
            else:
                print_save_file("[跳过] get_adjacent_chunks / get_chunks_by_lines：未解析到 doc_id")

            section("报告结束")
            print_save_file("以上是每个 MCP 函数在 HTTP 端口 9101 下的真实返回证据。")
        finally:
            sys.stdout = original_stdout

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
