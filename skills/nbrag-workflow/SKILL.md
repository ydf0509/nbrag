---
name: nbrag-workflow
description: >-
  使用 nbrag 知识库进行多轮智能检索。当用户询问代码实现、
  查找函数定义、理解项目结构、搜索文档内容、或提到"知识库""搜索代码"时使用。
  ai要注意，这里面的函数指的是nbrag mcp自身的函数名字，当mcp被接入其他agent时候，暴露给ai的function名字会加一些前缀，比如举个例子 nbrag_search 工具 可能会变成 mcp__my_rag__nbrag_search暴露给ai，ai要根据实际请求中的fucntion的名字为准，不要死搬硬套用这个skill中的描述的函数名。
---

# RAG 知识库检索工作流

nbrag 提供 12 个 MCP 工具，核心分三类：**发现 → 检索 → 深入**。


## 前提

- 以下 4 个工具依赖导入时的 raw cache：`nbrag_grep`、`nbrag_find_definition`、`nbrag_get_raw_file`、`nbrag_search_and_fetch`。
  - `nbrag_get_raw_file` 缺 cache 时报：`Raw file cache not found (doc_id=...). This file may have been imported before caching was enabled. Please re-import.`
  - `nbrag_search_and_fetch` 缺 cache 时报：`[{file_path}] raw cache not available`
  - `nbrag_grep` / `nbrag_find_definition` 缺 cache 时**静默返回空结果**（不报错），表现与"真的没有匹配"相同——如果怀疑是 cache 缺失，先用 `nbrag_stats` 确认 collection 存在且有 chunks。
- chunk 正文开头含注入 header（非原始源码），格式因上下文而异：
  - 模块级函数：`# [File: path] [Scope: func_name] [Sig: def func(...)] [Lines: N-M]`
  - 类体级：`# [File: path] [Scope: ClassName] [Sig: class ClassName(Base)] [Lines: N-M]`
  - 类方法：`# [File: path] [Class: class ClassName(Base)] [Method: method_name] [Sig: def method(...)] [Lines: N-M]`
  - 若无 `parent_class_sig` 回退为 `[Class: ClassName]`（无基类签名）
  - `[Sig]`、`[Lines]`、`[Class]` 部分字段可能缺失。

## 第一步：发现

```
nbrag_stats()
```

返回：所有 collection 名称、文档/chunk 数、embedding/rerank 模型、data_dir、chunk_size/chunk_overlap。
首次使用或不确定 collection 名称时先调用。已知名称可直接检索。
注意：仅 `nbrag_search` / `nbrag_search_and_fetch` 在 collection 不存在时会提示 `Available collections: [...]`，
`nbrag_grep` / `nbrag_find_definition` 不会提示（静默返回空）。

## 第二步：检索

### 策略 A：语义搜索（推荐首选）

```
nbrag_search(query="用户的问题", collection_name="xxx", top_k=5)
```

- 向量召回 + rerank 精排（rerank 需配置且召回数 > top_k 才生效，失败静默降级）
- 可选 `use_rerank=False` 禁用 rerank
- 适合自然语言提问："这个项目怎么处理并发？"
- 可选 `filter_filename="core.py"` 缩小搜索范围（仅匹配文件名，非完整路径）
- 返回每条结果包含两行：
  - 标题行：`[1/5] filename chunk:X/Y line:N-M scope:xxx doc_id:xxx dist:0.1234`
  - 路径行：`file_path: /absolute/path/to/file`
- 关键字段：`chunk:X/Y`（chunk 索引/总数）、`line:N-M`、`scope`（仅 Python）、`doc_id`、`dist`（cosine 距离，越小越相似）
- chunk preview 可能被截断（加 `...`）

### 策略 B：精确搜索（补充语义搜索）

```
nbrag_grep(keyword="UserService", collection_name="xxx")
```

- 关键词/正则匹配，搜索 raw cache 文件（非向量库）
- 适合搜索确切的类名、函数名、变量名、错误信息
- 可选：`max_results=10`（默认）、`case_sensitive=True`（默认 False）、`filter_filename="core.py"`、`context_lines=10`（默认 10）
- 返回匹配行及上下文，`>>>` 标记匹配行

### 策略 C：符号查找

```
nbrag_find_definition(symbol="get_by_id", collection_name="xxx")
```

- **Python 文件**：AST 精确解析，返回 class/function 完整定义 + class 方法签名列表。AST 解析失败（语法错误）的文件会被静默跳过。
- **非 Python 文件**：正则匹配，`symbol_type` 为 `unknown`，每个文件最多返回 1 处匹配，仅约 23 行上下文（前 3 行 + 后 20 行），非完整定义。
- 可选 `max_results=5`（默认）
- 支持 qualified name：`symbol="MyClass.__init__"`

### 策略 D：一站式检索（省一轮调用）

```
nbrag_search_and_fetch(query="...", collection_name="xxx", top_k=5)
```

- 语义搜索 + 自动抓取 top N 结果的 raw 源码（省去单独调用 `nbrag_get_raw_file`）
- 小文件（≤ 2×context_lines 行）抓全文；大文件只抓匹配位置 ±context_lines 行 excerpt
- 可选：`fetch_top_n_raw=3`（默认 3，设 0 跳过抓取）、`context_lines=100`（默认）
- 同一 `doc_id` 多次命中会合并行范围只抓取一次
- **限制**：不支持 `filter_filename`，始终启用 rerank
- 需要完整源码请再用 `nbrag_get_raw_file`

