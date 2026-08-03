---
name: nbrag-handle-consistency
description: Use when editing nbrag MCP tool functions, return text, Field definitions, or docstrings that touch follow-up handles (file_path, doc_id, chunk_index, line_start, line_end, total_chunks), to keep return fields and downstream input parameters exactly aligned so AI agents can chain tools without field-name guessing or value-form conversion.
---

# nbrag Handle Consistency

## Goal

让 `nbrag` 的 MCP 工具在**返回字段**和**下游入参**之间保持**名字一致 + 形态一致**，使 AI agent 在多轮检索组合拳里能直接把返回值抄进下一个函数的入参，零字段名猜测、零值形态转换、零幻觉机会。

判断标准优先看这些：
- AI 能不能从 A 函数返回里直接复制字段值，填进 B 函数的入参
- 字段名是否跨函数完全相同（不是"语义等价"而是"字符串相同"）
- 值形态是否跨函数完全相同（不在返回里是字符串、入参里是 int）
- 范围类 handle 是否用两个独立字段，而不是合并字符串

`nbrag` 的核心价值是 agentic 多轮检索，handle 在函数间**流动**。任何命名漂移或形态漂移都会在衔接点插入"判断 + 转换"步骤，每个步骤都是幻觉源。多轮链越长，累积出错率越高。

---

## When to Use

宏观 AI-facing surfaces 写作规范（audience、style、tool boundaries）见 `nbrag-code-authoring` skill；本 skill 只管 handle 字段名 + 形态一致性，以及承载 handle 的返回格式。

在这些场景使用本 skill：
- 新增或修改 `nbrag/server.py` 里任何 MCP tool 的 `Field(description=...)` 或函数签名
- 新增或修改 `nbrag/mcp_tools.py` 里任何函数的返回文本格式
- 修改 `nbrag/retrieval.py`（旧名 `core.py`，已重命名）里被上层依赖的返回结构（尤其 chunk metadata 的 key 名）
- 修改 `nbrag/skills/nbrag-workflow/SKILL.md` 里描述 follow-up handle 的部分
- 任何涉及 `file_path` / `doc_id` / `chunk_index` / `line_start` / `line_end` / `total_chunks` 的返回或入参改动

不要把它套用到非 handle 字段。`collection_name` 是 scope selector（跨函数流动但语义是"选择知识库"而非"定位证据"），不纳入本 skill 的 canonical handle set，但同样建议跨函数名字一致；展示类字段（`dist` / `score` / `rank` / `bm25` / `rerank` / `scope` / `filename` / `symbol_type` / `qualified_name` / `methods_summary`）不在本 skill 约束范围。

---

## Core Principle: Handle Consistency

> **凡是会被下游函数作为入参复用的返回字段（follow-up handle），其字段名和值形态必须与目标入参完全一致——名字相同、类型相同、不需转换。**

这条原则的目的是消灭 AI 在多轮检索衔接点的三类判断：
1. **字段名等价判断**："返回里的 `chunk_index` 是不是就是入参的 `start_chunk`？"
2. **值形态转换**："返回里的 `line:10-30` 怎么拆成 `line_start=10` 和 `line_end=30`？"
3. **语义映射**："返回里的 `matched_line` 对应入参的 `line_start` 还是 `line_end`？"

每消灭一个判断点，整条检索链的可靠性提升一档。

---

## Canonical Handle Field Set

这是 nbrag 全工具链**唯一**的 handle 字段名和形态。任何函数的返回和入参，只要涉及这些概念，必须用下表的名字和形态，不得发明别名或变体。

> **形态指语义类型**（int / 字符串），不指 XML 序列化形式。在 XML 属性里 int 也以无引号数字字面量书写（如 `chunk_index="3"`）；在纯文本 `key:value` 行里 int 直接写数字（如 `chunk_index:3`）。序列化细节见返回格式一节。

