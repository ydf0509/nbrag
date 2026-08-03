# nbrag MCP XML 化 + Handle 一致性 Implementation Plan

> **历史接口快照**
>
> 本计划描述的是实施时的旧 MCP 契约，不是当前接口。旧名称映射为：`nbrag_search` → `nbrag_retrieve_no_expand`，`nbrag_search_and_fetch` → `nbrag_retrieve`，`nbrag_search_only_bm25` → `nbrag_retrieve_only_bm25`，`nbrag_search_only_vector` → `nbrag_retrieve_only_vector`；请以当前 `nbrag/server.py` 暴露的工具 schema 为准。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 13 个 nbrag MCP 工具函数的返回改成 XML 标签 + 纯文本正文格式，handle 字段跨函数名字+形态完全一致，让 AI 打组合拳时零转换复用 handle。

**Architecture:** 纯格式化层重构，逻辑零改动。handle 放 XML 属性（紧凑可提取），正文放 `<content>` 子元素（零转义可读）。底层 `retrieval.py` dict key 不动，在 `mcp_tools.py` 格式层用映射 helper 转成 canonical 名字。

**Tech Stack:** Python 3.12（`D:/ProgramData/miniconda3/envs/py312/python.exe`）、FastMCP、ChromaDB

## Global Constraints

- **Python 解释器**：`D:/ProgramData/miniconda3/envs/py312/python.exe`（conda py312 环境，不用默认 python）
- **不改函数签名**：入参名、类型、默认值保持不变
- **不动 `retrieval.py` 底层 dict key**：`source` / `index` / `line_number` 保持原样，只在 `mcp_tools.py` 格式层映射
- **不改 `nbrag_add_document` / `nbrag_delete`**：未暴露为 MCP tool，保持现状
- **不写正式测试**：用户明确说不用管测试断言，验证靠 grep 扫描 + 9109 端口端到端调用
- **canonical handle 字段集**（跨函数强制一致）：`file_path` / `doc_id` / `chunk_index` / `total_chunks` / `line_start` / `line_end`
- **禁止变体**（必须废弃）：`chunk:X/Y` / `line:N-M` / `matched_line` / `line_range` / `chunk_count` / `chunk_id`（暴露给 AI）/ `index`（暴露给 AI）
- **正文零转义**：`<content>` 子元素内纯文本，不转义引号/换行/反斜杠
- **前置 skill**：`.agents/skills/nbrag-handle-consistency/SKILL.md`（已存在）
- **前置 spec**：`docs/superpowers/specs/2026-07-16-mcp-xml-handle-consistency/spec.md`（已存在）

---

## File Structure

| 文件 | 责任 | 改动类型 |
|---|---|---|
| `nbrag/mcp_tools.py` | 13 个函数返回 XML 化 + helper 重构 + 加映射 helper | Modify |
| `nbrag/server.py` | Field description / docstring 清理废弃字段名 + boundary case 补值兼容说明 | Modify |
| `nbrag/skills/nbrag-workflow/SKILL.md` | 清理废弃字段名提法 | Modify |
| `scripts/test_xml_format.py` | 改造期间临时自测脚本（验证 9109 端口返回格式），改造完可删 | Create（临时） |

不改：`retrieval.py` / `chunker.py` / `bm25_index.py` / 任何测试文件 / `nbrag_add_document` / `nbrag_delete`

---

### Task 1: 清理 `server.py` 文案 + 补 boundary case 说明

**Files:**
- Modify: `nbrag/server.py`（Field description 和 docstring，约 L44-L428）

**Interfaces:**
- Consumes: spec 里定义的 canonical 字段名 + boundary case 模板
- Produces: `server.py` 里所有 Field description 无废弃字段名；`filter_file_path` / `start_chunk` 的 Field description 补值兼容说明

**背景**：当前 `server.py` 的 Field description 里提到 `chunk:X/Y` / `line:N-M` / `matched_line` 等废弃形式，和即将 XML 化的返回不一致。先清理文案，避免 AI 看到过时描述。

