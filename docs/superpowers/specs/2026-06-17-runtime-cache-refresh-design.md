# Runtime Cache Refresh Design

## Goal

Prevent long-running HTTP MCP processes from holding stale Chroma/BM25/doc-id/symbol runtime caches after a rare external ingest rebuilds a prepared collection in `rag_db`.

## Context

`nbrag` supports manual ingest scripts that write to the same embedded storage used by the streamable-http MCP server. If the MCP process has already opened a Chroma collection, and another process later deletes/rebuilds that collection, the MCP process can keep an old HNSW segment reader in memory. A later `nbrag_search` or `nbrag_search_and_fetch` may then fail with errors such as `Error creating hnsw segment reader: Nothing found on disk`.

Raw-file tools such as `nbrag_grep` can still work because they read `raw_files/<collection>` directly and do not depend on Chroma's vector reader.

## Requirements

- Refresh runtime caches every 300 seconds at most.
- Do not run a background refresh thread.
- Refresh lazily at tool/core operation entry so the cache is cleared before work starts, not in the middle of a request.
- Protect Chroma client and in-memory caches with a process-local lock.
- Keep the refresh lightweight: clear only memory objects, not on-disk indexes or raw files.
- Do not change ingest behavior or expose ingest as an MCP tool.
- Preserve existing explicit invalidation behavior used by ingest/delete code paths.

## Architecture

Add a runtime cache guard in `nbrag/core.py`:

- `_runtime_cache_lock`: a `threading.RLock` used by public read/write operations that touch shared runtime state.
- `_last_runtime_cache_refresh_ts`: monotonic timestamp for the last periodic refresh.
- `_RUNTIME_CACHE_REFRESH_INTERVAL`: 300 seconds.
- `_refresh_runtime_caches_if_due_locked()`: assumes the caller holds the lock; if the interval has elapsed, sets `_chroma_client = None` and clears `_doc_id_cache`, `_doc_id_cache_ts`, `_bm25_cache`, and `_symbol_cache`.
- `_with_runtime_cache_refresh(fn, *args, **kwargs)`: small helper for public functions that should run under the lock after the due-refresh check.

The refresh must not call `invalidate_bm25_cache()` or `invalidate_symbol_cache()` because those functions delete persisted index directories. Periodic refresh is memory-only.

## Entry Points

Wrap the main core entry points used by MCP tools:

- `search`
- `get_file_chunks`
- `get_context_chunks`
- `grep_knowledge`
- `find_symbol_definition`
- `list_documents`
- `find_files`
- `get_stats`
- `delete_collection`
- `delete_document`
- `check_file_cache`
- `get_collection`
- `list_collections`

Internal helpers may continue assuming the caller has already entered the runtime guard.

## Trade-Offs

This is not strong cross-process consistency. If a query overlaps an external ingest rebuild, a transient Chroma error is still possible. The goal is to greatly reduce stale-reader failures in the common case where ingest is rare and a small delay is acceptable.

Locking whole public operations is conservative. It may serialize concurrent MCP requests, but local embedded Chroma/BM25 access is not the bottleneck for typical usage, and correctness matters more than marginal concurrency here.

## Testing

Tests should prove:

- Periodic refresh clears only in-memory caches and sets `_chroma_client` to `None`.
- Refresh does not delete BM25 or symbol index directories.
- The refresh is skipped before 300 seconds.
- Public operations acquire the same runtime lock and run the refresh check before touching Chroma/cache state.
- Existing path-filter tests and server contract tests still pass.
