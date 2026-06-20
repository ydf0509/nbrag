#coding=utf-8
"""P0-2 根因确认：mcp_tools 调用 get_context_chunks 时参数顺序是否错位。

对比两种调用：
  A. retrieval 层正确签名: get_context_chunks(doc_id, collection_name, chunk_index, window)
  B. mcp_tools 实际写法:   get_context_chunks(doc_id, chunk_index, collection_name, window)
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import my_load_config  # noqa

from nbrag import retrieval
from nbrag import mcp_tools

DOC_ID = "81ec846f7c63"
COLLECTION = "worker_rights"

print("=" * 70)
print("B. 复现 mcp_tools 的位置参数调用（疑似错位）")
print("  调用: get_context_chunks(doc_id, chunk_index=1, collection_name=worker_rights, window=1)")
print("  即位置传入: (doc_id, 1, 'worker_rights', 1)")
result_b = retrieval.get_context_chunks(DOC_ID, 1, "worker_rights", 1)
print("  found:", result_b.get("found"))
print("  chunks 数量:", len(result_b.get("chunks", [])))
print("  error:", result_b.get("error"))
print("  -> 这相当于 collection_name=1, chunk_index='worker_rights'(非数字)")
print()

print("=" * 70)
print("C. 直接调 mcp_tools.nbrag_get_adjacent_chunks（MCP 层封装）")
result_c = mcp_tools.nbrag_get_adjacent_chunks(DOC_ID, 1, COLLECTION, 1)
print(result_c[:500])
