"""存储层工具。

包含 ChromaDB collection、路径规范、原始文件缓存和 doc_id 映射缓存。
"""

from __future__ import annotations

import os
import time as _time

import chromadb

from nbrag.config import get_config
from nbrag import state
from nbrag.runtime import _runtime_guarded


_CHROMA_GET_BATCH = 500


def _cfg():
    return get_config()


def _ensure_dirs():
    if state._data_dir_initialized:
        return
    cfg = _cfg()
    os.makedirs(cfg.storage.db_path, exist_ok=True)
    os.makedirs(cfg.storage.raw_files_path, exist_ok=True)
    state._data_dir_initialized = True


def _get_chroma():
    if state._chroma_client is None:
        _ensure_dirs()
        state._chroma_client = chromadb.PersistentClient(path=_cfg().storage.db_path)
    return state._chroma_client


def _batch_get(col, include, ids=None, where=None):
    """分页获取 ChromaDB collection 数据，避免 SQLite 参数数量限制。"""
    if where is not None:
        kwargs = {"include": list(include)}
        if ids is not None:
            kwargs["ids"] = list(ids)
        kwargs["where"] = where
        return col.get(**kwargs)

    if ids is not None:
        ids_list = list(ids)
        if len(ids_list) <= _CHROMA_GET_BATCH:
            return col.get(ids=ids_list, include=list(include))
        result = {"ids": [], "documents": [], "metadatas": []}
        for i in range(0, len(ids_list), _CHROMA_GET_BATCH):
            batch = col.get(ids=ids_list[i:i + _CHROMA_GET_BATCH], include=list(include))
            for key in result:
                if key in batch and batch[key] is not None:
                    result[key].extend(batch[key])
        return result

    id_only = col.get(include=[])
    all_ids = id_only.get("ids", [])
    if not all_ids:
        return {"ids": [], "documents": [], "metadatas": []}
    if len(all_ids) <= _CHROMA_GET_BATCH:
        return col.get(include=list(include))
    result = {"ids": [], "documents": [], "metadatas": []}
    for i in range(0, len(all_ids), _CHROMA_GET_BATCH):
        batch = col.get(ids=all_ids[i:i + _CHROMA_GET_BATCH], include=list(include))
        for key in result:
            if key in batch and batch[key] is not None:
                result[key].extend(batch[key])
    return result


def _normalize_path(path):
    """统一路径格式（跨平台兼容）。"""
    p = os.path.abspath(path).replace("\\", "/")
    if len(p) >= 2 and p[1] == ":":
        p = p[0].upper() + p[1:]
    return p


def _is_absolute_path(path):
    """判断入参是否是完整绝对路径，避免 basename/相对路径造成歧义。"""
    if not path:
        return False
    p = str(path).strip()
    if os.path.isabs(p):
        return True
    return len(p) >= 3 and p[1] == ":" and p[2] in ("/", "\\")


@_runtime_guarded
def get_collection(name="default"):
    """获取或创建一个 ChromaDB collection（写操作用）。"""
    return _get_chroma().get_or_create_collection(
        name=name, metadata={"hnsw:space": "cosine"},
    )


def _get_existing_collection(name):
    """获取已存在的 collection，不存在时返回 None。"""
    try:
        return _get_chroma().get_collection(name=name)
    except (ValueError, Exception):
        return None


@_runtime_guarded
def delete_collection(name):
    """删除整个 collection（清空该知识库）。"""
    from nbrag.bm25_index import invalidate_bm25_cache
    from nbrag.symbol_index import invalidate_symbol_cache

    _get_chroma().delete_collection(name)
    invalidate_doc_id_cache(name)
    invalidate_bm25_cache(name)
    invalidate_symbol_cache(name)


@_runtime_guarded
def list_collections():
    """列出所有 collection。"""
    return _get_chroma().list_collections()


def _raw_files_dir():
    return _cfg().storage.raw_files_path


def _raw_file_dir(collection_name):
    d = os.path.join(_raw_files_dir(), collection_name)
    os.makedirs(d, exist_ok=True)
    return d


def _raw_file_path(collection_name, doc_id, ext=""):
    return os.path.join(_raw_file_dir(collection_name), f"{doc_id}{ext}")


def _cache_raw_file(text, collection_name, doc_id, ext=""):
    """将原始文件内容缓存到 raw_files/ 目录。"""
    path = _raw_file_path(collection_name, doc_id, ext)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _delete_raw_file(collection_name, doc_id):
    """删除缓存的原始文件（尝试所有可能的扩展名）。"""
    d = os.path.join(_raw_files_dir(), collection_name)
    if not os.path.isdir(d):
        return
    prefix = f"{doc_id}"
    for fname in os.listdir(d):
        if fname.startswith(prefix):
            try:
                os.remove(os.path.join(d, fname))
            except OSError:
                pass


def _read_raw_file(collection_name, doc_id):
    """读取缓存的原始文件，返回 (content, cached_path) 或 (None, None)。"""
    d = os.path.join(_raw_files_dir(), collection_name)
    if not os.path.isdir(d):
        return None, None
    prefix = f"{doc_id}"
    for fname in os.listdir(d):
        if fname.startswith(prefix):
            fpath = os.path.join(d, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    return f.read(), fpath
            except OSError:
                return None, None
    return None, None


def _delete_raw_files_collection(collection_name):
    """删除某个 collection 的全部缓存文件。"""
    import shutil

    d = os.path.join(_raw_files_dir(), collection_name)
    if os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)


def _get_doc_id_map(collection_name):
    """获取 collection 的 doc_id -> {filename, source} 映射（带内存缓存）。"""
    now = _time.time()
    if (
        collection_name in state._doc_id_cache
        and now - state._doc_id_cache_ts.get(collection_name, 0) < 600
    ):
        return state._doc_id_cache[collection_name]

    col = _get_existing_collection(collection_name)
    if col is None:
        return {}
    all_meta = _batch_get(col, include=["metadatas"])
    mapping = {}
    for meta in all_meta["metadatas"]:
        did = meta.get("doc_id", "")
        if did and did not in mapping:
            mapping[did] = {
                "filename": meta.get("filename", "?"),
                "source": meta.get("source", "?"),
            }
    state._doc_id_cache[collection_name] = mapping
    state._doc_id_cache_ts[collection_name] = now
    return mapping


def invalidate_doc_id_cache(collection_name=None):
    """清除 doc_id 映射缓存。"""
    if collection_name:
        state._doc_id_cache.pop(collection_name, None)
        state._doc_id_cache_ts.pop(collection_name, None)
    else:
        state._doc_id_cache.clear()
        state._doc_id_cache_ts.clear()
