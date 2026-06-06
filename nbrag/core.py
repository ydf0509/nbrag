"""
RAG 核心逻辑 —— 供 MCP 服务和独立脚本共同复用。

功能:
  - Embedding / Rerank API 调用（默认 SiliconFlow，可配置任何 OpenAI 兼容 API）
  - ChromaDB 向量存储（CRUD + 搜索）
  - 文件导入（切分 + enrichment + 存储）

分块增强逻辑（切分、行号、AST scope、头部注入）在 chunker.py 中。
配置从环境变量 / YAML 文件 / CLI 参数加载（见 config.py）。
"""

import os
import hashlib


import httpx
import chromadb
from nbrag.config import get_config
from nbrag.chunker import (
    chunk_text, enrich_chunks, collect_files,
    DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP,
)


def _cfg():
    return get_config()


# ─── 延迟初始化的全局对象 ──────────────────────────────────

_chroma_client = None
_data_dir_initialized = False


def _ensure_dirs():
    global _data_dir_initialized
    if _data_dir_initialized:
        return
    cfg = _cfg()
    os.makedirs(cfg.storage.db_path, exist_ok=True)
    os.makedirs(cfg.storage.raw_files_path, exist_ok=True)
    _data_dir_initialized = True


def _get_chroma():
    global _chroma_client
    if _chroma_client is None:
        _ensure_dirs()
        _chroma_client = chromadb.PersistentClient(path=_cfg().storage.db_path)
    return _chroma_client


EMBEDDING_BATCH_SIZE = 32
CHROMA_UPSERT_BATCH = 5000

_doc_id_cache = {}
_doc_id_cache_ts = {}


def _get_doc_id_map(collection_name):
    """获取 collection 的 doc_id → {filename, source} 映射（带 60s 内存缓存）。"""
    import time as _time
    now = _time.time()
    if (collection_name in _doc_id_cache
            and now - _doc_id_cache_ts.get(collection_name, 0) < 60):
        return _doc_id_cache[collection_name]

    col = _get_existing_collection(collection_name)
    if col is None:
        return {}
    all_meta = col.get(include=["metadatas"])
    mapping = {}
    for meta in all_meta["metadatas"]:
        did = meta.get("doc_id", "")
        if did and did not in mapping:
            mapping[did] = {
                "filename": meta.get("filename", "?"),
                "source": meta.get("source", "?"),
            }
    _doc_id_cache[collection_name] = mapping
    _doc_id_cache_ts[collection_name] = now
    return mapping


def invalidate_doc_id_cache(collection_name=None):
    """清除 doc_id 映射缓存（导入/删除 collection 后调用）。"""
    if collection_name:
        _doc_id_cache.pop(collection_name, None)
        _doc_id_cache_ts.pop(collection_name, None)
    else:
        _doc_id_cache.clear()
        _doc_id_cache_ts.clear()


def _normalize_path(path):
    """统一路径格式（跨平台兼容）。"""
    p = os.path.abspath(path).replace("\\", "/")
    if len(p) >= 2 and p[1] == ':':
        p = p[0].upper() + p[1:]
    return p


# ─── 底层工具函数 ─────────────────────────────────────────

def get_collection(name="default"):
    """获取或创建一个 ChromaDB collection（写操作用）。"""
    return _get_chroma().get_or_create_collection(
        name=name, metadata={"hnsw:space": "cosine"},
    )


def _get_existing_collection(name):
    """获取已存在的 collection，不存在时返回 None（只读操作用，避免自动创建空 collection）。"""
    try:
        return _get_chroma().get_collection(name=name)
    except (ValueError, Exception):
        return None


def delete_collection(name):
    """删除整个 collection（清空该知识库）。"""
    _get_chroma().delete_collection(name)
    invalidate_doc_id_cache(name)


def list_collections():
    """列出所有 collection。"""
    return _get_chroma().list_collections()


_http_client = None

