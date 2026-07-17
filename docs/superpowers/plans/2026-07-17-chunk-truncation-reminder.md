# chunk 截断提醒 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 nbrag 的三层 AI-facing 文本（mcp_tools.py 返回内容、server.py docstring、SKILL.md）中明确告诉 LLM "chunk 必然截断，有用必须扩展"，并把 Unlocks 措辞从"candidate"改为"required"。

**Architecture:** 纯文字层面修改，不加新属性、不加新标签、不改检索逻辑。在 7 处返回拼装位置加全局截断提醒，在 10 个函数 docstring 中加截断说明，在 SKILL.md 中覆盖 3 个矛盾章节，在 4 处 Unlocks 行强化措辞。

**Tech Stack:** Python (mcp_tools.py, server.py), Markdown (SKILL.md)

## Global Constraints

- 不改函数签名（入参名、入参类型、默认值）
- 不改检索逻辑、rerank、BM25、chunking 逻辑
- 不改 XML 标签结构和属性
- 不改 `retrieval.py` 底层 dict key
- 不改 `nbrag_add_document` / `nbrag_delete` 的返回格式
- `nbrag_find_files` 的 Unlocks 行保持不变（清单类、无 content）
- 每完成一个 Task 独立 commit

---

### Task 1: mcp_tools.py — 检索类函数返回内容加截断提醒 + Unlocks 措辞强化

**Files:**
- Modify: `d:/codes/nbrag/nbrag/mcp_tools.py:390-414`（`_format_search_results`）
- Modify: `d:/codes/nbrag/nbrag/mcp_tools.py:568-595`（`nbrag_search_and_fetch`）
- Modify: `d:/codes/nbrag/nbrag/mcp_tools.py:651-671`（`nbrag_grep`）
- Modify: `d:/codes/nbrag/nbrag/mcp_tools.py:708-738`（`nbrag_find_definition`）

**Interfaces:**
- Consumes: 无
- Produces: 4 个检索类函数的返回内容中包含截断提醒和 "Required when content is useful" 措辞

- [ ] **Step 1: 修改 `_format_search_results` — Unlocks 措辞 + 截断提醒**

在 `d:/codes/nbrag/nbrag/mcp_tools.py` 第 399 行，把 unlocks 变量改为 "Required when content is useful" 前缀：

```python
    unlocks = (
        "Required when content is useful: "
        "nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name) | "
        "nbrag_get_raw_file(file_path, collection_name, line_start, line_end) | "
        "nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name)"
    )
```

在第 405 行（`lines.append("")` 之后、`lines.append("<ranked_hits>")` 之前）加截断提醒：

```python
    lines.extend(_surfacing_block("Top result handles — reuse these values in the next call:", top_handles, unlocks))
    lines.append("")
    lines.append("<hit> 中的 <content> 是 RAG chunk，必然是截断片段，不是完整原文。若某条 content 对回答有帮助，必须调用 Required when content is useful 行中的工具扩展获取周围更多内容。")
    lines.append("")
    lines.append("<ranked_hits>")
```

- [ ] **Step 2: 修改 `nbrag_search_and_fetch` — Unlocks 措辞 + 截断提醒**

在第 577 行，把 unlocks 变量改为 "Required when content is useful" 前缀：

```python
    unlocks = (
        "Required when content is useful: "
        "nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name) | "
        "nbrag_get_raw_file(file_path, collection_name, line_start, line_end) | "
        "nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name)"
    )
```

在第 583 行（surfacing 块之后、`<ranked_hits>` 之前）加截断提醒：

```python
    lines.extend(_surfacing_block("Top result handles — reuse these values in the next call:", top_handles, unlocks))
    lines.append("")
    lines.append("<hit> 和 <fetched_raw> 中的 <content> 是 RAG chunk，必然是截断片段，不是完整原文。若某条 content 对回答有帮助，必须调用 Required when content is useful 行中的工具扩展获取周围更多内容。")
    lines.append("")
    lines.append("<ranked_hits>")
```

- [ ] **Step 3: 修改 `nbrag_grep` — Unlocks 措辞 + 截断提醒**

在第 646 行，把 unlocks 变量改为 "Required when content is useful" 前缀：

