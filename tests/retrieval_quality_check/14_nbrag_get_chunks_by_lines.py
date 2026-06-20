#coding=utf-8
"""测试 nbrag_get_chunks_by_lines() —— 按行号反查 chunk（通过端口 9101 调用 MCP）。
注意：需要先用 nbrag_search 拿到真实 doc_id 填入下方。"""
from _mcp_request import call_mcp_tool

# ===== 可编辑参数区域 =====
# 先跑 04_nbrag_search.py，从返回中复制 doc_id 填入下面
DOC_ID = "81ec846f7c63"
LINE_START = 45
LINE_END = 52
COLLECTION = "worker_rights"
# ==========================

params = {
    "doc_id": DOC_ID, "line_start": LINE_START,
    "line_end": LINE_END, "collection_name": COLLECTION,
}
result = call_mcp_tool("nbrag_get_chunks_by_lines", params)
print(f"调用函数: nbrag_get_chunks_by_lines")
print(f"入参: {params}")
print("-" * 70)
print(result)
