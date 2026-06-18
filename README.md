# nbrag

[English](README.md) | [简体中文](README.zh-CN.md)

Agentic RAG MCP Server for AI agents that need to retrieve evidence from user-prepared knowledge bases.

`nbrag` lets you import local text, documentation, regulations, manuals, notes, and Python source into a local knowledge base. MCP-compatible agents can then use 11 focused retrieval tools plus `nbrag_help` to search, grep, locate files, read original content, and build answers from real evidence instead of relying only on model memory.

Python source workflow is a first-class use case: `.py` chunks include AST scope and signature metadata, so agents can combine semantic search with `nbrag_grep`, `nbrag_find_definition`, and `nbrag_get_raw_file` for precise source navigation.

## Highlights

- **General-purpose knowledge bases**: works for law, medical guidelines, internal wiki pages, product manuals, standards, technical docs, and source code.
- **Python source retrieval**: especially effective after vectorizing Python projects, because `.py` files keep file paths, line numbers, AST scope, and function signatures.
- **Agentic retrieval workflow**: agents can call multiple tools, rewrite queries, grep exact terms, expand context, and read original files.
- **Hybrid search**: Vector + multi-channel BM25 -> Weighted RRF fusion -> optional reranker.
- **Original-file reading**: every imported file is cached as raw text, so agents can read exact line ranges without chunk overlap.
- **Full-path file operations**: tools return absolute `file_path` values and require those values for path-filtered reads, avoiding ambiguous short filenames.
- **MCP-first design**: works with Cursor, Claude Code/Desktop, OpenCode, Cherry Studio, Open WebUI, Dify, Cline, and other MCP clients.
- **Optional Skill**: tool docstrings and `nbrag_help` are self-contained; copying the bundled Skill improves workflow guidance but is not required.

## When To Use

Use `nbrag` when the agent needs evidence from information you control:

- **Professional knowledge**: legal texts, medical guidelines, industry standards, compliance rules.
- **Internal material**: company wiki pages, SOPs, product manuals, policies, design docs.
- **Technical material**: fast-moving library docs, local framework docs, Python source code, examples.
- **Private or offline content**: content that public services cannot index or should not receive.

`nbrag` is text-first. Convert PDFs, Word documents, web pages, scans, or other binary formats to `.md`, `.txt`, or `.html` before ingestion if you need reliable line-based retrieval.

## How It Compares

### Context7

Context7 is a useful hosted MCP documentation service for public libraries it has already indexed. `nbrag` is for knowledge bases you prepare yourself.

| | Context7 | nbrag |
|---|---|---|
| Source | Pre-indexed public docs | User-imported local/private text |
| Private/internal content | No | Yes |
| Original file reading | Limited by hosted snippets | Yes, by absolute file path and line range |
| Refresh model | Depends on hosted indexing | Re-ingest whenever you want |
| Storage | Hosted service | Local ChromaDB + raw files + local BM25/symbol indexes |
| Tools | Small API surface | 11 retrieval/read tools + `nbrag_help` |

They are complementary: use Context7 for quickly checking public docs it already covers; use `nbrag` for private, specialized, newly changed, or high-evidence local material.

### Naive RAG

Naive RAG usually performs one automatic top-k search and injects the result into the prompt. `nbrag` exposes retrieval as agent tools:

- The agent decides whether to search.
- The agent rewrites vague user questions into focused queries.
- The agent combines semantic search, BM25, regex grep, file lookup, and original-file reads.
- The agent can run several retrieval rounds before answering.

Core idea: **retrieval is an agent capability, not a fixed one-shot pipeline.**

## Quick Start

### 1. Install

```bash
pip install nbrag
```

You can also run it directly with `uvx`:

```bash
uvx nbrag --help
```

### 2. Configure Embedding/Rerank API

By default, `nbrag` uses SiliconFlow-compatible endpoints and BGE models. You can point it at another compatible provider with environment variables or YAML config.

Linux/macOS:

```bash
export NBRAG_API_KEY=sk-xxx
```

Windows PowerShell:

```powershell
$env:NBRAG_API_KEY = "sk-xxx"
```

### 3. Import A Knowledge Base

Ingestion is intentionally a manual Python operation, not an MCP tool. This keeps indexing/deleting under user control.

Create an ingest script:

