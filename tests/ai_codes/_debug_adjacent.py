#coding=utf-8
"""P0-2 根因调查：nbrag_get_adjacent_chunks 为什么对有效 doc_id+chunk_index 返回空。

逐层打印证据：chroma 查询 → items 数量 → 切片结果。
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import my_load_config  # noqa

from nbrag import retrieval
from nbrag.storage import _get_existing_collection

DOC_ID = "81ec846f7c63"   # retrieval_report.txt 里前置解析到的真实 doc_id
COLLECTION = "worker_rights"

print("=" * 70)
print("Layer 1: chroma 直接查 where doc_id = ", DOC_ID)
col = _get_existing_collection(COLLECTION)
print("collection obj:", col)
all_data = col.get(where={"doc_id": DOC_ID}, include=["documents", "metadatas"])
print("返回 ids 数量:", len(all_data.get("ids", [])))
print("前 3 个 metadata 的 chunk_index:",
      [m.get("chunk_index") for m in all_data.get("metadatas", [])[:3]])

print()
print("=" * 70)
print("Layer 2: get_context_chunks(chunk_index=1, window=1) 完整返回")
result = retrieval.get_context_chunks(DOC_ID, COLLECTION, chunk_index=1, window=1)
import pprint
pprint.pprint(result)

print()
print("=" * 70)
print("Layer 3: 对比 line_start/line_end 路径（get_chunks_by_lines 用）")
result2 = retrieval.get_context_chunks(DOC_ID, COLLECTION, line_start=45, line_end=52)
print("chunks 数量:", len(result2.get("chunks", [])))
print("total_chunks:", result2.get("total_chunks"))