```python
    unlocks = (
        "Required when content is useful: "
        "nbrag_get_raw_file(file_path, collection_name, line_start, line_end) | "
        "nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name) | "
        "nbrag_search_and_fetch(query, collection_name) for nearby semantic context"
    )
```

在第 655 行（surfacing 块之后、`<matches>` 之前）加截断提醒：

```python
    lines.extend(_surfacing_block("Top match handles — reuse these values in the next call:", top_handles, unlocks))
    lines.append("")
    lines.append("<match> 中的 <content> 是 RAG chunk，必然是截断片段，不是完整原文。若某条 content 对回答有帮助，必须调用 Required when content is useful 行中的工具扩展获取周围更多内容。")
    lines.append("")
    lines.append("<matches>")
```

- [ ] **Step 4: 修改 `nbrag_find_definition` — Unlocks 措辞 + 截断提醒**

在第 704 行，把 unlocks 变量改为 "Required when content is useful" 前缀：

```python
    unlocks = (
        "Required when content is useful: "
        "nbrag_get_raw_file(file_path, collection_name, line_start, line_end) | "
        "nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name)"
    )
```

在第 710 行（surfacing 块之后、`<definitions>` 之前）加截断提醒：

```python
    lines.extend(_surfacing_block("Top definition handles — reuse these values in the next call:", top_handles, unlocks))
    lines.append("")
    lines.append("<definition> 中的 <content> 是 RAG chunk，必然是截断片段，不是完整原文。若某条 content 对回答有帮助，必须调用 Required when content is useful 行中的工具扩展获取周围更多内容。")
    lines.append("")
    if has_non_python_fallback and not has_python_definition:
```

- [ ] **Step 5: Grep 验证检索类函数中无 "Unlocks:" 残留**

Run: `grep -n "Unlocks:" d:/codes/nbrag/nbrag/mcp_tools.py`
Expected: 只剩 `nbrag_find_files` 一处（第 762 行附近）

- [ ] **Step 6: Commit**

```bash
git add d:/codes/nbrag/nbrag/mcp_tools.py
git commit -m "feat: 检索类函数返回内容加 chunk 截断提醒 + Unlocks 措辞强化为 Required when content is useful"
```

---

### Task 2: mcp_tools.py — chunk 视图类函数返回内容加截断提醒

**Files:**
- Modify: `d:/codes/nbrag/nbrag/mcp_tools.py:818-846`（`nbrag_get_adjacent_chunks`）
- Modify: `d:/codes/nbrag/nbrag/mcp_tools.py:874-906`（`nbrag_get_file_chunks`）
- Modify: `d:/codes/nbrag/nbrag/mcp_tools.py:938-966`（`nbrag_get_chunks_by_lines`）

**Interfaces:**
- Consumes: 无
- Produces: 3 个 chunk 视图类函数的返回内容中包含截断提醒

- [ ] **Step 1: 修改 `nbrag_get_adjacent_chunks` — 加截断提醒**

在第 820 行（"Input chunk_index echoed..." 之后、`"<chunks>"` 之前）加截断提醒。现有代码：

```python
    lines = [
        f'<nbrag_get_adjacent_chunks file_path="{file_path}" doc_id="{doc_id_str}" total_chunks="{total_chunks}" window="{window}" anchor_chunk_index="{chunk_index}">',
        "Input chunk_index echoed above as anchor_chunk_index. Returned chunk handles below: chunk_index, line_start, line_end.",
        "",
        "<chunks>",
    ]
```

改为：

```python
    lines = [
        f'<nbrag_get_adjacent_chunks file_path="{file_path}" doc_id="{doc_id_str}" total_chunks="{total_chunks}" window="{window}" anchor_chunk_index="{chunk_index}">',
        "Input chunk_index echoed above as anchor_chunk_index. Returned chunk handles below: chunk_index, line_start, line_end.",
        "",
        "<chunk> 中的 <content> 是 RAG chunk，必然是截断片段，不是完整原文。若某条 content 对回答有帮助，必须调用 nbrag_get_raw_file 获取完整原文。",
        "",
        "<chunks>",
    ]
```

- [ ] **Step 2: 修改 `nbrag_get_file_chunks` — 加截断提醒**

