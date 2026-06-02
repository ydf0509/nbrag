# nbrag

**Agentic RAG MCP Server** — 基于 MCP 协议的智能知识库，可导入代码、文档、小说等任意文本，尤其对 Python 项目有奇效（AST 自动解析 class/function 作用域，搜索精准度远超普通 RAG）。支持接入任何 MCP 兼容的 AI 产品：Cursor、OpenCode、Claude Code、Cherry Studio、Open WebUI、Dify、Cline 等，也可嵌入用户自己开发的具备 ReAct Loop 的 Agent 程序。

AI Agent 自主决定何时搜、搜什么、搜几次。12 个精心设计的互补 MCP 工具，吊打传统一轮检索的 Naive RAG。

## 为什么不是 Naive RAG？

| | Naive RAG | **Agentic RAG (本项目)** |
|---|-----------|----------------------|
| 检索触发 | 每次提问自动检索 top-5 注入 | AI 自主决定是否检索、用哪个工具 |
| 检索轮次 | 1 次 | 多轮（实测 m 次搜索 + n 次文件读取） |
| 查询构造 | 用户原文 | AI 重写查询、组合多种检索策略 |
| 工具种类 | 仅语义搜索 | 语义 + grep + AST 符号定位 + 原文读取 |
| 分析深度 | 浅层描述 | 完整的跨文件调用链图 |
| 准确度 | 浅层匹配，容易遗漏 | **显著优于 Naive RAG**，跨文件关联更完整 |

核心观点：**检索不是管道，是 Agent 的一种能力。**

## 快速开始

### 1. 安装

```bash
# 方式 A: uvx (推荐，零安装)
uvx nbrag

# 方式 B: pip
pip install nbrag
```

### 2. 配置 API Key

```bash
# SiliconFlow 免费 API Key (https://siliconflow.cn)
export NBRAG_API_KEY=sk-xxx
```

### 3. 在 Cursor / Claude Desktop 中配置 MCP

有三种配置方式，选一种即可：

#### 方式 A: uvx 启动（推荐，零安装）

```json
{
  "mcpServers": {
    "rag": {
      "command": "uvx",
      "args": ["nbrag"],
      "env": {
        "NBRAG_API_KEY": "sk-xxx"
      }
    }
  }
}
```

#### 方式 B: python 命令启动

```json
{
  "mcpServers": {
    "rag": {
      "command": "python",
      "args": ["-m", "nbrag"],
      "env": {
        "NBRAG_API_KEY": "sk-xxx"
      }
    }
  }
}
```

#### 方式 C: HTTP 模式（推荐多项目共享）

> **为什么选 HTTP？** stdio 模式下每个 IDE 窗口会各起一个独立进程。如果你同时打开了几十个项目，
> 就是几十个 Python 进程 + 几十份 ChromaDB 内存。HTTP 模式只跑一个服务进程，所有 IDE 共享同一个端口，
> 省内存，也避免多进程并发写同一个 ChromaDB 数据库的锁冲突。

先启动服务：

```bash
# uvx 方式
uvx nbrag --transport streamable-http --port 9101

# 或 python 方式
python -m nbrag --transport streamable-http --port 9101
```

再配置客户端：

```json
{
  "mcpServers": {
    "rag": {
      "type": "http",
      "url": "http://localhost:9101/mcp"
    }
  }
}
```

### 4. 导入知识库

#### 方式 A: 让 AI 自动导入

告诉 AI：

> "帮我把 D:/codes/my_project 导入到 myproject 知识库，然后搜索 XXX"

AI 会自动调用 `nbrag_add_document` 导入，再用 `nbrag_search` + `nbrag_grep` + `nbrag_find_definition` 多轮检索回答你的问题。

#### 方式 B: 手动脚本导入（推荐大项目）

手动导入更灵活——可以精确指定目录、过滤文件后缀、控制 chunk 参数：

