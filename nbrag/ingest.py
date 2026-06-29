"""文件导入流水线。

负责读取文件、切分、embedding、写入 ChromaDB，并重建 BM25 / Symbol 索引。
"""

from __future__ import annotations

import hashlib
import os
import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed

from nbrag.bm25_index import build_bm25_index
from nbrag.chunker import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    chunk_text,
    collect_files,
    enrich_chunks,
)
from nbrag.collection_profiles import set_collection_profile
from nbrag.embeddings import embed
from nbrag.storage import (
    _batch_get,
    _cache_raw_file,
    _delete_raw_files_collection,
    _normalize_path,
    _raw_file_path,
    get_collection,
    delete_collection,
)
from nbrag.runtime import _runtime_guarded
from nbrag.symbol_index import build_symbol_index


CHROMA_UPSERT_BATCH = 5000


def prepare_file_no_embed(file_path, chunk_size=DEFAULT_CHUNK_SIZE,
                          chunk_overlap=DEFAULT_CHUNK_OVERLAP):
    """阶段 1a：读取 + 切分 + Enrichment（无 Embedding，无 DB 操作，可并行）。"""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception as e:
        return {"ok": False, "error": f"Cannot read {file_path}: {e}"}

    if not text.strip():
        return {"ok": False, "skipped": True, "reason": f"Empty file: {os.path.basename(file_path)}"}

    file_ext = os.path.splitext(file_path)[1]
    abs_path = _normalize_path(file_path)
    file_mtime = os.path.getmtime(file_path)
    raw_chunks = chunk_text(text, chunk_size, chunk_overlap, file_ext=file_ext)
    if not raw_chunks:
        return {"ok": False, "skipped": True, "reason": f"No chunks after split: {os.path.basename(file_path)}"}

    enriched_chunks, line_ranges, scopes = enrich_chunks(
        raw_chunks, text, file_path=abs_path, file_ext=file_ext,
    )

    filename = os.path.basename(file_path)
    doc_id = hashlib.md5(abs_path.encode()).hexdigest()[:12]

    return {
        "ok": True, "filename": filename, "file_ext": file_ext,
        "text": text, "abs_path": abs_path, "doc_id": doc_id,
        "enriched_chunks": enriched_chunks,
        "line_ranges": line_ranges, "scopes": scopes,
        "chars": len(text), "chunks": len(enriched_chunks),
        "file_mtime": file_mtime,
    }


def batch_embed_prepared(prepared_list, sleep_interval=0.0, verbose=False):
    """阶段 1b：批量调用 Embedding API，跨文件合并 chunks 减少 API 调用。"""
    all_chunks = []
    chunk_refs = []

    for file_idx, p in enumerate(prepared_list):
        if not p.get("ok"):
            continue
        for chunk_idx, chunk in enumerate(p["enriched_chunks"]):
            all_chunks.append(chunk)
            chunk_refs.append((file_idx, chunk_idx))

    if not all_chunks:
        return prepared_list

    all_embeddings = embed(all_chunks, sleep_interval=sleep_interval, verbose=verbose)

    for ref_idx, (file_idx, chunk_idx) in enumerate(chunk_refs):
        p = prepared_list[file_idx]
        if "embeddings" not in p:
            p["embeddings"] = [None] * len(p["enriched_chunks"])
        p["embeddings"][chunk_idx] = all_embeddings[ref_idx]

    return prepared_list


def _prepare_file(file_path, chunk_size=DEFAULT_CHUNK_SIZE,
                  chunk_overlap=DEFAULT_CHUNK_OVERLAP,
                  sleep_interval=0.0):
    """阶段 1：读取 + 切分 + Embedding（无 DB 操作，可并行）。"""
    prepared = prepare_file_no_embed(file_path, chunk_size, chunk_overlap)
    if not prepared["ok"]:
        return prepared
    prepared["embeddings"] = embed(prepared["enriched_chunks"], sleep_interval=sleep_interval)
    return prepared


