"""进程内共享状态。

这里只放缓存、客户端句柄和运行时计时器，不放业务逻辑。
"""

from __future__ import annotations

import threading
import time as _runtime_clock

_chroma_client = None
_data_dir_initialized = False

_doc_id_cache = {}
_doc_id_cache_ts = {}
_stats_cache = None
_stats_cache_ts = 0.0

_bm25_cache = {}
_symbol_cache = {}

_http_client = None

_RUNTIME_CACHE_REFRESH_INTERVAL = 300.0
_runtime_cache_lock = threading.RLock()
_last_runtime_cache_refresh_ts = _runtime_clock.monotonic()
