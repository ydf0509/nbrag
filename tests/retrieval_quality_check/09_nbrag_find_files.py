#coding=utf-8
"""测试 nbrag_find_files() —— 按文件名找路径（通过端口 9101 调用 MCP）。"""
from _mcp_request import call_mcp_tool

# ===== 可编辑参数区域 =====
PATTERN = "劳动合同法.md"
COLLECTION = "worker_rights"
MAX_RESULTS = 5
CASE_SENSITIVE = False
# ==========================

params = {
    "pattern": PATTERN, "collection_name": COLLECTION,
    "max_results": MAX_RESULTS, "case_sensitive": CASE_SENSITIVE,
}
result = call_mcp_tool("nbrag_find_files", params)
print(f"调用函数: nbrag_find_files")
print(f"入参: {params}")
print("-" * 70)
print(result)
