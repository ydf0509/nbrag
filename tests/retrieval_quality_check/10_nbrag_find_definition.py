#coding=utf-8
"""测试 nbrag_find_definition() —— Python 符号定义查找（通过端口 9101 调用 MCP）。"""
from _mcp_request import call_mcp_tool

# ===== 可编辑参数区域 =====
SYMBOL = "BoosterParams"
COLLECTION = "funboost"
MAX_RESULTS = 2
# ==========================

params = {
    "symbol": SYMBOL, "collection_name": COLLECTION,
    "max_results": MAX_RESULTS,
}
result = call_mcp_tool("nbrag_find_definition", params)
print(f"调用函数: nbrag_find_definition")
print(f"入参: {params}")
print("-" * 70)
print(result)
