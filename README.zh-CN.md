# nbrag

[English](README.md) | [简体中文](README.zh-CN.md)

面向 AI Agent 的 Agentic RAG MCP Server，用来从用户自己准备的知识库中检索证据、读取原文，并辅助 AI 基于真实内容回答问题。

`nbrag` 可以把本地文本、文档、法规、手册、笔记和 Python 源码导入为本地知识库。它尤其擅长 Python 项目源码向量化后的检索：源码 chunk 会注入文件路径、行号、AST scope 和函数签名，配合 `grep`、`find_definition`、原文读取等工具，对框架源码、三方库源码和内部 Python 项目有很强的定位效果。兼容 MCP 的 AI Agent 可以通过 10+ 个聚焦的检索/读取工具和 `nbrag_help` 导航工具，自主搜索、grep、定位文件、读取原文，并基于证据组织答案。

## 亮点

- **通用知识库**：适用于法律法规、医学指南、内部 wiki、产品手册、行业标准、技术文档和源码。
- **Python 源码检索优势**：对 `.py` 文件自动注入 AST scope 和函数签名，向量检索后还能用 `nbrag_find_definition` 获取完整 class/function/method 定义。
- **Agentic 检索工作流**：AI 可以多轮调用工具、改写查询、精确 grep、扩展上下文、读取原始文件。
- **混合检索**：Vector + 多通道 BM25 -> Weighted RRF 融合 -> 可选 Reranker。
- **原文读取**：导入文件会保存无 overlap 的原始文本快照，AI 可以按文件和行号读取准确上下文。
- **完整路径约束**：工具返回绝对 `file_path`，路径过滤和读取也要求使用完整路径，避免短文件名歧义。
- **MCP 优先设计**：可接入 Cursor、Claude Code/Desktop、OpenCode、Cherry Studio、Open WebUI、Dify、Cline 等 MCP 客户端。
- **Skill 可选**：MCP 工具 docstring 和 `nbrag_help` 已经自解释；复制内置 Skill 只是增强体验，不是必需步骤。

## 适合什么场景

当 AI 需要基于你自己掌握的资料回答问题时，可以使用 `nbrag`：

- **专业知识**：法律条文、医学指南、行业标准、合规规则。
- **内部资料**：公司 wiki、SOP、产品手册、制度规范、设计文档。
- **技术资料**：更新很快的三方库文档、本地框架文档、Python 源码、示例代码。
- **私有或离线内容**：公共服务无法索引，或不适合上传到公共服务的材料。

`nbrag` 是文本优先的工具。如果资料是 PDF、Word、网页、扫描件或图片，请先用你自己的解析/OCR 流程转换成 `.md`、`.txt` 或 `.html`，再导入知识库。

## 与其他方案的区别

### 与 Context7 的区别

Context7 是很有用的托管 MCP 文档服务，适合查询它已经收录的公开库文档。`nbrag` 面向的是你自己准备的本地/私有/专业知识库。

| | Context7 | nbrag |
|---|---|---|
| 数据来源 | 预索引的公开文档 | 用户自己导入的本地/私有文本 |
| 私有/内部资料 | 不支持 | 支持 |
| 原文读取 | 受托管片段限制 | 支持按绝对路径和行号读取 |
| 更新方式 | 取决于服务端索引 | 用户重新导入即可 |
| 存储 | 托管服务 | 本地 ChromaDB + raw files + BM25/symbol 索引 |
| 工具数量 | 较小 API 面 | 10+ 个检索/读取工具 + `nbrag_help` |

两者互补：Context7 适合快速查它已覆盖的公开文档；`nbrag` 适合私有、专业、刚更新、需要原文证据的本地资料。

### 与 Naive RAG 的区别

Naive RAG 通常是一次自动 top-k 检索，然后把结果塞进 prompt。`nbrag` 把检索作为 Agent 可以主动使用的工具能力：

- AI 决定是否检索。
- AI 把模糊问题改写成更聚焦的查询。
- AI 组合语义搜索、BM25、正则 grep、文件定位、原文读取。
- AI 可以多轮检索后再回答。

核心观点：**检索不是一次性管道，而是 Agent 的能力。**

