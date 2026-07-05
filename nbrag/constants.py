class CacheTTL:
    """缓存生存时间（秒）。

    主要依靠 CacheWatcher 基于 collection_profiles.json 的 mtime
    变更检测来主动预热缓存。TTL 仅作为极端情况的兜底安全网。
    """

    STATS = 86400.0
    DOCUMENT_LIST = 86400.0
    RAW_TEXT = 86400.0
    DOC_ID_MAP = 86400.0
    RUNTIME_REFRESH = 86400.0

    WATCHER_INTERVAL = 30.0


class NetworkTimeout:
    """网络请求超时（秒）。"""

    HTTP_CLIENT = 120
