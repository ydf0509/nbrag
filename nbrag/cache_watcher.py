"""基于 collection_profiles.json 变更检测的主动缓存预热。

后台 daemon 线程定期检查 collection_profiles.json 的 mtime，
发现变化后只预热受影响的 collection，保证用户查询始终命中热缓存。
"""

from __future__ import annotations

import os
import threading
import time

from nbrag import state
from nbrag.constants import CacheTTL
from nbrag.loggers import logger


class CacheWatcher:
    """监控 collection_profiles.json，主动预热受影响的缓存。"""

    def __init__(self):
        self._last_mtime: float = 0.0
        self._collection_timestamps: dict[str, str] = {}
        self._thread: threading.Thread | None = None

    def start(self):
        """启动 daemon watcher 线程。"""
        self._thread = threading.Thread(
            target=self._watch_loop, name="nbrag-cache-watcher", daemon=True
        )
        self._thread.start()
        logger.info(
            "cache watcher started (interval=%ds)", CacheTTL.WATCHER_INTERVAL
        )

    def _watch_loop(self):
        while True:
            try:
                self._check_and_prewarm()
            except Exception:
                logger.warning("cache watcher iteration failed", exc_info=True)
            time.sleep(CacheTTL.WATCHER_INTERVAL)

    def _check_and_prewarm(self):
        from nbrag.collection_profiles import _load_manifest, _manifest_path

        path = _manifest_path()
        if not os.path.isfile(path):
            return

        try:
            current_mtime = os.path.getmtime(path)
        except OSError:
            return

        if current_mtime == self._last_mtime:
            return

        manifest = _load_manifest()
        collections = manifest.get("collections", {})

        changed: list[str] = []
        for name, profile in collections.items():
            new_ts = profile.get("last_ingested_at", "")
            old_ts = self._collection_timestamps.get(name, "")
            if new_ts != old_ts:
                changed.append(name)

        deleted = set(self._collection_timestamps) - set(collections)

        all_ok = True

        for name in deleted:
            self._clear_collection_cache(name)
            logger.info("cache watcher: cleared caches for deleted collection %r", name)

        for name in changed:
            try:
                self._prewarm_collection(name)
                logger.info("cache watcher: pre-warmed collection %r", name)
            except Exception:
                logger.warning(
                    "cache watcher: failed to pre-warm collection %r",
                    name, exc_info=True,
                )
                all_ok = False

        need_global = bool(changed or deleted)
        mtime_changed_but_no_data_change = not changed and not deleted
        if mtime_changed_but_no_data_change:
            need_global = True

        if need_global:
            try:
                self._prewarm_global()
                logger.info(
                    "cache watcher: rebuilt global caches (changed=%d, deleted=%d)",
                    len(changed), len(deleted),
                )
            except Exception:
                logger.warning("cache watcher: failed to rebuild global caches", exc_info=True)
                all_ok = False

        if all_ok:
            self._last_mtime = current_mtime
            self._collection_timestamps = {
                name: p.get("last_ingested_at", "")
                for name, p in collections.items()
            }
        else:
            for name in deleted:
                self._collection_timestamps.pop(name, None)
            logger.info(
                "cache watcher: partial failure, will retry next round",
            )

    @staticmethod
    def _clear_collection_cache(name: str):
        with state._runtime_cache_lock:
            state._doc_id_cache.pop(name, None)
            state._doc_id_cache_ts.pop(name, None)
            state._document_list_cache.pop(name, None)
            state._document_list_cache_ts.pop(name, None)
            state._bm25_cache.pop(name, None)
            state._symbol_cache.pop(name, None)

    @staticmethod
    def _prewarm_collection(name: str):
        """预热单个 collection 的 per-collection 缓存。"""
        from nbrag.bm25_index import _load_bm25_index
        from nbrag.retrieval import _list_documents_cached
        from nbrag.storage import _get_doc_id_map
        from nbrag.symbol_index import _load_symbol_index
        from nbrag.tokenizer import BM25_CHANNELS

        with state._runtime_cache_lock:
            state._doc_id_cache.pop(name, None)
            state._doc_id_cache_ts.pop(name, None)
            state._document_list_cache.pop(name, None)
            state._document_list_cache_ts.pop(name, None)
            state._bm25_cache.pop(name, None)
            state._symbol_cache.pop(name, None)

        _get_doc_id_map(name)
        _list_documents_cached(name)
        for channel in BM25_CHANNELS:
            _load_bm25_index(name, channel)
        _load_symbol_index(name)

    @staticmethod
    def _prewarm_global():
        """重建全局缓存（stats / raw_text）。"""
        from nbrag.retrieval import _load_all_raw_texts_cached, get_stats

        with state._runtime_cache_lock:
            state._stats_cache = None
            state._stats_cache_ts = 0.0
            state._raw_text_cache = None
            state._raw_text_cache_ts = 0.0

        _load_all_raw_texts_cached()
        get_stats()


_watcher: CacheWatcher | None = None


def start_cache_watcher():
    """启动全局 CacheWatcher 单例（幂等调用）。"""
    global _watcher
    if _watcher is not None:
        return _watcher
    _watcher = CacheWatcher()
    _watcher.start()
    return _watcher
