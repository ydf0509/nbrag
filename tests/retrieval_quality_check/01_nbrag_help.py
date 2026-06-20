#coding=utf-8
"""测试 nbrag_help() —— 导航/入门指南（通过端口 9101 调用 MCP）。"""
from _mcp_request import call_mcp_tool

# ===== 可编辑参数区域 =====
# 无参数
# ==========================

result = call_mcp_tool("nbrag_help")
print(f"调用函数: nbrag_help")
print("-" * 70)
print(result)