@_runtime_guarded
def check_file_cache(file_path, collection_name="default"):
    """检查文件是否已缓存且未修改。"""
    abs_path = _normalize_path(file_path)
    doc_id = hashlib.md5(abs_path.encode()).hexdigest()[:12]
    try:
        file_mtime = os.path.getmtime(file_path)
    except Exception:
        return False, None

    try:
        col = get_collection(collection_name)
        result = col.get(
            where={"doc_id": doc_id},
            include=["metadatas"],
        )
        if result and result["metadatas"]:
            stored_mtime = result["metadatas"][0].get("file_mtime")
            if stored_mtime is not None and abs(stored_mtime - file_mtime) < 1e-6:
                file_ext = os.path.splitext(file_path)[1]
                raw_path = _raw_file_path(collection_name, doc_id, file_ext)
                if os.path.exists(raw_path):
                    return True, doc_id
    except Exception:
        pass
    return False, doc_id


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
    file_mtime = prepared.get("file_mtime")

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
            "file_mtime": file_mtime,
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


def _batch_write_to_db(prepared_list, collection_name,
                       results, errors, skipped,
                       on_progress, verbose, total_file_count):
    """批量写入 ChromaDB（delete_first=True 专用，跳过逐文件查旧/删旧）。"""
    col = get_collection(collection_name)
    all_ids = []
    all_documents = []
    all_embeddings = []
    all_metadatas = []

    for i, p in enumerate(prepared_list):
        fp = p.get("_fp", "?")
        if not p.get("ok"):
            if p.get("skipped"):
                skipped.append(p.get("reason", ""))
            elif p.get("error"):
                errors.append(p.get("error", "unknown error"))
            continue

        try:
            _cache_raw_file(p["text"], collection_name, p["doc_id"], p["file_ext"])
        except Exception as e:
            errors.append(f"{p['filename']}: cache_raw_file failed: {e}")
            continue

        doc_id = p["doc_id"]
        enriched_chunks = p["enriched_chunks"]
        embeddings = p["embeddings"]
        line_ranges = p["line_ranges"]
        scopes = p["scopes"]
        file_mtime = p.get("file_mtime")

        for ci in range(len(enriched_chunks)):
            all_ids.append(f"{doc_id}_c{ci}")
            all_documents.append(enriched_chunks[ci])
            all_embeddings.append(embeddings[ci])
            all_metadatas.append({
                "source": p["abs_path"],
                "filename": p["filename"],
                "doc_id": doc_id,
                "chunk_index": ci,
                "total_chunks": len(enriched_chunks),
                "line_start": line_ranges[ci][0],
                "line_end": line_ranges[ci][1],
                "scope": scopes[ci],
                "file_mtime": file_mtime,
            })

        r = {"ok": True, "filename": p["filename"],
             "chars": p["chars"], "chunks": p["chunks"], "doc_id": doc_id}
        results.append(r)

        if on_progress:
            on_progress(i + 1, total_file_count, fp, r)
        elif verbose:
            print(f"  [prepare-write {i + 1:>4}/{len(prepared_list)}] {p['filename']} ({p['chunks']} chunks)")

    if not all_ids:
        return

    if verbose:
        print(f"\n[rag] Batch upsert {len(all_ids)} chunks to ChromaDB...")

    for start in range(0, len(all_ids), CHROMA_UPSERT_BATCH):
        end = start + CHROMA_UPSERT_BATCH
        col.upsert(
            ids=all_ids[start:end],
            documents=all_documents[start:end],
            embeddings=all_embeddings[start:end],
            metadatas=all_metadatas[start:end],
        )
        if verbose:
            print(f"  [batch-upsert] {min(end, len(all_ids))}/{len(all_ids)} chunks written")