```python
from nbrag import batch_ingest, set_collection_profile

batch_ingest(
    paths=[
        "/data/docs/labor_law",
        "/data/docs/product_manuals",
    ],
    collection_name="company_knowledge",
    file_extensions=[".md", ".txt", ".html"],
    delete_first=True,
    verbose=True,
)

set_collection_profile(
    "company_knowledge",
    display_name="Company Knowledge Base",
    description="Internal labor-law notes and product manuals. Use this for company policy, labor contract, and product operation questions.",
    aliases=["company docs", "labor contract", "product manuals"],
    tags=["internal", "policy", "manual"],
)
```

Windows paths are also fine:

```python
from nbrag import batch_ingest, set_collection_profile

batch_ingest(
    paths=[
        "D:/docs/labor_law",
        "D:/docs/product_manuals",
    ],
    collection_name="company_knowledge",
    file_extensions=[".md", ".txt", ".html"],
    delete_first=True,
    verbose=True,
)

set_collection_profile(
    "company_knowledge",
    display_name="公司知识库",
    description="包含劳动合同资料和产品手册，适合查询公司制度、劳动合同和产品操作问题。",
    aliases=["公司资料", "劳动合同", "产品手册"],
    tags=["内部资料", "制度", "手册"],
)
```

For Python docs/source code:

```python
from nbrag import batch_ingest, set_collection_profile

batch_ingest(
    paths=[
        "/data/projects/my_framework/src",
        "/data/projects/my_framework/docs",
    ],
    collection_name="my_framework",
    file_extensions=[".py", ".md", ".txt"],
    delete_first=True,
    verbose=True,
)

set_collection_profile(
    "my_framework",
    display_name="My Framework Source And Docs",
    description="Python source and documentation for my_framework. Use this for API usage, implementation details, classes, functions, and examples.",
    aliases=["my_framework", "framework docs", "framework source"],
    tags=["Python", "source", "docs"],
)
```

Example ingest scripts are available under `scripts/`:

- `scripts/ingest_project.py` — generic project/document template
- `scripts/ingest_ex1/` — Civil Code text example
- `scripts/ingest_ex2_marriage_law/` — marriage/family law example
- `scripts/ingest_ex3_worker_rights/` — worker rights and labor law example

### 4. Describe Collections For AI Routing

ChromaDB collection names must be ASCII-like slugs such as `sanguo_yanyi`, so `nbrag` keeps human-readable collection profiles in:

```text
rag_db/collection_profiles.json
```

Use `set_collection_profile()` in your ingest script to describe what the knowledge base contains. `nbrag_stats()` merges this manifest into its output, so agents can choose the right `collection_name` from display names, descriptions, aliases, and tags.

This manifest is separate from Chroma collection metadata. Chroma metadata remains reserved for vector-store configuration such as `hnsw:space`; `collection_profiles.json` stores business meaning and AI routing hints.

### 5. Start MCP Server

#### stdio mode

Use stdio when one client owns one server process.

```bash
nbrag
```

Cursor / Claude Desktop style config:

```json
{
  "mcpServers": {
    "nbrag": {
      "command": "nbrag",
      "env": {
        "NBRAG_API_KEY": "sk-xxx"
      }
    }
  }
}
```

With `uvx`:

```json
{
  "mcpServers": {
    "nbrag": {
      "command": "uvx",
      "args": ["nbrag"],
      "env": {
        "NBRAG_API_KEY": "sk-xxx"
      }
    }
  }
}
```

#### HTTP mode

Use HTTP mode when multiple MCP clients or many IDE windows should share one local server process.

```bash
nbrag --transport streamable-http --port 9101
```

Client config:

```json
{
  "mcpServers": {
    "nbrag": {
      "url": "http://localhost:9101/mcp"
    }
  }
}
```

### 6. Ask The Agent To Discover Collections

After ingestion, ask the MCP client:

```text
Call nbrag_stats and tell me which knowledge bases are available.
```

Then ask a domain question:

```text
In collection company_knowledge, what does the labor contract material say about probation period limits?
```

If the agent is unsure which tool to use, it can call `nbrag_help`.

## MCP Tools

`nbrag` exposes 11 retrieval/read tools plus one navigation tool.

