#coding=utf-8
"""测试 nbrag_retrieve_no_expand() —— 不自动扩读的混合检索（通过端口 9101 调用 MCP）。"""
from _mcp_request import call_mcp_tool

# ===== 可编辑参数区域 =====
QUERY = "1年劳动合同试用期期限上限"
BM25_QUERY = "试用期 一年劳动合同"
COLLECTION = "worker_rights"
TOP_K = 3
FILTER_FILE_PATH = ""
INCLUDE_CONTENT = True
# ==========================

params = {
    "query": QUERY, "bm25_query": BM25_QUERY, "collection_name": COLLECTION,
    "top_k": TOP_K, "filter_file_path": FILTER_FILE_PATH,
    "include_content": INCLUDE_CONTENT,
}
result = call_mcp_tool("nbrag_retrieve_no_expand", params)
print(f"调用函数: nbrag_retrieve_no_expand")
print(f"入参: {params}")
print("-" * 70)
print(result)
