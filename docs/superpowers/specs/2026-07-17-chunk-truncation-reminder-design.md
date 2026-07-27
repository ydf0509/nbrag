# chunk 截断提醒设计

## 背景与动机

LLM 在使用 nbrag 检索知识库时，看到 `<hit>` / `<match>` / `<definition>` / `<chunk>` 的 `<content>` 就认为"内容够了"，直接开始总结回答，不会继续调用工具扩展获取完整内容。

根因：LLM 不知道自己在用 RAG 知识库，不知道 `<content>` 是按 `chunk_size`（默认1000字符）机械切断的片段。现有的工具描述、返回内容、SKILL 都没有明确告诉 LLM "chunk 是必然截断的"。

此外，SKILL.md 现有的 stop signals 和 multi-turn pattern 说"只在不够时才扩展"、"top-k hits already directly answer the user's question"——这些逻辑与新规则"chunk 必然截断，有用必须扩展"直接冲突。

## 核心原则

- **chunk 必然是截断片段**，不是完整原文。按 `chunk_size` 机械切断，不存在"完整内容"。
- **若某条 content 对回答有帮助，必须调用工具扩展**获取周围更多内容。这不是可选行为。
- `nbrag_read_more_original_text` 是唯一返回完整原文（非截断）的工具。
- 即使行尾完整，扩展也有帮助（函数签名缺失、return 缺失、前后条文缺失等）。

## 方案：文字提醒 + Unlocks 措辞强化

纯文字层面修改，不加新属性、不加新标签。在三层 AI-facing 文本中同步加入截断提醒，并把 Unlocks 行措辞从"candidate"改为"required"。

## 影响范围

### 受影响的函数（返回 chunk content）

**检索类（4个函数，返回 `<hit>` / `<match>` / `<definition>` 的 `<content>`）：**
- `nbrag_search` / `nbrag_search_only_bm25` / `nbrag_search_only_vector` — 共用 `_format_search_results`
- `nbrag_search_and_fetch` — 独立返回逻辑，含 `<hit>` 和 `<fetched_raw>` 两种 content
- `nbrag_grep` — 独立返回逻辑
- `nbrag_find_definition` — 独立返回逻辑

**chunk 视图类（3个函数，返回 `<chunk>` 的 `<content>`）：**
- `nbrag_get_adjacent_chunks`
- `nbrag_get_file_chunks`
- `nbrag_get_chunks_by_lines`

### 反向说明

- `nbrag_read_more_original_text` — 返回原始文件快照、非 chunk，docstring 加一句"这是获取完整原文的工具"

### 其他受影响

- `nbrag_help` 返回内容 — 加全局 chunk 截断提醒
- `include_content` Field 描述 — 加一句"content 是截断 chunk 片段"

### 不受影响

- `nbrag_stats` / `nbrag_list` / `nbrag_find_files` — 清单类，无 content（但 `nbrag_find_files` 的 Unlocks 行不改，保持 "Unlocks"）
- `nbrag_add_document` / `nbrag_delete` — 未暴露为 MCP tool
- 检索逻辑、rerank、BM25、chunking 逻辑、函数签名 — 零改动

## 详细修改

### 1. mcp_tools.py 返回内容 — 7处修改位置（覆盖9个函数）顶部加全局截断提醒

在根标签下方、surfacing 块之后、集合标签上方，加一句全局提醒：

```
<hit>/<match>/<definition>/<chunk> 中的 <content> 是 RAG chunk，必然是截断片段，不是完整原文。
若某条 content 对回答有帮助，必须调用 Required when content is useful 行中的工具扩展获取周围更多内容。
```

涉及 7 处修改位置（覆盖 9 个函数）：
- `_format_search_results`（第 390 行附近）— search/only_bm25/only_vector 共用
- `nbrag_search_and_fetch`（第 568 行附近）
- `nbrag_grep`（第 651 行附近）
- `nbrag_find_definition`（第 708 行附近）
- `nbrag_get_adjacent_chunks`（第 839 行附近）
- `nbrag_get_file_chunks`（第 895 行附近）
- `nbrag_get_chunks_by_lines`（第 959 行附近）

### 2. server.py docstring — 9个函数 + 1个 Field + nbrag_help

**检索类（6个函数 docstring）：**

`nbrag_search` / `nbrag_search_only_bm25` / `nbrag_search_only_vector`：
```
Each <hit>'s <content> is a RAG chunk — a necessarily truncated fragment, not the full source.
If a hit's content is useful, you MUST call nbrag_read_more_original_text or nbrag_get_adjacent_chunks to expand.
```

`nbrag_search_and_fetch`：
```
Both <hit> <content> and <fetched_raw> <content> are RAG chunks — necessarily truncated fragments.
If a hit's content is useful, you MUST call nbrag_read_more_original_text or nbrag_get_adjacent_chunks to expand further.
```

