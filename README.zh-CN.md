# nbrag

[English](README.md) | [简体中文](README.zh-CN.md)

`nbrag` 是一个 PyPI 三方包，用来构建本地文本知识库，并通过 MCP server 给 llm提供rag知识库检索能力。   
nbrag 是 agentic rag，由llm主动调用主动根据上下文构造向量检索语句和bm25检索语句。   
nbrag 使llm能根据chunk块，自动以及llm自主扩大阅读范围，吊打任何传统rag，可以完成横跨多个文件的多跳检索的极端复杂任务推理。     
nbrag 作为mcp可以配置给任意agent工具，包括openclaw codex claudecode cursor trae opencode workbuddy lc-aegnt 等等。    

适合这样的场景：你希望 MCP 客户端能从你自己掌控的文件里检索知识，例如内部文档、法规、手册、笔记、本地项目文档或 
Python 源码。
nbrag 自带 向量检索 bm25检索 和混合检索，通过强力的提示词和10+个工具，ai检索出最相关的知识。

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

### 导入 GitHub 项目到 nbrag 知识库

`nbrag.contrib.ingest_github_proj` 可以直接下载 GitHub 仓库 ZIP 并导入知识库：

```python
from nbrag.contrib.ingest_github_proj import ingest_github_proj

ingest_github_proj(
    "https://github.com/owner/repo",
    collection_name="repo",
    relative_paths=["src", "docs"],
    branch="main",
    delete_first=True,
    verbose=True,
)
```

### ingest_github_proj 的好处

你可以使用 `nbrag/.agents/skills/ingest-github-proj/SKILL.md` 里的 skill，让ai帮你写导入github项目的脚本。

你可以把你关心的 github项目的 源码和教程 同时都向量化到一个知识库，源码和教程一把抓， 让ai无幻觉辅助你写代码。 llm搭配nbrag mcp 吊打 llm搭配知名的context7 mcp。


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
| 检索 | `nbrag_retrieve`, `nbrag_retrieve_no_expand` | 在导入后的 collection 里做语义/混合检索 |
| 检索诊断 | `nbrag_retrieve_only_bm25`, `nbrag_retrieve_only_vector` | 单独观察词法检索或向量检索效果 |
| 精确文本查找 | `nbrag_grep` | 在保存的原文里做逐行匹配 |
| 原文读取 | `nbrag_read_more_original_text`, `nbrag_get_file_chunks` | 读取原文或 chunk 视图 |
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


## 为什么传统 RAG 不行，被 nbrag 吊打，举个典型例子？

传统 RAG 的最大缺陷，是**把检索当成一次性的"相似度赌博"**：query 是什么样，就直接拿去 embedding 检索，捞到什么算什么，捞错了也不自知。

### 一个典型的对话场景

假设有一个知识库，里面有世界各国 历史、面积、经济、人口、文化、gdp、军力、武器 等知识内容。

假设用户分两次提问，第一句问“美国和中国谁军事厉害？”，第二句问“那美国和俄罗斯呢？” ，注意第二句故意演示半句残缺不完整的提问，用户没有明说完整提问”那美国和俄罗斯谁的军事实力更强？“。

> 用户：美国和中国谁军事厉害？
> 用户：那美国和俄罗斯呢？

### 传统 RAG 的表现：直接懵逼

"那美国和俄罗斯呢？" 这句话在传统 RAG 面前是**连环死局**：

- **残缺 query 导致结果跑偏**："那…呢"只有指代，没有任何"军事"语义信号，embedding 根本不知道要查什么，捞回来的尽是人口、文化、面积这类和军力无关的片段，答非所问；
- **查不到不存在的文本**：知识库里只有各国单列数据（美国军力、俄罗斯军力），**没有任何"美俄军力对比"的现成原话**。传统 RAG 只能返回语料里真实存在的片段——而"答案"这个片段压根不存在，怎么捞都是空；
- **跨文档拼装不能**：就算侥幸捞回美国军力的 chunk，topk 是单次相似度赌博，不会同时把俄罗斯的数据也捞回来。两国的数据散落在各自的 chunk 里，**凑不成对比**；
- **单轮、无记忆**：第一轮"美国和中国谁军事厉害"查完就结束，第二轮"那美国和俄罗斯呢"和第一轮完全隔离，又要重新赌一次，连"美国刚才已经查过"都不知道；
- **无自检、无补救**：不知道答案还缺一半，捞错了就是错了，一把梭没有回头路。

