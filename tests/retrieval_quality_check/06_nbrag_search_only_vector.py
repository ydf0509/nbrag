#coding=utf-8
"""测试 nbrag_search_only_vector() —— 纯向量语义检索（通过端口 9101 调用 MCP）。"""
from _mcp_request import call_mcp_tool

# ===== 可编辑参数区域 =====
QUERY = "1年劳动合同试用期最长能约定几个月"
COLLECTION = "worker_rights"
TOP_K = 3
FILTER_FILE_PATH = ""
INCLUDE_CONTENT = True
# ==========================

params = {
    "query": QUERY, "collection_name": COLLECTION,
    "top_k": TOP_K, "filter_file_path": FILTER_FILE_PATH,
    "include_content": INCLUDE_CONTENT,
}
result = call_mcp_tool("nbrag_search_only_vector", params)
print(f"调用函数: nbrag_search_only_vector")
print(f"入参: {params}")
print("-" * 70)
print(result)
