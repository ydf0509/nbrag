# nbrag

[English](README.md) | [简体中文](README.zh-CN.md)

`nbrag` 是一个 PyPI 三方包，用来构建本地文本知识库，并通过 MCP server 对外提供检索能力。

适合这样的场景：你希望 MCP 客户端能从你自己掌控的文件里检索证据，例如内部文档、法规、手册、笔记、本地项目文档或 Python 源码。

## nbrag 是做什么的

`nbrag` 主要解决这些问题：

- 把本地文本文件导入为可搜索的知识库
- 向量数据和原文快照都保存在你自己的机器上
- 用 `set_collection_profile()` 给 collection 补充人类可理解的说明信息
- 通过 stdio 或 HTTP 启动 MCP server，供 MCP 客户端调用

`nbrag` 是文本优先的工具。如果你的资料原始格式是 PDF、Word、图片、扫描件或网页，建议先转换成 `.md`、`.txt` 或 `.html` 再导入。

## 安装

```bash
pip install nbrag
```

安装后可以这样确认包和 CLI 可用：

```bash
python -m nbrag --help
```

## 配置 API key

默认情况下，`nbrag` 使用 SiliconFlow 兼容的 embedding 和 rerank 接口。导入知识库或启动服务之前，先设置 `NBRAG_API_KEY`。

Linux/macOS：

```bash
export NBRAG_API_KEY=sk-xxx
```

Windows PowerShell：

```powershell
$env:NBRAG_API_KEY = "sk-xxx"
```

## 快速开始

通常流程是：

1. 准备一批文本文件
2. 用 `batch_ingest()` 导入
3. 用 `set_collection_profile()` 描述 collection
4. 启动 MCP server
5. 配置 MCP 客户端接入

### 最小导入示例

创建一个脚本，例如 `ingest_my_docs.py`：

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
    display_name="公司知识库",
    description="内部制度和产品手册。",
    aliases=["公司资料", "制度", "手册"],
    tags=["内部资料", "制度", "手册"],
)
```

运行：

```bash
python ingest_my_docs.py
```

几个常用参数的理解：

- `collection_name`：稳定的机器侧名字(知识库名字)
- `file_extensions`：限制要导入的文本文件类型
- `delete_first=True`：如果每次需要调参，全量重建这个 collection（可以增量导入，那就别先删除）
- `verbose=True`：在刚开始使用或调试时很有帮助

### 为什么 `set_collection_profile()` 很重要

`collection_name` 是给存储和 MCP 调用使用的机器标识，最好保持稳定、简短、slug 化，例如 `company_knowledge`。

`set_collection_profile()` 则是在这个 slug 上补充人类可理解的元信息：

- `display_name`
- `description`
- `aliases`
- `tags`

这样做的好处是：

- 人更容易看懂这个 collection 里装了什么
- MCP 路由在多个 collection 之间更容易选对目标

### Python 源码场景也是同一套导入流程

Python 项目并不需要另一套导入方式。通常你只需要调整：

- 导入路径
- `file_extensions`，例如改成 `['.py', '.md', '.txt']`
- `set_collection_profile()` 里的描述，让它更像“源码/API/实现细节”知识库

示例：

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
    display_name="my_framework 源码与文档知识库",
    description="my_framework 的 Python 源码和文档。",
    aliases=["my_framework", "框架源码", "框架文档"],
    tags=["Python", "源码", "文档"],
)
```

仓库里的 `scripts/` 目录下已经有一些 ingest 示例可参考。

## 启动 MCP server

### stdio 模式

适合一个客户端独占一个服务进程。

```bash
python -m nbrag
```

### HTTP 模式

适合多个客户端或多个 IDE 窗口共享同一个本地服务进程。

```bash
python -m nbrag --transport streamable-http --port 9101
```

## 配置 MCP 客户端

### stdio 配置

把 MCP 客户端指向安装了 `nbrag` 的 Python 环境。

示例：

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

如果客户端使用的不是你当前 shell 的 Python，请把 `python` 改成解释器绝对路径。

### HTTP 配置

先启动共享本地服务：

```bash
python -m nbrag --transport streamable-http --port 9101
```

然后在客户端里配置：

```json
{
  "mcpServers": {
    "nbrag": {
      "url": "http://localhost:9101/mcp"
    }
  }
}
```

## MCP 能力概览

服务启动后，`nbrag` 会暴露一组以检索为核心的 MCP 工具。对人类使用者来说，最容易理解的方式是按能力分类：

| 能力 | 代表工具 | 作用 |
|---|---|---|
| 搜索 | `nbrag_search`, `nbrag_search_and_fetch` | 在导入后的 collection 里做语义/混合检索 |
| 检索诊断 | `nbrag_search_only_bm25`, `nbrag_search_only_vector` | 单独观察词法检索或向量检索效果 |
| 精确文本查找 | `nbrag_grep` | 在保存的原文里做逐行匹配 |
| 原文读取 | `nbrag_get_raw_file`, `nbrag_get_file_chunks` | 读取原文或 chunk 视图 |
| 扩展与定位 | `nbrag_get_adjacent_chunks`, `nbrag_get_chunks_by_lines`, `nbrag_find_files` | 围绕命中扩展上下文，或定位精确文件路径 |
| 清单与路由 | `nbrag_stats`, `nbrag_list` | 查看有哪些 collection / 文档 |

## 和 Naive RAG 的区别

Naive RAG 往往是固定的一次性 top-k 检索：取回若干 chunk，然后直接塞进 prompt。

`nbrag` 的不同点主要在两件事上：

- 知识库由你自己准备和维护
- 检索能力通过 MCP tools 暴露出来，客户端可以继续搜索、缩小范围、查看原文、补充上下文

## 配置参考

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
| `NBRAG_RAW_FILES_PATH` | 否 | `<db_path>/raw_files` | 原文快照路径 |
| `NBRAG_CHUNK_SIZE` | 否 | `1000` | chunk 大小 |
| `NBRAG_CHUNK_OVERLAP` | 否 | `150` | chunk overlap |

### YAML 配置

`nbrag` 会自动查找：

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