| Category | Tool | Purpose |
|---|---|---|
| Navigation | `nbrag_help` | Compact workflow guide for agents that are unsure how to combine tools |
| Search | `nbrag_search` | Hybrid search: Vector + BM25 -> RRF -> rerank |
| Search | `nbrag_search_and_fetch` | Hybrid search plus automatic original-file context fetch |
| Exact search | `nbrag_grep` | Keyword/regex search for article numbers, terms, headings, error codes, API names |
| Python source | `nbrag_find_definition` | Find complete Python class/function/method definitions with AST when available |
| File lookup | `nbrag_find_files` | Find the unique absolute `file_path` for later reads or filters |
| Context | `nbrag_get_file_chunks` | Browse a file by chunks with metadata |
| Context | `nbrag_get_raw_file` | Read original cached file content without chunk overlap |
| Context | `nbrag_get_adjacent_chunks` | Expand around a search result using `doc_id` + `chunk_index` |
| Context | `nbrag_get_chunks_by_lines` | Get chunks covering a specific line range |
| Read-only inventory | `nbrag_list` | List documents in a collection |
| Read-only inventory | `nbrag_stats` | Show collections, doc counts, chunk counts, and storage config |

Ingestion and deletion are not exposed as MCP tools. Use Python scripts for those operations.

## Recommended Agent Workflows

### 通用知识场景

For law, guidelines, manuals, standards, policy documents, and internal wiki material:

```text
1. nbrag_stats
   Discover available collection_name values.

2. nbrag_search_and_fetch
   Start with a focused semantic/keyword query and get nearby original text.

3. nbrag_grep
   Use exact terms, article numbers, headings, error codes, or quoted phrases.

4. nbrag_get_raw_file / nbrag_get_adjacent_chunks
   Read fuller context before answering.

5. nbrag_find_files
   If only a filename/path fragment is known, resolve it to a full absolute file_path first.
```

Example:

```text
User: 一年劳动合同，试用期五个月合法吗？能要什么赔偿？

Agent:
1. nbrag_search_and_fetch("试用期 最长期限 一年劳动合同")
2. nbrag_search_and_fetch("违法约定试用期 赔偿")
3. nbrag_grep("第十九条")
4. nbrag_grep("第八十三条")
5. Answer with cited evidence from original text.
```

### 代码场景

For Python source code and framework/API documentation:

Python source workflow: start with semantic/context search, then use exact-name tools instead of relying on one retrieval mode.

```text
1. nbrag_search_and_fetch
   Find relevant concepts, examples, or API usage.

2. nbrag_grep
   Search exact names, constants, imports, error strings, decorators, or config keys.

3. nbrag_find_definition
   For Python `.py` files only, retrieve the complete class/function/method definition.

4. nbrag_get_raw_file
   Read the full source or docs around the hit.

5. Repeat across files as new symbols appear.
```

### Path Rules

All `file_path` and `filter_file_path` arguments must be complete absolute paths returned by `nbrag` tools, for example:

```text
/data/docs/labor_law/劳动合同法.md
D:/docs/labor_law/劳动合同法.md
```

Do not pass short paths such as `劳动合同法.md`, `core.py`, or `src/core.py`. If only a filename or fragment is known, call `nbrag_find_files` first.

## Optional Skill

`nbrag_help` and MCP tool descriptions are enough for MCP-only usage, so users do **not** need to copy a Skill for the tools to work. 换句话说，用户不复制 Skill 也能正常使用 MCP 工具；the bundled Skill is optional workflow guidance for agents that support local skills.

Locate the bundled Skill:

```bash
python -c "import nbrag, os; print(os.path.join(os.path.dirname(nbrag.__file__), 'skills', 'nbrag-workflow'))"
```

Copy it to the Skills directory used by your agent, for example:

```bash
cp -r "$SKILL_PATH" .agents/skills/
cp -r "$SKILL_PATH" .claude/skills/
cp -r "$SKILL_PATH" .cursor/skills/
```

Agents that do not copy Skill files can still call `nbrag_help` for a compact workflow guide.

## Configuration

Configuration priority:

```text
CLI arguments > environment variables > YAML config > defaults
```

### Environment Variables