def _get_http_client():
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.Client(timeout=120)
    return _http_client


def embed(texts, max_retries=3):
    """调用 Embedding API，自动分批，失败自动重试。"""
    cfg = _cfg()
    api_key = cfg.embedding.api_key
    if not api_key:
        raise ValueError(
            "NBRAG_API_KEY is empty. Set the environment variable or configure in nbrag_config.yaml"
        )
    import time as _time
    client = _get_http_client()
    all_embeddings = []
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i:i + EMBEDDING_BATCH_SIZE]
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
            except Exception:
                if attempt < max_retries - 1:
                    _time.sleep(2 ** attempt)
                else:
                    raise
    return all_embeddings


def rerank(query, documents, top_n=5, max_retries=3):
    """调用 Rerank API，返回重排后的索引列表，失败自动重试。"""
    import time as _time
    cfg = _cfg()
    if not cfg.embedding.api_key or not cfg.rerank.model:
        return list(range(min(top_n, len(documents))))

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
            return [r["index"] for r in data["results"]]
        except Exception:
            if attempt < max_retries - 1:
                _time.sleep(2 ** attempt)
            else:
                raise


# ─── 原始文件缓存 ─────────────────────────────────────────

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


# ─── 高级操作 ─────────────────────────────────────────────

def _prepare_file(file_path, chunk_size=DEFAULT_CHUNK_SIZE,
                  chunk_overlap=DEFAULT_CHUNK_OVERLAP):
    """阶段 1：读取 + 切分 + Embedding（无 DB 操作，可并行）。"""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception as e:
        return {"ok": False, "error": f"Cannot read {file_path}: {e}"}

    if not text.strip():
        return {"ok": False, "skipped": True, "reason": f"Empty file: {os.path.basename(file_path)}"}

    file_ext = os.path.splitext(file_path)[1]
    abs_path = _normalize_path(file_path)
    raw_chunks = chunk_text(text, chunk_size, chunk_overlap, file_ext=file_ext)
    if not raw_chunks:
        return {"ok": False, "skipped": True, "reason": f"No chunks after split: {os.path.basename(file_path)}"}

    enriched_chunks, line_ranges, scopes = enrich_chunks(
        raw_chunks, text, file_path=abs_path, file_ext=file_ext,
    )

    embeddings = embed(enriched_chunks)

    filename = os.path.basename(file_path)
    doc_id = hashlib.md5(abs_path.encode()).hexdigest()[:12]

    return {
        "ok": True, "filename": filename, "file_ext": file_ext,
        "text": text, "abs_path": abs_path, "doc_id": doc_id,
        "enriched_chunks": enriched_chunks, "embeddings": embeddings,
        "line_ranges": line_ranges, "scopes": scopes,
        "chars": len(text), "chunks": len(enriched_chunks),
    }


def _write_to_db(prepared, collection_name="default"):
    """阶段 2：写入 ChromaDB + 缓存原文（必须串行）。"""
    if not prepared["ok"]:
        return prepared

    text = prepared["text"]
    abs_path = prepared["abs_path"]
    filename = prepared["filename"]
    doc_id = prepared["doc_id"]
    file_ext = prepared["file_ext"]
    enriched_chunks = prepared["enriched_chunks"]
    embeddings = prepared["embeddings"]
    line_ranges = prepared["line_ranges"]
    scopes = prepared["scopes"]

    _cache_raw_file(text, collection_name, doc_id, file_ext)

    col = get_collection(collection_name)

    try:
        old_data = col.get(where={"doc_id": doc_id}, include=[])
        if old_data["ids"]:
            col.delete(ids=old_data["ids"])
    except Exception:
        pass

    ids = [f"{doc_id}_c{i}" for i in range(len(enriched_chunks))]
    metadatas = [
        {
            "source": abs_path,
            "filename": filename,
            "doc_id": doc_id,
            "chunk_index": i,
            "total_chunks": len(enriched_chunks),
            "line_start": line_ranges[i][0],
            "line_end": line_ranges[i][1],
            "scope": scopes[i],
        }
        for i in range(len(enriched_chunks))
    ]

    for start in range(0, len(ids), CHROMA_UPSERT_BATCH):
        end = start + CHROMA_UPSERT_BATCH
        col.upsert(
            ids=ids[start:end],
            documents=enriched_chunks[start:end],
            embeddings=embeddings[start:end],
            metadatas=metadatas[start:end],
        )
    return {
        "ok": True, "filename": filename,
        "chars": prepared["chars"], "chunks": prepared["chunks"], "doc_id": doc_id,
    }


