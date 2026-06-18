"""端到端测试：BM25 + RRF 混合检索。

使用内存中的小 corpus 验证：
1. BM25 索引构建和持久化
2. _bm25_search 检索
3. RRF 融合逻辑
4. _preprocess_for_bm25 分词器
"""
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from nbrag.bm25_index import (
    _preprocess_for_bm25,
    _rrf_fusion,
    _weighted_rrf_fusion,
    build_bm25_index,
    _load_bm25_index,
    _bm25_search,
    invalidate_bm25_cache,  
    _bm25_cache,
)
from nbrag.tokenizer import BM25_CHANNELS


def test_preprocess():
    """测试代码感知分词预处理。"""
    # camelCase 拆分
    result = _preprocess_for_bm25("getUserById")
    assert "get" in result and "user" in result and "by" in result and "id" in result, f"camelCase split failed: {result}"

    # snake_case 拆分
    result = _preprocess_for_bm25("get_user_by_id")
    assert "get" in result and "user" in result, f"snake_case split failed: {result}"

    # PascalCase 拆分
    result = _preprocess_for_bm25("BrokerEnum")
    assert "broker" in result and "enum" in result, f"PascalCase split failed: {result}"

    # chunk header 去除
    result = _preprocess_for_bm25("# [File: /path/to/file.py] [Scope: MyClass] [Lines: 1-10]\ndef hello():\n    pass")
    assert "[file:" not in result, f"Header not stripped: {result}"
    assert "hello" in result, f"Content lost: {result}"

    # 中文保留
    result = _preprocess_for_bm25("用户认证 authentication")
    assert "认证" in result or "用户" in result, f"Chinese lost: {result}"

    print("  [PASS] preprocess_for_bm25")


def test_rrf_fusion():
    """测试 RRF 融合逻辑。"""
    vec_ids = ["doc_a", "doc_b", "doc_c"]
    bm25_ids = ["doc_b", "doc_d", "doc_a"]

    fused = _rrf_fusion(vec_ids, bm25_ids, k=60)

    # doc_a 和 doc_b 在两路都出现，应该排在前面
    assert fused[0] in ("doc_a", "doc_b"), f"Top result should be doc_a or doc_b, got {fused[0]}"
    assert fused[1] in ("doc_a", "doc_b"), f"2nd result should be doc_a or doc_b, got {fused[1]}"
    # doc_c 和 doc_d 只在一路出现，排后面
    assert set(fused[2:]) == {"doc_c", "doc_d"}, f"Single-source docs wrong: {fused[2:]}"

    # 空输入
    assert _rrf_fusion([], []) == []
    assert len(_rrf_fusion(["a", "b"], [])) == 2

    weighted = _weighted_rrf_fusion([
        ("vector", ["doc_a", "doc_b"], 1.0),
        ("ngram", ["doc_c"], 3.0),
    ])
    assert weighted[0] == "doc_c", f"Weighted source should lift doc_c, got {weighted}"

    print("  [PASS] rrf_fusion")


def test_bm25_index_build_and_search():
    """测试 BM25 索引构建、持久化、加载、搜索。"""
    from nbrag.config import load_config

    tmp_dir = tempfile.mkdtemp(prefix="nbrag_test_")
    try:
        load_config()
        from nbrag import config as _config_mod
        orig_db = _config_mod._config.storage.db_path
        _config_mod._config.storage.db_path = tmp_dir

        collection_name = "test_bm25"

        documents = [
            "class BrokerEnum:\n    REDIS = 'redis'\n    KAFKA = 'kafka'\n    RABBITMQ = 'rabbitmq'",
            "def get_user_by_id(user_id):\n    return db.query(User).filter(User.id == user_id).first()",
            "async def push_task(task_data, queue_name):\n    await redis.lpush(queue_name, json.dumps(task_data))",
            "import threading\nclass ThreadPoolExecutor:\n    def __init__(self, max_workers=4):\n        self.pool = []",
            "# Configuration file\nDATABASE_URL = 'postgresql://localhost/mydb'\nREDIS_HOST = 'localhost'",
            "# 中文注释和文档\n# funboost 发布任务到 redis 队列，支持分布式消费和失败重试\nclass RedisQueuePublisher:\n    pass",
            "劳动合同期限一年以上不满三年的，试用期不得超过二个月。",
        ]
        chunk_ids = [f"chunk_{i}" for i in range(len(documents))]

        # 构建索引
        build_bm25_index(collection_name, documents, chunk_ids)
        assert collection_name in _bm25_cache, "BM25 cache not populated after build"

        # 验证磁盘持久化
        index_root = os.path.join(tmp_dir, "bm25_index_v2", collection_name)
        assert os.path.isdir(index_root), f"BM25 index root not created: {index_root}"
        for channel in BM25_CHANNELS:
            index_dir = os.path.join(index_root, channel)
            assert os.path.isdir(index_dir), f"BM25 channel dir not created: {index_dir}"

        # 清除内存缓存，测试从磁盘加载
        _bm25_cache.pop(collection_name, None)
        retriever, ids = _load_bm25_index(collection_name, "word")
        assert retriever is not None, "Failed to load BM25 index from disk"
        assert ids == chunk_ids, f"Chunk IDs mismatch: {ids}"

        # BM25 搜索
        ids_result, scores = _bm25_search("BrokerEnum redis kafka", collection_name, 3)
        assert len(ids_result) > 0, "BM25 search returned no results"
        assert ids_result[0] == "chunk_0", f"BrokerEnum should match chunk_0, got {ids_result[0]}"
        print(f"    BM25 search 'BrokerEnum redis kafka': top={ids_result[0]}, scores={scores[:3]}")

        ids_result, scores = _bm25_search("ThreadPoolExecutor threading", collection_name, 3)
        assert "chunk_3" in ids_result[:2], f"ThreadPool should match chunk_3, got {ids_result[:2]}"
        print(f"    BM25 search 'ThreadPoolExecutor': top={ids_result[0]}")

        ids_result, scores = _bm25_search("get_user_by_id database query", collection_name, 3)
        assert "chunk_1" in ids_result[:2], f"get_user_by_id should match chunk_1, got {ids_result[:2]}"
        print(f"    BM25 search 'get_user_by_id': top={ids_result[0]}")

        ids_result, scores = _bm25_search("funboost redis 队列 失败重试", collection_name, 5)
        assert "chunk_5" in ids_result[:2], f"Chinese code docs should match chunk_5, got {ids_result[:3]}"
        print(f"    BM25 search 'funboost redis 队列 失败重试': top={ids_result[0]}")

        ids_result, scores = _bm25_search("试用期不得超过", collection_name, 5)
        assert "chunk_6" in ids_result[:2], f"Chinese legal prose should match chunk_6, got {ids_result[:3]}"
        print(f"    BM25 search '试用期不得超过': top={ids_result[0]}")

        # 清除缓存
        invalidate_bm25_cache(collection_name)
        assert collection_name not in _bm25_cache, "Cache not cleared"
        assert not os.path.isdir(index_root), "Disk index not deleted"

        _config_mod._config.storage.db_path = orig_db
        print("  [PASS] bm25_index_build_and_search")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    print("Testing BM25 + RRF...")
    test_preprocess()
    test_rrf_fusion()
    test_bm25_index_build_and_search()
    print("\nAll tests passed!")