`nbrag_grep`：
```
Each <match>'s <content> is a RAG chunk — a necessarily truncated fragment, not the full source.
If a match's content is useful, you MUST call nbrag_read_more_original_text to expand.
```

`nbrag_find_definition`：
```
Each <definition>'s <content> is a RAG chunk — a necessarily truncated fragment, not the full source.
If a definition's content is useful, you MUST call nbrag_read_more_original_text or nbrag_get_chunks_by_lines to expand.
```

**chunk 视图类（3个函数 docstring）：**

`nbrag_get_adjacent_chunks` / `nbrag_get_file_chunks` / `nbrag_get_chunks_by_lines`：
```
Each <chunk>'s <content> is a RAG chunk — a necessarily truncated fragment, not the full source.
If a chunk's content is useful, you MUST call nbrag_read_more_original_text to get the overlap-free original text.
```

**反向说明（1个函数 docstring）：**

`nbrag_read_more_original_text`：
```
Unlike chunk-based tools, this returns overlap-free original text, not a truncated chunk.
Use this when chunk content is useful and you need the complete surrounding text.
```

**Field 描述（1处）：**

`include_content`（第99行）— 在现有描述后加：
```
content is a truncated chunk fragment, not the full source
```

**nbrag_help 返回内容（mcp_tools.py 第258行）：**

加一句全局提醒：
```
所有检索类和 chunk 视图类工具返回的 <content> 都是 RAG chunk，必然是截断片段。若 content 有用，必须调用 nbrag_read_more_original_text 或 nbrag_get_adjacent_chunks 扩展。
```

### 3. SKILL.md — 覆盖3个章节的矛盾逻辑

**3.1 "Raw text vs chunk view" 章节开头（第156行附近）：**

加核心规则：
```markdown
**核心规则：chunk 必然是截断片段，不是完整原文。**
所有检索类工具（search/grep/find_definition）和 chunk 视图类工具返回的 `<content>` 都是 RAG chunk，
按 chunk_size 机械切断，不存在"完整内容"。若某条 content 对回答有帮助，必须调用
nbrag_read_more_original_text 或 nbrag_get_adjacent_chunks 获取周围更多内容。
nbrag_read_more_original_text 是唯一返回完整原文（非截断）的工具。
```

**3.2 "Normal multi-turn pattern"（第260-277行）：**

覆盖第5、6步和 stop signals：
```markdown
5. 若某条 hit 的 content 对回答有帮助，必须调用 nbrag_read_more_original_text 或 nbrag_get_adjacent_chunks 扩展
6. Stop once the expanded original text is enough to answer

Stop signals — any one is sufficient:
- 扩展后的完整原文已经足以回答用户问题
- additional rounds only surface duplicate / less-relevant hits
- the requested handle (file_path / line range / definition) has been located
- 删除 "the top-k hits already directly answer the user's question"——chunk 截断，不能直接回答
```

**3.3 强化 Pattern A（第295-298行）：**

```markdown
### Pattern A — Semantic hit, then expand chunk context
Goal: a ranked hit is useful → 必须扩展获取完整内容（chunk 必然截断）。
1. `nbrag_search_and_fetch(query, collection_name)` → Top result handles
2. `nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name)` → nearby chunks
   或 `nbrag_read_more_original_text(file_path, collection_name, line_start, line_end)` → 完整原文
```

### 4. Unlocks 措辞强化（方案B）

把检索类函数的 `_surfacing_block` unlocks 参数从 `"Unlocks: ..."` 改为 `"Required when content is useful: ..."`。

**mcp_tools.py 中需要改的调用点（4处）：**
1. `_format_search_results`（第 399-403 行）— search/only_bm25/only_vector 共用
2. `nbrag_search_and_fetch`（第 577-581 行）
3. `nbrag_grep`（第 646-650 行）
4. `nbrag_find_definition`（第 704-707 行）

**不改的调用点：**
- `nbrag_find_files`（第 762-766 行）— 清单类、无 content，保持 `"Unlocks: ..."`

## 不改动

- 检索逻辑、rerank、BM25、chunking 逻辑
- 函数签名（入参名、入参类型、默认值）
- `retrieval.py` 底层 dict key
- XML 标签结构和属性
- `nbrag_add_document` / `nbrag_delete` 的返回格式

## 验证方式

- 重启 MCP 服务（端口 9101）
- 用 Python 脚本调用检索类工具，检查返回内容是否包含截断提醒
- 检查 server.py docstring 是否包含截断说明
- 检查 SKILL.md 是否覆盖了矛盾逻辑
- 用 Grep 验证无遗漏的 `"Unlocks: ..."` 在检索类函数中残留
