"""BM25 多通道索引与 RRF 融合。"""

from __future__ import annotations

import gc
import json
import os
import re
import shutil

import bm25s

from nbrag import state
from nbrag.config import get_config
from nbrag.tokenizer import BM25_CHANNELS, normalize_text, tokenize_all, tokenize_query_all


_CAMEL_SPLIT_RE = re.compile(r"([a-z])([A-Z])")
_CAMEL_UPPER_RE = re.compile(r"([A-Z]+)([A-Z][a-z])")
_HEADER_RE = re.compile(r"^#\s*\[File:.*$", re.MULTILINE)
_BM25_INDEX_VERSION = 2
_BM25_CHANNEL_WEIGHTS = {
    "word": 1.10,
    "ngram": 0.75,
    "code": 1.20,
}
_BM25_EMPTY_TOKEN = "__nbrag_empty_channel__"


def _cfg():
    return get_config()


def _preprocess_for_bm25(text):
    """预处理文本供 BM25 分词：去 chunk header、拆 camelCase/snake_case、小写化。"""
    text = normalize_text(text)
    text = _HEADER_RE.sub("", text)
    text = _CAMEL_SPLIT_RE.sub(r"\1 \2", text)
    text = _CAMEL_UPPER_RE.sub(r"\1 \2", text)
    text = text.replace("_", " ")
    return text.lower()


def _bm25_index_root(collection_name):
    return os.path.join(_cfg().storage.db_path, "bm25_index_v2", collection_name)


def _bm25_index_dir(collection_name, channel="word"):
    return os.path.join(_bm25_index_root(collection_name), channel)


def _legacy_bm25_index_dir(collection_name):
    return os.path.join(_cfg().storage.db_path, "bm25_index", collection_name)


def build_bm25_index(collection_name, documents, chunk_ids):
    """构建多通道 BM25 索引并持久化到磁盘。"""
    if not documents:
        return

    from datetime import datetime, timezone

    index_root = _bm25_index_root(collection_name)
    if os.path.isdir(index_root):
        shutil.rmtree(index_root, ignore_errors=True)
    os.makedirs(index_root, exist_ok=True)

    tokenized_docs = [tokenize_all(doc) for doc in documents]
    channel_cache = {}
    for channel in BM25_CHANNELS:
        corpus_tokens = [doc_tokens.get(channel, []) or [_BM25_EMPTY_TOKEN] for doc_tokens in tokenized_docs]
        retriever = bm25s.BM25(method="lucene")
        retriever.index(corpus_tokens)

        index_dir = _bm25_index_dir(collection_name, channel)
        os.makedirs(index_dir, exist_ok=True)
        retriever.save(index_dir)
        with open(os.path.join(index_dir, "chunk_ids.json"), "w", encoding="utf-8") as f:
            json.dump(chunk_ids, f, ensure_ascii=False)
        channel_cache[channel] = (retriever, chunk_ids)

    meta = {
        "version": _BM25_INDEX_VERSION,
        "channels": list(BM25_CHANNELS),
        "weights": _BM25_CHANNEL_WEIGHTS,
        "tokenizer": "jieba_search+cjk_2_3gram+code",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(os.path.join(index_root, "tokenizer_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    state._bm25_cache[collection_name] = channel_cache


def _load_bm25_index(collection_name, channel="word"):
    """从磁盘加载指定通道的 BM25 索引到内存缓存。"""
    cached = state._bm25_cache.get(collection_name, {})
    if channel in cached:
        return cached[channel]

    index_dir = _bm25_index_dir(collection_name, channel)
    if not os.path.isdir(index_dir):
        return None, None

    ids_path = os.path.join(index_dir, "chunk_ids.json")
    if not os.path.isfile(ids_path):
        return None, None

    try:
        retriever = bm25s.BM25.load(index_dir, mmap=False)
        with open(ids_path, "r", encoding="utf-8") as f:
            chunk_ids = json.load(f)
        state._bm25_cache.setdefault(collection_name, {})[channel] = (retriever, chunk_ids)
        return retriever, chunk_ids
    except Exception:
        return None, None


def _bm25_search_channel(query_tokens, collection_name, channel, top_k):
    """在单个 BM25 通道中检索，返回 ids。"""
    retriever, chunk_ids = _load_bm25_index(collection_name, channel)
    if retriever is None or not query_tokens:
        return []
    try:
        results, _scores = retriever.retrieve([query_tokens], k=top_k, show_progress=False)
        ids = []
        for idx in results[0]:
            try:
                idx_int = int(idx)
            except Exception:
                continue
            if 0 <= idx_int < len(chunk_ids):
                ids.append(chunk_ids[idx_int])
        return ids
    except Exception:
        return []


def _bm25_search_channels(query, collection_name, top_k):
    """在所有 BM25 通道中检索，返回 channel -> ranked ids。"""
    query_tokens_by_channel = tokenize_query_all(query)
    channel_results = {}
    for channel in BM25_CHANNELS:
        ids = _bm25_search_channel(
            query_tokens_by_channel.get(channel, []), collection_name, channel, top_k
        )
        if ids:
            channel_results[channel] = ids
    return channel_results


def _weighted_rrf_fusion(ranked_sources, k=60):
    """加权 RRF 融合多个 ranked id 列表。"""
    scores = {}
    for _name, ids, weight in ranked_sources:
        for rank, doc_id in enumerate(ids):
            scores[doc_id] = scores.get(doc_id, 0.0) + weight / (k + rank + 1)
    return [doc_id for doc_id, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]


def _bm25_search(query, collection_name, top_k):
    """兼容旧测试的 BM25 搜索接口，返回 (ids, scores)。"""
    channel_results = _bm25_search_channels(query, collection_name, top_k)
    if not channel_results:
        return [], []
    ranked_sources = [
        (channel, ids, _BM25_CHANNEL_WEIGHTS.get(channel, 1.0))
        for channel, ids in channel_results.items()
    ]
    fused = _weighted_rrf_fusion(ranked_sources)[:top_k]
    return fused, [1.0] * len(fused)


def _rrf_fusion(vec_ids, bm25_ids, k=60):
    """兼容旧接口的双路 RRF 融合。"""
    return _weighted_rrf_fusion([
        ("vector", vec_ids, 1.0),
        ("bm25", bm25_ids, 1.0),
    ], k=k)


def invalidate_bm25_cache(collection_name=None):
    """清除 BM25 索引缓存（导入/删除 collection 后调用）。"""
    if collection_name:
        state._bm25_cache.pop(collection_name, None)
        gc.collect()
        for index_dir in (_bm25_index_root(collection_name), _legacy_bm25_index_dir(collection_name)):
            if os.path.isdir(index_dir):
                shutil.rmtree(index_dir, ignore_errors=True)
    else:
        state._bm25_cache.clear()
        gc.collect()
        for dirname in ("bm25_index_v2", "bm25_index"):
            bm25_root = os.path.join(_cfg().storage.db_path, dirname)
            if os.path.isdir(bm25_root):
                shutil.rmtree(bm25_root, ignore_errors=True)


_bm25_cache = state._bm25_cache
