---
name: nbrag-code-authoring
description: Use when editing nbrag AI-facing surfaces—MCP tool docstrings, Field descriptions, return text, workflow skills, or retrieval behavior—so future agents receive precise, stable, low-ambiguity guidance.
---

# nbrag Code Authoring

## Goal

把 `nbrag` 写成一个 **agentic RAG MCP contract**，而不只是“能跑的检索代码”。

判断标准优先看这些：
- future agent 能不能更稳定地选对 tool
- 能不能写对参数名与字段名
- 能不能复用真实 returned handles 继续 follow-up
- 能不能少幻觉、少误解、少走机械流程

`nbrag` 的核心不是 one-shot top-k search，而是让 agent 能多轮检索、路径收窄、证据扩展、继续追问。

---

## When to Use

在这些场景使用本 skill：
- 修改 `nbrag/server.py` 的 MCP tools、`Field(description=...)`、docstring
- 修改 `nbrag/mcp_tools.py` 的 return text、error text、follow-up handle wording
- 修改 `nbrag/core.py` / retrieval behavior / rerank / BM25 / raw-vs-chunk semantics
- 修改 `nbrag/skills/` 或 `.agents/skills/` 下的 workflow / authoring guidance
- 修改 README，且需要区分 human-facing vs AI-facing audience
- 用户要求“让 AI 更容易正确使用 nbrag”或“让 MCP 工具更 AI-friendly”

不要把它套用到与 `nbrag` 无关的普通项目。

---

## Audience Split

### AI-facing surfaces
默认首先写给 agent 看：
- `nbrag/server.py` → MCP contract layer
- `nbrag/mcp_tools.py` → output contract layer
- `nbrag/skills/nbrag-workflow/SKILL.md` → workflow strategy layer

### Human-facing surfaces
默认首先写给人看：
- `README.md`
- `README.zh-CN.md`

写法不同：
- human-facing text 解释产品、安装、启动、能力概览
- AI-facing text 解释 tool boundary、parameter contract、routing hints、follow-up handles

如果修改 README，中英文两个版本都要同步。

---

## Core Principle

在 `nbrag` 里，很多“文字”本身就是 product interface：
- tool names
- parameter names
- `Field(description=...)`
- docstrings
- returned markers like `file_path`, `doc_id`, `chunk_index`, `line:N-M`
- recovery hints

所以：
- prose polish 不是第一目标
- exact contract 才是第一目标
- wording 必须和真实行为对齐

如果 behavior 和 wording 不一致：
- behavior 对、wording 歪 → 改 wording
- wording 对、behavior 歪 → 改 code
- 两边都不稳 → 先定边界，再写文案

---

## Stable Boundaries to Preserve

### 1. `query` vs `bm25_query`
- `query` = semantic query for vector retrieval and reranking
- `bm25_query` = lexical-anchor query for BM25

写法目标：
- `query` 保持 semantic completeness
- `bm25_query` 提供 more source-facing lexical anchors
- 不要把两者写成同一个概念
- 不要把 `bm25_query` 写成 another semantic question

### 2. semantic retrieval vs lexical retrieval
- semantic retrieval → meaning / concept / usage / explanation / paraphrase
- lexical retrieval → identifiers / titles / article numbers / exact phrases / error strings / symbols

常见路径：
- semantic → `nbrag_search()` / `nbrag_search_and_fetch()`
- lexical → `bm25_query` / `nbrag_grep()`

### 3. `nbrag_search(_and_fetch)` vs `nbrag_grep()`
- `nbrag_search()` / `nbrag_search_and_fetch()` = ranked semantic or hybrid retrieval
- `nbrag_grep()` = literal / regex matching over stored original text

不要把 `grep` 描述成 concept search。

### 4. raw file vs chunk view
- `nbrag_get_raw_file()` = stored original snapshot, overlap-free view
- `nbrag_get_file_chunks()` / `nbrag_get_adjacent_chunks()` / `nbrag_get_chunks_by_lines()` = chunk-structured view, overlap can happen by design

不要把 raw view 和 chunk view 混成一个概念。

### 5. Python definition lookup vs general text lookup
- `nbrag_find_definition()` 强能力边界在 Python `.py`
- non-Python results 如果存在，应写成 fallback，不应写成同等级能力

### 6. exact full `file_path` discipline
- `file_path` / `filter_file_path` 应来自 nbrag 工具返回的完整绝对路径
- 不要写成 basename / relative path / guessed path
- 只知道片段时，先用 `nbrag_find_files()`

### 7. logical tool names vs exposed tool names
文档里可以解释逻辑名，如：
- `nbrag_search`
- `nbrag_grep`