| 概念 | 字段名 | 形态 | 说明 |
|---|---|---|---|
| 文件绝对路径 | `file_path` | 绝对路径字符串 | 来自 nbrag 工具返回，不接受 basename / relative / guessed |
| 文档 ID | `doc_id` | 字符串 | 由 nbrag 工具返回，跨所有函数复用 |
| chunk 在文件中的序号 | `chunk_index` | int（0-based） | 定位到某个具体 chunk 的 handle |
| 文件的 chunk 总数 | `total_chunks` | int | 与 `chunk_index` 配合表达"第 X 个 / 共 Y 个" |
| 行范围起点 | `line_start` | int（1-based） | 范围类 handle 的左边界 |
| 行范围终点 | `line_end` | int（1-based，inclusive） | 范围类 handle 的右边界 |

### 严格规则

1. **名字唯一**：一个概念只有一个名字，跨所有函数（返回 + 入参）完全相同。
2. **形态唯一**：一个概念只有一种形态，不在返回里用字符串、入参里用 int。
3. **范围类用两个独立字段**：`line_start` + `line_end`，**禁止**用 `line:10-30` / `line:10~30` / `line_range` 等合并字符串形式。
4. **序号类用独立字段**：`chunk_index` + `total_chunks`，**禁止**用 `chunk:3/10` 这种一个字段编两份数据的合并形式。
5. **单行用 start==end 表达**：grep 单行匹配返回 `line_start=15, line_end=15`，**禁止**发明 `matched_line` / `line=15` 等第三种字段。

### 禁止的变体（必须避免）

| 错误形式 | 问题 | 正确形式 |
|---|---|---|
| `chunk:3/10` | 一个字段编两份数据，AI 要拆分 | `chunk_index="3" total_chunks="10"` |
| `line:10-30` | 合并字符串，AI 要拆分且分隔符有歧义 | `line_start="10" line_end="30"` |
| `matched_line: 15` | 单行发明第三种字段名 | `line_start="15" line_end="15"` |
| `start_chunk`（当用作 chunk 定位 handle 时） | 与 `chunk_index` 命名漂移，AI 要判断等价性；`start_chunk` 仅保留作分页游标语义，见 Boundary Cases | `chunk_index` |
| `chunk_id`（暴露给 AI 时） | "id" 在 LLM 语料里常指 UUID/hash，AI 可能幻觉编值 | `chunk_index`（内部 ID 不暴露） |
| 返回 `index` 但入参 `chunk_index` | 名字不一致，AI 要语义映射 | 统一用 `chunk_index` |
| `chunk_count`（与 `total_chunks` 并存） | 同一概念两个名字，AI 要判断用哪个；当前代码 `retrieval.py` 的 `find_files`/`list_documents` 返回同时含两者，必须二选一 | 统一用 `total_chunks` |
| 返回 `source` 但输出为 `file_path` | 底层 dict key 和对外字段名不一致，格式层做隐式转换易漏 | 对外统一输出 `file_path`（底层 key 可保留 `source`，但格式化层必须显式映射并覆盖所有出口） |
| 同名 handle 返回是字符串、入参是 int | 形态漂移，AI 要做类型转换 | 形态一致（同为 int 或同为字符串） |
| `matched_line` / `line=15`（grep 消费侧历史形式） | 旧版本返回里可能出现；新代码禁止产出，但消费侧 AI 若遇到应理解为 `line_start==line_end=<matched_line>` | 新代码统一 `line_start==line_end` |

---

## How AI Chains Tools（为什么一致性重要）

nbrag 的多轮检索靠 handle 在函数间流动：

```
nbrag_retrieve 返回 → AI 读取 handle → AI 选下一个函数 → AI 把 handle 填进入参 → 下一个函数返回 → ...
```

