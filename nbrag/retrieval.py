"""检索与查询操作。

包含向量/BM25 混合搜索、原文读取、grep、definition 查找、文档列表和统计。
"""

from __future__ import annotations

import ast as _ast
import os
import re
import time as _time
import warnings as _warnings

from nbrag import state
from nbrag.bm25_index import (
    _BM25_CHANNEL_WEIGHTS,
    _bm25_search_channels,
    _weighted_rrf_fusion,
    invalidate_bm25_cache,
)
from nbrag.config import get_config
from nbrag.collection_profiles import list_collection_profiles
from nbrag.embeddings import embed, rerank
from nbrag.runtime import _runtime_guarded
from nbrag.storage import (
    _batch_get,
    _delete_raw_file,
    _get_chroma,
    _get_doc_id_map,
    _get_existing_collection,
    _is_absolute_path,
    _normalize_path,
    _raw_file_path,
    _raw_files_dir,
    _read_raw_file,
    list_collections,
)
from nbrag.symbol_index import (
    _load_symbol_index,
    _query_symbol_index,
    invalidate_symbol_cache,
)

_STATS_CACHE_TTL_SECONDS = 300.0
_DOCUMENT_LIST_CACHE_TTL_SECONDS = 300.0
_RAW_TEXT_CACHE_TTL_SECONDS = 300.0


def _cfg():
    return get_config()


def _load_all_raw_texts_cached():
    """加载并缓存所有知识库的 raw_files 原文快照，TTL 300 秒。"""
    now = _time.time()
    if state._raw_text_cache is not None and now - state._raw_text_cache_ts < _RAW_TEXT_CACHE_TTL_SECONDS:
        return state._raw_text_cache

    root = _raw_files_dir()
    collections = {}
    if os.path.isdir(root):
        for collection_name in os.listdir(root):
            collection_dir = os.path.join(root, collection_name)
            if not os.path.isdir(collection_dir):
                continue
            doc_id_to_info = _get_doc_id_map(collection_name)
            docs = {}
            for fname in os.listdir(collection_dir):
                fpath = os.path.join(collection_dir, fname)
                if not os.path.isfile(fpath):
                    continue
                doc_id = os.path.splitext(fname)[0]
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                except OSError:
                    continue
                info = doc_id_to_info.get(doc_id, {})
                docs[doc_id] = {
                    "doc_id": doc_id,
                    "filename": info.get("filename", fname),
                    "source": info.get("source", fpath),
                    "content": content,
                }
            collections[collection_name] = docs

    state._raw_text_cache = collections
    state._raw_text_cache_ts = now
    return collections


def _get_cached_raw_doc(collection_name, doc_id=None, source=None):
    """从全局 raw text cache 中按 doc_id 或 source 取单个文档。"""
    cache = _load_all_raw_texts_cached()
    docs = cache.get(collection_name, {})
    if doc_id is not None:
        return docs.get(doc_id)
    if source is not None:
        normalized = _normalize_path(source)
        for item in docs.values():
            if item.get("source") == normalized:
                return item
    return None