- [ ] **Step 1: 读 `server.py` 找出所有废弃字段名引用**

Run: 用 Grep 扫 `server.py` 里的废弃字段名
```
pattern: "chunk:\\d|line:\\d|matched_line|line_range|chunk_count|chunk_id|start_chunk"
path: nbrag/server.py
output_mode: content, -n=true
```
记录所有命中行号。

- [ ] **Step 2: 清理 Field description 里的废弃字段名**

逐个 Edit 命中行，把废弃字段名改成 canonical 形式：
- `chunk:X/Y` → `chunk_index + total_chunks`
- `line:N-M` → `line_start + line_end`
- `matched_line` → `line_start == line_end`
- `line_range` → `line_start + line_end`
- `chunk_count` → `total_chunks`

- [ ] **Step 3: 给 `filter_file_path` 的 Field description 补值兼容说明**

找到 `filter_file_path` 的 Field description（在 `nbrag_search` / `nbrag_search_and_fetch` / `nbrag_grep` 等函数的入参定义处），追加一句：
```
Value comes from the file_path handle returned by nbrag tools.
```

- [ ] **Step 4: 给 `start_chunk` 的 Field description 补值兼容说明**

找到 `nbrag_get_file_chunks` 的 `start_chunk` 入参 Field description，追加：
```
0-based chunk index; same value space as the chunk_index handle, but used as a pagination cursor (semantic: 'start browsing from chunk N').
```

- [ ] **Step 5: grep 扫描确认 `server.py` 无废弃字段名残留**

Run:
```
pattern: "chunk:\\d|line:\\d|matched_line|line_range|chunk_count"
path: nbrag/server.py
```
Expected: 0 命中（`start_chunk` 作为合法入参名保留，不算违规）

- [ ] **Step 6: Commit**

```bash
git add nbrag/server.py
git commit -m "refactor(server): clean deprecated field names from Field descriptions"
```

---

### Task 2: 加映射 helper + 重构错误 helper

**Files:**
- Modify: `nbrag/mcp_tools.py:122-180`（helper 函数区）+ 顶部加新 helper

**Interfaces:**
- Consumes: `retrieval.py` 底层 dict key（`source` / `index` / `filename`）
- Produces: `_meta_file_path(meta)` / `_meta_chunk_index(meta)` 返回 canonical 字符串；`_path_error` / `_collection_issue_text` / `_collection_presence_issue_text` / `_no_search_results_text` 返回 `<error type="..." field="...">` 格式

**背景**：错误返回和底层 key 映射是后续所有函数的基础设施，先做底层 helper，上层函数才能直接用。

- [ ] **Step 1: 在 `mcp_tools.py` 顶部（`_str_param` 附近，约 L74 后）加两个映射 helper**

```python
def _meta_file_path(meta: dict) -> str:
    """Map retrieval.py's source key to canonical file_path handle."""
    return str(meta.get("source", meta.get("filename", "?")))


def _meta_chunk_index(meta: dict) -> str:
    """Map retrieval.py's index key to canonical chunk_index handle."""
    return str(meta.get("chunk_index", meta.get("index", "?")))
```

- [ ] **Step 2: 重构 `_path_error`（约 L122）为 XML error 格式**

读当前 `_path_error` 实现，改成：
```python
def _path_error(field_name: str) -> str:
    return (
        f"<error type=\"invalid_file_path\" field=\"{field_name}\">\n"
        f"{field_name} must be a full absolute file_path returned by nbrag tools.\n"
        f"Recovery: use nbrag_find_files(pattern, collection_name) when you only know a filename, "
        f"or nbrag_list(collection_name) to browse available file_path values.\n"
        f"</error>"
    )
```

- [ ] **Step 3: 重构 `_collection_issue_text`（约 L131）拆成 missing/empty 两种 type**