## 第三步：深入

检索结果通常是代码片段（chunk），需要更多上下文时选择：

| 工具 | 特点 | 适用场景 |
|------|------|---------|
| `nbrag_get_raw_file` | 无 overlap 的干净源码，无 scope | 看完整文件或指定行号范围 |
| `nbrag_get_file_chunks` | 有 scope 元数据，chunk 间有 200 字符 overlap | 分页浏览 + 了解作用域 |
| `nbrag_get_adjacent_chunks` | 有 scope，有 overlap | 扩展搜索结果的上下文 |
| `nbrag_get_chunks_by_lines` | 有 scope，有 overlap | 按行号精确取 chunk |

### 看原始文件

```
nbrag_get_raw_file(file_path="从搜索结果获取", collection_name="xxx")
```

- 支持 `line_start` / `line_end` 指定范围（1-based），默认 -1 表示读全文
- 大文件返回后会提示 `(N lines remaining, use line_start=... to continue)`
- `file_path` 也可只传文件名（如 `"core.py"`）

### 看相邻代码块

```
nbrag_get_adjacent_chunks(doc_id="从搜索结果获取", chunk_index=3, collection_name="xxx", window=3)
```

- `chunk_index` 从搜索结果的 `chunk:X/Y` 中取 X
- `window` 默认 3，返回 chunk_index ± 3（最多 7 个 chunk）

### 按行号获取

```
nbrag_get_chunks_by_lines(doc_id="...", line_start=50, line_end=100, collection_name="xxx")
```

### 分页浏览文件

```
nbrag_get_file_chunks(file_path="...", collection_name="xxx", start_chunk=0, max_chunks=10)
```

- 与 `nbrag_get_raw_file` 的区别：有 scope 元数据 + chunk 间有 overlap，适合需要作用域信息的场景

## 推荐调用顺序

```
nbrag_stats()                          # 1. 发现知识库
    ↓
nbrag_search() / nbrag_grep()            # 2. 检索（可多次、换策略）
    ↓                                # 快捷路径：直接 nbrag_search_and_fetch() 一步到位
nbrag_find_definition()                # 3. 需要完整 class/function 定义时（Python 最佳）
    ↓
nbrag_get_raw_file()                   # 4. 看完整源码（无 overlap，无 scope）
或 nbrag_get_adjacent_chunks()          #    或扩展上下文（有 scope）
或 nbrag_get_chunks_by_lines()          #    或按行号取 chunk（有 scope）
或 nbrag_get_file_chunks()              #    或分页浏览全文件 chunks（有 scope）
    ↓
跨文件追踪：遇到未知符号 → 重复 2-4
```

## 多轮检索策略

如果第一轮搜索结果不理想：

1. **换关键词**：用同义词或更具体/更宽泛的词重新 `nbrag_search`
2. **换策略**：语义搜索不行就试 `nbrag_grep` 精确搜索
3. **缩小范围**：用 `filter_filename` 限定文件（仅 `nbrag_search` / `nbrag_grep` 支持）
4. **查定义**：找到了引用但不知道定义在哪 → `nbrag_find_definition`
5. **跨 collection**：不同知识库可能有不同内容

## 常见错误处理

### Collection 不存在

| 工具 | 返回信息 |
|------|---------|
| `nbrag_search` / `nbrag_search_and_fetch` | `collection 'xxx' does not exist. Available collections: [...] Use nbrag_add_document to create and import docs.` |
| `nbrag_grep` / `nbrag_find_definition` | **静默返回空**（与"无匹配"不可区分） |

→ 建议：用 `nbrag_stats()` 确认 collection 名称。

### Collection 为空

| 工具 | 返回信息 |
|------|---------|
| `nbrag_search` / `nbrag_search_and_fetch` | `collection 'xxx' is empty. Use nbrag_add_document to import docs first.` |

### Raw cache 缺失

| 工具 | 返回信息 |
|------|---------|
| `nbrag_get_raw_file` | `Raw file cache not found (doc_id=...). This file may have been imported before caching was enabled. Please re-import.` |
| `nbrag_search_and_fetch` | `[{file_path}] raw cache not available` |
| `nbrag_grep` / `nbrag_find_definition` | **静默返回空** |

→ 建议：重新导入该文件/目录。

### 其他常见错误

| 返回信息 | 含义 | 建议动作 |
|----------|------|---------|
| `No results (collection has N chunks, filter: xxx)` | 搜索无匹配 | 换关键词或去掉 filter |
| `No definition found ... Try nbrag_grep` | 符号未找到（或 AST 解析失败） | 用 `nbrag_grep` 扩大搜索 |
| `File not found: 'xxx'` | 文件路径或文件名不存在 | 检查路径是否正确 |
| `Document not found: 'xxx'` | 文档 ID 不存在 | 用 `nbrag_list` 查看有效 doc_id |
| `No chunks matching line range ...` | 行号范围内无 chunk | 调整行号或用 `nbrag_get_raw_file` |
| `[path] excerpt failed` | 自动抓取源码失败 | 改用 `nbrag_get_raw_file` 手动抓取 |

## 不需要 AI 调用的工具

以下工具通常由用户手动操作：

- `nbrag_add_document` — 知识库导入（人工一次性批量操作）
- `nbrag_delete` — 删除文档
- `nbrag_list` — 列出文档（除非用户明确要求）