在第 876 行（"Input start_chunk echoed..." 之后、`"<chunks>"` 之前）加截断提醒。现有代码：

```python
    lines = [
        f'<nbrag_get_file_chunks file_path="{file_path_str}" doc_id="{doc_id_str}" total_chunks="{total_chunks}" total_lines="{total_lines}" start_chunk="{start_chunk}" max_chunks="{max_chunks}" has_more="{has_more}">',
        "Input start_chunk echoed above (pagination cursor, value-compatible with chunk_index but not a chunk handle). Returned chunk handles below: chunk_index, line_start, line_end.",
        "",
        "<chunks>",
    ]
```

改为：

```python
    lines = [
        f'<nbrag_get_file_chunks file_path="{file_path_str}" doc_id="{doc_id_str}" total_chunks="{total_chunks}" total_lines="{total_lines}" start_chunk="{start_chunk}" max_chunks="{max_chunks}" has_more="{has_more}">',
        "Input start_chunk echoed above (pagination cursor, value-compatible with chunk_index but not a chunk handle). Returned chunk handles below: chunk_index, line_start, line_end.",
        "",
        "<chunk> 中的 <content> 是 RAG chunk，必然是截断片段，不是完整原文。若某条 content 对回答有帮助，必须调用 nbrag_get_raw_file 获取完整原文。",
        "",
        "<chunks>",
    ]
```

- [ ] **Step 3: 修改 `nbrag_get_chunks_by_lines` — 加截断提醒**

在第 940 行（"Input line_start/line_end echoed..." 之后、`"<chunks>"` 之前）加截断提醒。现有代码：

```python
    lines = [
        f'<nbrag_get_chunks_by_lines doc_id="{doc_id_str}" file_path="{file_path}" total_chunks="{total_chunks}" requested_line_start="{line_start}" requested_line_end="{line_end}">',
        "Input line_start/line_end echoed above as requested_line_start/requested_line_end. Returned chunk handles below: chunk_index, line_start, line_end (actual chunk coverage may differ from requested range).",
        "",
        "<chunks>",
    ]
```

改为：

```python
    lines = [
        f'<nbrag_get_chunks_by_lines doc_id="{doc_id_str}" file_path="{file_path}" total_chunks="{total_chunks}" requested_line_start="{line_start}" requested_line_end="{line_end}">',
        "Input line_start/line_end echoed above as requested_line_start/requested_line_end. Returned chunk handles below: chunk_index, line_start, line_end (actual chunk coverage may differ from requested range).",
        "",
        "<chunk> 中的 <content> 是 RAG chunk，必然是截断片段，不是完整原文。若某条 content 对回答有帮助，必须调用 nbrag_get_raw_file 获取完整原文。",
        "",
        "<chunks>",
    ]
```

- [ ] **Step 4: Commit**

```bash
git add d:/codes/nbrag/nbrag/mcp_tools.py
git commit -m "feat: chunk 视图类函数返回内容加 chunk 截断提醒"
```

---

### Task 3: mcp_tools.py — nbrag_help 返回内容加全局截断提醒

**Files:**
- Modify: `d:/codes/nbrag/nbrag/mcp_tools.py:260-296`（`nbrag_help` 的 skeleton 列表）

**Interfaces:**
- Consumes: 无
- Produces: `nbrag_help()` 返回内容中包含全局 chunk 截断提醒

- [ ] **Step 1: 在 `nbrag_help` 的 skeleton 列表中加截断提醒**

在第 293 行（"Only the TOP result is surfaced..." 之后、`""` 之前）加一行。现有代码：

```python
        "Only the TOP result is surfaced via `key = value` lines; for non-top results, always scan the corresponding <hit>/<match>/<definition>/<file>/<document> XML attributes.",
        "",
        "Stable follow-up fields: file_path, doc_id, chunk_index, line_start, line_end.",
    ]
```

改为：

