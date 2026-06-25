"""Python Symbol 索引。

为 find_definition 提供快速的 AST 符号查找。
"""

from __future__ import annotations

import ast as _ast
import json
import os
import shutil
import warnings as _warnings

from nbrag import state
from nbrag.config import get_config
from nbrag.storage import _get_doc_id_map, _raw_files_dir


def _cfg():
    return get_config()


def _symbol_index_dir(collection_name):
    return os.path.join(_cfg().storage.db_path, "symbol_index", collection_name)


def build_symbol_index(collection_name):
    """扫描 raw_files 中所有 .py 文件的 AST，构建 symbol 索引并持久化到磁盘。"""
    from nbrag.chunker import _extract_signature, get_ast_definition_line_range

    raw_dir = os.path.join(_raw_files_dir(), collection_name)
    if not os.path.isdir(raw_dir):
        return

    doc_id_to_info = _get_doc_id_map(collection_name)
    index = {}

    for fname in os.listdir(raw_dir):
        if not fname.lower().endswith(".py"):
            continue
        doc_id = os.path.splitext(fname)[0]
        info = doc_id_to_info.get(doc_id, {})
        fpath = os.path.join(raw_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            continue
        try:
            with _warnings.catch_warnings():
                _warnings.simplefilter("ignore", SyntaxWarning)
                tree = _ast.parse(content)
        except SyntaxError:
            continue

        def _walk(node, parent_chain=""):
            for child in _ast.iter_child_nodes(node):
                if not isinstance(child, (_ast.ClassDef, _ast.FunctionDef, _ast.AsyncFunctionDef)):
                    continue
                name = child.name
                qualified = f"{parent_chain}.{name}" if parent_chain else name
                start, end = get_ast_definition_line_range(child)
                sym_type = "class" if isinstance(child, _ast.ClassDef) else "function"
                sig = _extract_signature(child)

                methods = []
                if isinstance(child, _ast.ClassDef):
                    for sub in _ast.iter_child_nodes(child):
                        if isinstance(sub, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                            methods.append(_extract_signature(sub))

                entry = {
                    "doc_id": doc_id,
                    "filename": info.get("filename", fname),
                    "source": info.get("source", fpath),
                    "type": sym_type,
                    "qualified": qualified,
                    "line_start": start,
                    "line_end": end,
                    "sig": sig,
                    "methods": methods,
                }
                index.setdefault(name, []).append(entry)
                _walk(child, qualified)

        _walk(tree)

    index_dir = _symbol_index_dir(collection_name)
    os.makedirs(index_dir, exist_ok=True)
    with open(os.path.join(index_dir, "symbols.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)

    state._symbol_cache[collection_name] = index
    return index


def _load_symbol_index(collection_name):
    """从磁盘加载 Symbol 索引到内存缓存。"""
    if collection_name in state._symbol_cache:
        return state._symbol_cache[collection_name]

    index_dir = _symbol_index_dir(collection_name)
    symbols_path = os.path.join(index_dir, "symbols.json")
    if not os.path.isfile(symbols_path):
        return None

    try:
        with open(symbols_path, "r", encoding="utf-8") as f:
            index = json.load(f)
        state._symbol_cache[collection_name] = index
        return index
    except Exception:
        return None


def invalidate_symbol_cache(collection_name=None):
    """清除 Symbol 索引缓存（导入/删除后调用）。"""
    if collection_name:
        state._symbol_cache.pop(collection_name, None)
        index_dir = _symbol_index_dir(collection_name)
        if os.path.isdir(index_dir):
            shutil.rmtree(index_dir, ignore_errors=True)
    else:
        state._symbol_cache.clear()
        symbol_root = os.path.join(_cfg().storage.db_path, "symbol_index")
        if os.path.isdir(symbol_root):
            shutil.rmtree(symbol_root, ignore_errors=True)


def _query_symbol_index(symbol, index):
    """在 Symbol 索引中查找匹配项，返回 entry 列表。"""
    results = []
    seen = set()
    lookup_key = symbol.rsplit(".", 1)[-1]

    for entry in index.get(lookup_key, []):
        name = entry["qualified"].rsplit(".", 1)[-1]
        qualified = entry["qualified"]
        if name == symbol or qualified == symbol or qualified.endswith(f".{symbol}"):
            key = (entry["doc_id"], entry["line_start"])
            if key not in seen:
                seen.add(key)
                results.append(entry)

    if "." in symbol:
        first_part = symbol.split(".")[0]
        for entry in index.get(first_part, []):
            qualified = entry["qualified"]
            if qualified == symbol or qualified.endswith(f".{symbol}"):
                key = (entry["doc_id"], entry["line_start"])
                if key not in seen:
                    seen.add(key)
                    results.append(entry)

    return results


_symbol_cache = state._symbol_cache
