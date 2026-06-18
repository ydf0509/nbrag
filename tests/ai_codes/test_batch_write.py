"""验证 batch_write 优化后功能正确性。"""

import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from my_load_config import *

from nbrag import batch_ingest, search, list_documents, find_symbol_definition, get_stats


def main():
    test_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "nbrag")
    collection = "test_batch_write"

    print("=" * 60)
    print(f"测试批量写入（delete_first=True）")
    print(f"导入路径: {test_path}")
    print(f"collection: {collection}")
    print("=" * 60)

    t0 = time.perf_counter()
    stats = batch_ingest(
        paths=[test_path],
        collection_name=collection,
        file_extensions=[".py"],
        delete_first=True,
        verbose=True,
    )
    elapsed = time.perf_counter() - t0
    print(f"\n导入耗时: {elapsed:.2f}s")
    print(f"结果: {stats['success']} ok, {stats['failed']} failed, {stats['total_chunks']} chunks")

    print("\n--- 验证数据完整性 ---")
    docs = list_documents(collection)
    print(f"文档数: {len(docs)}")
    for did, info in list(docs.items())[:5]:
        print(f"  {info['filename']} | {info['chunk_count']} chunks | doc_id:{did}")

    print("\n--- 验证 find_definition (symbol 索引) ---")
    results = find_symbol_definition("search", collection, 3)
    print(f"find_def('search') → {len(results)} results")
    for r in results[:3]:
        print(f"  {r['filename']}:{r['line_start']}-{r['line_end']} {r['qualified_name']}")

    print("\n--- 验证 search ---")
    documents, metas, dists, reranked, total, scores = search("embedding API", collection, top_k=3)
    print(f"search('embedding API') → {len(documents)} results, total={total}")
    for i, (doc, meta) in enumerate(zip(documents, metas)):
        print(f"  [{i+1}] {meta.get('filename', '?')} chunk:{meta.get('chunk_index', '?')}")

    print("\n验证完成 ✓")


if __name__ == "__main__":
    main()
