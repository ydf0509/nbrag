"""Embedding 与 Rerank API 调用。"""

from __future__ import annotations

import time as _time

import httpx

from nbrag.config import get_config
from nbrag import state
from nbrag.loggers import logger


EMBEDDING_BATCH_SIZE = 32


def _cfg():
    return get_config()


def _get_http_client():
    if state._http_client is None or state._http_client.is_closed:
        state._http_client = httpx.Client(timeout=120)
    return state._http_client


def embed(texts, max_retries=10, sleep_interval=0.0, verbose=False):
    """调用 Embedding API，自动分批，失败自动重试。"""
    cfg = _cfg()
    api_key = cfg.embedding.api_key
    if not api_key:
        raise ValueError(
            "NBRAG_API_KEY is empty. Set the environment variable or configure in nbrag_config.yaml"
        )
    client = _get_http_client()
    all_embeddings = []
    total_chunks = len(texts)
    num_batches = (total_chunks + EMBEDDING_BATCH_SIZE - 1) // EMBEDDING_BATCH_SIZE

    for batch_idx, i in enumerate(range(0, total_chunks, EMBEDDING_BATCH_SIZE)):
        if i > 0 and sleep_interval > 0:
            _time.sleep(sleep_interval)
        batch = texts[i:i + EMBEDDING_BATCH_SIZE]
        if verbose:
            processed = min(i + EMBEDDING_BATCH_SIZE, total_chunks)
            print(f"  [embed {batch_idx + 1:>4}/{num_batches}] {processed}/{total_chunks} chunks")
        for attempt in range(max_retries):
            try:
                resp = client.post(
                    f"{cfg.embedding.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": cfg.embedding.model,
                        "input": batch,
                        "encoding_format": "float",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                sorted_data = sorted(data["data"], key=lambda x: x["index"])
                all_embeddings.extend([d["embedding"] for d in sorted_data])
                break
            except Exception as e:
                logger.error(f"Embedding API error: {e} , attempt :{attempt}")
                if attempt < max_retries - 1:
                    _time.sleep(2 ** attempt)
                else:
                    raise
    return all_embeddings


def rerank(query, documents, top_n=5, max_retries=3):
    """调用 Rerank API，返回 (indices, scores)。"""
    cfg = _cfg()
    if not cfg.embedding.api_key or not cfg.rerank.model:
        n = min(top_n, len(documents))
        return list(range(n)), [0.0] * n

    client = _get_http_client()
    for attempt in range(max_retries):
        try:
            resp = client.post(
                f"{cfg.embedding.base_url}/rerank",
                headers={
                    "Authorization": f"Bearer {cfg.embedding.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": cfg.rerank.model,
                    "query": query,
                    "documents": documents,
                    "top_n": top_n,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            indices = [r["index"] for r in data["results"]]
            scores = [r.get("relevance_score", 0.0) for r in data["results"]]
            return indices, scores
        except Exception:
            if attempt < max_retries - 1:
                _time.sleep(2 ** attempt)
            else:
                raise
