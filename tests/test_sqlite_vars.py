"""测试 ChromaDB 在大集合上的 col.get() 行为。"""
import shutil
import tempfile
from pathlib import Path

import chromadb


def test_many_chunks():
    """插入大量 chunk，验证 col.get() 在不同参数下的行为。"""
    tmp = Path(tempfile.mkdtemp(prefix="nbrag_test_"))
    try:
        client = chromadb.PersistentClient(path=str(tmp))
        col = client.get_or_create_collection("test_large")

        N = 2000  # 超过 SQLite 默认 999 变量限制
        print(f"[1] 插入 {N} 个 documents...")
        for i in range(0, N, 100):
            batch_end = min(i + 100, N)
            ids = [f"doc_{j}" for j in range(i, batch_end)]
            docs = [f"content number {j}" for j in range(i, batch_end)]
            metas = [{"doc_id": f"file_{j % 100}", "filename": f"f{j}.py"}
                     for j in range(i, batch_end)]
            col.add(ids=ids, documents=docs, metadatas=metas)
        print(f"    → 完成，count={col.count()}")

        # 测试 1: 只拿 ids (include=[])
        print("\n[2] col.get(include=[]) 只拿 ids...")
        r = col.get(include=[])
        print(f"    → 成功 {len(r['ids'])} 条")

        # 测试 2: 全量 metadatas
        print("\n[3] col.get(include=['metadatas']) 全量查 metadatas...")
        try:
            r = col.get(include=["metadatas"])
            print(f"    → 成功 {len(r['metadatas'])} 条")
        except Exception as e:
            print(f"    ✗ 失败: {type(e).__name__}: {e}")

        # 测试 3: 全量 documents
        print("\n[4] col.get(include=['documents']) 全量查 documents...")
        try:
            r = col.get(include=["documents"])
            print(f"    → 成功 {len(r['documents'])} 条")
        except Exception as e:
            print(f"    ✗ 失败: {type(e).__name__}: {e}")

        # 测试 4: 全量 documents + metadatas
        print("\n[5] col.get(include=['documents','metadatas']) 全量查...")
        try:
            r = col.get(include=["documents", "metadatas"])
            print(f"    → 成功 {len(r['ids'])} 条")
        except Exception as e:
            print(f"    ✗ 失败: {type(e).__name__}: {e}")

        # 测试 5: 带 ids 查 1200 个
        print("\n[6] col.get(ids=[1200个], include=['metadatas'])...")
        ids_1200 = [f"doc_{j}" for j in range(1200)]
        try:
            r = col.get(ids=ids_1200, include=["metadatas"])
            print(f"    → 成功 {len(r['metadatas'])} 条")
        except Exception as e:
            print(f"    ✗ 失败: {type(e).__name__}: {e}")

        # 测试 6: 带 ids 查 500 个
        print("\n[7] col.get(ids=[500个], include=['metadatas'])...")
        ids_500 = [f"doc_{j}" for j in range(500)]
        try:
            r = col.get(ids=ids_500, include=["metadatas"])
            print(f"    → 成功 {len(r['metadatas'])} 条")
        except Exception as e:
            print(f"    ✗ 失败: {type(e).__name__}: {e}")

        # 测试 7: where 过滤
        print("\n[8] col.get(where={'doc_id':'file_1'}, include=['metadatas'])...")
        try:
            r = col.get(where={"doc_id": "file_1"}, include=["metadatas"])
            print(f"    → 成功 {len(r['metadatas'])} 条")
        except Exception as e:
            print(f"    ✗ 失败: {type(e).__name__}: {e}")

        print("\n✓ 测试完成")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_many_chunks()
