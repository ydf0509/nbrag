---
name: nbrag-workflow
version: "1.2.0"
description: >-
  Use when answering questions from an existing nbrag knowledge base / 已准备好的知识库,
  including docs, laws, manuals, business text, code, or other stored text. Trigger on 知识库、搜索、
  查定义、某某库怎么用、查法条、查询已准备内容。
---

# nbrag 知识库检索工作流

nbrag 提供 11 个 MCP 检索工具 + `nbrag_help` 导航工具，核心分三类：**发现 → 检索 → 深入**。

> **注意**：本文档中的函数名是 nbrag MCP 自身的函数名。当 nbrag 被接入其他 Agent 框架时，
> 函数名会带前缀（如变成 mcp__xxx__nbrag_search），AI 应以实际接收到的 function 名称为准。

## 快速决策：用哪个工具？

**核心原则：默认用 `nbrag_search_and_fetch`，它会同时给搜索命中和原文证据，避免只拿碎片 chunk 就回答。**

如果没有加载本 Skill 或不确定下一步，先调用 `nbrag_help` 获取 MCP 内置的简短组合拳指南。

| 用户问的是什么 | 工具 | 备注 |
|---|---|---|
| 不确定该用哪个 nbrag 工具 | `nbrag_help` | 无参数，返回简短 workflow |
| 知识/用法/示例问题（"试用期合法吗" / "设备报警码E42" / "create_agent怎么用"） | **`nbrag_search_and_fetch`** | 默认首选，一步到位 |
| 需要精细控制（禁用 BM25/rerank、只要 metadata、调整召回数量） | `nbrag_search` | 仅高级场景 |
| 精确字符串/术语/条文编号（"第一千零七十七条" / "ThreadPool"） | `nbrag_grep` | 正则匹配，返回上下文 |
| Python 精确符号名（"UserService 在哪定义"） | `nbrag_find_definition` | Python .py 专用增强；非 Python 内容用 `nbrag_grep` |
| 已知文件名或路径片段，需要完整路径 | `nbrag_find_files` | 返回可用于 `file_path` / `filter_file_path` 的完整绝对路径 |

**搜索上限**：10 轮不同策略和关键词都没找到 → 告知用户"知识库中可能没有相关内容"，不要无限重试。

## 文件类型与功能支持

| 内容类型 | `nbrag_search` | `nbrag_grep` | `nbrag_find_definition` | AST scope |
|---|---|---|---|---|
| `.md` / `.txt` / `.html` 等文档 | ✅ | ✅ | 不推荐，改用 `nbrag_grep` | ❌ |
| `.py` 源码 | ✅ | ✅ | ✅ AST 精确解析 | ✅ |

## Python source workflow / Python 源码检索

Python source workflow is a first-class nbrag use case, but it should not rely on one tool only. For `.py` files, chunks include file path, line range, AST scope, and signature metadata.

推荐组合：

1. `nbrag_search_and_fetch` — 找概念、示例、调用关系方向，并自动读取命中文件原文。
2. `nbrag_grep` — 查精确 class/function 名、import、常量、decorator、错误字符串、配置 key。
3. `nbrag_find_definition` — 仅对 Python `.py` 文件，读取完整 class/function/method 定义。
4. `nbrag_get_raw_file` — 用完整绝对 `file_path` 读取更大的源码上下文。

非 Python 文档、法律、手册不要套用符号定义工具；查条文、标题、术语、编号时继续优先 `nbrag_search_and_fetch` + `nbrag_grep`。

## 检索策略

### 策略 A（默认首选）：一站式检索

```
nbrag_search_and_fetch(query="...", collection_name="xxx")
```

- 语义搜索 + 自动抓取匹配文件的原文，**一次调用获得完整上下文，避免碎片化 chunk**
- 小文件抓全文，大文件抓匹配位置附近 N 行（默认 ±100 行）
- `fetch_top_n_raw=3` 控制抓几个文件原文（设 0 跳过抓取）
- 同一文件多次命中只抓一次（合并行范围）
- 结果格式：`[1/5] file_path dist:0.1234` → 搜索排名 → 原文内容
- 支持 `filter_file_path` 用搜索结果里的完整绝对 `file_path` 精确限定文件

### 策略 B：精细搜索

```
nbrag_search(query="...", collection_name="xxx", top_k=5)
```

