---
name: nbrag-workflow
version: "1.2.0"
description: >-
  用于回答基于已准备好的 nbrag 知识库的问题，尤其是在用户提到知识库检索、搜索已导入内容、查询某个项目/框架/文档怎么用、查源码定义、查条文、查手册、查资料时。
  适用于代码、文档、说明书、业务资料、规范、教程以及其他任意已入库文本，不要把它局限为某几个固定领域。
---

# nbrag 知识库检索工作流

nbrag 提供 10+ 个 MCP 检索工具 + `nbrag_help` 导航工具，核心分三类：**发现 → 检索 → 深入**。

> **注意**：本文档中的函数名是 nbrag MCP 自身的函数名。当 nbrag 被接入其他 Agent 框架时，
> 实际暴露的 function 名称可能带前缀（例如 `xxx_nbrag_search` 或 `mcp__xxx__nbrag_search`），AI 应以实际接收到的 function 名称为准。

## 快速决策：用哪个工具？

**核心原则：多数知识/用法/证据类问题可以先用 `nbrag_search_and_fetch`，但不要机械套流程；根据用户目标和返回内容决定是否继续调用其他工具。**

如果没有加载本 Skill 或不确定下一步，先调用 `nbrag_help` 获取 MCP 内置的简短组合拳指南。

| 用户问的是什么 | 工具 | 备注 |
|---|---|---|
| 不确定该用哪个 nbrag 工具 | `nbrag_help` | 无参数，返回简短 workflow |
| 知识/用法/示例问题（"试用期合法吗" / "设备报警码E42" / "create_agent怎么用"） | **`nbrag_search_and_fetch`** | 默认首选，一步到位 |
| 需要精细控制（禁用 BM25/rerank、只要 metadata、调整召回数量） | `nbrag_search` | 仅高级场景 |
| 想单独观察词法召回是否有效（术语、条文号、缩写、关键词组合） | `nbrag_search_only_bm25` | 纯 BM25，无向量、无 rerank |
| 想单独观察语义召回是否有效（自然语言意图、概念问法） | `nbrag_search_only_vector` | 纯向量，无 BM25、无 rerank |
| 精确字符串/术语/条文编号（"第一千零七十七条" / "ThreadPool"） | `nbrag_grep` | 逐行字面文本 / 正则匹配，返回上下文。⚠️ 只匹配原文中实际出现的 wording，不支持概念理解（'空城计'搜不到原文中的'焚香操琴'） |
| Python 精确符号名（"UserService 在哪定义"） | `nbrag_find_definition` | Python .py 专用增强；非 Python 内容用 `nbrag_grep` |
| 已知文件名或路径片段，需要完整路径 | `nbrag_find_files` | 返回可用于 `file_path` / `filter_file_path` 的完整绝对路径 |

**搜索上限**：10 轮不同策略和关键词都没找到 → 告知用户"知识库中可能没有相关内容"，不要无限重试。

## 文件类型与功能支持

| 内容类型 | `nbrag_search` | `nbrag_grep` | `nbrag_find_definition` | AST scope |
|---|---|---|---|---|
| `.md` / `.txt` / `.html` 等文档 | ✅ | ✅ | 不适合，改用 `nbrag_grep` | ❌ |
| `.py` 源码 | ✅ | ✅ | ✅ AST 精确解析 | ✅ |

## Python source workflow / Python 源码检索

Python 源码检索是 nbrag 的首要场景之一，但不应只依赖单一工具。对 `.py` 文件，chunk 会包含文件路径、行号范围、AST scope 和 signature metadata，方便 AI 先发现方向，再精确读取定义和源码上下文。

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
- 小文件抓全文；大文件围绕命中位置按字符预算对称扩窗抓原文（默认 `fetch_chars=4000`）
- `fetch_top_n_raw=3` 控制抓几个文件原文（设 0 跳过抓取）
- 同一文件多次命中只抓一次（合并扩窗后的行范围）
- 结果包含 `Ranked search results` 和 `Auto-fetched original content` 两段，分别展示搜索排名和自动抓取原文
- 支持 `filter_file_path` 用搜索结果里的完整绝对 `file_path` 精确限定文件

### 策略 B：精细搜索

```
nbrag_search(query="...", collection_name="xxx", top_k=5)
```

- Vector + BM25 → RRF 融合 → Rerank 精排
- 可选：`use_bm25=False`、`use_rerank=False`、`include_content=False`、`preview_chars=1200`、`filter_file_path="D:/docs/labor_law/劳动合同法.md"`（必须是完整绝对路径）
- 返回 chunk preview，可能被截断（加 `...`）
- 关键字段：`chunk:X/Y`、`chunk_index:X`、`total_chunks:Y`、`line:N-M`、`scope`（仅 Python）、`doc_id`、`file_path`、`dist`
- **大多数场景用策略 A 就够了，策略 B 仅用于需要精细控制的场景**