### Agentic RAG（nbrag）的表现：有状态的知识采集

nbrag 把"检索"从一次性管道，变成**多轮自主决策、且有记忆的知识采集流程**：

1. **第一轮拆解子问题，搜两国**：对"美国和中国谁军事厉害"，LLM 把"军力"拆成核弹头、航母、潜艇、轰炸机、陆军、海军、空军人数等子问题，把**美国**和**中国**的军力数据都检索进上下文；
2. **第二轮补全指代，只补俄罗斯**："那美国和俄罗斯呢"→ 补全为"美俄谁的军力更强"。LLM 发现**美国数据第一轮已经拿到**，于是只对俄罗斯检索，**不会重复搜索美国**；
3. **每一轮都走双通道检索**：
   - **语义通道**（query）："俄罗斯的军事力量"——管概念；
   - **词面锚点**（bm25_query）：分别用 `俄罗斯 军费开支`、`俄罗斯 潜艇 轰炸机 航母`、`俄罗斯 陆军 海军 空军` 多轮检索——管强词面信号。残缺 query 语义不可靠时，国家名、武器名这类词面信号兜底；
4. **命中即扩读**：对有用的 chunk 自动扩读原文，防止答案被 chunk 边界截断；
5. **知识完整性自检**：对比需要双方数据，发现还缺俄罗斯的某项数据，就继续查，直到数据齐全；
6. **LLM 综合对比**：美国数据来自 chunk A、俄罗斯数据来自 chunk B——**分头检索、最后拼装**，基于双方核弹头、航母、潜艇、轰炸机、陆军、海军、空军人数等数据给出军力对比结论。


### 假设用户提问 "韩国和巴西谁军事更强?"传统 RAG 被碾压。

```
对于传统rag知识库，直接检索 "韩国和巴西谁军事更强?" 绝对是返回毫不相关的内容，
或一次检索不到足够能回答用户问题的知识。

因为 "俄罗斯和美国谁厉害","中国和美国谁厉害" ，因为这是主流的大众津津乐道的好奇心，
所以这种关于两国的直接性比较，在知识库是有一定可能有直接的两国国力对比的原话。

但是"韩国和巴西谁军事更强?" 这个问题，在世界互联网上几乎不可能有现成的比较，
这两个国家相隔2万公里，无冤无仇，八竿子打不着。这两国也不是世界上军力最强国家行列，
绝对没有媒体会如此无聊的直接有原始原话对比"韩国和巴西的军事实力"。
传统rag知识库强行使用用户原话检索和生成，检索不到相关原文，导致ai瞎几把乱回答。

但是nbrag不一样，nbrag是ai根据上下文，以及根据上一步检索到的结果，
持续多轮换语义检索语句和bm25检索关键词描点，轻松分别找到韩国和巴西的各项军事指标。
然后ai根据多轮检索的两国军力的内容，再生成答案，那么其结果是远远暴击传统rag方式。
```


### 对比总结

| 维度 | 传统 RAG | Agentic RAG（nbrag） |
| --- | --- | --- |
| 残缺 query | 裸检索，无语义信号 | LLM 结合上文补全指代 |
| 检索目标 | 找"最像的文本片段" | 找"拼起来能回答的知识" |
| 跨文档综合 | 语料没有对比原话就嗝屁 | 各国知识分头检索、最后拼装 |
| 多轮状态 | 每轮独立、无记忆 | 记住已查数据，第二轮只补俄罗斯 |
| 检索通道 | 单一向量相似度 | 语义 query + BM25 词面锚点 双通道 |
| 知识自检 | 不知道缺什么 | 知道缺哪个国家的数据，继续查 |
| 错误补救 | 无，一把梭 | 多轮扩读、重检、修正 |
| 最终回答 | 抄不到现成段落就编 | 数据支撑的综合对比 |

**一句话总结**：传统 RAG 是"给什么查什么、查像的、抄现成的"；Agentic RAG 是"想清楚再查、查不到再查、记住查过的、拼装知识回答"——这就是 nbrag 和传统 RAG 的本质差距。



## License

MIT
