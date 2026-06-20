#coding=utf-8
"""测试 nbrag_get_raw_file() —— 读原始文件（通过端口 9101 调用 MCP）。"""
from _mcp_request import call_mcp_tool

# ===== 可编辑参数区域 =====
FILE_PATH = "D:/codes/nbrag/scripts/ingest_ex3_worker_rights/劳动合同法.md"
COLLECTION = "worker_rights"
LINE_START = 45
LINE_END = 52
# ==========================

params = {
    "file_path": FILE_PATH, "collection_name": COLLECTION,
    "line_start": LINE_START, "line_end": LINE_END,
}
result = call_mcp_tool("nbrag_get_raw_file", params)
print(f"调用函数: nbrag_get_raw_file")
print(f"入参: {params}")
print("-" * 70)
print(result)