### 策略 C：单策略诊断（隔离某一层召回）

```python
nbrag_search_only_bm25(query="违法约定试用期赔偿金", collection_name="xxx")
nbrag_search_only_vector(query="试用期被辞退有赔偿吗", collection_name="xxx")
```

- `nbrag_search_only_bm25`：固定 BM25-only，无向量、无 rerank
- `nbrag_search_only_vector`：固定 vector-only，无 BM25、无 rerank
- 适合回答“这次命中是不是 BM25 的功劳”或“embedding 语义召回到底抓到了什么”
- 不建议把这两个工具当默认入口；默认入口仍然通常是 `nbrag_search_and_fetch`
- 如果只需要正常混合检索但又要关某个开关，优先用 `nbrag_search`

### 策略 D：精确匹配（仅限逐字字符串，不支持概念）

```
nbrag_grep(keyword="第十九条", collection_name="xxx")
```

- 在已存储的原始文本中进行逐行字面文本 / 正则匹配（re.search），不是语义搜索
- ⚠️ 只匹配原文中实际出现的 wording；如果传的是合法 regex，则按 regex 规则匹配
- 概念性提问（如"空城计"）很可能搜不到，尤其当原文只写了具体描写而没写这个概括词；这种情况改用 `nbrag_search_and_fetch`
- 匹配是按行进行的，跨行短语可能无法按预期命中
- `context_lines=10` 控制上下文（默认 10，匹配行前后各 N 行）
- 可选 `case_sensitive=True`、`filter_file_path="D:/docs/labor_law/劳动合同法.md"`（必须是完整绝对路径）
- `>>>` 标记匹配行

### 策略 E：Python 符号定义（源码专用增强）

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

## 常见调用路径（不是固定流程）

```
不知道 collection_name → nbrag_stats()
知识/用法/证据问题 → 通常先 nbrag_search_and_fetch()
需要精细控制/只要 metadata → nbrag_search()
需要精确词、条文号、标题、错误码 → nbrag_grep()
只有文件名/路径片段 → nbrag_find_files() 换成完整 file_path
需要引用原文或扩大上下文 → nbrag_get_raw_file() / nbrag_get_adjacent_chunks()
Python .py 精确符号定义 → nbrag_find_definition()
```

不要为了走完流程而调用工具；如果当前返回已经足够回答，就停止检索并作答。

## 多轮检索策略

**核心原则**：可以改写，但应改写成更聚焦、更可检索的自然语言短查询；不要机械改写成大量空格分隔的关键词串。

优先保留用户问题中的核心对象、约束、条件和专业术语。只有在查条文号、标题、错误码、类名、函数名等精确目标时，才适合使用更短的关键词查询，或改用 `nbrag_grep`。

**示例**：用户问 "公司让我试用期干了5个月不转正，签的1年合同，合法吗？"
- 第1轮: `nbrag_search_and_fetch("1年劳动合同试用期期限上限")` → 找到试用期上限
- 第2轮: `nbrag_search_and_fetch("违法约定试用期赔偿金")` → 找到赔偿标准
- 如需精确原文，可分别尝试 `nbrag_grep("第十九条")`、`nbrag_grep("第八十三条")`；是否继续取决于前两轮证据是否已经足够

搜索不理想时的策略：缩短问题 → 更换术语 → 提取少量关键约束 → 换工具（语义→grep）→ 用 `nbrag_find_files` 找完整路径后缩小文件范围 → 跨 collection

## 常见问题速查

| 症状 | 原因 | 解决 |
|------|------|------|
| collection 不存在 | 知识库未准备好或名称错误 | `nbrag_stats()` 确认名称 |
| 搜索返回空 | 无匹配、关键词不合适、或 collection 名称不对 | 换关键词 / 用 `nbrag_stats` 确认知识库名 |
| `nbrag_grep` / `nbrag_find_definition` 无结果 | 没有精确匹配（grep 只搜字面串），或该内容不适合该工具 | 换关键词 / 如果是概念性提问改用 `nbrag_search_and_fetch` / 确认原文确实使用了该词汇 |
| 想查 .md/.txt 条文、标题、术语却用了 `nbrag_find_definition` | 该工具是 Python 源码专用增强 | 改用 `nbrag_grep` |

**详细错误信息**：各工具的报错信息在 MCP 工具描述中已注明，AI 应根据返回的错误信息判断原因。

## 可选只读管理工具

- `nbrag_list` — 除非用户明确要求列出文档