@_runtime_guarded
def search(query, collection_name="default", top_k=5, use_rerank=True,
           use_bm25=True, filter_file_path=None, use_vector=True):
    """混合检索：Vector + BM25 -> RRF 融合 -> Reranker 精排。

    当 use_vector=False 且 use_bm25=True 时，只走 BM25 多通道检索，
    不生成 query embedding，也不执行 Chroma 向量查询。"""
    col = _get_existing_collection(collection_name)
    if col is None:
        return [], [], [], False, 0, []
    total = col.count()

    if total == 0:
        return [], [], [], False, 0, []
    if filter_file_path and not _is_absolute_path(filter_file_path):
        return [], [], [], False, total, []

    if use_bm25 and not use_vector:
        recall_k = min(max(top_k * (20 if filter_file_path else 4), top_k), total)
        channel_results = _bm25_search_channels(query, collection_name, recall_k)
        if not channel_results:
            return [], [], [], False, total, []

        ranked_sources = [
            (channel, ids, _BM25_CHANNEL_WEIGHTS.get(channel, 1.0))
            for channel, ids in channel_results.items()
        ]
        fused_ids = _weighted_rrf_fusion(ranked_sources)
        normalized_filter_path = _normalize_path(filter_file_path) if filter_file_path else None

        try:
            extra = _batch_get(col, ids=fused_ids, include=["documents", "metadatas"])
        except Exception:
            return [], [], [], False, total, []

        id_to_data = {
            eid: (extra["documents"][i], extra["metadatas"][i])
            for i, eid in enumerate(extra["ids"])
        }
        documents = []
        metadatas = []
        for cid in fused_ids:
            if cid not in id_to_data:
                continue
            doc, meta = id_to_data[cid]
            if normalized_filter_path and meta.get("source", "") != normalized_filter_path:
                continue
            documents.append(doc)
            metadatas.append(meta)
            if len(documents) >= top_k:
                break
        distances = [0.0] * len(documents)
        return documents, metadatas, distances, False, total, []

    query_vec = embed([query])[0]
    recall_k = min(top_k * 4, total) if (use_rerank or use_bm25) else min(top_k, total)

    where_filter = {"source": _normalize_path(filter_file_path)} if filter_file_path else None
    vec_results = col.query(
        query_embeddings=[query_vec],
        n_results=recall_k,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )
    vec_ids = vec_results["ids"][0]
    vec_docs = vec_results["documents"][0]
    vec_metas = vec_results["metadatas"][0]
    vec_dists = vec_results["distances"][0]

    if use_bm25 and not filter_file_path:
        channel_results = _bm25_search_channels(query, collection_name, recall_k)
        if channel_results:
            ranked_sources = [("vector", vec_ids, 1.0)]
            ranked_sources.extend(
                (channel, ids, _BM25_CHANNEL_WEIGHTS.get(channel, 1.0))
                for channel, ids in channel_results.items()
            )
            fused_ids = _weighted_rrf_fusion(ranked_sources)

            id_to_data = {vid: (vec_docs[i], vec_metas[i], vec_dists[i])
                          for i, vid in enumerate(vec_ids)}

            bm25_only = [bid for bid in fused_ids if bid not in id_to_data]
            if bm25_only:
                max_vec_dist = max(vec_dists) if vec_dists else 1.0
                try:
                    extra = _batch_get(col, ids=bm25_only, include=["documents", "metadatas"])
                    for i, eid in enumerate(extra["ids"]):
                        id_to_data[eid] = (extra["documents"][i], extra["metadatas"][i], max_vec_dist)
                except Exception:
                    pass

            documents = [id_to_data[cid][0] for cid in fused_ids if cid in id_to_data]
            metadatas = [id_to_data[cid][1] for cid in fused_ids if cid in id_to_data]
            distances = [id_to_data[cid][2] for cid in fused_ids if cid in id_to_data]
        else:
            documents, metadatas, distances = vec_docs, vec_metas, vec_dists
    else:
        documents, metadatas, distances = vec_docs, vec_metas, vec_dists

    cfg = _cfg()
    rerank_used = False
    rerank_scores = []
    if use_rerank and cfg.rerank.model and len(documents) > top_k:
        try:
            reranked_idx, rerank_scores = rerank(query, documents, top_n=top_k)
            documents = [documents[i] for i in reranked_idx]
            metadatas = [metadatas[i] for i in reranked_idx]
            distances = [distances[i] for i in reranked_idx]
            rerank_used = True
        except Exception:
            documents = documents[:top_k]
            metadatas = metadatas[:top_k]
            distances = distances[:top_k]
    else:
        documents = documents[:top_k]
        metadatas = metadatas[:top_k]
        distances = distances[:top_k]

    return documents, metadatas, distances, rerank_used, total, rerank_scores