- Vector + BM25 → RRF 融合 → Rerank 精排
- 可选：`use_bm25=False`、`use_rerank=False`、`include_content=False`、`preview_chars=1200`、`filter_file_path="D:/docs/labor_law/劳动合同法.md"`（必须是完整绝对路径）
- 返回 chunk preview，可能被截断（加 `...`）
- 关键字段：`chunk:X/Y`、`line:N-M`、`scope`（仅 Python）、`doc_id`、`file_path`、`dist`
- **大多数场景用策略 A 就够了，策略 B 仅用于需要精细控制的场景**

### 策略 C：精确匹配

```
nbrag_grep(keyword="第十九条", collection_name="xxx")
```

- 搜索已存储原文（非向量库），适合精确字符串
- `context_lines=10` 控制上下文（默认 10，匹配行前后各 N 行）
- 可选 `case_sensitive=True`、`filter_file_path="D:/docs/labor_law/劳动合同法.md"`（必须是完整绝对路径）
- `>>>` 标记匹配行

### 策略 D：Python 符号定义（源码专用增强）

```
nbrag_find_definition(symbol="get_by_id", collection_name="xxx")
```

- Python：AST 精确解析，返回 class/function 完整定义 + 方法签名列表
- 非 Python 内容不要优先用它；查条文、标题、术语、错误码请用 `nbrag_grep`
- `max_results=3`（默认）。公共符号可先设 `max_results=1`，需要候选对比时再加大

## 深入：获取更多上下文

| 工具 | 场景 | 关键参数 |
|------|------|---------|
| `nbrag_find_files` | 根据文件名/路径片段找到完整路径 | `pattern`, `case_sensitive=False` |
| `nbrag_get_raw_file` | 看完整文件（无 overlap） | 完整绝对 `file_path`, `line_start`, `line_end` |
| `nbrag_get_adjacent_chunks` | 扩展搜索结果的上下文 | `doc_id`, `chunk_index`, `window=3` |
| `nbrag_get_chunks_by_lines` | 按行号取 chunk | `doc_id`, `line_start`, `line_end` |
| `nbrag_get_file_chunks` | 分页浏览（有 scope） | 完整绝对 `file_path`, `start_chunk=0`, `max_chunks=10` |

**路径规则**：所有需要 `file_path` / `filter_file_path` 的工具，都必须传搜索结果、`nbrag_find_files` 或 `nbrag_list` 返回的完整绝对路径。不要传 `劳动合同法.md`、`core.py`、`src/core.py` 这类短路径或相对路径。

## 推荐调用流程

```
nbrag_stats()                         # 1. 确定知识库名
    ↓
nbrag_search_and_fetch()              # 2. 默认首选（一步拿到搜索+原文）
    ↓                                #   如需精细控制：nbrag_search()
nbrag_grep()                          # 3. 精确定位术语/条文/标题/关键词
    ↓                                #   Python 源码符号可插入 nbrag_find_definition()
nbrag_find_files()                    # 4. 只有文件名/路径片段时，先换成完整 file_path
    ↓
nbrag_get_raw_file() / nbrag_get_adjacent_chunks()  # 5. 扩展上下文
    ↓
跨资料追踪：需要更多证据 → 重复 2-5；Python 源码遇到未知符号也重复
```

## 多轮检索策略

**核心原则**：不要把用户问题原封不动丢给搜索，主动拆解改写。

**示例**：用户问 "公司让我试用期干了5个月不转正，签的1年合同，合法吗？"
- 第1轮: `nbrag_search_and_fetch("试用期 最长期限 1年合同")` → 找到试用期上限
- 第2轮: `nbrag_search_and_fetch("违法约定试用期 赔偿")` → 找到赔偿标准
- 第3轮: `nbrag_grep("第十九条")` → 精确定位法条原文

搜索不理想时的策略：换关键词 → 换工具（语义→grep）→ 用 `nbrag_find_files` 找完整路径后缩小文件范围 → 跨 collection

## 常见问题速查

| 症状 | 原因 | 解决 |
|------|------|------|
| collection 不存在 | 知识库未准备好或名称错误 | `nbrag_stats()` 确认名称 |
| 搜索返回空 | 无匹配、关键词不合适、或 collection 名称不对 | 换关键词 / 用 `nbrag_stats` 确认知识库名 |
| `nbrag_grep` / `nbrag_find_definition` 无结果 | 没有精确匹配，或该内容不适合该工具 | 换关键词 / 改用 `nbrag_search_and_fetch` |
| 想查 .md/.txt 条文、标题、术语却用了 `nbrag_find_definition` | 该工具是 Python 源码专用增强 | 改用 `nbrag_grep` |

**详细错误信息**：各工具的报错信息在 MCP 工具描述中已注明，AI 应根据返回的错误信息判断原因。

## 可选只读管理工具

- `nbrag_list` — 除非用户明确要求列出文档