handle 流动路径举例：
- `nbrag_retrieve` 返回 `doc_id + chunk_index` → 喂给 `get_adjacent_chunks(doc_id, chunk_index, ...)`
- `nbrag_retrieve` 返回 `doc_id + line_start + line_end` → 喂给 `get_chunks_by_lines(doc_id, line_start, line_end, ...)`
- `nbrag_retrieve` 返回 `file_path` → 喂给 `get_raw_file(file_path, ...)`
- `nbrag_retrieve_no_expand` 返回 `file_path` → 喂给 `get_file_chunks(file_path, ...)` 或 `get_raw_file(file_path, ...)`
- `grep` 返回 `file_path + line_start + line_end` → 喂给 `get_raw_file(file_path, ..., line_start, line_end)` 或 `get_chunks_by_lines(doc_id, line_start, line_end, ...)`
- `find_files` 返回 `file_path` → 喂给 `nbrag_retrieve_no_expand(filter_file_path=...)` 或 `get_raw_file(file_path, ...)`
- `find_definition` 返回 `file_path + line_start + line_end` → 喂给 `get_raw_file(file_path, ..., line_start, line_end)` 取定义完整上下文，或 `get_chunks_by_lines(doc_id, line_start, line_end, ...)` 取覆盖该定义的 chunk
- `list` 返回 `doc_id + file_path` → 喂给 `get_file_chunks(file_path, ...)` 或 `get_adjacent_chunks(doc_id, chunk_index, ...)`

AI 传递 handle 靠**模式匹配 + 语义联想**，不是查 schema 表。字段名相同时是纯字符串匹配（零幻觉）；字段名不同时 AI 要做语义等价判断（大概率对但有小概率错）；形态不同时 AI 要做值拆分（易错）。本 skill 把所有 handle 传递路径变成纯字符串匹配。

---

## Return Format Recommendation

为配合 handle 一致性，返回格式推荐 **XML 风格标签 + 纯文本正文**（不是 JSON），原因：

1. **正文零转义**：chunk 内容是代码/markdown/法律条文，JSON 要转义 `"` `\` 换行，破坏 LLM 对原文的理解通路；XML 标签内放纯文本，所见即所读。
2. **边界清晰**：`<chunk>...</chunk>` 明确起止，不怕内部空行；纯文本靠 `\n\n` 分隔易和内容空行混淆。
3. **handle 放属性，正文放标签内**：metadata 和 content 天然分层，AI 一眼区分"可复用 handle"vs"待阅读正文"。
4. **属性名直接对齐入参**：`line_start="10"` 的属性名 == 入参名 `line_start`，AI 直接抄。

### 标准返回结构

以 `nbrag_retrieve` 为例：

```xml
<nbrag_retrieve collection_name="my_kb" total_chunks="1234" bm25="on" rerank="BAAI/bge-reranker-v2-m3">

<ranked_hits>
<hit rank="1" file_path="D:/codes/foo.py" doc_id="abc123" chunk_index="3" total_chunks="10" line_start="15" line_end="28" scope="ClassA.get_by_id" dist="0.1234" score="0.5678">
<content>
def get_by_id(self, id):
    ...
</content>
</hit>
</ranked_hits>

<fetched_raw>
<raw file_path="D:/codes/foo.py" doc_id="abc123" line_start="8" line_end="35">
<content>
... 原始文件内容，原样无转义 ...
</content>
</raw>
</fetched_raw>

</nbrag_retrieve>
```

grep 示例（单行匹配 `line_start==line_end`，多行匹配 `line_start<line_end`）：

```xml
<nbrag_grep case_sensitive="false" filter_file_path="">

<matches>
<match file_path="D:/codes/foo.py" doc_id="abc123" line_start="15" line_end="15">
<content>
    raise ValueError("invalid id")
</content>
</match>
<match file_path="D:/codes/bar.py" doc_id="def456" line_start="40" line_end="42">
<content>
def process(data):
    # multi-line regex match
    return data
</content>
</match>
</matches>

