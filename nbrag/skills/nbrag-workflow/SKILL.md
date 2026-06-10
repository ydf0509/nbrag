---
name: nbrag-workflow
version: "1.2.0"
description: >-
  当用户的问题涉及已导入 nbrag 知识库的内容时使用此 Skill。
  前提：相关知识必须已经通过 nbrag_add_document 导入并向量化，先用 nbrag_stats 确认知识库存在。
  通过多轮检索基于真实内容回答，避免幻觉。适用于代码、文档、法律、历史等任何已导入的知识领域。
  触发词：知识库、搜索、查定义、某某库怎么用、查法条、查询已导入的内容。
---

# nbrag 知识库检索工作流

nbrag 提供 12 个 MCP 工具，核心分三类：**发现 → 检索 → 深入**。

> **注意**：本文档中的函数名是 nbrag MCP 自身的函数名。当 nbrag 被接入其他 Agent 框架时，
> 函数名会带前缀（如变成 mcp__xxx__nbrag_search），AI 应以实际接收到的 function 名称为准。

## 快速决策：用哪个工具？

**核心原则：默认用 `nbrag_search_and_fetch`，它是打包好的最佳实践，省 token、省 round-trip。**

| 用户问的是什么 | 工具 | 备注 |
|---|---|---|
| 知识/用法/示例问题（"create_agent怎么用" / "离婚财产怎么分"） | **`nbrag_search_and_fetch`** | 默认首选，一步到位 |
| 需要精细控制（禁用 BM25、指定 chunk 数、按文件名过滤） | `nbrag_search` | 仅高级场景 |
| 精确符号名（"UserService 在哪定义"） | `nbrag_find_definition` | Python .py 最佳，非 .py 回退 regex |
| 精确字符串/术语/条文编号（"ThreadPool" / "第一千零七十七条"） | `nbrag_grep` | 正则匹配，返回上下文 |

**搜索上限**：10 轮不同策略和关键词都没找到 → 告知用户"知识库中可能没有相关内容"，不要无限重试。

## 文件类型与功能支持

| 导入类型 | `nbrag_search` | `nbrag_grep` | `nbrag_find_definition` | AST scope |
|---|---|---|---|---|
| `.py` 源码 | ✅ | ✅ | ✅ AST 精确解析 | ✅ |
| `.md` / `.txt` 等 | ✅ | ✅ | ⚠️ regex 回退 | ❌ |

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
- 不支持 `filter_filename`

### 策略 B：精细搜索

```
nbrag_search(query="...", collection_name="xxx", top_k=5)
```

- Vector + BM25 → RRF 融合 → Rerank 精排
- 可选：`use_bm25=False`、`use_rerank=False`、`filter_filename="core.py"`（精确匹配文件名）
- 返回 chunk preview，可能被截断（加 `...`）
- 关键字段：`chunk:X/Y`、`line:N-M`、`scope`（仅 Python）、`doc_id`、`file_path`、`dist`
- **大多数场景用策略 A 就够了，策略 B 仅用于需要精细控制的场景**

### 策略 C：精确匹配

```
nbrag_grep(keyword="UserService", collection_name="xxx")
```

- 搜索 raw cache 文件的原始内容（非向量库），适合精确字符串
- `context_lines=10` 控制上下文（默认 10，匹配行前后各 N 行）
- 可选 `case_sensitive=True`、`filter_filename="core.py"`
- `>>>` 标记匹配行

### 策略 D：符号定义

```
nbrag_find_definition(symbol="get_by_id", collection_name="xxx")
```

- Python：AST 精确解析，返回 class/function 完整定义 + 方法签名列表
- 非 Python：regex 回退，每个文件最多 1 处匹配，约 24 行上下文
- `max_results=5`（默认）

## 深入：获取更多上下文

| 工具 | 场景 | 关键参数 |
|------|------|---------|
| `nbrag_get_raw_file` | 看完整文件（无 overlap） | `file_path`, `line_start`, `line_end` |
| `nbrag_get_adjacent_chunks` | 扩展搜索结果的上下文 | `doc_id`, `chunk_index`, `window=3` |
| `nbrag_get_chunks_by_lines` | 按行号取 chunk | `doc_id`, `line_start`, `line_end` |
| `nbrag_get_file_chunks` | 分页浏览（有 scope） | `file_path`, `start_chunk=0`, `max_chunks=10` |

## 推荐调用流程

```
nbrag_stats()                         # 1. 确定知识库名
    ↓
nbrag_search_and_fetch()              # 2. 默认首选（一步拿到搜索+原文）
    ↓                                #   如需精细控制：nbrag_search()
nbrag_grep() / nbrag_find_definition() # 3. 精确定位符号/术语
    ↓
nbrag_get_raw_file() / nbrag_get_adjacent_chunks()  # 4. 扩展上下文
    ↓
跨文件追踪：遇到未知符号 → 重复 2-4
```

## 多轮检索策略

**核心原则**：不要把用户问题原封不动丢给搜索，主动拆解改写。

**示例**：用户问 "公司让我试用期干了5个月不转正，签的1年合同，合法吗？"
- 第1轮: `nbrag_search_and_fetch("试用期 最长期限 1年合同")` → 找到试用期上限
- 第2轮: `nbrag_search_and_fetch("违法约定试用期 赔偿")` → 找到赔偿标准
- 第3轮: `nbrag_grep("第十九条")` → 精确定位法条原文

搜索不理想时的策略：换关键词 → 换工具（语义→grep）→ 缩小文件范围 → 跨 collection

## 常见问题速查

| 症状 | 原因 | 解决 |
|------|------|------|
| collection 不存在 | 未导入或名称错误 | `nbrag_stats()` 确认名称 |
| 搜索返回空 | 无匹配或 raw cache 缺失 | 换关键词 / 重导入 |
| `nbrag_grep` / `nbrag_find_definition` 静默无结果 | raw cache 缺失或无匹配 | 用 `nbrag_stats` 确认 |
| `nbrag_find_definition` 对 .md 无效 | AST 仅解析 .py | 改用 `nbrag_grep` |

**详细错误信息**：各工具的报错信息在 MCP 工具描述中已注明，AI 应根据返回的错误信息判断原因。

## 能力边界

- ❌ 只检索已导入内容，不生成新内容
- ❌ 不导入文档（由用户手动操作）
- ❌ 不修改文件，只读取和搜索
- ✅ 超出知识库范围的，如实告知

## AI 不需要调用的工具

- `nbrag_add_document` — 用户手动导入
- `nbrag_delete` — 用户手动操作
- `nbrag_list` — 除非用户明确要求列出文档