def ingest_file(file_path, collection_name="default",
                chunk_size=DEFAULT_CHUNK_SIZE,
                chunk_overlap=DEFAULT_CHUNK_OVERLAP):
    """导入单个文件到知识库，返回结果 dict（串行版本，兼容旧调用）。"""
    prepared = _prepare_file(file_path, chunk_size, chunk_overlap)
    if not prepared["ok"]:
        return prepared
    return _write_to_db(prepared, collection_name)


def ingest_path(path, collection_name="default",
                chunk_size=DEFAULT_CHUNK_SIZE,
                chunk_overlap=DEFAULT_CHUNK_OVERLAP,
                file_extensions=None):
    """导入文件或目录到知识库。返回 (results_list, errors_list, skipped_count)。"""
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return [], [f"Path not found: {path}"], 0

    files = collect_files(path, file_extensions=file_extensions)
    if not files:
        return [], [f"No text files found in: {path}"], 0

    results = []
    errors = []
    skipped = []
    for fp in files:
        try:
            r = ingest_file(fp, collection_name, chunk_size, chunk_overlap)
        except Exception as e:
            r = {"ok": False, "error": f"{os.path.basename(fp)}: {type(e).__name__}: {e}"}
        if r["ok"]:
            results.append(r)
        elif r.get("skipped"):
            skipped.append(r["reason"])
        else:
            errors.append(r["error"])

    return results, errors, len(skipped)