## 快速开始

### 1. 安装

```bash
pip install nbrag
```

也可以直接用 `uvx` 运行：

```bash
uvx nbrag --help
```

### 2. 配置 Embedding/Rerank API

默认配置使用 SiliconFlow 兼容接口和 BGE 模型。你也可以通过环境变量或 YAML 配置切换到其他兼容服务。

Linux/macOS：

```bash
export NBRAG_API_KEY=sk-xxx
```

Windows PowerShell：

```powershell
$env:NBRAG_API_KEY = "sk-xxx"
```

### 3. 导入知识库

导入是人工 Python 脚本操作，不暴露成 MCP 工具。这样索引和删除始终由用户明确控制。

创建一个导入脚本：

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
    display_name="公司知识库",
    description="包含劳动合同资料和产品手册，适合查询公司制度、劳动合同和产品操作问题。",
    aliases=["公司资料", "劳动合同", "产品手册"],
    tags=["内部资料", "制度", "手册"],
)
```

Windows 路径也可以：

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

导入 Python 文档/源码：

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
    display_name="my_framework 源码与文档知识库",
    description="包含 my_framework 的 Python 源码和文档，适合查询 API 用法、实现细节、类、函数和示例。",
    aliases=["my_framework", "框架文档", "框架源码"],
    tags=["Python", "源码", "文档"],
)
```

`scripts/` 下有示例：

- `scripts/ingest_project.py` — 通用项目/文档导入模板
- `scripts/ingest_ex1/` — 民法典文本示例
- `scripts/ingest_ex2_marriage_law/` — 婚姻家庭法示例
- `scripts/ingest_ex3_worker_rights/` — 劳动者权益和劳动法示例

### 4. 描述知识库，帮助 AI 选对 collection

ChromaDB 的 collection name 必须是类似 `sanguo_yanyi` 的 ASCII slug，不能直接写中文。所以 `nbrag` 把给人和 AI 看的知识库说明保存在：

```text
rag_db/collection_profiles.json
```

建议在导入脚本里调用 `set_collection_profile()`，写清楚这个知识库的中文名、描述、别名和标签。`nbrag_stats()` 会把这些信息合并到输出里，AI 就能从“关羽、张飞、三国演义”等别名判断应该使用 `sanguo_yanyi`，而不是只靠英文 slug 猜。

这个 manifest 和 Chroma collection metadata 是分开的：Chroma metadata 只保留向量库底层配置，例如 `hnsw:space`；`collection_profiles.json` 才保存业务语义和 AI 路由信息。

### 5. 启动 MCP Server

#### stdio 模式

适合一个客户端独占一个服务进程。

```bash
nbrag
```

Cursor / Claude Desktop 风格配置：

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

使用 `uvx`：

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

#### HTTP 模式

多个 MCP 客户端或多个 IDE 窗口共享一个本地服务进程时，推荐 HTTP 模式。

```bash
nbrag --transport streamable-http --port 9101
```

客户端配置：

```json
{
  "mcpServers": {
    "nbrag": {
      "url": "http://localhost:9101/mcp"
    }
  }
}
```

### 6. 让 AI 发现知识库

导入后，让 MCP 客户端先调用：

```text
Call nbrag_stats and tell me which knowledge bases are available.
```

然后再提问：

```text
In collection company_knowledge, what does the labor contract material say about probation period limits?
```

如果 AI 不确定该用哪个工具，可以调用 `nbrag_help`。

## MCP 工具

`nbrag` 暴露 10+ 个检索/读取工具，以及 `nbrag_help` 导航工具。