@_runtime_guarded
def get_file_chunks(file_identifier, collection_name="default",
                    start_chunk=0, max_chunks=5,
                    raw=False, line_start=-1, line_end=-1):
    """按完整绝对文件路径获取知识库中该文件的内容。"""
    col = _get_existing_collection(collection_name)
    if col is None:
        return {"found": False, "error": f"collection '{collection_name}' does not exist"}
    total = col.count()
    if total == 0:
        return {"found": False, "error": f"collection '{collection_name}' is empty"}
    if not _is_absolute_path(file_identifier):
        return {"found": False, "error": "Full absolute file_path is required. Use the file_path returned by search/list tools."}

    all_data = _query_file_by_identifier(col, file_identifier)

    if not all_data["ids"]:
        return {"found": False, "error": f"File not found: '{file_identifier}'"}

    items = list(zip(all_data["ids"], all_data["documents"], all_data["metadatas"]))
    items.sort(key=lambda x: x[2].get("chunk_index", 0))

    first_meta = items[0][2]
    total_chunks = len(items)
    max_line = max(m.get("line_end", 0) for _, _, m in items)
    doc_id = first_meta.get("doc_id", "?")
    source = first_meta.get("source", "?")
    actual_filename = first_meta.get("filename", "?")

    if raw:
        return _get_raw_file_result(
            collection_name, doc_id, source, actual_filename,
            total_chunks, max_line, line_start, line_end,
        )

    chunk_line_ranges = [
        (m.get("line_start", 0), m.get("line_end", 0)) for _, _, m in items
    ]

    end_chunk = min(start_chunk + max_chunks, total_chunks)
    selected = items[start_chunk:end_chunk]

    chunks = []
    for _, doc, meta in selected:
        chunks.append({
            "index": meta.get("chunk_index", 0),
            "line_start": meta.get("line_start", 0),
            "line_end": meta.get("line_end", 0),
            "scope": meta.get("scope", ""),
            "content": doc,
        })

    return {
        "found": True,
        "source": source,
        "filename": actual_filename,
        "doc_id": doc_id,
        "total_chunks": total_chunks,
        "total_lines": max_line,
        "chunk_line_ranges": chunk_line_ranges,
        "chunks": chunks,
        "start_chunk": start_chunk,
        "end_chunk": end_chunk,
    }


@_runtime_guarded
def get_raw_file(file_identifier, collection_name="default", line_start=-1, line_end=-1):
    """读取完整原文内容的兼容包装。"""
    return get_file_chunks(
        file_identifier,
        collection_name=collection_name,
        raw=True,
        line_start=line_start,
        line_end=line_end,
    )


def _query_file_by_identifier(col, file_identifier):
    """按完整绝对路径查找文件的 chunks。"""
    empty = {"ids": [], "documents": [], "metadatas": []}

    if not _is_absolute_path(file_identifier):
        return empty
    normalized = _normalize_path(file_identifier)
    try:
        return col.get(where={"source": normalized}, include=["documents", "metadatas"])
    except Exception:
        return empty


def _get_raw_file_result(collection_name, doc_id, source, filename,
                         total_chunks, total_lines, line_start, line_end):
    """从全局 raw text cache 读取原始文件，支持按行截取。"""
    cached = _get_cached_raw_doc(collection_name, doc_id=doc_id, source=source)
    if not cached:
        content, _cached_path = _read_raw_file(collection_name, doc_id)
        if content is None:
            return {
                "found": False,
                "error": f"Stored raw content is unavailable for file_path: {source}",
            }
    else:
        content = cached["content"]

    lines = content.splitlines(keepends=True)
    actual_total = len(lines)

    ls = max(1, line_start) if line_start > 0 else 1
    le = min(actual_total, line_end) if line_end > 0 else actual_total
    selected_lines = lines[ls - 1:le]

    return {
        "found": True,
        "raw": True,
        "source": source,
        "filename": filename,
        "doc_id": doc_id,
        "total_chunks": total_chunks,
        "total_lines": actual_total,
        "line_start": ls,
        "line_end": le,
        "content": "".join(selected_lines),
    }


