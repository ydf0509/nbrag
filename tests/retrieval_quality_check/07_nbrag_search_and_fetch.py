#coding=utf-8
"""测试 nbrag_search_and_fetch() —— 搜索+抓原文（通过端口 9101 调用 MCP）。

fetch_context_chars 是每条 ranked hit 的总上下文预算，会近似平分到命中处前后；不是所有结果的总长度上限。
"""
from _mcp_request import call_mcp_tool

# ===== 可编辑参数区域 =====
QUERY = "1年劳动合同试用期期限上限"
BM25_QUERY = "试用期 一年劳动合同"
COLLECTION = "worker_rights"
TOP_K = 3
FETCH_TOP_N_RAW = 1
FETCH_CONTEXT_CHARS = 4000
FILTER_FILE_PATH = ""
# ==========================

params = {
    "query": QUERY, "bm25_query": BM25_QUERY, "collection_name": COLLECTION,
    "top_k": TOP_K, "fetch_top_n_raw": FETCH_TOP_N_RAW,
    "fetch_context_chars": FETCH_CONTEXT_CHARS, "filter_file_path": FILTER_FILE_PATH,
}
result = call_mcp_tool("nbrag_search_and_fetch", params)
print(f"调用函数: nbrag_search_and_fetch")
print(f"入参: {params}")
print("-" * 70)
print(result)