读当前实现，改成根据 `total` 判断：
```python
def _collection_issue_text(collection_name: str, total: int) -> str:
    if total == 0:
        return (
            f"<error type=\"empty_collection\" field=\"collection_name\">\n"
            f"collection '{collection_name}' exists but has 0 chunks.\n"
            f"Recovery: ingest documents first, or call nbrag_stats() to inspect other collections.\n"
            f"</error>"
        )
    return ""
```
（注：原函数若还做"不存在"判断，把"不存在"分支改成 `type="missing_collection"`，body 里列 available collections）

- [ ] **Step 4: 重构 `_collection_presence_issue_text`（约 L150）为 missing_collection 错误**

读当前实现，改成：
```python
def _collection_presence_issue_text(collection_name: str) -> str:
    from nbrag import get_stats
    stats = get_stats()
    available = [c.get("collection_name", c.get("name", "?")) for c in stats.get("collections", [])]
    return (
        f"<error type=\"missing_collection\" field=\"collection_name\">\n"
        f"collection '{collection_name}' does not exist.\n"
        f"Available collections: {available}\n"
        f"Recovery: call nbrag_stats() to inspect valid collection_name values, then retry with the correct prepared knowledge base.\n"
        f"</error>"
    )
```

- [ ] **Step 5: 重构 `_no_search_results_text`（约 L173）为 no_results 错误**

```python
def _no_search_results_text(total: int) -> str:
    return (
        f"<error type=\"no_results\" field=\"query\">\n"
        f"No results (collection has {total} chunks).\n"
        f"Recovery: verify collection_name, minimally normalize the natural-language query without changing intent, "
        f"provide a bm25_query as lexical anchors, try nbrag_grep for exact terms, "
        f"or use nbrag_find_files + filter_file_path to narrow to a known file.\n"
        f"</error>"
    )
```

- [ ] **Step 6: 验证 helper 能被 import 且返回包含 `<error`**

Run:
```powershell
D:/ProgramData/miniconda3/envs/py312/python.exe -c "from nbrag.mcp_tools import _path_error, _no_search_results_text; print(_path_error('filter_file_path')); print(_no_search_results_text(100))"
```
Expected: 输出包含 `<error type="invalid_file_path"` 和 `<error type="no_results"`

- [ ] **Step 7: Commit**

```bash
git add nbrag/mcp_tools.py
git commit -m "refactor(mcp_tools): add handle mapping helpers + XML error format"
```

---

### Task 3: 重构 `_format_search_results`（影响 3 个 search 函数）

**Files:**
- Modify: `nbrag/mcp_tools.py:252-335`（`_format_search_results`）

**Interfaces:**
- Consumes: Task 2 的 `_meta_file_path` / `_meta_chunk_index` helper
- Produces: `_format_search_results` 返回 `<nbrag_search>` XML 格式（`nbrag_search` / `nbrag_search_only_bm25` / `nbrag_search_only_vector` 三个函数共用）

**背景**：`_format_search_results` 是三个 search 函数共用的内部格式化函数，改它等于同时改三个函数的返回。这是改动量最大、收益最高的函数。

- [ ] **Step 1: 读当前 `_format_search_results`（L252-L335）理解当前格式**

读 `nbrag/mcp_tools.py:252-335`，记录：当前返回的 header 散文、每条 hit 的字段名和格式、`include_content` 的处理方式。

- [ ] **Step 2: 重写 `_format_search_results` 为 XML 格式**

按 spec 的目标格式重写，关键点：
- 根标签 `<nbrag_search collection_name="..." total_chunks="..." bm25="..." rerank="...">`（注意：三个函数共用此 helper，但根标签名应随调用函数变化。**决策**：给 `_format_search_results` 加一个 `root_tag` 参数，调用方传入 `"nbrag_search"` / `"nbrag_search_only_bm25"` / `"nbrag_search_only_vector"`）
- 根标签后第一行：`Follow-up handles in <hit>: file_path, doc_id, chunk_index, line_start, line_end.`
- `<ranked_hits>` 集合内每个 `<hit>`：属性 `rank` → handle 属性（`file_path` 用 `_meta_file_path(meta)`，`doc_id` 直接用 `meta.get("doc_id", "?")`，`chunk_index` 用 `_meta_chunk_index(meta)`，`total_chunks` 用 `meta.get("total_chunks", "?")`，`line_start` / `line_end` 直接用）→ 展示属性（`scope` / `dist` / `score`）
- `include_content=True` 时 `<hit>` 内加 `<content>` 子元素，正文原样不转义
- `include_content=False` 时 `<hit>` 自闭合或空内容（倾向自闭合 `<hit ... />`）
- 删除 header 里关于 query/bm25_query/fetch_context_chars 的解释散文