def batch_ingest(paths, collection_name="default",
                 chunk_size=DEFAULT_CHUNK_SIZE,
                 chunk_overlap=DEFAULT_CHUNK_OVERLAP,
                 file_extensions=None,
                 delete_first=False, on_progress=None,
                 verbose=False, max_workers=1,
                 sleep_interval=0.01,
                 ):
    """批量导入多个路径到知识库（一站式封装）。

    两阶段流水线设计：
      阶段 1（可并行）：读取文件 → 文本切分 → 调用 Embedding API 获取向量
      阶段 2（必须串行）：写入 ChromaDB + 缓存原始文件

    Embedding API 调用是 I/O 密集型（网络等待），是整个导入流程的主要瓶颈。
    通过 max_workers > 1 可以并行执行阶段 1，显著加速大批量导入。
    ChromaDB（SQLite 底层）不支持并发写，所以阶段 2 始终串行。

    Args:
        paths: 文件/目录路径列表（或单个字符串）。
        collection_name: 知识库名称，不存在时自动创建。
        chunk_size: 分块大小（字符数），默认 1500。
        chunk_overlap: 分块重叠（字符数），默认 200。
        file_extensions: 可选后缀过滤列表（如 [".py", ".md"]），None 表示全部文本文件。
        delete_first: 是否先清空旧数据再导入（适用于全量重建）。
        on_progress: 可选回调 fn(current, total, file_path, result)，用于自定义进度展示。
        verbose: 是否打印详细日志。
        max_workers: Embedding 并发线程数。
                     1 = 串行（默认，兼容旧行为）；
                     2-4 = 并行读取+Embedding，串行写入 ChromaDB。
                     不建议超过 4，避免触发 Embedding API 频率限制。
    """
    import time as _time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if isinstance(paths, str):
        paths = [paths]

    t0 = _time.time()

    if delete_first:
        deleted_col = False
        try:
            delete_collection(collection_name)
            deleted_col = True
        except Exception:
            pass
        try:
            _delete_raw_files_collection(collection_name)
        except Exception:
            pass
        if verbose:
            print(f"[rag] Deleted old collection: {collection_name}"
                  f" (collection={'ok' if deleted_col else 'not found'}, raw_files=cleaned)")

    all_files = []
    for p in paths:
        p = os.path.expanduser(p)
        if os.path.exists(p):
            found = collect_files(p, file_extensions=file_extensions)
            if verbose:
                ext_info = f" (filter: {file_extensions})" if file_extensions else ""
                print(f"[rag] {p} -> {len(found)} files{ext_info}")
            all_files.extend(found)

    if verbose:
        mode_str = f"parallel(workers={max_workers})" if max_workers > 1 else "sequential"
        print(f"[rag] Total {len(all_files)} files, mode: {mode_str}, starting Embedding...\n")

    results = []
    errors = []
    skipped = []
    total_chars = 0
    total_chunks = 0
    large_files = []

    for fp in all_files:
        file_size = os.path.getsize(fp)
        if file_size > 100 * 1024:
            large_files.append((fp, file_size))
            if verbose:
                print(f"  [large] {fp} ({file_size / 1024:.1f} KB)")

    if max_workers <= 1:
        prepared_list = []
        for i, fp in enumerate(all_files):
            _time.sleep(sleep_interval)
            try:
                p = _prepare_file(fp, chunk_size, chunk_overlap)
            except Exception as e:
                p = {"ok": False, "error": f"{os.path.basename(fp)}: {type(e).__name__}: {e}", "_fp": fp}
            p["_fp"] = fp
            p["_idx"] = i
            prepared_list.append(p)
            if verbose:
                name = os.path.basename(fp)
                if p["ok"]:
                    print(f"  [embed {i + 1:>4}/{len(all_files)}] {name} ({p['chunks']} chunks)")
                elif p.get("skipped"):
                    print(f"  [embed {i + 1:>4}/{len(all_files)}] - {name}  (skipped)")
    else:
        prepared_list = [None] * len(all_files)
        done_count = 0
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_idx = {}
            for i, fp in enumerate(all_files):
                _time.sleep(sleep_interval)
                fut = pool.submit(_prepare_file, fp, chunk_size, chunk_overlap)
                future_to_idx[fut] = (i, fp)

            for fut in as_completed(future_to_idx):
                i, fp = future_to_idx[fut]
                try:
                    p = fut.result()
                except Exception as e:
                    p = {"ok": False, "error": f"{os.path.basename(fp)}: {type(e).__name__}: {e}"}
                p["_fp"] = fp
                p["_idx"] = i
                prepared_list[i] = p
                done_count += 1
                if verbose:
                    name = os.path.basename(fp)
                    if p["ok"]:
                        print(f"  [embed {done_count:>4}/{len(all_files)}] {name} ({p['chunks']} chunks)")
                    elif p.get("skipped"):
                        print(f"  [embed {done_count:>4}/{len(all_files)}] - {name}  (skipped)")

    if verbose:
        embed_elapsed = _time.time() - t0
        print(f"\n[rag] Embedding done in {embed_elapsed:.1f}s, writing to ChromaDB...\n")

    for i, p in enumerate(prepared_list):
        fp = p.get("_fp", "?")
        try:
            r = _write_to_db(p, collection_name) if p["ok"] else p
        except Exception as e:
            r = {"ok": False, "error": f"{os.path.basename(fp)}: {type(e).__name__}: {e}"}

        if r["ok"]:
            results.append(r)
            total_chars += r["chars"]
            total_chunks += r["chunks"]
        elif r.get("skipped"):
            skipped.append(r.get("reason", ""))
        else:
            errors.append(r.get("error", "unknown error"))

        if on_progress:
            on_progress(i + 1, len(all_files), fp, r)
        elif verbose:
            idx = i + 1
            name = os.path.basename(fp)
            if r["ok"]:
                print(f"  [write {idx:>4}/{len(all_files)}] {name} ({r['chunks']} chunks)")
            elif not r.get("skipped"):
                print(f"  [write {idx:>4}/{len(all_files)}] X {name}  ({r.get('error', '')})")

    elapsed = _time.time() - t0
    stats = {
        "success": len(results), "failed": len(errors), "skipped": len(skipped),
        "total_chars": total_chars, "total_chunks": total_chunks,
        "file_count": len(all_files), "elapsed": elapsed,
        "results": results, "errors": errors, "skipped_reasons": skipped,
        "large_files": large_files,
    }

    if verbose:
        skip_str = f" {stats['skipped']} skipped" if skipped else ""
        print(f"\n[rag] Done! {stats['success']} ok {stats['failed']} failed{skip_str}"
              f" | {total_chunks} chunks {total_chars:,} chars | {elapsed:.0f}s")
        if large_files:
            print(f"\n[rag] Large files (>100KB) summary ({len(large_files)}):")
            large_files_sorted = sorted(large_files, key=lambda x: x[1], reverse=True)
            for fp, size in large_files_sorted:
                print(f"  {size / 1024:.1f} KB  {fp}")
            total_large_size = sum(s for _, s in large_files)
            print(f"  Total: {len(large_files)} files, {total_large_size / 1024 / 1024:.2f} MB")

    return stats