| Variable | Required | Default | Description |
|---|---:|---|---|
| `NBRAG_API_KEY` | Yes | | Embedding/rerank API key |
| `NBRAG_BASE_URL` | No | `https://api.siliconflow.cn/v1` | OpenAI-compatible API base URL |
| `NBRAG_EMBEDDING_MODEL` | No | `BAAI/bge-m3` | Embedding model |
| `NBRAG_RERANK_MODEL` | No | `BAAI/bge-reranker-v2-m3` | Rerank model |
| `NBRAG_DB_PATH` | No | `<project>/rag_db` | ChromaDB and local indexes path |
| `NBRAG_RAW_FILES_PATH` | No | `<db_path>/raw_files` | Original-file snapshot path |
| `NBRAG_CHUNK_SIZE` | No | `1500` | Chunk size |
| `NBRAG_CHUNK_OVERLAP` | No | `200` | Chunk overlap |

### YAML Config

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
  chunk_size: 1500
  chunk_overlap: 200
```

### CLI

```bash
nbrag --help
nbrag --transport stdio
nbrag --transport streamable-http --port 9101
nbrag --api-key sk-xxx
nbrag --db-path /data/rag
nbrag --config ./nbrag_config.yaml
```

## Operational Notes

### HTTP Server And External Ingest

HTTP mode keeps a long-running Python process. If an external ingest script rebuilds a collection while the server is running, the server may temporarily hold old Chroma/BM25/doc-id/symbol runtime caches.

`nbrag` refreshes those process-local runtime caches lazily every 300 seconds at core operation entry. The refresh is memory-only and does not delete persisted indexes or raw files.

For the most predictable results:

- Avoid querying a collection while another process is rebuilding the same collection.
- After a large `delete_first=True` rebuild, either wait for the refresh interval or restart the HTTP MCP server.
- Use one HTTP server process for many clients instead of many stdio processes writing to the same `rag_db`.

This is local embedded storage, not a distributed database with cross-process transaction coordination.

### Supported Content

`nbrag` indexes text content. Python `.py` files get additional AST-based scope metadata. Other text files use semantic search, BM25, grep, and original-file reads.

For PDFs, Word files, slides, images, scans, and web pages, use your preferred extraction/OCR pipeline first, then ingest the resulting `.md`, `.txt`, or `.html` files.

## Metadata

Each chunk stored in ChromaDB includes metadata used by downstream tools:

| Field | Example | Description |
|---|---|---|
| `source` | `/data/docs/labor_law/劳动合同法.md` | Normalized absolute file path; the authoritative value for `file_path` |
| `filename` | `劳动合同法.md` | Display-only filename |
| `doc_id` | `a1b2c3d4e5f6` | Stable file identifier derived from path |
| `chunk_index` | `3` | 0-based chunk index within the file |
| `total_chunks` | `15` | Total chunks for that file |
| `line_start` | `120` | 1-based start line |
| `line_end` | `180` | End line |
| `scope` | `MyClass.my_method` | Python AST scope, empty for non-Python files |

Chunk headers are injected before embedding to improve search:

```text
# [File: /data/docs/labor_law/劳动合同法.md] [Lines: 120-180]
```

Python chunks also include AST information:

```text
# [File: /data/project/core.py] [Class: class Service] [Method: run] [Sig: def run(self)] [Lines: 45-78]
```

## Architecture

`nbrag` uses four local storage layers:

- **ChromaDB**: vector chunks with overlap for semantic search.
- **raw_files/**: original file snapshots without overlap for exact reads.
- **bm25_index_v2/**: persisted multi-channel BM25 indexes for lexical recall.
- **symbol_index/**: Python AST symbol index for `nbrag_find_definition`.

The search pipeline is:

```text
query
  -> embedding vector search
  -> multi-channel BM25 search
  -> Weighted RRF fusion
  -> optional reranker
  -> original-file context fetch when using nbrag_search_and_fetch
```

BM25 v2 uses three channels:

- `word`: Chinese search-mode tokenization plus English/numeric tokens.
- `ngram`: Chinese 2/3-gram recall for short phrases.
- `code`: camelCase, snake_case, constants, paths, and API-like symbols.

Python AST scope injection applies only to `.py` files. Non-Python files remain general text and rely on semantic search, BM25, grep, and original-file reads.

## Development

```bash
git clone https://github.com/ydf0509/nbrag.git
cd nbrag
pip install -e ".[dev]"

python -m nbrag
python -m nbrag --transport streamable-http --port 9101

python -m pytest tests/ -q
mypy nbrag/
```

## License

MIT