- [ ] **Step 3: 修改三个调用方传入 `root_tag`**

- `nbrag_search`（L336）：调用 `_format_search_results(..., root_tag="nbrag_search")`
- `nbrag_search_only_bm25`（L359）：`root_tag="nbrag_search_only_bm25"`
- `nbrag_search_only_vector`（L378）：`root_tag="nbrag_search_only_vector"`

- [ ] **Step 4: grep 扫描确认 `_format_search_results` 作用域内无废弃字段名**

Run:
```
pattern: "chunk:\\d|line:\\d|matched_line|line_range|chunk_count"
path: nbrag/mcp_tools.py
```
重点看 L252-L395 区间无命中。

- [ ] **Step 5: Commit**

```bash
git add nbrag/mcp_tools.py
git commit -m "refactor(mcp_tools): XML format for _format_search_results (affects 3 search fns)"
```

---

### Task 4: 重构 `nbrag_search_and_fetch`

**Files:**
- Modify: `nbrag/mcp_tools.py:396-516`（`nbrag_search_and_fetch`）

**Interfaces:**
- Consumes: Task 2 的 helper；Task 3 的 `_format_search_results`（或类似格式化逻辑）
- Produces: `<nbrag_search_and_fetch>` XML，含 `<ranked_hits>` + `<fetched_raw>` 两个 section

**背景**：`search_and_fetch` 比 `search` 多一个 `<fetched_raw>` section，是 AI 最常用的入口函数。

- [ ] **Step 1: 读当前 `nbrag_search_and_fetch`（L396-L516）理解 fetched_raw 生成逻辑**

读 `nbrag/mcp_tools.py:396-516`，记录：ranked hits 怎么来的、fetched_raw 怎么 merge line range、当前输出格式。

- [ ] **Step 2: 重写返回为 XML 格式**

按 spec 目标格式：
- 根标签 `<nbrag_search_and_fetch collection_name="..." total_chunks="..." bm25="..." rerank="...">`
- 根标签后第一行 handle 提醒
- `<ranked_hits>` section：复用 Task 3 的 hit 格式化逻辑（可抽一个小 helper `_format_hit_xml(meta, rank, include_content)` 供 search 和 search_and_fetch 共用，避免重复）
- `<fetched_raw>` section：每个 `<raw file_path="..." doc_id="..." line_start="..." line_end="..."><content>...</content></raw>`，同一文件多个不连续 range 平铺多个 `<raw>`
- 删除 header 散文解释

- [ ] **Step 3: （可选）抽 `_format_hit_xml` helper 供 Task 3/4 共用**

如果 Task 3 没抽，这里抽出来，放 helper 区。然后回头让 Task 3 的 `_format_search_results` 也调用它。保持 DRY。

- [ ] **Step 4: grep 扫描确认 L396-L516 无废弃字段名**

- [ ] **Step 5: Commit**

```bash
git add nbrag/mcp_tools.py
git commit -m "refactor(mcp_tools): XML format for nbrag_search_and_fetch with fetched_raw section"
```

---

### Task 5: 重构 `nbrag_grep`

**Files:**
- Modify: `nbrag/mcp_tools.py:517-565`（`nbrag_grep`）

**Interfaces:**
- Consumes: Task 2 的 `_meta_file_path` helper
- Produces: `<nbrag_grep>` XML，`<match>` 用 `line_start==line_end` 表达单行匹配

**背景**：grep 当前用 `matched_line` / `line_range` 字段，废弃它们统一成 `line_start` + `line_end`。单行匹配 `line_start==line_end`。

