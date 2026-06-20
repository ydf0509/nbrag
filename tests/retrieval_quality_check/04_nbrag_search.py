#coding=utf-8
"""测试 nbrag_search() —— 混合检索（通过端口 9101 调用 MCP）。"""
from _mcp_request import call_mcp_tool

# ===== 可编辑参数区域 =====
QUERY = "1年劳动合同试用期期限上限"
COLLECTION = "worker_rights"
TOP_K = 3
USE_RERANK = True
USE_BM25 = True
FILTER_FILE_PATH = ""
INCLUDE_CONTENT = True
# ==========================

params = {
    "query": QUERY, "collection_name": COLLECTION,
    "top_k": TOP_K, "use_rerank": USE_RERANK,
    "use_bm25": USE_BM25, "filter_file_path": FILTER_FILE_PATH,
    "include_content": INCLUDE_CONTENT,
}
result = call_mcp_tool("nbrag_search", params)
print(f"调用函数: nbrag_search")
print(f"入参: {params}")
print("-" * 70)
print(result)