</nbrag_grep>
```

### 属性 vs 子元素的规则

- **handle 字段** → 属性（`file_path="..."` / `doc_id="..."` / `chunk_index="..."` / `line_start="..."` / `line_end="..."` / `total_chunks="..."`）
- **标量展示字段** → 属性（`dist="..."` / `score="..."` / `rank="..."` / `scope="..."` / `filename="..."` / `symbol_type="..."` / `qualified_name="..."`）
- **正文内容** → `<content>` 子元素（纯文本，无转义）
- **结构化附加信息**（如 Python definition 的 `methods_summary`）→ 独立子元素

**标量→结构化提升兜底**：标量展示字段（如 `scope="ClassA.get_by_id"`）放属性；若某字段演化为结构化（如多层 scope 需拆成 `class` / `method` 两维，单属性值装不下），提升为独立子元素，原属性名变为标签名（如 `<scope class="ClassA" method="get_by_id">`）。判断标准：信息能否用单个属性值无歧义表达，能则属性，不能则子元素。

### 标签命名约定

每个函数有独立的根标签（不用占位符），条目级标签按函数语义命名。三个 `get_*_chunks` 函数虽然条目都叫 `<chunk>`，但根标签不同，差异信息放根标签属性或独立子元素，使 AI 能区分返回类型。

| 函数 | 根标签 | 集合标签 | 单条标签 | 差异信息归属 |
|---|---|---|---|---|
| `nbrag_retrieve_no_expand` | `<nbrag_retrieve_no_expand>` | `<ranked_hits>` | `<hit>` | 根属性：`bm25` / `rerank` / `filter_file_path` |
| `nbrag_retrieve` | `<nbrag_retrieve>` | `<ranked_hits>` + `<fetched_raw>` | `<hit>` / `<raw>` | 根属性同上；`<fetched_raw>` 内 `<raw>` 携带 `line_start`/`line_end` |
| `nbrag_retrieve_only_bm25` | `<nbrag_retrieve_only_bm25>` | `<ranked_hits>` | `<hit>` | 根属性：`bm25` / `rerank=off` |
| `nbrag_retrieve_only_vector` | `<nbrag_retrieve_only_vector>` | `<ranked_hits>` | `<hit>` | 根属性：`bm25=off` / `rerank=off` |
| `nbrag_grep` | `<nbrag_grep>` | `<matches>` | `<match>` | 根属性：`case_sensitive` / `filter_file_path`；单行匹配 `line_start==line_end`，多行匹配 `line_start<line_end` |
| `nbrag_find_definition` | `<nbrag_find_definition>` | `<definitions>` | `<definition>` | 单条属性：`symbol_type` / `qualified_name`；`<methods_summary>` 子元素（若有） |
| `nbrag_find_files` | `<nbrag_find_files>` | `<files>` | `<file>` | 单条属性：`filename` / `match` |
| `nbrag_get_file_chunks` | `<nbrag_get_file_chunks>` | `<chunks>` | `<chunk>` | 根属性：`start_chunk`（分页游标）/ `max_chunks` / `has_more`；单条属性：`scope` |
| `nbrag_get_adjacent_chunks` | `<nbrag_get_adjacent_chunks>` | `<chunks>` | `<chunk>` | 根属性：`window`（前后的 chunk 数）；单条属性：`scope` |
| `nbrag_get_chunks_by_lines` | `<nbrag_get_chunks_by_lines>` | `<chunks>` | `<chunk>` | 根属性：`requested_line_start` / `requested_line_end`；单条属性：`scope` |
| `nbrag_read_more_original_text` | `<nbrag_read_more_original_text>` | — | `<raw>` | 根属性：`total_lines` / `line_start` / `line_end`（返回范围） |
| `nbrag_list` | `<nbrag_list>` | `<documents>` | `<document>` | 根属性：`offset` / `limit`；单条属性：`filename` |
| `nbrag_stats` | `<nbrag_stats>` | `<collections>` | `<collection>` | 单条属性：`display_name` / `description` / `aliases` / `tags` / `chunk_size` / `chunk_overlap` / `last_ingested_at`（可选，有则写，无则省略） |

每个单条标签（`<hit>` / `<match>` / `<chunk>` / `<raw>` / `<document>` / `<definition>` / `<file>`）都应携带它能提供的 handle 属性（`file_path` / `doc_id` / `chunk_index` / `line_start` / `line_end` / `total_chunks` 按适用情况）。

`nbrag_stats` 的变长可选字段用"有则写、无则省略"原则，不写空属性，避免属性集膨胀。

---

## Error Return Format

错误返回也用标签包，便于 AI 分类错误并决策下一步：

```xml
<error type="invalid_file_path" field="filter_file_path">
filter_file_path must be a full absolute file_path returned by nbrag tools.
Recovery: use nbrag_find_files(pattern, collection_name) when you only know a filename, or nbrag_list(collection_name) to browse available file_path values.
</error>
```

`type` 属性让 AI 快速分类错误（`invalid_file_path` / `missing_collection` / `empty_collection` / `no_results`），`field` 属性指出错的是哪个参数。

---

## Boundary Cases（语义不同但值可互通）

有些字段语义不同但值可互通，这种情况**保留不同名字**以维护语义纯粹性，但在 docstring / Field description 里明确两者的值兼容关系。

### `file_path` vs `filter_file_path`

- `file_path`（入参）= 明确读取这个文件（如 `get_raw_file(file_path=...)`）
- `filter_file_path`（入参）= 把检索范围缩到这个文件（如 `nbrag_retrieve_no_expand(filter_file_path=...)`）

两者值是同一个（绝对路径 handle），但入参语义不同。保留不同名字，但在 `filter_file_path` 的 Field description 里加一句值兼容说明。

docstring 模板：
> `filter_file_path` must be a full absolute path previously returned as `file_path` by nbrag tools. The value is the same handle; only the parameter name differs to express "narrow retrieval to this file" vs "read this file directly".

### `chunk_index` vs `start_chunk`

- `chunk_index`（handle）= 定位到某个具体 chunk（如 `get_adjacent_chunks(doc_id, chunk_index, ...)`）
- `start_chunk`（分页游标）= 从第几个 chunk 开始分页浏览（如 `get_file_chunks(file_path, ..., start_chunk=0, max_chunks=10)`）

两者值都是 0-based chunk 序号，可互通。保留不同名字，但在 `start_chunk` 的 Field description 里加一句值兼容说明，并明确禁止把 `start_chunk` 当 chunk 定位 handle 传给 `get_adjacent_chunks`。

docstring 模板：
> `start_chunk` is a pagination cursor (0-based chunk index to start browsing from). Its value is compatible with the `chunk_index` handle returned by search tools — both are 0-based chunk indices. When you need to locate a specific chunk for `nbrag_get_adjacent_chunks`, use the `chunk_index` handle directly, not `start_chunk`.

---

## Handle vs Display Field（约束边界）

本 skill 只约束 **handle 字段**（会被下游函数复用的）。**展示字段**（只用一次、不跨函数复用）不在此约束范围：

| 类型 | 字段 | 约束 |
|---|---|---|
| handle | `file_path` / `doc_id` / `chunk_index` / `line_start` / `line_end` / `total_chunks` | 严格一致（名字 + 形态） |
| 展示 | `dist` / `score` / `rank` / `scope` / `bm25` / `rerank` | 内部一致即可，不强求和入参一致（因为没有对应入参） |

不要把"归一化"做过头——对纯展示字段强加"和入参一致"的约束没意义，因为根本没有对应入参，反而让返回啰嗦。

---

## Authoring Workflow

修改 nbrag 代码时按此流程检查：

1. **识别 touched 的 handle 字段**：本次改动涉及哪些 `file_path` / `doc_id` / `chunk_index` / `line_start` / `line_end` / `total_chunks`？
2. **检查返回↔入参一致性**：读下游函数签名（`nbrag/server.py` 里对应 tool 的 `Field(...)`），对比返回里出现的 handle 字段名与下游入参名是否**字符串完全相同**（不是语义等价）。
3. **检查形态一致性**：返回里的值形态（int / 字符串 / 合并字符串），是否和下游入参的形态相同？
4. **检查范围类字段**：是否用了 `line:N-M` / `chunk:X/Y` 等合并字符串？如果有，拆成两个独立字段。
5. **检查冗余编码**：是否一个字段编了两份数据（如 `chunk:3/10`）？如果有，拆成 `chunk_index` + `total_chunks`。是否还有 `chunk_count` 和 `total_chunks` 并存？如果有，统一成 `total_chunks`。
6. **检查单行表达**：grep 单行匹配是否用了 `matched_line` / `line=15` 等第三种字段？如果有，改成 `line_start==line_end`。
7. **检查底层 key 到对外字段的映射**：`nbrag/retrieval.py` 返回的 dict key（`source` / `index` / `line_number`）是否在 `nbrag/mcp_tools.py` 格式化层完整映射到 canonical 名（`file_path` / `chunk_index` / `line_start`+`line_end`）？映射是否覆盖所有出口？
8. **检查返回格式**：是否用了 XML 标签 + 纯文本正文？handle 是否放属性？正文是否放 `<content>` 子元素？根标签是否用具体函数名（非占位符）？
9. **检查 docstring / Field description**：是否还提到废弃字段名（`chunk:X/Y` / `line:N-M` / `matched_line`）？如果有，清理。boundary case（`filter_file_path` / `start_chunk`）的 Field description 是否有值兼容说明？
10. **更新 skill 文档**：如果 handle 流动路径变化，同步更新 `nbrag/skills/nbrag-workflow/SKILL.md` 里的 follow-up handle 说明。

---

## Failure Smells

看到这些味道，应停下来按本 skill 重写：

- 返回里出现 `chunk:X/Y` 合并字符串
- 返回里出现 `line:N-M` 合并字符串
- 返回里出现 `matched_line` 而不是 `line_start`+`line_end`
- 返回里出现 `chunk_count` 和 `total_chunks` 并存
- 同一概念在不同函数里有不同字段名（`chunk_index` vs `start_chunk` vs `chunk_id` vs `index`）
- 同一 handle 在返回是字符串、入参是 int（形态漂移）
- 底层 `retrieval.py` 返回 `source` / `index` / `line_number`，但 `mcp_tools.py` 格式化层未映射到 `file_path` / `chunk_index` / `line_start`+`line_end` 就直接输出
- docstring / Field description 里还提到废弃字段名（`chunk:X/Y` / `line:N-M` / `matched_line`）
- `filter_file_path` / `start_chunk` 的 Field description 没有值兼容说明
- 返回正文用 JSON 字符串值（带转义）而不是纯文本标签
- handle 字段和展示字段混在同一行用同样格式，AI 无法区分
- chunk 之间只靠空行分隔，没有明确边界标签
- 根标签用占位符（如 `<nbrag_get_...>`）而非具体函数名
- error 返回是纯散文，AI 无法快速分类错误类型

---

## Final Check

提交前快速检查：
- 每个 handle 字段（`file_path` / `doc_id` / `chunk_index` / `line_start` / `line_end` / `total_chunks`）在所有函数的返回和入参里**名字完全相同**
- 每个 handle 字段在返回和入参里**形态相同**（同为 int 或同为字符串，没有返回字符串、入参 int 的情况）
- 范围类 handle（`line_start` + `line_end`）全部是两个独立 int 字段，没有 `line:N-M` 合并字符串
- 序号类 handle（`chunk_index` + `total_chunks`）是两个独立字段，没有 `chunk:X/Y` 合并形式，也没有 `chunk_count` 别名并存
- 单行匹配用 `line_start==line_end`，没有 `matched_line` 第三种字段名
- 返回格式是 XML 标签 + 纯文本正文，handle 放属性，正文放 `<content>` 子元素，根标签用具体函数名
- 底层 `retrieval.py` 的 `source` / `index` / `line_number` 在 `mcp_tools.py` 格式层完整映射到 canonical 名，覆盖所有出口
- docstring / Field description 里没有废弃字段名（`chunk:X/Y` / `line:N-M` / `matched_line`）
- 边界 case（`file_path` vs `filter_file_path`、`chunk_index` vs `start_chunk`）在 Field description 里有值兼容说明
- 展示字段（`dist` / `score` / `rank` / `scope` / `filename` / `symbol_type` / `qualified_name` / `methods_summary`）没有被误纳入 handle 一致性约束

如果改完后你仍然怀疑：
- AI 会把 `line:10-30` 当成填 `line_start` / `line_end` 的输入
- AI 会从 `chunk:3/10` 里提取错值填 `chunk_index`
- AI 会把 `matched_line` 当成和 `line_start` 不同的概念
- AI 会因为 `chunk_count` 和 `total_chunks` 并存而不知道用哪个
- AI 会因为返回是 JSON 转义字符串而误解 chunk 正文

说明这次改动还不够好，继续按本 skill 改。