def ingest_file(file_path, collection_name="default",
                chunk_size=DEFAULT_CHUNK_SIZE,
                chunk_overlap=DEFAULT_CHUNK_OVERLAP,
                sleep_interval=0.0,
                use_cache=True,
                verbose=False):
    """导入单个文件到知识库，返回结果 dict（串行版本）。"""
    from nbrag import state

    if use_cache:
        is_cached, _ = check_file_cache(file_path, collection_name)
        if is_cached:
            abs_path = _normalize_path(file_path)
            doc_id = hashlib.md5(abs_path.encode()).hexdigest()[:12]
            if verbose:
                name = os.path.basename(file_path)
                print(f"  [cache] {name} (skipped, unchanged)")
            return {
                "ok": True,
                "filename": os.path.basename(file_path),
                "chars": 0,
                "chunks": 0,
                "doc_id": doc_id,
                "_cached": True,
            }
    prepared = _prepare_file(file_path, chunk_size, chunk_overlap, sleep_interval=sleep_interval)
    if not prepared["ok"]:
        return prepared
    result = _write_to_db(prepared, collection_name)
    if result["ok"]:
        state._bm25_cache.pop(collection_name, None)
        state._symbol_cache.pop(collection_name, None)
        state._document_list_cache.pop(collection_name, None)
        state._document_list_cache_ts.pop(collection_name, None)
        state._stats_cache = None
        state._stats_cache_ts = 0.0
        state._raw_text_cache = None
        state._raw_text_cache_ts = 0.0
    return result


