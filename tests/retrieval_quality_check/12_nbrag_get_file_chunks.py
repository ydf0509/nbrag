#coding=utf-8
"""测试 nbrag_get_file_chunks() —— 分页浏览 chunk（通过端口 9101 调用 MCP）。"""
from _mcp_request import call_mcp_tool

# ===== 可编辑参数区域 =====
FILE_PATH = "D:/codes/nbrag/scripts/ingest_ex3_worker_rights/劳动合同法.md"
COLLECTION = "worker_rights"
START_CHUNK = 0
MAX_CHUNKS = 2
# ==========================

params = {
    "file_path": FILE_PATH, "collection_name": COLLECTION,
    "start_chunk": START_CHUNK, "max_chunks": MAX_CHUNKS,
}
result = call_mcp_tool("nbrag_get_file_chunks", params)
print(f"调用函数: nbrag_get_file_chunks")
print(f"入参: {params}")
print("-" * 70)
print(result)
