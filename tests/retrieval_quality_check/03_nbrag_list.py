#coding=utf-8
"""测试 nbrag_list() —— 列出知识库中的文档（通过端口 9101 调用 MCP）。"""
from _mcp_request import call_mcp_tool

# ===== 可编辑参数区域 =====
COLLECTION = "worker_rights"   # 知识库名（不知道时先跑 02_nbrag_stats.py）
LIMIT = 5                      # 返回多少条
OFFSET = 0                     # 分页偏移
# ==========================

params = {"collection_name": COLLECTION, "limit": LIMIT, "offset": OFFSET}
result = call_mcp_tool("nbrag_list", params)
print(f"调用函数: nbrag_list")
print(f"入参: {params}")
print("-" * 70)
print(result)
