# nbrag

[English](README.md) | [简体中文](README.zh-CN.md)

`nbrag` is a PyPI package for building a local text knowledge base and exposing it through an MCP server.

Use it when you want an MCP-compatible client to retrieve evidence from files you control, such as internal documentation, regulations, manuals, notes, local project docs, or Python source code.

## When to use nbrag

`nbrag` is a good fit when you want to:

- index **private or local text** that hosted services cannot see
- build a **domain-specific knowledge base** from your own files
- let an MCP client search both **vectorized chunks and stored original text**
- keep storage **on your own machine**

`nbrag` is text-first. If your source material starts as PDF, Word, images, scans, or web pages, convert it to `.md`, `.txt`, or `.html` before ingestion for the best results.

## Install

```bash
pip install nbrag
```

To confirm the package is available:

```bash
python -m nbrag --help
```

## Configure the API key

By default, `nbrag` uses SiliconFlow-compatible embedding and rerank endpoints. Set `NBRAG_API_KEY` before ingestion or serving.

Linux/macOS:

```bash
export NBRAG_API_KEY=sk-xxx
```

Windows PowerShell:

```powershell
$env:NBRAG_API_KEY = "sk-xxx"
```

## Quick start

The normal workflow is:

1. prepare a folder of text files
2. ingest it with `batch_ingest()`
3. describe the collection with `set_collection_profile()`
4. start the MCP server
5. connect your MCP client

### Minimal ingestion example

Create a script such as `ingest_my_docs.py`:

```python
from nbrag import batch_ingest, set_collection_profile

batch_ingest(
    paths=[
        "D:/docs/company_policies",
        "D:/docs/product_manuals",
    ],
    collection_name="company_knowledge",
    file_extensions=[".md", ".txt", ".html"],
    delete_first=True,
    verbose=True,
)

set_collection_profile(
    "company_knowledge",
    display_name="Company Knowledge Base",
    description="Internal policies and product manuals.",
    aliases=["company docs", "policies", "manuals"],
    tags=["internal", "policy", "manual"],
)
```

Run it with Python:

```bash
python ingest_my_docs.py
```

A few practical notes:

- `collection_name` is the stable machine-facing identifier （knowledge base name）
- `file_extensions` lets you limit which text files are ingested
- `delete_first=True` If you need to adjust parameters, you can fully rebuild this collection. However, if incremental import is supported, avoid deleting it beforehand.
- `verbose=True` is useful while you are learning or debugging your ingest flow

### Why `set_collection_profile()` matters

Chroma collection names should stay simple and slug-like, such as `company_knowledge`.

`set_collection_profile()` adds the human-facing metadata that helps both people and MCP routing understand what a collection contains:

- `display_name`
- `description`
- `aliases`
- `tags`

That metadata is stored separately from the vector-store internals and is used to make collection selection easier and clearer.

## Python source code uses the same ingestion flow

Python projects do not require a separate ingestion workflow. In practice, you usually only change:

- the folders you ingest
- the `file_extensions` list, for example `['.py', '.md', '.txt']`
- the collection description in `set_collection_profile()`

Example:

```python
from nbrag import batch_ingest, set_collection_profile

batch_ingest(
    paths=[
        "D:/projects/my_framework/src",
        "D:/projects/my_framework/docs",
    ],
    collection_name="my_framework",
    file_extensions=[".py", ".md", ".txt"],
    delete_first=True,
    verbose=True,
)

set_collection_profile(
    "my_framework",
    display_name="My Framework Source And Docs",
    description="Python source and documentation for my_framework.",
    aliases=["my_framework", "framework source", "framework docs"],
    tags=["python", "source", "docs"],
)
```

## Start the MCP server

### stdio mode

Use stdio when one client owns one server process.

```bash
python -m nbrag
```

### HTTP mode

Use HTTP mode when multiple clients or many IDE windows should share one local server process.

```bash
python -m nbrag --transport streamable-http --port 9101
```

## Configure MCP clients

### stdio configuration

Point the client at the Python environment where `nbrag` is installed.

