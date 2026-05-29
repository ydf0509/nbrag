# nbrag — AI Agent 指令

## 项目概览

Agentic RAG MCP Server。Python 3.11+，FastMCP，ChromaDB，SiliconFlow Embedding/Rerank。

架构：4 个核心模块，扁平包布局（无 `src/` 目录）。

| 模块 | 职责 |
|------|------|
| `nbrag/server.py` | 12 个 MCP 工具，CLI 入口 (`main()`) |
| `nbrag/core.py` | Embedding/Rerank API 调用，ChromaDB CRUD，文件导入 |
| `nbrag/chunker.py` | 文本切分，行号计算，Python AST 作用域解析 |
| `nbrag/config.py` | 配置加载：CLI > 环境变量 > YAML > 默认值 |

## 构建与测试

```bash
# 开发模式安装
pip install -e ".[dev]"

# 启动 MCP 服务（stdio 模式）
python -m nbrag

# 启动 MCP 服务（HTTP 模式）
python -m nbrag --transport streamable-http --port 9101

# 类型检查
mypy nbrag/

# 运行测试
python -m pytest tests/ -x -v
```

## 代码规范

### 必须

- 数据导入函数使用 `ingest_` 前缀（不用 `import_`，避免与 Python 关键字混淆）。
- `core.py` 所有公开函数必须有文档字符串。
- MCP 工具描述必须用英文（AI 解析英文工具文档更准确）。
- MCP 工具文档字符串必须包含"后续工具"或"典型工作流"提示。
- 配置优先级：CLI 参数 > 环境变量 > YAML 文件 > 硬编码默认值。
- 存入 ChromaDB metadata 前，文件路径必须通过 `_normalize_path()` 统一格式。
- `chunker.py` 不允许依赖 ChromaDB 或 config 模块 —— 它只做文本处理。

### 禁止

- 禁止硬编码 API 密钥或敏感信息。
- 禁止使用 `import_` 作为函数前缀（用 `ingest_` 代替）。
- 禁止在文档字符串或 README 中使用 funboost 专属示例 —— 使用通用示例。
- 禁止向 `FastMCP()` 构造函数传 `port` 参数 —— 用 `mcp.settings.port` 动态设置。
- 禁止创建大而全的 MCP 工具加 `mode` 参数 —— 每个工具职责单一。
- 禁止从 `learn_agent` 导入任何内容 —— 本项目完全独立。

### 风格

- 可使用 Python 3.11+ 语法（match/case、`Self` 类型等）。
- 文档字符串：模块级用中文，MCP 工具描述用英文。
- 配置结构用 `dataclass`（不用 Pydantic，保持简洁）。
- MCP 工具参数用 `pydantic.Field`（FastMCP 要求）。

## 架构决策

### 双存储

ChromaDB 存向量化 chunks（有 overlap），用于语义搜索。
`raw_files/` 存原始文件快照（无 overlap），用于精确行号读取。
两者缺一不可，不要移除任何一个。

### 12 个工具，不是 3 个

每个 MCP 工具职责单一、参数最少。
一个大而全的 `rag_query(mode=...)` 会导致 AI 在参数选择上产生幻觉。
新增工具时遵循同样的模式：清晰的命名、聚焦的功能、文档字符串中的工作流提示。

### AST 作用域注入

Python 文件的 chunk 在 embedding 前注入 `[File:] [Scope:] [Sig:] [Lines:]` 头部。
这显著提升了代码查询的搜索精度。
逻辑在 `chunker.py` 中 —— 不要混入 `core.py`。

### Metadata 字段

每个 chunk 在 ChromaDB 中存储 8 个 metadata 字段：
`source`、`filename`、`doc_id`、`chunk_index`、`total_chunks`、`line_start`、`line_end`、`scope`。

不要删除或重命名这些字段 —— 下游工具依赖它们。

## 文件组织

```
nbrag/          # 包根目录
  __init__.py            # 仅版本号
  __main__.py            # python -m 入口
  config.py              # dataclass 配置 + YAML 加载
  chunker.py             # 文本切分 + AST（无存储依赖）
  core.py                # ChromaDB + Embedding + Rerank + ingest
  server.py              # 12 个 MCP 工具 + CLI main()
scripts/                 # 用户便捷脚本（不属于包）
  start_http_rag_mcp.py  # 快速启动 HTTP 服务
  ingest_project.py      # 批量导入模板
  ingest_funboost.py     # 示例：导入 funboost 项目
```

## 新增 MCP 工具步骤

1. 在 `core.py` 实现核心逻辑（返回 dict，不返回格式化字符串）。
2. 在 `server.py` 添加 MCP 包装器，使用 `@mcp.tool()` 装饰器。
3. 所有参数使用 `pydantic.Field`，写清晰的 `description`。
4. 文档字符串中包含工作流提示：下一步该调用什么工具。
5. 更新 `README.md` 中的工具表格。
6. 如果架构有变化，同步更新本文件的模块表格。

## 依赖

| 包 | 用途 | 版本 |
|----|------|------|
| `mcp` | FastMCP 服务框架 | >=1.0.0 |
| `httpx` | Embedding/Rerank HTTP 客户端 | >=0.24.0 |
| `chromadb` | 本地向量数据库 | >=0.4.0 |
| `langchain-text-splitters` | 代码感知文本切分 | >=0.2.0 |
| `pydantic` | MCP 工具参数校验 | >=2.0.0 |
| `pyyaml` | YAML 配置文件解析 | >=6.0 |

不要添加重型依赖（torch、transformers 等）—— embedding 通过 API 调用完成。

## python 解释器要求

ai运行此项目脚本时候使用我本地的python解释器 D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/start_http_rag_mcp.py