```python
        "Only the TOP result is surfaced via `key = value` lines; for non-top results, always scan the corresponding <hit>/<match>/<definition>/<file>/<document> XML attributes.",
        "",
        "IMPORTANT: 所有检索类和 chunk 视图类工具返回的 <content> 都是 RAG chunk，必然是截断片段，不是完整原文。若 content 对回答有帮助，必须调用 nbrag_get_raw_file 或 nbrag_get_adjacent_chunks 扩展获取周围更多内容。nbrag_get_raw_file 是唯一返回完整原文（非截断）的工具。",
        "",
        "Stable follow-up fields: file_path, doc_id, chunk_index, line_start, line_end.",
    ]
```

- [ ] **Step 2: Commit**

```bash
git add d:/codes/nbrag/nbrag/mcp_tools.py
git commit -m "feat: nbrag_help 返回内容加全局 chunk 截断提醒"
```

---

### Task 4: server.py — 检索类函数 docstring 加截断说明

**Files:**
- Modify: `d:/codes/nbrag/nbrag/server.py:114-132`（`nbrag_search` docstring）
- Modify: `d:/codes/nbrag/nbrag/server.py:161-173`（`nbrag_search_only_bm25` docstring）
- Modify: `d:/codes/nbrag/nbrag/server.py:191-203`（`nbrag_search_only_vector` docstring）
- Modify: `d:/codes/nbrag/nbrag/server.py:223-247`（`nbrag_search_and_fetch` docstring）
- Modify: `d:/codes/nbrag/nbrag/server.py:268-275`（`nbrag_grep` docstring）
- Modify: `d:/codes/nbrag/nbrag/server.py:285-292`（`nbrag_find_definition` docstring）

**Interfaces:**
- Consumes: 无
- Produces: 6 个检索类函数的 docstring 中包含 chunk 截断说明

- [ ] **Step 1: `nbrag_search` docstring 加截断说明**

在第 132 行（"Returned text is structured..." 段落末尾）加一句。现有代码末尾：

```
    The top result's handle block (file_path, doc_id, chunk_index, line_start, line_end) is surfaced as ready-to-use `key = value` lines at the top of the returned text, with an `Unlocks:` line listing candidate follow-up tools. Only the top result is surfaced this way; for non-top results, scan the <hit> XML attributes.
```

在末尾加：

```
    Each <hit>'s <content> is a RAG chunk — a necessarily truncated fragment, not the full source. If a hit's content is useful, you MUST call nbrag_get_raw_file or nbrag_get_adjacent_chunks to expand.
```

- [ ] **Step 2: `nbrag_search_only_bm25` docstring 加截断说明**

在第 167 行末尾加：

```
    Each <hit>'s <content> is a RAG chunk — a necessarily truncated fragment, not the full source. If a hit's content is useful, you MUST call nbrag_get_raw_file or nbrag_get_adjacent_chunks to expand.
```

- [ ] **Step 3: `nbrag_search_only_vector` docstring 加截断说明**

在第 197 行末尾加：

```
    Each <hit>'s <content> is a RAG chunk — a necessarily truncated fragment, not the full source. If a hit's content is useful, you MUST call nbrag_get_raw_file or nbrag_get_adjacent_chunks to expand.
```

- [ ] **Step 4: `nbrag_search_and_fetch` docstring 加截断说明**

在第 244 行末尾加：

```
    Both <hit> <content> and <fetched_raw> <content> are RAG chunks — necessarily truncated fragments. If a hit's content is useful, you MUST call nbrag_get_raw_file or nbrag_get_adjacent_chunks to expand further.
```

- [ ] **Step 5: `nbrag_grep` docstring 加截断说明**

在第 274 行末尾加：

```
    Each <match>'s <content> is a RAG chunk — a necessarily truncated fragment, not the full source. If a match's content is useful, you MUST call nbrag_get_raw_file to expand.
```

- [ ] **Step 6: `nbrag_find_definition` docstring 加截断说明**

在第 291 行末尾加：

```
    Each <definition>'s <content> is a RAG chunk — a necessarily truncated fragment, not the full source. If a definition's content is useful, you MUST call nbrag_get_raw_file or nbrag_get_chunks_by_lines to expand.
```

- [ ] **Step 7: Commit**

```bash
git add d:/codes/nbrag/nbrag/server.py
git commit -m "feat: 检索类函数 docstring 加 chunk 截断说明"
```

---

### Task 5: server.py — chunk 视图类函数 + nbrag_get_raw_file + include_content Field