def ingest_path(path, collection_name="default",
                chunk_size=DEFAULT_CHUNK_SIZE,
                chunk_overlap=DEFAULT_CHUNK_OVERLAP,
                file_extensions=None,
                excluded_paths=None,
                sleep_interval=0.0,
                use_cache=True,
                verbose=False):
    """导入文件或目录到知识库。返回 (results_list, errors_list, skipped_count)。"""
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return [], [f"Path not found: {path}"], 0

    files = collect_files(path, file_extensions=file_extensions, excluded_paths=excluded_paths)
    if not files:
        return [], [f"No text files found in: {path}"], 0

    results = []
    errors = []
    skipped = []
    for fp in files:
        try:
            r = ingest_file(
                fp, collection_name, chunk_size, chunk_overlap,
                sleep_interval=sleep_interval, use_cache=use_cache, verbose=verbose,
            )
        except Exception as e:
            r = {"ok": False, "error": f"{os.path.basename(fp)}: {type(e).__name__}: {e}"}
        if r["ok"]:
            if not r.get("_cached"):
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
                 excluded_paths=None,
                 delete_first=False, on_progress=None,
                 verbose=False, max_workers=1,
                 sleep_interval=0.01,
                 use_cache=True):
    """批量导入多个路径到知识库（一站式封装）。

    excluded_paths 可显式排除文件或目录。
    另外，batch_ingest() 会对每个目录型 path 自动追加排除 path/.git，
    避免把 Git 元数据目录当作知识库内容扫描。
    """
    if isinstance(paths, str):
        paths = [paths]

    t0 = _time.time()

    effective_excluded_paths = []
    if excluded_paths:
        if isinstance(excluded_paths, str):
            effective_excluded_paths = [excluded_paths]
        else:
            effective_excluded_paths = list(excluded_paths)
    for p in paths:
        expanded = os.path.expanduser(p)
        if os.path.isdir(expanded):
            effective_excluded_paths.append(os.path.join(expanded, ".git"))

    if delete_first:
        deleted_col = False
        raw_files_deleted = False
        try:
            delete_collection(collection_name)
            deleted_col = True
        except Exception:
            pass
        try:
            _delete_raw_files_collection(collection_name)
            raw_files_deleted = True
        except Exception:
            pass
        if verbose:
            print(f"[rag] Deleted old collection: {collection_name}"
                  f" (collection={'ok' if deleted_col else 'not found'}, raw_files={'ok' if raw_files_deleted else 'not found'})")

    all_files = []
    for p in paths:
        p = os.path.expanduser(p)
        if os.path.exists(p):
            found = collect_files(p, file_extensions=file_extensions, excluded_paths=effective_excluded_paths)
            if verbose:
                ext_info = f" (filter: {file_extensions})" if file_extensions else ""
                exclude_info = f" excluded_paths: {len(effective_excluded_paths) if not isinstance(effective_excluded_paths, str) else 1}" if effective_excluded_paths else ""
                print(f"[rag] {p} -> {len(found)} files{ext_info}{exclude_info}")
            all_files.extend(found)

    files_to_process = []
    cached_count = 0
    if use_cache and not delete_first:
        for fp in all_files:
            is_cached, _ = check_file_cache(fp, collection_name)
            if is_cached:
                cached_count += 1
                if verbose:
                    name = os.path.basename(fp)
                    print(f"  [cache] {name} (skipped, unchanged)")
            else:
                files_to_process.append(fp)
    else:
        files_to_process = all_files

    if verbose:
        mode_str = f"parallel(workers={max_workers})" if max_workers > 1 else "sequential"
        cache_note = f", cache: {cached_count} skipped" if cached_count > 0 else ""
        print(f"[rag] Total {len(all_files)} files ({len(files_to_process)} to process{cache_note}), mode: {mode_str}, starting...\n")

    results = []
    errors = []
    skipped = []
    total_chars = 0
    total_chunks = 0
    large_files = []

    for fp in files_to_process:
        file_size = os.path.getsize(fp)
        if file_size > 100 * 1024:
            large_files.append((fp, file_size))
            if verbose:
                print(f"  [large] {fp} ({file_size / 1024:.1f} KB)")

    if max_workers <= 1:
        prepared_list = []
        for i, fp in enumerate(files_to_process):
            try:
                p = prepare_file_no_embed(fp, chunk_size, chunk_overlap)
            except Exception as e:
                p = {"ok": False, "error": f"{os.path.basename(fp)}: {type(e).__name__}: {e}", "_fp": fp}
            p["_fp"] = fp
            p["_idx"] = i
            prepared_list.append(p)
            if verbose:
                name = os.path.basename(fp)
                if p["ok"]:
                    print(f"  [prepare {i + 1:>4}/{len(files_to_process)}] {name} ({p['chunks']} chunks)")
                elif p.get("skipped"):
                    print(f"  [prepare {i + 1:>4}/{len(files_to_process)}] - {name}  (skipped)")
    else:
        prepared_list = [None] * len(files_to_process)
        done_count = 0
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_idx = {}
            for i, fp in enumerate(files_to_process):
                fut = pool.submit(prepare_file_no_embed, fp, chunk_size, chunk_overlap)
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
                        print(f"  [prepare {done_count:>4}/{len(files_to_process)}] {name} ({p['chunks']} chunks)")
                    elif p.get("skipped"):
                        print(f"  [prepare {done_count:>4}/{len(files_to_process)}] - {name}  (skipped)")

    if verbose and files_to_process:
        prepare_elapsed = _time.time() - t0
        total_chunks_to_embed = sum(p["chunks"] for p in prepared_list if p.get("ok"))
        print(f"\n[rag] Prepare done in {prepare_elapsed:.1f}s, batch embedding {total_chunks_to_embed} chunks...\n")

    if files_to_process:
        prepared_list = batch_embed_prepared(prepared_list, sleep_interval=sleep_interval, verbose=verbose)

        if verbose:
            embed_elapsed = _time.time() - t0
            print(f"\n[rag] Embedding done in {embed_elapsed:.1f}s, writing to ChromaDB...\n")

        if delete_first:
            _batch_write_to_db(
                prepared_list, collection_name,
                results, errors, skipped,
                on_progress, verbose, len(all_files),
            )
            total_chars = sum(r["chars"] for r in results)
            total_chunks = sum(r["chunks"] for r in results)
        else:
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
    elif verbose:
        print("\n[rag] No files to process (all cached).\n")

    if results:
        if verbose:
            print("\n[rag] Building BM25 index...")
        try:
            col = get_collection(collection_name)
            all_data = _batch_get(col, include=["documents"])
            build_bm25_index(collection_name, all_data["documents"], all_data["ids"])
            if verbose:
                print(f"[rag] BM25 index built ({len(all_data['ids'])} chunks)")
        except Exception as e:
            if verbose:
                print(f"[rag] BM25 index build failed (non-fatal): {e}")

    if results:
        if verbose:
            print("[rag] Building Symbol index...")
        try:
            sym_index = build_symbol_index(collection_name)
            if verbose:
                sym_count = sum(len(v) for v in (sym_index or {}).values())
                print(f"[rag] Symbol index built ({sym_count} symbols)")
        except Exception as e:
            if verbose:
                print(f"[rag] Symbol index build failed (non-fatal): {e}")

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

    if results:
        set_collection_profile(
            collection_name,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            last_ingested_at=_time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(_time.time())),
        )

    return stats