@_runtime_guarded
def get_context_chunks(doc_id, collection_name="default",
                       chunk_index=None, window=2,
                       line_start=None, line_end=None):
    """获取指定文档的上下文 chunks。"""
    col = _get_existing_collection(collection_name)
    if col is None:
        return {"found": False, "error": f"collection '{collection_name}' does not exist"}

    try:
        all_data = col.get(
            where={"doc_id": doc_id},
            include=["documents", "metadatas"],
        )
    except Exception:
        all_data = {"ids": [], "documents": [], "metadatas": []}

    if not all_data["ids"]:
        return {"found": False, "error": f"Document not found: '{doc_id}'"}

    items = list(zip(all_data["ids"], all_data["documents"], all_data["metadatas"]))
    items.sort(key=lambda x: x[2].get("chunk_index", 0))

    if chunk_index is not None:
        idx_min = max(0, chunk_index - window)
        idx_max = min(len(items) - 1, chunk_index + window)
        selected = items[idx_min:idx_max + 1]
    elif line_start is not None and line_end is not None:
        selected = []
        for item in items:
            meta = item[2]
            cl_start = meta.get("line_start", 0)
            cl_end = meta.get("line_end", 0)
            if cl_start <= line_end and cl_end >= line_start:
                selected.append(item)
        if not selected:
            return {"found": True, "chunks": [],
                    "message": f"No chunks matching line range {line_start}-{line_end}"}
    else:
        return {"found": False, "error": "Provide either chunk_index or line_start+line_end"}

    first_meta = items[0][2]
    chunks = []
    for _, doc, meta in selected:
        chunks.append({
            "index": meta.get("chunk_index", 0),
            "line_start": meta.get("line_start", 0),
            "line_end": meta.get("line_end", 0),
            "scope": meta.get("scope", ""),
            "content": doc,
        })

    return {
        "found": True,
        "source": first_meta.get("source", "?"),
        "filename": first_meta.get("filename", "?"),
        "doc_id": doc_id,
        "total_chunks": len(items),
        "chunks": chunks,
    }


@_runtime_guarded
def grep_knowledge(keyword, collection_name="default", max_results=10,
                   case_sensitive=False, filter_file_path=None, context_lines=5):
    """在知识库的全局 raw text cache 中进行关键词/正则搜索。"""
    if filter_file_path and not _is_absolute_path(filter_file_path):
        return []

    docs = _load_all_raw_texts_cached().get(collection_name, {})
    if not docs:
        return []
    normalized_filter_path = _normalize_path(filter_file_path) if filter_file_path else None

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(keyword, flags)
    except re.error:
        pattern = re.compile(re.escape(keyword), flags)

    results = []
    for doc_id, info in docs.items():
        if normalized_filter_path and info.get("source", "") != normalized_filter_path:
            continue

        file_lines = info.get("content", "").splitlines()
        for i, line in enumerate(file_lines):
            if pattern.search(line):
                ctx_start = max(0, i - context_lines)
                ctx_end = min(len(file_lines), i + context_lines + 1)
                ctx_parts = []
                for j in range(ctx_start, ctx_end):
                    prefix = ">>>" if j == i else "   "
                    ctx_parts.append(f"{prefix} {j + 1:>5}| {file_lines[j].rstrip()}")

                results.append({
                    "filename": info.get("filename", f"{doc_id}.txt"),
                    "source": info.get("source", "?"),
                    "doc_id": doc_id,
                    "line_number": i + 1,
                    "line_content": line.rstrip(),
                    "context": "\n".join(ctx_parts),
                })

                if len(results) >= max_results:
                    return results

    return results


@_runtime_guarded
def find_symbol_definition(symbol, collection_name="default", max_results=3):
    """在知识库中查找符号（类/函数/方法）的完整定义。"""
    raw_dir = os.path.join(_raw_files_dir(), collection_name)
    if not os.path.isdir(raw_dir):
        return []

    index = _load_symbol_index(collection_name)
    if index is not None:
        return _find_definition_via_index(symbol, collection_name, index, raw_dir, max_results)

    return _find_definition_full_scan(symbol, collection_name, raw_dir, max_results)