**Files:**
- Modify: `d:/codes/nbrag/nbrag/server.py:99`（`include_content` Field 描述）
- Modify: `d:/codes/nbrag/nbrag/server.py:321-328`（`nbrag_get_file_chunks` docstring）
- Modify: `d:/codes/nbrag/nbrag/server.py:339-344`（`nbrag_get_raw_file` docstring）
- Modify: `d:/codes/nbrag/nbrag/server.py:355-361`（`nbrag_get_adjacent_chunks` docstring）
- Modify: `d:/codes/nbrag/nbrag/server.py:372-377`（`nbrag_get_chunks_by_lines` docstring）

**Interfaces:**
- Consumes: 无
- Produces: 4 个函数 docstring 和 1 个 Field 描述中包含截断说明

- [ ] **Step 1: `include_content` Field 描述加截断说明**

第 99 行现有代码：

```python
    include_content: bool = Field(default=True, description="Include chunk content in each hit. Set false for metadata-only lookup when you only need handles like file_path/doc_id/chunk_index")
```

改为：

```python
    include_content: bool = Field(default=True, description="Include chunk content in each hit. Set false for metadata-only lookup when you only need handles like file_path/doc_id/chunk_index. Content is a truncated chunk fragment, not the full source")
```

- [ ] **Step 2: `nbrag_get_file_chunks` docstring 加截断说明**

第 327 行末尾加：

```
    Each <chunk>'s <content> is a RAG chunk — a necessarily truncated fragment, not the full source. If a chunk's content is useful, you MUST call nbrag_get_raw_file to get the overlap-free original text.
```

- [ ] **Step 3: `nbrag_get_raw_file` docstring 加反向说明**

第 344 行末尾加：

```
    Unlike chunk-based tools, this returns overlap-free original text, not a truncated chunk. Use this when chunk content is useful and you need the complete surrounding text.
```

- [ ] **Step 4: `nbrag_get_adjacent_chunks` docstring 加截断说明**

第 361 行末尾加：

```
    Each <chunk>'s <content> is a RAG chunk — a necessarily truncated fragment, not the full source. If a chunk's content is useful, you MUST call nbrag_get_raw_file to get the overlap-free original text.
```

- [ ] **Step 5: `nbrag_get_chunks_by_lines` docstring 加截断说明**

第 377 行末尾加：

```
    Each <chunk>'s <content> is a RAG chunk — a necessarily truncated fragment, not the full source. If a chunk's content is useful, you MUST call nbrag_get_raw_file to get the overlap-free original text.
```

- [ ] **Step 6: Commit**

```bash
git add d:/codes/nbrag/nbrag/server.py
git commit -m "feat: chunk 视图类函数 docstring 加截断说明 + nbrag_get_raw_file 反向说明 + include_content Field 补充"
```

---

### Task 6: SKILL.md — 覆盖3个矛盾章节

**Files:**
- Modify: `d:/codes/nbrag/nbrag/skills/nbrag-workflow/SKILL.md:156-178`（"Raw text vs chunk view" 章节）
- Modify: `d:/codes/nbrag/nbrag/skills/nbrag-workflow/SKILL.md:260-277`（"Normal multi-turn pattern" 章节）
- Modify: `d:/codes/nbrag/nbrag/skills/nbrag-workflow/SKILL.md:295-298`（Pattern A）

**Interfaces:**
- Consumes: 无
- Produces: SKILL.md 中 3 个章节覆盖为新规则

- [ ] **Step 1: "Raw text vs chunk view" 章节开头加核心规则**

在第 156 行（`## 7. Raw text vs chunk view` 之后）加核心规则段落：

现有代码：

```markdown
## 7. Raw text vs chunk view

### Use `nbrag_get_raw_file()` when you need:
```

改为：

```markdown
## 7. Raw text vs chunk view

**核心规则：chunk 必然是截断片段，不是完整原文。**
所有检索类工具（search/grep/find_definition）和 chunk 视图类工具返回的 `<content>` 都是 RAG chunk，
按 chunk_size 机械切断，不存在"完整内容"。若某条 content 对回答有帮助，必须调用
nbrag_get_raw_file 或 nbrag_get_adjacent_chunks 获取周围更多内容。
nbrag_get_raw_file 是唯一返回完整原文（非截断）的工具。

### Use `nbrag_get_raw_file()` when you need:
```