- [ ] **Step 1: 读当前 `nbrag_grep`（L517-L565）理解当前格式**

记录：`matched_line` / `line_range` 怎么生成的、多行匹配怎么处理、`case_sensitive` 怎么展示。

- [ ] **Step 2: 重写返回为 XML 格式**

按 spec 目标格式：
- 根标签 `<nbrag_grep case_sensitive="true|false">`
- handle 提醒句：`Follow-up handles in <match>: file_path, doc_id, line_start, line_end.`
- `<matches>` 内每个 `<match file_path="..." doc_id="..." line_start="..." line_end="..."><content>...</content></match>`
- 单行匹配：`line_start == line_end`（值都填行号）
- 多行匹配：`line_start < line_end`
- 废弃 `matched_line` / `line_range`

- [ ] **Step 3: grep 扫描确认 `matched_line` / `line_range` 在 mcp_tools.py 里无残留**

Run:
```
pattern: "matched_line|line_range"
path: nbrag/mcp_tools.py
```
Expected: 0 命中

- [ ] **Step 4: Commit**

```bash
git add nbrag/mcp_tools.py
git commit -m "refactor(mcp_tools): XML format for nbrag_grep, deprecate matched_line/line_range"
```

---

### Task 6: 重构 `nbrag_find_definition`

**Files:**
- Modify: `nbrag/mcp_tools.py:566-618`（`nbrag_find_definition`）

**Interfaces:**
- Consumes: Task 2 的 `_meta_file_path` helper
- Produces: `<nbrag_find_definition>` XML，`<definition>` 含 `<content>` + `<methods_summary>` 子元素

- [ ] **Step 1: 读当前 `nbrag_find_definition`（L566-L618）理解当前格式**

记录：`symbol_type` / `qualified_name` / `methods_summary` 怎么来的、regex_fallback 怎么标记。

- [ ] **Step 2: 重写返回为 XML 格式**

按 spec 目标格式：
- 根标签 `<nbrag_find_definition>`
- handle 提醒句：`Follow-up handles in <definition>: file_path, doc_id, line_start, line_end.`
- `<definitions>` 内每个 `<definition symbol_type="..." qualified_name="..." file_path="..." doc_id="..." line_start="..." line_end="...">`
- 内部 `<content>` 子元素放定义正文
- `<methods_summary>` 子元素放方法列表（可能多行，原样输出）
- `symbol_type="regex_fallback"` 标记 regex 兜底结果，不加额外标签

- [ ] **Step 3: grep 扫描确认 L566-L618 无废弃字段名**

- [ ] **Step 4: Commit**

```bash
git add nbrag/mcp_tools.py
git commit -m "refactor(mcp_tools): XML format for nbrag_find_definition"
```

---

### Task 7: 重构 4 个 chunk 视图函数

**Files:**
- Modify: `nbrag/mcp_tools.py:651-787`（`nbrag_get_adjacent_chunks` / `nbrag_get_file_chunks` / `nbrag_get_chunks_by_lines` / `nbrag_read_more_original_text`）

**Interfaces:**
- Consumes: Task 2 的 `_meta_file_path` / `_meta_chunk_index` helper；底层 `chunk.get("index")` / `chunk.get("line_start")` / `chunk.get("line_end")`
- Produces: 4 个函数分别返回 `<nbrag_get_*>` XML，`<chunk>` 用 canonical handle 属性

**背景**：4 个函数模式一致（都是读底层 chunk 列表然后格式化），放一个 task 里改，保持风格统一。差异信息放根属性。

- [ ] **Step 1: 读 4 个函数当前实现（L651-L787）**

记录：每个函数的入参、底层 chunk dict key、当前返回格式、差异信息（分页游标 / window / requested line range / 纯原文）。

- [ ] **Step 2: 重写 `nbrag_get_file_chunks`（L685）为 XML**