| 类别 | 工具 | 用途 |
|---|---|---|
| 导航 | `nbrag_help` | AI 不确定如何组合工具时，返回简短工作流指南 |
| 搜索 | `nbrag_search` | 混合检索：Vector + BM25 -> RRF -> rerank |
| 搜索 | `nbrag_search_and_fetch` | 混合检索并自动读取命中位置附近原文 |
| 精确搜索 | `nbrag_grep` | 关键词/正则搜索，适合条文编号、术语、标题、错误码、API 名 |
| Python 源码 | `nbrag_find_definition` | 定位 Python class/function/method 完整定义，优先使用 AST |
| 文件定位 | `nbrag_find_files` | 根据文件名或路径片段找到唯一绝对 `file_path` |
| 上下文 | `nbrag_get_file_chunks` | 按 chunk 浏览文件 |
| 上下文 | `nbrag_get_raw_file` | 读取无 overlap 的原始文件内容 |
| 上下文 | `nbrag_get_adjacent_chunks` | 根据 `doc_id` + `chunk_index` 扩展相邻 chunks |
| 上下文 | `nbrag_get_chunks_by_lines` | 获取覆盖指定行号范围的 chunks |
| 只读清单 | `nbrag_list` | 列出 collection 中的文档 |
| 只读清单 | `nbrag_stats` | 查看知识库、文档数、chunk 数和存储配置 |

导入和删除不暴露为 MCP 工具，请使用 Python 脚本人工维护。

## 推荐 Agent 工作流

### 通用知识场景

适合法律条文、指南、手册、标准、制度文档、内部 wiki：

```text
1. nbrag_stats
   发现可用 collection_name。

2. nbrag_search_and_fetch
   用聚焦查询做语义+关键词混合检索，并读取命中位置附近原文。

3. nbrag_grep
   搜索精确术语、条文编号、标题、错误码或原文短语。

4. nbrag_get_raw_file / nbrag_get_adjacent_chunks
   回到完整原文上下文，避免只看碎片 chunk。

5. nbrag_find_files
   如果只有文件名或路径片段，先解析成完整绝对 file_path。
```

示例：

```text
用户：一年劳动合同，试用期五个月合法吗？能要什么赔偿？

AI：
1. nbrag_search_and_fetch("试用期 最长期限 一年劳动合同")
2. nbrag_search_and_fetch("违法约定试用期 赔偿")
3. nbrag_grep("第十九条")
4. nbrag_grep("第八十三条")
5. 基于原文证据回答。
```

### 代码场景

适合 Python 源码和框架/API 文档：

```text
1. nbrag_search_and_fetch
   查相关概念、示例、API 用法。

2. nbrag_grep
   精确查类名、方法名、常量、import、错误字符串、装饰器、配置 key。

3. nbrag_find_definition
   仅对 Python `.py` 文件，获取完整 class/function/method 定义。

4. nbrag_get_raw_file
   读取完整源码或文档上下文。

5. 发现新符号后跨文件重复检索。
```

### 路径规则

所有 `file_path` 和 `filter_file_path` 入参都必须使用 `nbrag` 工具返回的完整绝对路径，例如：

```text
/data/docs/labor_law/劳动合同法.md
D:/docs/labor_law/劳动合同法.md
```

不要传 `劳动合同法.md`、`core.py`、`src/core.py` 这类短路径。如果只有文件名或路径片段，先调用 `nbrag_find_files`。

## 可选 Skill

`nbrag_help` 和 MCP 工具描述已经足够 MCP-only 场景使用，所以用户不复制 Skill 也能正常使用 MCP 工具。内置 Skill 只是给支持本地 Skill 的 Agent 提供更完整的工作流提示。

定位内置 Skill：

```bash
python -c "import nbrag, os; print(os.path.join(os.path.dirname(nbrag.__file__), 'skills', 'nbrag-workflow'))"
```

复制到你的 Agent 使用的 Skills 目录，例如：

```bash
cp -r "$SKILL_PATH" .agents/skills/
cp -r "$SKILL_PATH" .claude/skills/
cp -r "$SKILL_PATH" .cursor/skills/
```

不支持 Skill 的 Agent 仍然可以通过 `nbrag_help` 获取简短组合拳指南。

## 配置

配置优先级：

```text
CLI 参数 > 环境变量 > YAML 配置 > 默认值
```