def search(query, collection_name="default", top_k=5, use_rerank=True,
           filter_filename=None):
    """语义搜索。返回 (documents, metadatas, distances, rerank_used, total)。"""
    col = _get_existing_collection(collection_name)
    if col is None:
        return [], [], [], False, 0
    total = col.count()

    if total == 0:
        return [], [], [], False, 0

    query_vec = embed([query])[0]
    retrieve_k = min(top_k * 4, total) if use_rerank else min(top_k, total)

    where_filter = None
    if filter_filename:
        where_filter = {"filename": filter_filename}

    results = col.query(
        query_embeddings=[query_vec],
        n_results=retrieve_k,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    cfg = _cfg()
    rerank_used = False
    if use_rerank and cfg.rerank.model and len(documents) > top_k:
        try:
            reranked_idx = rerank(query, documents, top_n=top_k)
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

    return documents, metadatas, distances, rerank_used, total


def get_file_chunks(file_identifier, collection_name="default",
                    start_chunk=0, max_chunks=5,
                    raw=False, line_start=-1, line_end=-1):
    """按文件路径或文件名获取知识库中该文件的内容。"""
    col = _get_existing_collection(collection_name)
    if col is None:
        return {"found": False, "error": f"collection '{collection_name}' does not exist"}
    total = col.count()
    if total == 0:
        return {"found": False, "error": f"collection '{collection_name}' is empty"}

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


def _query_file_by_identifier(col, file_identifier):
    """按路径或文件名查找文件的 chunks。"""
    is_path = ('/' in file_identifier or '\\' in file_identifier)
    empty = {"ids": [], "documents": [], "metadatas": []}

    if is_path:
        normalized = _normalize_path(file_identifier)
        try:
            result = col.get(where={"source": normalized}, include=["documents", "metadatas"])
            if result["ids"]:
                return result
        except Exception:
            pass
        basename = os.path.basename(file_identifier)
        try:
            return col.get(where={"filename": basename}, include=["documents", "metadatas"])
        except Exception:
            return empty

    try:
        return col.get(where={"filename": file_identifier}, include=["documents", "metadatas"])
    except Exception:
        return empty


def _get_raw_file_result(collection_name, doc_id, source, filename,
                         total_chunks, total_lines, line_start, line_end):
    """从缓存读取原始文件，支持按行截取。"""
    content, cached_path = _read_raw_file(collection_name, doc_id)
    if content is None:
        return {
            "found": False,
            "error": f"Raw file cache not found (doc_id={doc_id}). "
                     f"This file may have been imported before caching was enabled. Please re-import.",
        }

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
            if cl_start < line_end and cl_end > line_start:
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


def grep_knowledge(keyword, collection_name="default", max_results=10,
                    case_sensitive=False, filter_filename=None, context_lines=5):
    """在知识库的原始缓存文件中进行关键词/正则搜索。"""
    import re

    raw_dir = os.path.join(_raw_files_dir(), collection_name)
    if not os.path.isdir(raw_dir):
        return []

    doc_id_to_info = _get_doc_id_map(collection_name)

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pattern = re.compile(keyword, flags)
    except re.error:
        pattern = re.compile(re.escape(keyword), flags)

    results = []
    for fname in os.listdir(raw_dir):
        doc_id = os.path.splitext(fname)[0]
        info = doc_id_to_info.get(doc_id, {})

        if filter_filename and info.get("filename", "") != filter_filename:
            continue

        fpath = os.path.join(raw_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                file_lines = f.readlines()
        except OSError:
            continue

        for i, line in enumerate(file_lines):
            if pattern.search(line):
                ctx_start = max(0, i - context_lines)
                ctx_end = min(len(file_lines), i + context_lines + 1)
                ctx_parts = []
                for j in range(ctx_start, ctx_end):
                    prefix = ">>>" if j == i else "   "
                    ctx_parts.append(f"{prefix} {j + 1:>5}| {file_lines[j].rstrip()}")

                results.append({
                    "filename": info.get("filename", fname),
                    "source": info.get("source", fpath),
                    "doc_id": doc_id,
                    "line_number": i + 1,
                    "line_content": line.rstrip(),
                    "context": "\n".join(ctx_parts),
                })

                if len(results) >= max_results:
                    return results

    return results


def find_symbol_definition(symbol, collection_name="default", max_results=5):
    """在知识库中查找符号（类/函数/方法）的完整定义。"""
    import re
    import ast as _ast
    import warnings as _warnings

    raw_dir = os.path.join(_raw_files_dir(), collection_name)
    if not os.path.isdir(raw_dir):
        return []

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
                        end = child.end_lineno if hasattr(child, 'end_lineno') and child.end_lineno else start
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
        pattern = re.compile(r'\b' + re.escape(symbol) + r'\b')
        for fname in other_files:
            doc_id = os.path.splitext(fname)[0]
            info = doc_id_to_info.get(doc_id, {})
            fpath = os.path.join(raw_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError:
                continue
            file_lines = content.splitlines()
            for i, line in enumerate(file_lines):
                if pattern.search(line):
                    ctx_start = max(0, i - 3)
                    ctx_end = min(len(file_lines), i + 20)
                    results.append({
                        "filename": info.get("filename", fname),
                        "source": info.get("source", fpath),
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


def list_documents(collection_name="default"):
    """列出知识库中已导入的文档。"""
    col = _get_existing_collection(collection_name)
    if col is None:
        return {}
    total = col.count()
    if total == 0:
        return {}

    all_data = col.get(include=["metadatas"])
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
    return docs


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
    return len(doc_data["ids"]), filename


def get_stats():
    """返回所有知识库的统计信息。"""
    cfg = _cfg()
    collections = list_collections()
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
                all_meta = col.get(include=["metadatas"])
                doc_ids = set(m.get("doc_id", "") for m in all_meta["metadatas"] if m is not None)
                stats["collections"][name] = {
                    "doc_count": len(doc_ids), "chunk_count": count,
                }
            else:
                stats["collections"][name] = {"doc_count": 0, "chunk_count": 0}
        except Exception as e:
            stats["collections"][name] = {"error": str(e)}

    return stats