按 spec：
- 根标签 `<nbrag_get_file_chunks file_path="..." doc_id="..." total_chunks="..." total_lines="..." start_chunk="..." max_chunks="..." has_more="true|false">`
- handle 提醒：`Follow-up handles in <chunk>: chunk_index, line_start, line_end.`
- `<chunks>` 内每个 `<chunk chunk_index="..." total_chunks="..." line_start="..." line_end="..." scope="..."><content>...</content></chunk>`
- `chunk_index` 用 `_meta_chunk_index(chunk)`，`file_path` 用 `_meta_file_path(chunk)`

- [ ] **Step 3: 重写 `nbrag_get_adjacent_chunks`（L651）为 XML**

按 spec：
- 根标签 `<nbrag_get_adjacent_chunks file_path="..." doc_id="..." total_chunks="..." window="..." anchor_chunk_index="...">`
- `anchor_chunk_index` = 入参的 `chunk_index`
- `<chunks>` 同上

- [ ] **Step 4: 重写 `nbrag_get_chunks_by_lines`（L726）为 XML**

按 spec：
- 根标签 `<nbrag_get_chunks_by_lines doc_id="..." file_path="..." total_chunks="..." requested_line_start="..." requested_line_end="...">`
- `<chunks>` 同上

- [ ] **Step 5: 重写 `nbrag_read_more_original_text`（L763）为 XML**

按 spec：
- 根标签 `<nbrag_read_more_original_text file_path="..." doc_id="..." total_lines="..." line_start="..." line_end="...">`
- **无 `<chunks>` 集合标签**，直接 `<content>` 子元素放整段原文
- `line_start` / `line_end` 放根属性表示返回范围

- [ ] **Step 6: grep 扫描确认 L651-L787 无废弃字段名**

Run:
```
pattern: "chunk:\\d|line:\\d|matched_line|line_range|chunk_count|chunk_id"
path: nbrag/mcp_tools.py
```
重点看该区间无命中（`start_chunk` 作为合法入参名/root 属性保留）。

- [ ] **Step 7: Commit**

```bash
git add nbrag/mcp_tools.py
git commit -m "refactor(mcp_tools): XML format for 4 chunk view functions"
```

---

### Task 8: 重构 3 个清单类函数

**Files:**
- Modify: `nbrag/mcp_tools.py:619-858`（`nbrag_find_files` / `nbrag_list` / `nbrag_stats`）

**Interfaces:**
- Consumes: Task 2 的 `_meta_file_path` helper；底层 `find_files` / `list_documents` / `get_stats` 返回
- Produces: 3 个函数分别返回 `<nbrag_find_files>` / `<nbrag_list>` / `<nbrag_stats>` XML，单条标签自闭合（无正文）

**背景**：清单类无正文，单条标签自闭合 `<file ... />`。废弃 `chunk_count` 统一 `total_chunks`。`nbrag_stats` 保留前后 routing 提醒句。

- [ ] **Step 1: 读 3 个函数当前实现（L619-L858）**

记录：每个函数的字段名、`chunk_count` 出现位置、`nbrag_stats` 的 routing 提醒句当前文本。

- [ ] **Step 2: 重写 `nbrag_find_files`（L619）为 XML**

按 spec：
- 根标签 `<nbrag_find_files>`
- handle 提醒：`Follow-up handle in <file>: file_path.`
- `<files>` 内每个 `<file file_path="..." doc_id="..." filename="..." total_chunks="..." match="..."/>`（自闭合）
- `chunk_count` → `total_chunks`

- [ ] **Step 3: 重写 `nbrag_list`（L788）为 XML**

按 spec：
- 根标签 `<nbrag_list collection_name="..." offset="..." limit="...">`
- handle 提醒：`Follow-up handles in <document>: doc_id, file_path.`
- `<documents>` 内每个 `<document doc_id="..." file_path="..." filename="..." total_chunks="..."/>`（自闭合）
- `chunk_count` → `total_chunks`

- [ ] **Step 4: 重写 `nbrag_stats`（L814）为 XML**

