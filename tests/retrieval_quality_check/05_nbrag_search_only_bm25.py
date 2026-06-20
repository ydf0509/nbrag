#coding=utf-8
"""测试 nbrag_search_only_bm25() —— 纯 BM25 词法检索（通过端口 9101 调用 MCP）。"""
from _mcp_request import call_mcp_tool

# ===== 可编辑参数区域 =====
QUERY = "试用期"
COLLECTION = "worker_rights"
TOP_K = 3
FILTER_FILE_PATH = ""
INCLUDE_CONTENT = True
PREVIEW_CHARS = 500
# ==========================

params = {
    "query": QUERY, "collection_name": COLLECTION,
    "top_k": TOP_K, "filter_file_path": FILTER_FILE_PATH,
    "include_content": INCLUDE_CONTENT, "preview_chars": PREVIEW_CHARS,
}
result = call_mcp_tool("nbrag_search_only_bm25", params)
print(f"调用函数: nbrag_search_only_bm25")
print(f"入参: {params}")
print("-" * 70)
print(result)
