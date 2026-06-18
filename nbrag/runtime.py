"""运行时缓存守卫。

负责周期性清理进程内缓存，并为公共核心操作提供统一加锁入口。
"""

from __future__ import annotations

from functools import wraps

from nbrag import state


def _refresh_runtime_caches_if_due_locked():
    """清理进程内缓存。

    调用方必须持有 `_runtime_cache_lock`。
    这只影响内存态缓存，不会删除磁盘上的 BM25 / symbol / raw / Chroma 数据。
    """
    now = state._runtime_clock.monotonic()
    if now - state._last_runtime_cache_refresh_ts < state._RUNTIME_CACHE_REFRESH_INTERVAL:
        return False

    state._chroma_client = None
    state._doc_id_cache.clear()
    state._doc_id_cache_ts.clear()
    state._bm25_cache.clear()
    state._symbol_cache.clear()
    state._last_runtime_cache_refresh_ts = now
    return True


def _with_runtime_cache_refresh(func, *args, **kwargs):
    """在运行时缓存锁保护下执行一次公共操作。"""
    with state._runtime_cache_lock:
        _refresh_runtime_caches_if_due_locked()
        return func(*args, **kwargs)


def _runtime_guarded(func):
    """为需要访问共享运行时状态的公共函数加锁和缓存刷新。"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        return _with_runtime_cache_refresh(func, *args, **kwargs)

    return wrapper