按 spec：
- 根标签 `<nbrag_stats>`
- 根标签后第一句 routing：`Use collection_name exactly as shown below when calling retrieval tools.`
- `<collections>` 内每个 `<collection collection_name="..." docs="..." chunks="..." display_name="..." description="..." aliases="..." tags="..." chunk_size="..." chunk_overlap="..." last_ingested_at="..."/>`（自闭合，变长可选字段有则写无则省略）
- `</collections>` 后一句：`After choosing collection_name, continue with nbrag_search_and_fetch for most questions.`

- [ ] **Step 5: grep 扫描确认 `chunk_count` 在 mcp_tools.py 里无残留**

Run:
```
pattern: "chunk_count"
path: nbrag/mcp_tools.py
```
Expected: 0 命中

- [ ] **Step 6: Commit**

```bash
git add nbrag/mcp_tools.py
git commit -m "refactor(mcp_tools): XML format for 3 listing functions, deprecate chunk_count"
```

---

### Task 9: 清理 `nbrag_help` + workflow SKILL.md

**Files:**
- Modify: `nbrag/mcp_tools.py:218-251`（`nbrag_help`）
- Modify: `nbrag/skills/nbrag-workflow/SKILL.md`

**Interfaces:**
- Consumes: canonical 字段名集
- Produces: `nbrag_help` 散文里无废弃字段名；workflow SKILL.md 无废弃字段名

**背景**：`nbrag_help` 保持散文格式（它返回的是 workflow skill 文本，不是结构化数据），但提到的字段名要对齐 canonical。workflow SKILL.md 同理。

- [ ] **Step 1: 读 `nbrag_help`（L218-L251）和 workflow SKILL.md**

记录：`nbrag_help` 怎么生成返回（是否直接读 SKILL.md 文本）、废弃字段名出现位置。

- [ ] **Step 2: 清理 `nbrag_help` 里的废弃字段名**

如果 `nbrag_help` 直接返回 `_load_workflow_skill_text()`，则改 SKILL.md 即可，`nbrag_help` 不用改代码。如果 `nbrag_help` 自己拼了字符串，清理那些字符串里的废弃字段名。

- [ ] **Step 3: 清理 `nbrag/skills/nbrag-workflow/SKILL.md` 里的废弃字段名**

用 Grep 扫 SKILL.md 找废弃字段名，逐个 Edit 改成 canonical：
- `chunk:X/Y` → `chunk_index + total_chunks`
- `line:N-M` → `line_start + line_end`
- `matched_line` → `line_start == line_end`
- `line_range` → `line_start + line_end`
- `chunk_count` → `total_chunks`

- [ ] **Step 4: grep 扫描确认 SKILL.md 和 `nbrag_help` 无废弃字段名**

Run:
```
pattern: "chunk:\\d|line:\\d|matched_line|line_range|chunk_count"
path: nbrag/skills/nbrag-workflow/SKILL.md
```
Expected: 0 命中

- [ ] **Step 5: Commit**

```bash
git add nbrag/mcp_tools.py nbrag/skills/nbrag-workflow/SKILL.md
git commit -m "refactor: clean deprecated field names from nbrag_help and workflow SKILL"
```

---

### Task 10: 端到端验证（9109 端口 + 自测脚本）

**Files:**
- Create: `scripts/test_xml_format.py`（临时自测脚本，改造完可删）

**Interfaces:**
- Consumes: Task 1-9 的所有改动
- Produces: 验证报告——13 个函数返回 XML 格式正确、handle 流动路径零转换

**背景**：不依赖 Trae MCP 重连，用独立端口 9109 + Python 脚本调 MCP HTTP 接口，端到端验证所有改动。

- [ ] **Step 1: 启动 9109 端口 MCP 实例**

Run（non-blocking）:
```powershell
D:/ProgramData/miniconda3/envs/py312/python.exe -m nbrag --transport streamable-http --port 9109
```
等启动日志显示监听 9109。

- [ ] **Step 2: 写 `scripts/test_xml_format.py` 自测脚本**