但要提醒：
- host 暴露名可能带前缀
- agent 调用时应以当前 host 实际暴露名为准

### 8. `filter_file_path` is strong narrowing
当前 hybrid behavior 下：
- it narrows retrieval to one stored file
- it skips cross-file BM25 fusion

不要把它写成 harmless ranking preference。

### 9. stored snapshot, not live filesystem refresh
`nbrag_get_raw_file()` 和 auto-fetched raw snippets 读取的是 ingested snapshot。
不要把它写成实时文件系统读取。

---

## Writing Style for AI-Facing Surfaces

优先写成：
- contract
- distinction
- trigger condition
- next-step guidance
- stable field reuse

少写成：
- marketing prose
- long philosophy essay
- prompt slogans
- author inner monologue

### Hard rules vs soft guidance
只在真正的 product boundary 上使用 hard wording。
例如：
- real field names
- true capability boundaries
- returned handle contracts
- actual retrieval semantics

如果没有明确广泛证据，不要堆太多 speculative prohibitions 把 agent 写得太死板。
优先使用：
- role framing
- decision framing
- switch conditions
- stop conditions

比起写：
- always first
- must always
- never do X

更优先写：
- when this is the right tool
- what this field is for
- what current output unlocks next
- when another tool becomes more direct

---

## Authoring Workflow

1. Identify touched AI-facing surfaces.
2. Read code first to determine real behavior.
3. Update wording to match real behavior exactly.
4. Preserve exact field names / returned markers / handle names.
5. Re-check the key boundaries:
   - semantic vs lexical
   - raw vs chunk
   - Python definition vs general text
   - file_path discipline
6. Make next-step guidance useful, but not rigid.
7. If multiple AI-facing surfaces describe the same behavior, keep them aligned.
8. If editing README, keep human-facing tone and sync EN/ZH.

---

## File-Specific Focus

### `nbrag/server.py`
关注：
- `Field(description=...)` 是否清楚表达 parameter contract
- docstring 是否说明 when to use / when another tool is more direct
- query / bm25 / grep / definition / raw / chunk boundaries 是否清楚
- follow-up handles 是否被明确点出

避免：
- 把多个工具能力揉成一个模糊大工具
- 用人类散文替代 contract wording
- 写出与实际 behavior 不一致的 routing hints

### `nbrag/mcp_tools.py`
关注：
- returned markers 是否稳定且真实
- output 是否支持下一轮 follow-up
- error text 是否给出 recovery path
- raw / chunk / grep / search headers 是否准确反映行为

避免：
- invented field names
- 把 logs 风格写成 contract text
- 用漂亮话掩盖真实边界

### `nbrag/core.py`
关注：
- retrieval semantics 是否稳定
- vector / BM25 / rerank roles 是否清楚
- returned structures 是否被上层依赖
- metadata path normalization 是否稳定

避免：
- 文案问题用逻辑 patch 掩盖
- unstable behavior 留给上层 wording 兜底

### `skills/`
关注：
- skill description 是否清楚说明何时使用
- 内容是否帮助 agent 做判断
- 是否与 MCP contract 一致

避免：
- 复述 README
- rigid mandatory workflow
- 把 skill 写成工具可用性的前提

### `README.md` / `README.zh-CN.md`
关注：
- human-facing clarity
- install / start / capability overview
- collection metadata explanation if needed

避免：
- 承担 AI runtime policy
- 细粒度 tool routing 规范
- 替代 workflow skill / MCP docstrings

---

## Failure Smells

看到这些味道，应停下来重写：
- 使用不存在的术语、字段名、返回标记名
- 把 semantic retrieval、lexical retrieval、raw view、chunk view 写混
- 把 fallback 描述成 primary capability
- 把 `grep` 写成 semantic retrieval
- 把 `find_definition` 写成 general definition lookup
- 把 `file_path` 写成 basename / relative path / guessed path
- 把 README 当成 AI runtime policy
- 写 rigid workflow，如 “永远第一步”“必须按顺序”
- 忘了提醒 actual exposed tool names may be host-prefixed
- 一句话同时承担：功能定义 + 作者心理活动 + 设计辩解

---

## Final Check

提交前快速检查：
- wording matches real behavior
- field names and returned markers are real and stable
- tool boundaries remain distinct
- next-step guidance helps routing but does not force ritual
- AI is less likely to hallucinate fields or misuse follow-up handles after this change
- if README changed, EN/ZH are both updated

如果改完后你仍然怀疑：
- agent 会误选工具
- agent 会复制错字段名
- agent 会把建议路径误读成 rigid workflow
- agent 会把 README 当成 runtime policy

说明这次改动还不够好，继续改。