### 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|---|---:|---|---|
| `NBRAG_API_KEY` | 是 | | Embedding/rerank API key |
| `NBRAG_BASE_URL` | 否 | `https://api.siliconflow.cn/v1` | OpenAI-compatible API base URL |
| `NBRAG_EMBEDDING_MODEL` | 否 | `BAAI/bge-m3` | Embedding 模型 |
| `NBRAG_RERANK_MODEL` | 否 | `BAAI/bge-reranker-v2-m3` | Rerank 模型 |
| `NBRAG_DB_PATH` | 否 | `<project>/rag_db` | ChromaDB 和本地索引路径 |
| `NBRAG_RAW_FILES_PATH` | 否 | `<db_path>/raw_files` | 原始文件快照路径 |
| `NBRAG_CHUNK_SIZE` | 否 | `1500` | chunk 大小 |
| `NBRAG_CHUNK_OVERLAP` | 否 | `200` | chunk overlap |

### YAML 配置

`nbrag` 自动查找：

1. `./nbrag_config.yaml`
2. `./nbrag_config.yml`
3. `~/.config/nbrag/config.yaml`
4. `~/.config/nbrag/config.yml`

示例：

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

## 运行注意事项

### HTTP Server 与外部导入

HTTP 模式是长驻 Python 进程。如果外部导入脚本在服务运行期间重建某个 collection，服务进程可能短时间内持有旧的 Chroma/BM25/doc-id/symbol 运行时缓存。

`nbrag` 会在 core 操作入口按需每 300 秒刷新一次这些进程内缓存。刷新只清内存，不删除持久化索引或原始文件。

为了结果更稳定：

- 避免在另一个进程重建同一 collection 时同时查询它。
- 大规模 `delete_first=True` 重建后，可以等待刷新间隔，或直接重启 HTTP MCP server。
- 多客户端共享时，优先使用一个 HTTP server，而不是多个 stdio 进程同时写同一个 `rag_db`。

这是本地嵌入式存储，不是带跨进程事务协调的分布式数据库。

### 支持内容

`nbrag` 索引文本内容。Python `.py` 文件会额外生成 AST scope metadata。其他文本文件使用语义搜索、BM25、grep 和原文读取。

PDF、Word、幻灯片、图片、扫描件、网页等内容建议先用外部解析/OCR 流程转成 `.md`、`.txt` 或 `.html` 再导入。

## Metadata

每个写入 ChromaDB 的 chunk 都包含 metadata，供后续工具使用：

| 字段 | 示例 | 说明 |
|---|---|---|
| `source` | `/data/docs/labor_law/劳动合同法.md` | 规范化绝对路径，是 `file_path` 的权威值 |
| `filename` | `劳动合同法.md` | 仅用于显示的文件名 |
| `doc_id` | `a1b2c3d4e5f6` | 根据路径生成的稳定文件标识 |
| `chunk_index` | `3` | 文件内 0-based chunk 序号 |
| `total_chunks` | `15` | 该文件总 chunk 数 |
| `line_start` | `120` | 1-based 起始行 |
| `line_end` | `180` | 结束行 |
| `scope` | `MyClass.my_method` | Python AST scope，非 Python 文件为空 |

embedding 前会注入 chunk header 提升检索效果：

```text
# [File: /data/docs/labor_law/劳动合同法.md] [Lines: 120-180]
```

Python chunk 还会注入 AST 信息：

```text
# [File: /data/project/core.py] [Class: class Service] [Method: run] [Sig: def run(self)] [Lines: 45-78]
```

## 架构

`nbrag` 使用四层本地存储：

- **ChromaDB**：带 overlap 的向量 chunks，用于语义搜索。
- **raw_files/**：无 overlap 的原始文件快照，用于精确读取。
- **bm25_index_v2/**：持久化多通道 BM25 索引，用于关键词召回。
- **symbol_index/**：Python AST 符号索引，用于 `nbrag_find_definition`。

搜索管线：

```text
query
  -> embedding vector search
  -> multi-channel BM25 search
  -> Weighted RRF fusion
  -> optional reranker
  -> nbrag_search_and_fetch 自动读取原文上下文
```

BM25 v2 使用三路 token：

- `word`：中文 search-mode 分词 + 英文/数字 token。
- `ngram`：中文 2/3-gram，提升短语召回。
- `code`：camelCase、snake_case、常量、路径和 API-like 符号。

Python AST scope 注入仅对 `.py` 文件生效。非 Python 文件作为通用文本处理，依赖语义搜索、BM25、grep 和原文读取。

## 开发

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