Example:

```json
{
  "mcpServers": {
    "nbrag": {
      "command": "python",
      "args": ["-m", "nbrag"],
      "env": {
        "NBRAG_API_KEY": "sk-xxx"
      }
    }
  }
}
```

If your client does not use the same interpreter as your shell, replace `python` with the full interpreter path.

### HTTP configuration

First start the shared local server:

```bash
python -m nbrag --transport streamable-http --port 9101
```

Then point the client to:

```json
{
  "mcpServers": {
    "nbrag": {
      "url": "http://localhost:9101/mcp"
    }
  }
}
```

## MCP capabilities overview

After the server starts, `nbrag` exposes a set of retrieval-oriented MCP tools. For human readers, the easiest way to think about them is by capability:

| Capability | Representative tools | What it covers |
|---|---|---|
| Search | `nbrag_search`, `nbrag_search_and_fetch` | semantic and hybrid retrieval over ingested collections |
| Search inspection | `nbrag_search_only_bm25`, `nbrag_search_only_vector` | inspecting lexical-only or vector-only behavior |
| Exact text lookup | `nbrag_grep` | line-by-line matching over stored original text |
| Original text reading | `nbrag_get_raw_file`, `nbrag_get_file_chunks` | reading stored original files or chunk views |
| Expansion and lookup | `nbrag_get_adjacent_chunks`, `nbrag_get_chunks_by_lines`, `nbrag_find_files` | expanding context around hits and resolving exact file paths |
| Inventory and routing | `nbrag_stats`, `nbrag_list` | discovering collections and browsing imported documents |

## How this differs from naive RAG

Naive RAG is usually a fixed one-shot pipeline: retrieve top-k chunks once and place them into the prompt.

`nbrag` is different in two practical ways:

- you prepare and control the knowledge base yourself
- retrieval is exposed through MCP tools, so the client can search, refine, inspect original text, and fetch more context when needed

## Configuration reference

Configuration priority:

```text
CLI arguments > environment variables > YAML config > defaults
```

### Environment variables

| Variable | Required | Default | Description |
|---|---:|---|---|
| `NBRAG_API_KEY` | Yes | | Embedding/rerank API key |
| `NBRAG_BASE_URL` | No | `https://api.siliconflow.cn/v1` | OpenAI-compatible API base URL |
| `NBRAG_EMBEDDING_MODEL` | No | `BAAI/bge-m3` | Embedding model |
| `NBRAG_RERANK_MODEL` | No | `BAAI/bge-reranker-v2-m3` | Rerank model |
| `NBRAG_DB_PATH` | No | `<project>/rag_db` | ChromaDB and local indexes path |
| `NBRAG_RAW_FILES_PATH` | No | `<db_path>/raw_files` | Stored original-file snapshot path |
| `NBRAG_CHUNK_SIZE` | No | `1000` | Chunk size |
| `NBRAG_CHUNK_OVERLAP` | No | `150` | Chunk overlap |

### YAML config

`nbrag` automatically looks for:

1. `./nbrag_config.yaml`
2. `./nbrag_config.yml`
3. `~/.config/nbrag/config.yaml`
4. `~/.config/nbrag/config.yml`

Example:

```yaml
embedding:
  api_key: ${NBRAG_API_KEY}
  base_url: https://api.siliconflow.cn/v1
  model: BAAI/bge-m3

rerank:
  model: BAAI/bge-reranker-v2-m3

storage:
  db_path: ./rag_db

chunking:
  chunk_size: 1000
  chunk_overlap: 150
```

### CLI

```bash
python -m nbrag --help
python -m nbrag --transport stdio
python -m nbrag --transport streamable-http --port 9101
python -m nbrag --api-key sk-xxx
python -m nbrag --db-path /data/rag
python -m nbrag --config ./nbrag_config.yaml
```



## Development

```bash
git clone https://github.com/ydf0509/nbrag.git
cd nbrag
pip install -e ".[dev]"

python -m nbrag
python -m nbrag --transport streamable-http --port 9101
```

## License

MIT