脚本逻辑：
1. 用 httpx 或 requests 连 `http://localhost:9109/mcp`（按实际 MCP HTTP 协议端点）
2. 调用 `nbrag_stats` → 确认返回是 `<nbrag_stats>...<collections><collection .../></collections>...</nbrag_stats>` 格式
3. 取一个 `collection_name`，调用 `nbrag_search_and_fetch` → 确认返回含 `<ranked_hits><hit ...>` 和 `<fetched_raw><raw ...>`
4. 从 `<hit>` 提取 `file_path` / `doc_id` / `chunk_index` / `line_start` / `line_end` 属性值
5. 把这些值直接填进 `nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name)` → 确认调用成功、返回 `<nbrag_get_adjacent_chunks>...<chunks><chunk ...>`
6. 把 `doc_id` / `line_start` / `line_end` 填进 `nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name)` → 确认成功
7. 把 `file_path` / `line_start` / `line_end` 填进 `nbrag_read_more_original_text(file_path, collection_name, line_start, line_end)` → 确认成功
8. 调用 `nbrag_grep` → 确认 `<match>` 用 `line_start == line_end` 表达单行
9. 调用 `nbrag_find_files` / `nbrag_list` → 确认自闭合标签、`total_chunks` 字段
10. 触发一个错误（如传非法 `filter_file_path`）→ 确认返回 `<error type="invalid_file_path" field="filter_file_path">`

脚本只 print 通过/失败，不 assert（用户说不用管测试断言，但脚本本身作为人工验证工具还是有用的）。

- [ ] **Step 3: 运行自测脚本**

Run:
```powershell
D:/ProgramData/miniconda3/envs/py312/python.exe scripts/test_xml_format.py
```
确认所有 10 项检查通过。

- [ ] **Step 4: 停掉 9109 端口实例**

用 StopCommand 停掉 Step 1 启动的进程。

- [ ] **Step 5: grep 全局扫描确认无废弃字段名残留**

Run（针对所有改过的文件）:
```
pattern: "chunk:\\d|line:\\d|matched_line|line_range|chunk_count"
path: nbrag/
glob: "*.py"
```
Expected: 0 命中（`start_chunk` 作为合法入参名保留）

- [ ] **Step 6: （可选）删除临时自测脚本**

如果用户不想保留 `scripts/test_xml_format.py`，删除它。如果用户想保留作为后续回归工具，commit 它。

- [ ] **Step 7: Commit 最终验证记录**

```bash
git add scripts/test_xml_format.py  # 如果保留
git commit -m "test: add temporary XML format verification script for 9109 port"
```
或如果删除了脚本：
```bash
git commit --allow-empty -m "chore: complete XML format refactor, verified via 9109 port"
```

---

## Self-Review

**1. Spec coverage**:
- XML 格式总规范 → Task 2-8 各函数实现 ✓
- handle 字段一致性 → Task 2 映射 helper + 各 Task 用 canonical 名 ✓
- 错误返回 XML → Task 2 helper 重构 ✓
- 标签命名约定表 → Task 3-8 各函数根标签/集合/单条标签 ✓
- 底层 key 映射 → Task 2 加 `_meta_file_path` / `_meta_chunk_index` ✓
- `server.py` 文案清理 → Task 1 ✓
- workflow SKILL.md 清理 → Task 9 ✓
- `nbrag_add_document` / `nbrag_delete` 不改 → Global Constraints 明确 ✓
- 9109 端口验证 → Task 10 ✓
- `nbrag_help` 清理 → Task 9 ✓

**2. Placeholder scan**: 无 TBD/TODO/"implement later"。每个步骤有具体代码或具体 Grep 命令。

**3. Type consistency**:
- `_meta_file_path(meta)` / `_meta_chunk_index(meta)` 在 Task 2 定义，Task 3/4/5/6/7/8 使用，签名一致 ✓
- canonical 字段名 `file_path` / `doc_id` / `chunk_index` / `total_chunks` / `line_start` / `line_end` 跨所有 Task 一致 ✓
- `root_tag` 参数在 Task 3 引入，三个 search 函数传入对应值 ✓
- `<error type="...">` 格式在 Task 2 定义，各函数错误路径复用 ✓

无遗漏。
