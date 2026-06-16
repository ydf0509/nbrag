"""
配置加载模块 — CLI > 环境变量 > YAML 配置文件 > 默认值。

最小启动只需要一个环境变量:
    export NBRAG_API_KEY=sk-xxx
    uvx nbrag
"""

import os
from dataclasses import dataclass, field


# 项目根目录（config.py 位于 <PROJECT_ROOT>/nbrag/config.py）
# 用 __file__ 推导绝对路径，确保不论从哪里启动脚本，db_path 都指向同一个固定位置
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_DB_PATH = os.path.join(_PROJECT_ROOT, "rag_db")


@dataclass
class EmbeddingConfig:
    api_key: str = ""
    base_url: str = "https://api.siliconflow.cn/v1"
    model: str = "BAAI/bge-m3"


@dataclass
class RerankConfig:
    model: str = "BAAI/bge-reranker-v2-m3"


@dataclass
class StorageConfig:
    db_path: str = _DEFAULT_DB_PATH
    raw_files_path: str = ""  # 默认 db_path/raw_files


@dataclass
class ChunkingConfig:
    chunk_size: int = 1500
    chunk_overlap: int = 200


@dataclass
class RagConfig:
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    rerank: RerankConfig = field(default_factory=RerankConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)

    def __post_init__(self):
        if not self.storage.raw_files_path:
            self.storage.raw_files_path = os.path.join(self.storage.db_path, "raw_files")


_config: RagConfig = None


def _load_yaml(path):
    """加载 YAML 配置文件，返回 dict（文件不存在返回空 dict）。"""
    if not path or not os.path.isfile(path):
        return {}
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _find_config_file():
    """按优先级查找配置文件。"""
    candidates = [
        os.path.join(os.getcwd(), "nbrag_config.yaml"),
        os.path.join(os.getcwd(), "nbrag_config.yml"),
        os.path.expanduser("~/.config/nbrag/config.yaml"),
        os.path.expanduser("~/.config/nbrag/config.yml"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def _resolve_env_ref(value):
    """解析 ${VAR_NAME} 环境变量引用。"""
    if not isinstance(value, str):
        return value
    if value.startswith("${") and value.endswith("}"):
        var_name = value[2:-1]
        return os.environ.get(var_name, "")
    return value


def load_config(cli_args=None) -> RagConfig:
    """加载配置：CLI > 环境变量 > YAML > 默认值。"""
    global _config

    yaml_path = None
    if cli_args and hasattr(cli_args, 'config') and cli_args.config:
        yaml_path = cli_args.config
    else:
        yaml_path = os.environ.get("NBRAG_CONFIG", None) or _find_config_file()

    yaml_data = _load_yaml(yaml_path)

    embedding_data = yaml_data.get("embedding", {})
    rerank_data = yaml_data.get("rerank", {})
    storage_data = yaml_data.get("storage", {})
    chunking_data = yaml_data.get("chunking", {})

    api_key = (
        (getattr(cli_args, 'api_key', None) if cli_args else None)
        or os.environ.get("NBRAG_API_KEY", "")
        or _resolve_env_ref(embedding_data.get("api_key", ""))
    )

    base_url = (
        os.environ.get("NBRAG_BASE_URL", "")
        or embedding_data.get("base_url", "")
        or "https://api.siliconflow.cn/v1"
    )

    embedding_model = (
        os.environ.get("NBRAG_EMBEDDING_MODEL", "")
        or embedding_data.get("model", "")
        or "BAAI/bge-m3"
    )

    rerank_model = (
        os.environ.get("NBRAG_RERANK_MODEL", "")
        or rerank_data.get("model", "")
        or "BAAI/bge-reranker-v2-m3"
    )

    db_path = (
        (getattr(cli_args, 'db_path', None) if cli_args else None)
        or os.environ.get("NBRAG_DB_PATH", "")
        or storage_data.get("db_path", "")
        or _DEFAULT_DB_PATH
    )

    raw_files_path = (
        os.environ.get("NBRAG_RAW_FILES_PATH", "")
        or storage_data.get("raw_files_path", "")
        or ""
    )

    chunk_size = int(
        os.environ.get("NBRAG_CHUNK_SIZE", "")
        or chunking_data.get("chunk_size", 0)
        or 1500
    )

    chunk_overlap = int(
        os.environ.get("NBRAG_CHUNK_OVERLAP", "")
        or chunking_data.get("chunk_overlap", 0)
        or 200
    )

    _config = RagConfig(
        embedding=EmbeddingConfig(api_key=api_key, base_url=base_url, model=embedding_model),
        rerank=RerankConfig(model=rerank_model),
        storage=StorageConfig(db_path=db_path, raw_files_path=raw_files_path),
        chunking=ChunkingConfig(chunk_size=chunk_size, chunk_overlap=chunk_overlap),
    )
    return _config


def get_config() -> RagConfig:
    """获取当前配置（未加载时自动从环境变量加载）。"""
    global _config
    if _config is None:
        load_config()
    return _config
