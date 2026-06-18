"""知识库 profile 管理。

这里保存给 AI 和人看的语义说明，不写入 Chroma collection metadata。
"""

from __future__ import annotations

import json
import os
import threading
from copy import deepcopy

from nbrag.config import get_config

_PROFILE_FILE = "collection_profiles.json"
_manifest_lock = threading.RLock()


def _cfg():
    return get_config()


def _manifest_path():
    return os.path.join(_cfg().storage.db_path, _PROFILE_FILE)


def _ensure_manifest_dir():
    os.makedirs(_cfg().storage.db_path, exist_ok=True)


def _empty_manifest():
    return {"version": 1, "collections": {}}


def _normalize_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text


def _normalize_items(values):
    if values is None:
        return None
    if isinstance(values, str):
        values = [values]
    items = []
    seen = set()
    for value in values:
        text = _normalize_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
    return items


def _load_manifest():
    path = _manifest_path()
    if not os.path.isfile(path):
        return _empty_manifest()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return _empty_manifest()

    if not isinstance(data, dict):
        return _empty_manifest()

    collections = data.get("collections", {})
    if not isinstance(collections, dict):
        collections = {}

    return {
        "version": int(data.get("version", 1) or 1),
        "collections": collections,
    }


def _write_manifest(manifest):
    _ensure_manifest_dir()
    path = _manifest_path()
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp_path, path)


def _clean_collection_name(collection_name):
    name = _normalize_text(collection_name)
    if not name:
        raise ValueError("collection_name is required")
    return name


def _augment_profile(collection_name, profile):
    result = deepcopy(profile) if isinstance(profile, dict) else {}
    result["collection_name"] = collection_name
    result.setdefault("display_name", "")
    result.setdefault("description", "")
    result.setdefault("aliases", [])
    result.setdefault("tags", [])
    return result


def set_collection_profile(collection_name, display_name=None, description=None, aliases=None, tags=None, **extra):
    """创建或更新知识库 profile。

    只管理应用层语义信息，不影响 Chroma collection metadata。
    """
    collection_name = _clean_collection_name(collection_name)

    with _manifest_lock:
        manifest = _load_manifest()
        collections = manifest.setdefault("collections", {})
        profile = dict(collections.get(collection_name, {}))

        if display_name is not None:
            profile["display_name"] = _normalize_text(display_name)
        if description is not None:
            profile["description"] = _normalize_text(description)
        if aliases is not None:
            profile["aliases"] = _normalize_items(aliases)
        if tags is not None:
            profile["tags"] = _normalize_items(tags)

        for key, value in extra.items():
            if value is not None:
                profile[key] = value

        collections[collection_name] = profile
        _write_manifest(manifest)
        return _augment_profile(collection_name, profile)


def get_collection_profile(collection_name):
    """读取单个知识库 profile，不存在时返回 None。"""
    collection_name = _clean_collection_name(collection_name)
    with _manifest_lock:
        manifest = _load_manifest()
        profile = manifest.get("collections", {}).get(collection_name)
        if profile is None:
            return None
        return _augment_profile(collection_name, profile)


def list_collection_profiles():
    """列出所有已配置的知识库 profile。"""
    with _manifest_lock:
        manifest = _load_manifest()
        profiles = {}
        for collection_name in sorted(manifest.get("collections", {}).keys()):
            profiles[collection_name] = _augment_profile(
                collection_name,
                manifest["collections"].get(collection_name, {}),
            )
        return profiles