```python
from nbrag.core import batch_ingest

batch_ingest(
    paths=[
        "D:/codes/my_project/src",     # 只导入 src 目录
        "D:/codes/my_project/docs",    # 加上文档目录
    ],
    collection_name="my_project",
    file_extensions=[".py", ".md"],    # 只要 Python 和 Markdown 文件
    delete_first=True,                 # 清空旧数据重新导入
    verbose=True,
)
```

参见 `scripts/ingest_project.py` 获取完整示例。

## 12 个工具

| 类别 | 工具 | 功能 |
|------|------|------|
| **导入** | `nbrag_add_document` | 导入文件/目录（自动分块 + Embedding + 缓存原文） |
| **语义检索** | `nbrag_search` | 向量搜索 + Rerank 精排 |
| **语义检索** | `nbrag_search_and_fetch` | 搜索 + 自动取源码（省一次 round-trip） |
| **精确检索** | `nbrag_grep` | 关键词/正则搜索（和语义搜索互补） |
| **精确检索** | `nbrag_find_definition` | AST 精确定位 class/function 完整定义 |
| **上下文扩展** | `nbrag_get_file_chunks` | 按 chunk 分页浏览文件 |
| **上下文扩展** | `nbrag_get_raw_file` | 读取无 overlap 的原始文件 |
| **上下文扩展** | `nbrag_get_adjacent_chunks` | 获取相邻 chunks |
| **上下文扩展** | `nbrag_get_chunks_by_lines` | 按行号范围取 chunks |
| **管理** | `nbrag_list` | 列出知识库所有文档 |
| **管理** | `nbrag_delete` | 删除指定文档 |
| **管理** | `nbrag_stats` | 知识库统计信息 |

### Skill 指南（教 AI 打组合拳）

12 个工具暴露给 AI 后，AI 只知道"能调什么"，不知道"按什么顺序调"。
项目附带一个 Skill 文件，打包在 `nbrag` 包内，把最佳检索流程写成 AI 能读懂的指南。

**使用方法**：从 pip 安装路径复制到你项目的 Skills 目录，AI 就自动学会多轮检索策略。

```bash
# 先获取 skill 路径
SKILL_PATH=$(python -c "import nbrag, os; print(os.path.join(os.path.dirname(nbrag.__file__), 'skills', 'nbrag-workflow'))")

# Cursor
cp -r $SKILL_PATH .cursor/skills/

# Claude Code
cp -r $SKILL_PATH .claude/skills/

# nb_agent
cp -r $SKILL_PATH .nb_agent/skills/

# OpenAI Codex / Gemini CLI /nb_agent（跨平台标准）
cp -r $SKILL_PATH .agents/skills/
```

Skill 内容包括：发现（nbrag_stats）→ 检索（4 种策略选择）→ 深入（4 种上下文获取方式）→ 多轮重试策略。

### AI 推荐的深度分析工作流

```
1. nbrag_search → 找到相关文件和大致位置
2. nbrag_grep → 精确定位类名/方法名/常量（语义搜索漏掉的）
3. nbrag_find_definition → 获取完整的类/函数定义源码
4. nbrag_get_raw_file → 读取完整源码验证细节
5. 跨文件追踪：发现未知符号时重复 2-4 步
```

## 向量数据库 Metadata 字段

每个 chunk 入库时除了 embedding 向量，还存储了丰富的 metadata。这是很多 RAG 方案忽略的关键设计——有了 metadata，才能实现按文件过滤、按行号定位、按作用域追踪等高级能力。

| 字段 | 类型 | 示例 | 说明 |
|------|------|------|------|
| `source` | str | `D:/codes/myproject/core.py` | 文件绝对路径（跨平台统一格式） |
| `filename` | str | `core.py` | 文件名（方便 `filter_filename` 过滤） |
| `doc_id` | str | `a1b2c3d4e5f6` | 路径 MD5 前 12 位（文件唯一标识） |
| `chunk_index` | int | `3` | 当前 chunk 在文件中的序号（0-based） |
| `total_chunks` | int | `15` | 该文件的总 chunk 数 |
| `line_start` | int | `45` | chunk 对应的起始行号（1-based） |
| `line_end` | int | `78` | chunk 对应的结束行号 |
| `scope` | str | `MyClass.my_method` | Python AST 解析的作用域（非 Python 文件为空） |

