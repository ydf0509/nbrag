#coding=utf-8
"""测试 nbrag_get_adjacent_chunks() —— 按 doc_id+chunk 扩上下文（通过端口 9101 调用 MCP）。
注意：需要先用 nbrag_search 拿到真实 doc_id 填入下方。"""
from _mcp_request import call_mcp_tool

# ===== 可编辑参数区域 =====
# 先跑 04_nbrag_search.py，从返回中复制 doc_id 填入下面
DOC_ID = "81ec846f7c63"
CHUNK_INDEX = 1
COLLECTION = "worker_rights"
WINDOW = 2
# ==========================

params = {
    "doc_id": DOC_ID, "chunk_index": CHUNK_INDEX,
    "collection_name": COLLECTION, "window": WINDOW,
}
result = call_mcp_tool("nbrag_get_adjacent_chunks", params)
print(f"调用函数: nbrag_get_adjacent_chunks")
print(f"入参: {params}")
print("-" * 70)
print(result)