def _find_definition_via_index(symbol, collection_name, index, raw_dir, max_results):
    """通过 Symbol 索引查找定义（快速路径）。"""
    entries = _query_symbol_index(symbol, index)
    results = []

    for entry in entries[:max_results]:
        doc_id = entry["doc_id"]
        content = None
        rpath = _raw_file_path(collection_name, doc_id, ".py")
        if os.path.isfile(rpath):
            try:
                with open(rpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError:
                pass
        if content is None:
            content_from_raw, _ = _read_raw_file(collection_name, doc_id)
            content = content_from_raw

        if content is None:
            continue
        file_lines = content.splitlines()
        ls, le = entry["line_start"], entry["line_end"]
        definition = "\n".join(file_lines[ls - 1:le])

        methods_summary = ""
        if entry.get("methods"):
            methods_summary = "\n".join(f"  {s}" for s in entry["methods"])

        results.append({
            "filename": entry["filename"],
            "source": entry["source"],
            "doc_id": doc_id,
            "symbol_type": entry["type"],
            "qualified_name": entry["qualified"],
            "line_start": entry["line_start"],
            "line_end": entry["line_end"],
            "definition": definition,
            "methods_summary": methods_summary,
        })

    if len(results) < max_results:
        pattern = re.compile(r"\b" + re.escape(symbol) + r"\b")
        docs = _load_all_raw_texts_cached().get(collection_name, {})

        for doc_id, info in docs.items():
            source = info.get("source", "")
            if source.lower().endswith(".py"):
                continue
            file_lines = info.get("content", "").splitlines()
            for i, line in enumerate(file_lines):
                if pattern.search(line):
                    ctx_start = max(0, i - 3)
                    ctx_end = min(len(file_lines), i + 20)
                    results.append({
                        "filename": info.get("filename", f"{doc_id}.txt"),
                        "source": source,
                        "doc_id": doc_id,
                        "symbol_type": "unknown",
                        "qualified_name": symbol,
                        "line_start": i + 1,
                        "line_end": ctx_end,
                        "definition": "\n".join(file_lines[ctx_start:ctx_end]),
                        "methods_summary": "",
                    })
                    break
            if len(results) >= max_results:
                break

    return results


def _find_definition_full_scan(symbol, collection_name, raw_dir, max_results):
    """全量 AST 扫描查找定义（回退路径，兼容无索引的旧数据）。"""
    doc_id_to_info = _get_doc_id_map(collection_name)
    all_files = os.listdir(raw_dir)
    py_files = [f for f in all_files if f.lower().endswith(".py")]
    other_files = [f for f in all_files if not f.lower().endswith(".py")]

    results = []

    def _scan_py(fname):
        doc_id = os.path.splitext(fname)[0]
        info = doc_id_to_info.get(doc_id, {})
        fpath = os.path.join(raw_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            return
        try:
            with _warnings.catch_warnings():
                _warnings.simplefilter("ignore", SyntaxWarning)
                tree = _ast.parse(content)
        except SyntaxError:
            return

        file_lines = content.splitlines()

        def _search_nodes(node, parent_chain=""):
            for child in _ast.iter_child_nodes(node):
                if isinstance(child, (_ast.ClassDef, _ast.FunctionDef, _ast.AsyncFunctionDef)):
                    name = child.name
                    qualified = f"{parent_chain}.{name}" if parent_chain else name
                    if name == symbol or qualified == symbol or qualified.endswith(f".{symbol}"):
                        start = child.lineno
                        end = child.end_lineno if hasattr(child, "end_lineno") and child.end_lineno else start
                        definition_lines = file_lines[start - 1:end]
                        sym_type = "class" if isinstance(child, _ast.ClassDef) else "function"

                        methods_summary = ""
                        if isinstance(child, _ast.ClassDef):
                            from nbrag.chunker import _extract_signature

                            method_sigs = []
                            for sub in _ast.iter_child_nodes(child):
                                if isinstance(sub, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                                    method_sigs.append(_extract_signature(sub))
                            if method_sigs:
                                methods_summary = "\n".join(f"  {s}" for s in method_sigs)

                        results.append({
                            "filename": info.get("filename", fname),
                            "source": info.get("source", fpath),
                            "doc_id": doc_id,
                            "symbol_type": sym_type,
                            "qualified_name": qualified,
                            "line_start": start,
                            "line_end": end,
                            "definition": "\n".join(definition_lines),
                            "methods_summary": methods_summary,
                        })
                    _search_nodes(child, qualified)

        _search_nodes(tree)

    for fname in py_files:
        _scan_py(fname)
        if len(results) >= max_results:
            break

    if len(results) < max_results:
        pattern = re.compile(r"\b" + re.escape(symbol) + r"\b")
        docs = _load_all_raw_texts_cached().get(collection_name, {})
        for doc_id, info in docs.items():
            source = info.get("source", "")
            if source.lower().endswith(".py"):
                continue
            file_lines = info.get("content", "").splitlines()
            for i, line in enumerate(file_lines):
                if pattern.search(line):
                    ctx_start = max(0, i - 3)
                    ctx_end = min(len(file_lines), i + 20)
                    results.append({
                        "filename": info.get("filename", f"{doc_id}.txt"),
                        "source": source,
                        "doc_id": doc_id,
                        "symbol_type": "unknown",
                        "qualified_name": symbol,
                        "line_start": i + 1,
                        "line_end": ctx_end,
                        "definition": "\n".join(file_lines[ctx_start:ctx_end]),
                        "methods_summary": "",
                    })
                    break
            if len(results) >= max_results:
                break

    return results


def _list_documents_uncached(collection_name="default"):
    """列出知识库中已导入的完整文档列表，不做分页。"""
    col = _get_existing_collection(collection_name)
    if col is None:
        return {}
    total = col.count()
    if total == 0:
        return {}

    all_data = _batch_get(col, include=["metadatas"])
    docs = {}
    for meta in all_data["metadatas"]:
        if meta is None:
            continue
        did = meta.get("doc_id", "unknown")
        if did not in docs:
            docs[did] = {
                "filename": meta.get("filename", "?"),
                "source": meta.get("source", "?"),
                "total_chunks": meta.get("total_chunks", 0),
                "chunk_count": 0,
            }
        docs[did]["chunk_count"] += 1

    return dict(sorted(docs.items(), key=lambda x: x[0]))


def _list_documents_cached(collection_name="default"):
    """缓存去重后的文档列表，避免反复从 Chroma 全量拉取 chunk metadata。"""
    now = _time.time()
    cached = state._document_list_cache.get(collection_name)
    cached_ts = state._document_list_cache_ts.get(collection_name, 0.0)
    if cached is not None and now - cached_ts < _DOCUMENT_LIST_CACHE_TTL_SECONDS:
        return cached

    docs = _list_documents_uncached(collection_name)
    state._document_list_cache[collection_name] = docs
    state._document_list_cache_ts[collection_name] = now
    return docs


@_runtime_guarded
def list_documents(collection_name="default", offset=0, limit=None):
    """列出知识库中已导入的文档。支持 offset/limit 分页。"""
    docs = _list_documents_cached(collection_name)
    if not docs:
        return {}

    sorted_items = list(docs.items())
    if offset:
        sorted_items = sorted_items[offset:]
    if limit is not None:
        sorted_items = sorted_items[:limit]
    return dict(sorted_items)


@_runtime_guarded
def find_files(pattern, collection_name="default", max_results=20, case_sensitive=False):
    """按文件名或完整路径查找文档，返回可用于 file_path 入参的绝对路径。"""
    docs = list_documents(collection_name)
    if not docs or not pattern:
        return []

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        regex = re.compile(pattern, flags)
    except re.error:
        regex = re.compile(re.escape(pattern), flags)

    query = pattern if case_sensitive else pattern.lower()
    results = []
    for doc_id, info in docs.items():
        filename = info.get("filename", "?")
        source = info.get("source", "?")
        filename_cmp = filename if case_sensitive else filename.lower()
        source_cmp = source if case_sensitive else source.lower()

        filename_match = regex.search(filename) is not None
        source_match = regex.search(source) is not None
        if not filename_match and not source_match:
            continue

        if filename_cmp == query:
            rank = 0
        elif filename_cmp.endswith(query):
            rank = 1
        elif query in filename_cmp:
            rank = 2
        elif query in source_cmp:
            rank = 3
        else:
            rank = 4

        results.append({
            "doc_id": doc_id,
            "filename": filename,
            "file_path": source,
            "source": source,
            "chunk_count": info.get("chunk_count", 0),
            "total_chunks": info.get("total_chunks", info.get("chunk_count", 0)),
            "match": "filename" if filename_match else "file_path",
            "_rank": rank,
        })

    results.sort(key=lambda r: (r["_rank"], r["filename"].lower(), r["file_path"].lower()))
    limited = results[:max(1, max_results)]
    for item in limited:
        item.pop("_rank", None)
    return limited


@_runtime_guarded
def delete_document(doc_id, collection_name="default"):
    """删除指定文档的所有向量数据及缓存文件。返回 (deleted_count, filename)。"""
    col = _get_existing_collection(collection_name)
    if col is None:
        return 0, "?"

    try:
        doc_data = col.get(where={"doc_id": doc_id}, include=["metadatas"])
    except Exception:
        doc_data = {"ids": [], "metadatas": []}

    if not doc_data["ids"]:
        return 0, "?"

    filename = doc_data["metadatas"][0].get("filename", "?") if doc_data["metadatas"] else "?"
    col.delete(ids=doc_data["ids"])
    _delete_raw_file(collection_name, doc_id)
    state._document_list_cache.pop(collection_name, None)
    state._document_list_cache_ts.pop(collection_name, None)
    state._stats_cache = None
    state._stats_cache_ts = 0.0
    state._raw_text_cache = None
    state._raw_text_cache_ts = 0.0
    invalidate_bm25_cache(collection_name)
    invalidate_symbol_cache(collection_name)
    return len(doc_data["ids"]), filename


@_runtime_guarded
def get_stats():
    """返回所有知识库的统计信息。"""
    now = _time.time()
    if state._stats_cache is not None and now - state._stats_cache_ts < _STATS_CACHE_TTL_SECONDS:
        return state._stats_cache

    cfg = _cfg()
    collections = list_collections()
    profiles = list_collection_profiles()
    stats = {
        "embedding_model": cfg.embedding.model,
        "rerank_model": cfg.rerank.model or "not configured",
        "data_dir": cfg.storage.db_path,
        "collection_count": len(collections),
        "collections": {},
    }

    chroma = _get_chroma()
    for col_obj in collections:
        name = col_obj.name
        try:
            col = chroma.get_collection(name)
            count = col.count()
            if count > 0:
                all_meta = _batch_get(col, include=["metadatas"])
                doc_ids = set(m.get("doc_id", "") for m in all_meta["metadatas"] if m is not None)
                stats["collections"][name] = {
                    "doc_count": len(doc_ids),
                    "chunk_count": count,
                }
            else:
                stats["collections"][name] = {"doc_count": 0, "chunk_count": 0}
            profile = profiles.get(name)
            if profile:
                for key in ("display_name", "description", "aliases", "tags"):
                    value = profile.get(key)
                    if value:
                        stats["collections"][name][key] = value
        except Exception as e:
            stats["collections"][name] = {"error": str(e)}

    state._stats_cache = stats
    state._stats_cache_ts = now
    return stats
