#coding=utf-8
"""测试 nbrag_grep() —— 逐行精确匹配（通过端口 9101 调用 MCP）。

match_context_chars 是每个 grep match 的总上下文预算，会近似平分到匹配行前后；不是所有匹配结果的总长度上限。
"""
from _mcp_request import call_mcp_tool

# ===== 可编辑参数区域 =====
KEYWORD = "试用期"
COLLECTION = "worker_rights"
MAX_RESULTS = 5
CASE_SENSITIVE = False
FILTER_FILE_PATH = ""
MATCH_CONTEXT_CHARS = 2000
# ==========================

params = {
    "keyword": KEYWORD, "collection_name": COLLECTION,
    "max_results": MAX_RESULTS, "case_sensitive": CASE_SENSITIVE,
    "filter_file_path": FILTER_FILE_PATH, "match_context_chars": MATCH_CONTEXT_CHARS,
}
result = call_mcp_tool("nbrag_grep", params)
print(f"调用函数: nbrag_grep")
print(f"入参: {params}")
print("-" * 70)
print(result)