**chunk 头部注入示例**（embedding 前自动添加，提升搜索精度）：

```
# [File: D:/codes/myproject/core.py] [Class: class MyClass(Base)] [Method: process] [Sig: def process(self, data: dict)] [Lines: 45-78]
```

有了这些 metadata + 头部注入，`nbrag_search` 搜 "process 方法" 就能精准命中 `MyClass.process`，而不是随机匹配到别的 "process" 字符串。

## 配置

### 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `NBRAG_API_KEY` | **是** | | Embedding/Rerank API Key |
| `NBRAG_BASE_URL` | 否 | `https://api.siliconflow.cn/v1` | API Base URL |
| `NBRAG_EMBEDDING_MODEL` | 否 | `BAAI/bge-m3` | Embedding 模型 |
| `NBRAG_RERANK_MODEL` | 否 | `BAAI/bge-reranker-v2-m3` | Rerank 模型 |
| `NBRAG_DB_PATH` | 否 | `./rag_db` | ChromaDB 存储路径 |
| `NBRAG_CHUNK_SIZE` | 否 | `1500` | 分块大小 |
| `NBRAG_CHUNK_OVERLAP` | 否 | `200` | 分块重叠 |

### 配置文件 (可选)

支持 YAML 配置文件，自动搜索顺序：
1. `./nbrag_config.yaml`
2. `~/.config/nbrag/config.yaml`

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

### CLI 参数

```bash
nbrag --help
nbrag --transport stdio              # 默认
nbrag --transport streamable-http    # HTTP 模式
nbrag --api-key sk-xxx              # 直接传 API Key
nbrag --db-path /data/rag           # 指定存储路径
nbrag --config ./my_config.yaml     # 指定配置文件
```

## 设计决策

### 为什么 chunk_size = 1500？

BGE-M3 的最佳召回区间是 700-3000 字符。如果 chunk_size 设太小（如 500），一个 8000 字符的大类会被切成 40+ 块，语义搜索碎片化严重、召回率下降。1500 是实测平衡点，大多数函数/类能完整落入 1-2 个 chunk 内。

即使 chunk 切分不完美，Agentic RAG 也不会像 Naive RAG 那样只用碎片凑答案。AI 会自主判断当前 chunk 信息不足，然后调用 `nbrag_get_raw_file` 读完整源码、用 `nbrag_find_definition` 精确定位类/函数定义、用 `nbrag_grep` 全文搜索关键词，多轮组合直到信息充分。这正是 "检索是 Agent 的能力" 而非固定管道的意义。

### 为什么双存储？

- **ChromaDB**：存向量 chunks（有 overlap），用于语义搜索
- **raw_files/**：存原始文件快照（无 overlap），用于精确行号读取

AI 经常需要看完整源码，如果只有 chunks 会有 overlap 重复，浪费 token 还容易困惑。

### 为什么 AST scope 注入？

每个 chunk 的 embedding 前注入 `[File: path] [Scope: MyClass.my_method] [Sig: def my_method(self, x)]`。
这样搜索 "process 方法" 时更容易命中 `class DataProcessor` 下的 `def process(self, data)`，而不是随机匹配到别的 "process" 字符串。

### 为什么 12 个工具而不是 3 个？

MCP 工具设计原则：**职责单一、参数最少、docstring 引导下一步**。

一个大而全的 `rag_query(mode="search|grep|raw|...")` 会导致 AI 幻觉——它不知道该传什么参数。
拆成 12 个小工具后，每个工具参数清晰，AI 的调用准确率大幅提升。

## 技术栈

| 组件 | 选择 |
|------|------|
| Embedding | SiliconFlow BGE-M3（免费、中文最强之一） |
| Rerank | SiliconFlow BGE-Reranker-v2-m3（免费） |
| 向量数据库 | ChromaDB（本地持久化，无需外部服务） |
| 分块 | LangChain TextSplitter + 自研 AST 增强 |
| MCP | FastMCP (Python) |
| 传输 | stdio / streamable-http / SSE |

## License

MIT