- [ ] **Step 2: "Normal multi-turn pattern" 覆盖第5、6步和 stop signals**

第 268-276 行现有代码：

```markdown
5. Expand with raw text or chunk context only when the current excerpt is insufficient
6. Stop once the evidence is enough to answer

Stop signals — any one is sufficient:
- the top-k hits already directly answer the user's question
- additional rounds only surface duplicate / less-relevant hits
- the requested handle (file_path / line range / definition) has been located
- a follow-up raw/chunk read already produced the quotable evidence
```

改为：

```markdown
5. 若某条 hit 的 content 对回答有帮助，必须调用 nbrag_get_raw_file 或 nbrag_get_adjacent_chunks 扩展
6. Stop once the expanded original text is enough to answer

Stop signals — any one is sufficient:
- 扩展后的完整原文已经足以回答用户问题
- additional rounds only surface duplicate / less-relevant hits
- the requested handle (file_path / line range / definition) has been located
- a follow-up raw/chunk read already produced the quotable evidence
```

- [ ] **Step 3: 强化 Pattern A**

第 295-298 行现有代码：

```markdown
### Pattern A — Semantic hit, then expand chunk context
Goal: a ranked hit is relevant but you want more surrounding chunks.
1. `nbrag_search_and_fetch(query, collection_name)` → Top result handles block gives `doc_id` + `chunk_index` (the `Unlocks:` line already shows this exact follow-up)
2. `nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name)` → nearby `<chunk>`s (each `<chunk>` carries its own `chunk_index` for further expansion)
```

改为：

```markdown
### Pattern A — Semantic hit, then expand chunk context
Goal: a ranked hit is useful → 必须扩展获取完整内容（chunk 必然截断）。
1. `nbrag_search_and_fetch(query, collection_name)` → Top result handles block gives `doc_id` + `chunk_index` (the `Required when content is useful:` line already shows this exact follow-up)
2. `nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name)` → nearby `<chunk>`s (each `<chunk>` carries its own `chunk_index` for further expansion)
   或 `nbrag_get_raw_file(file_path, collection_name, line_start, line_end)` → 完整原文
```

- [ ] **Step 4: Grep 验证 SKILL.md 无矛盾残留**

Run: `grep -n "only when the current excerpt is insufficient" d:/codes/nbrag/nbrag/skills/nbrag-workflow/SKILL.md`
Expected: 无输出

Run: `grep -n "top-k hits already directly answer" d:/codes/nbrag/nbrag/skills/nbrag-workflow/SKILL.md`
Expected: 无输出

- [ ] **Step 5: Commit**

```bash
git add d:/codes/nbrag/nbrag/skills/nbrag-workflow/SKILL.md
git commit -m "feat: SKILL.md 覆盖3个矛盾章节，强化 chunk 必然截断规则"
```

---

### Task 7: 验证 — 重启 MCP 服务 + Python 脚本调用验证

**Files:**
- 无文件修改，仅验证

- [ ] **Step 1: 重启 MCP 服务**

Run: `D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/start_http_rag_mcp.py`

- [ ] **Step 2: 用 Python 脚本调用检索类工具，检查返回内容是否包含截断提醒**

验证脚本检查返回内容中是否包含 "必然是截断片段" 字样。

- [ ] **Step 3: Grep 验证 server.py docstring 包含截断说明**

Run: `grep -n "necessarily truncated fragment" d:/codes/nbrag/nbrag/server.py`
Expected: 至少 9 行匹配

- [ ] **Step 4: Grep 验证 SKILL.md 无矛盾残留**

Run: `grep -n "only when the current excerpt is insufficient" d:/codes/nbrag/nbrag/skills/nbrag-workflow/SKILL.md`
Expected: 无输出

- [ ] **Step 5: Grep 验证检索类函数中无 "Unlocks:" 残留**

Run: `grep -n "Unlocks:" d:/codes/nbrag/nbrag/mcp_tools.py`
Expected: 只剩 `nbrag_find_files` 一处
