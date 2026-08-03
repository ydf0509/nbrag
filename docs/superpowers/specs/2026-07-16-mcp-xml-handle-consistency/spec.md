# Spec: nbrag MCP 返回格式 XML 化 + Handle 字段一致性

> **历史接口快照**
>
> 本规格使用的是旧 MCP 名称。映射为：`nbrag_search` → `nbrag_retrieve_no_expand`，`nbrag_search_and_fetch` → `nbrag_retrieve`，`nbrag_search_only_bm25` → `nbrag_retrieve_only_bm25`，`nbrag_search_only_vector` → `nbrag_retrieve_only_vector`；请以当前 `nbrag/server.py` 暴露的工具 schema 为准。

**日期**: 2026-07-16
**类型**: 格式化层重构（逻辑零改动）
**前置 skill**: `.agents/skills/nbrag-handle-consistency/SKILL.md`

## 背景与动机

nbrag 是 agentic RAG，靠多轮检索打组合拳。AI 把 A 函数返回的 handle 字段（file_path / doc_id / chunk_index / line_start / line_end）填进 B 函数入参，实现链式检索。

当前实现存在两类问题，导致 AI 在衔接点多走认知中介、幻觉率上升：

1. **返回格式对 AI 不友好**：正文用 JSON 字符串值，引号/换行需转义（`\"` / `\n`），AI 读取和复述都要做"反转义"，注意力被转义符劫持，边界识别要维护状态，复述给用户时易失真。
2. **handle 字段命名/形态漂移**：`chunk:3/10` / `chunk_index` / `start_chunk` / `index` / `chunk_id` 五种叫法；`line:10-30` 合并字符串 vs `line_start+line_end` 两个 int；`matched_line` 第三种字段。AI 在每个衔接点要做"字段名等价判断 + 值形态转换"，每步都是幻觉源。

## 目标

1. 所有 MCP 工具返回改成 **XML 标签 + 纯文本正文** 格式：handle 放属性（紧凑可提取），正文放 `<content>` 子元素（零转义可读）。
2. handle 字段跨函数**名字+形态完全一致**，AI 从返回抄到入参零转换。
3. 清理所有 docstring / Field description / workflow skill 里提到的废弃字段名。

## 非目标

- 不动检索逻辑、rerank、BM25、chunking 逻辑
- 不动函数签名（入参名、类型、默认值）
- 不动 `retrieval.py` 底层 dict key（`source` / `index` / `line_number` 保持原样），只在 `mcp_tools.py` 格式层做显式映射
- 不改 `nbrag_add_document` / `nbrag_delete`（未暴露为 MCP tool，人工脚本调用，保持现状）
- 不保留/不写正式测试（用户明确说不用管测试）

## 改造范围

### 要改的文件

| 文件 | 改动 |
|---|---|
| `nbrag/mcp_tools.py` | 13 个函数的 return 语句重写为 XML；helper 函数重构；加映射 helper |
| `nbrag/server.py` | 清理 Field description 和 docstring 里的废弃字段名；boundary case 补值兼容说明 |
| `nbrag/skills/nbrag-workflow/SKILL.md` | 清理废弃字段名提法 |

### 不改的文件

- `nbrag/retrieval.py`（底层 dict key 保持）
- `nbrag/chunker.py`（chunking 逻辑）
- `nbrag/bm25_index.py`（BM25 逻辑）
- 任何测试文件

## XML 格式总规范

### 整体结构

```
<根标签 全局属性>
Follow-up handles 提醒句（一行）

<集合标签>
<单条标签 handle属性 展示属性>
<content>
正文（纯文本，零转义）
</content>
</单条标签>
</集合标签>

</根标签>
```

### 属性规则

- **handle 属性**（必须跨函数一致）：`file_path` / `doc_id` / `chunk_index` / `total_chunks` / `line_start` / `line_end`
- **展示属性**（仅内部一致）：`dist` / `score` / `rank` / `scope` / `filename` / `symbol_type` / `qualified_name` / `bm25` / `rerank` / `has_more` 等
- **属性顺序**：`rank` 最前 → handle 属性 → 展示属性
- **可选属性**：有则写、无则省略，不写空属性（`scope=""`）
- **布尔/枚举**：`has_more="true"/"false"`、`bm25="on"/"off"`、`rerank="<model>"或"off"`
- **值类型**：属性值在 XML 里是字符串，但内容是字面量（`chunk_index="3"`），AI 能直接抄

### 正文规则

- 正文放 `<content>` 子元素，纯文本，**零转义**
- 正文里若恰好出现 `</content>`（极罕见），先不加 CDATA（YAGNI），遇真实 bug 再加
- 无正文的单条标签（清单类）自闭合 `<file ... />`，不写 `<content>`

### Section 分隔

- 集合标签之间用空行分隔
- 根标签内、集合标签外，放一句 handle 提醒（硬契约，防 AI 写错字段名）

### 错误返回

```
<error type="..." field="...">
散文说明
Recovery: ...
</error>
```

错误 type 枚举：`invalid_file_path` / `missing_collection` / `empty_collection` / `no_results` / `not_found` / `invalid_param`

### Header 散文处理

- **删除** query / bm25_query / fetch_context_chars 的解释（Field description 已说）
- **保留** 一句 handle 提醒（放根标签开标签后第一行）
- **保留** `nbrag_stats` 的 routing 提醒（前后各一句，引导选 collection_name 和下一步）

## 各函数返回结构

### 检索类（ranked hits）

**`nbrag_search` / `nbrag_search_only_bm25` / `nbrag_search_only_vector`**（共用内部 `_format_search_results`）：

```xml
<nbrag_search collection_name="my_kb" total_chunks="1234" bm25="on" rerank="BAAI/bge-reranker-v2-m3">
Follow-up handles in <hit>: file_path, doc_id, chunk_index, line_start, line_end.

<ranked_hits>
<hit rank="1" file_path="D:/codes/foo.py" doc_id="abc123" chunk_index="3" total_chunks="10" line_start="15" line_end="28" scope="ClassA.get_by_id" dist="0.1234" score="0.5678">
<content>
def get_by_id(self, id):
    ...
</content>
</hit>
</ranked_hits>

</nbrag_search>
```

- `include_content=False` 时 `<hit>` 不带 `<content>`
- `filter_file_path` 为空时省略该属性
- `bm25`/`rerank` 值：`on`/`off`/具体模型名

**`nbrag_search_and_fetch`**（额外 `<fetched_raw>` section）：

```xml
<nbrag_search_and_fetch collection_name="my_kb" total_chunks="1234" bm25="on" rerank="...">
Follow-up handles in <hit>: file_path, doc_id, chunk_index, line_start, line_end.

<ranked_hits>
<hit rank="1" file_path="..." doc_id="..." chunk_index="..." total_chunks="..." line_start="..." line_end="..." scope="..." dist="..." score="...">
<content>...</content>
</hit>
</ranked_hits>

<fetched_raw>
<raw file_path="..." doc_id="..." line_start="8" line_end="35">
<content>
... 原始文件内容，原样无转义 ...
</content>
</raw>
</fetched_raw>

</nbrag_search_and_fetch>
```

- 同一文件多个不连续 range → 平铺多个 `<raw>`，不做 `<file>` 分组

### 精确匹配类

**`nbrag_grep`**：

```xml
<nbrag_grep case_sensitive="false">
Follow-up handles in <match>: file_path, doc_id, line_start, line_end.

<matches>
<match file_path="D:/codes/foo.py" doc_id="abc123" line_start="15" line_end="15">
<content>
    raise ValueError("invalid id")
</content>
</match>
<match file_path="D:/codes/bar.py" doc_id="def456" line_start="40" line_end="42">
<content>
def process(data):
    return data
</content>
</match>
</matches>

</nbrag_grep>
```

- 单行匹配：`line_start==line_end`
- 多行匹配：`line_start<line_end`
- 废弃 `matched_line` / `line_range`

**`nbrag_find_definition`**：

```xml
<nbrag_find_definition>
Follow-up handles in <definition>: file_path, doc_id, line_start, line_end.

<definitions>
<definition symbol_type="class" qualified_name="UserService" file_path="D:/codes/services.py" doc_id="abc123" line_start="10" line_end="50">
<content>
class UserService:
    ...
</content>
<methods_summary>
- get_by_id(id)
- delete(id)
</methods_summary>
</definition>
</definitions>

</nbrag_find_definition>
```

- `symbol_type`：`class`/`function`/`method`/`regex_fallback`
- `methods_summary` 作为子元素（可能多行）
- regex_fallback 靠 `symbol_type` 属性区分，不加额外标签

### chunk 视图类

**`nbrag_get_file_chunks`**（分页）：

```xml
<nbrag_get_file_chunks file_path="D:/codes/foo.py" doc_id="abc123" total_chunks="10" total_lines="200" start_chunk="0" max_chunks="10" has_more="false">
Follow-up handles in <chunk>: chunk_index, line_start, line_end.

<chunks>
<chunk chunk_index="0" total_chunks="10" line_start="1" line_end="28" scope="module">
<content>...</content>
</chunk>
</chunks>

</nbrag_get_file_chunks>
```

**`nbrag_get_adjacent_chunks`**（window 扩展）：

```xml
<nbrag_get_adjacent_chunks file_path="D:/codes/foo.py" doc_id="abc123" total_chunks="10" window="3" anchor_chunk_index="5">
Follow-up handles in <chunk>: chunk_index, line_start, line_end.

<chunks>
<chunk chunk_index="2" total_chunks="10" line_start="..." line_end="..." scope="...">
<content>...</content>
</chunk>
</chunks>

</nbrag_get_adjacent_chunks>
```

- `anchor_chunk_index` = 入参的 `chunk_index`，放根属性让 AI 知道围绕哪个 chunk 扩展

**`nbrag_get_chunks_by_lines`**（按行范围查 chunk）：

```xml
<nbrag_get_chunks_by_lines doc_id="abc123" file_path="D:/codes/foo.py" total_chunks="10" requested_line_start="15" requested_line_end="40">
Follow-up handles in <chunk>: chunk_index, line_start, line_end.

<chunks>
<chunk chunk_index="3" total_chunks="10" line_start="15" line_end="28" scope="...">
<content>...</content>
</chunk>
</chunks>

</nbrag_get_chunks_by_lines>
```

**`nbrag_read_more_original_text`**（无 chunk 结构，纯原文）：

```xml
<nbrag_read_more_original_text file_path="D:/codes/foo.py" doc_id="abc123" total_lines="200" line_start="1" line_end="200">
<content>
... 原始文件内容，原样无转义 ...
</content>

</nbrag_read_more_original_text>
```

- 没有 `<chunks>` 集合标签，直接 `<content>` 子元素
- `line_start`/`line_end` 放根属性表示返回的范围

### 清单类（无正文，自闭合标签）

**`nbrag_find_files`**：

```xml
<nbrag_find_files>
Follow-up handle in <file>: file_path.

<files>
<file file_path="D:/codes/foo.py" doc_id="abc123" filename="foo.py" total_chunks="10" match="foo"/>
<file file_path="D:/codes/bar.py" doc_id="def456" filename="bar.py" total_chunks="5" match="bar"/>
</files>

</nbrag_find_files>
```

- 废弃 `chunk_count`，统一 `total_chunks`

**`nbrag_list`**：

```xml
<nbrag_list collection_name="my_kb" offset="0" limit="100">
Follow-up handles in <document>: doc_id, file_path.

<documents>
<document doc_id="abc123" file_path="D:/codes/foo.py" filename="foo.py" total_chunks="10"/>
<document doc_id="def456" file_path="D:/codes/bar.py" filename="bar.py" total_chunks="5"/>
</documents>

</nbrag_list>
```

- 废弃 `chunk_count`，统一 `total_chunks`

**`nbrag_stats`**：

```xml
<nbrag_stats>
Use collection_name exactly as shown below when calling retrieval tools.

<collections>
<collection collection_name="my_kb" docs="50" chunks="1200" display_name="My Knowledge Base" description="Internal policies." aliases="policies, manuals" tags="internal, policy" chunk_size="1000" chunk_overlap="150" last_ingested_at="2026-07-15"/>
</collections>

After choosing collection_name, continue with nbrag_search_and_fetch for most questions.

</nbrag_stats>
```

- 变长可选字段有则写、无则省略
- `aliases` / `tags` 用逗号分隔字符串（放属性）
- 保留前后 routing 提醒句

### 错误返回（所有函数通用）

```xml
<error type="invalid_file_path" field="filter_file_path">
filter_file_path must be a full absolute file_path returned by nbrag tools.
Recovery: use nbrag_find_files(pattern, collection_name) when you only know a filename, or nbrag_list(collection_name) to browse available file_path values.
</error>
```

```xml
<error type="missing_collection" field="collection_name">
collection 'my_kb' does not exist.
Available collections: ['other_kb']
Recovery: call nbrag_stats() to inspect valid collection_name values, then retry with the correct prepared knowledge base.
</error>
```

```xml
<error type="no_results" field="query">
No results (collection has 1234 chunks).
Recovery: verify collection_name, minimally normalize the natural-language query without changing intent, provide a bm25_query as lexical anchors, try nbrag_grep for exact terms, or use nbrag_find_files + filter_file_path to narrow to a known file.
</error>
```

## 底层 key 映射

`retrieval.py` 底层 dict key 与 canonical handle 的映射关系，集中在 `mcp_tools.py` 顶部两个 helper：

```python
def _meta_file_path(meta: dict) -> str:
    """Map retrieval.py's source key to canonical file_path."""
    return str(meta.get("source", meta.get("filename", "?")))

def _meta_chunk_index(meta: dict) -> str:
    """Map retrieval.py's index key to canonical chunk_index."""
    return str(meta.get("chunk_index", meta.get("index", "?")))
```

其他 key 直接用（`line_start` / `line_end` / `doc_id` / `total_chunks` 在底层已合规）。

grep 的 `line_number` → `line_start`+`line_end`（1→2 映射），就地处理不写 helper。

find_definition 的 `r.get("source")` → 输出 `file_path`，用 `_meta_file_path` helper。

## 实施步骤

### 步骤 1：清理 `server.py` 文案

- 清理所有 `Field(description=...)` 里提到的废弃字段名（`chunk:X/Y` / `line:N-M` / `matched_line`）
- 清理所有 docstring 里提到的废弃字段名
- `filter_file_path` 的 Field description 补值兼容说明：`Value comes from the file_path handle returned by nbrag tools.`
- `start_chunk` 的 Field description 补值兼容说明：`0-based chunk index; same value space as the chunk_index handle, but used as a pagination cursor (semantic: 'start browsing from chunk N').`

### 步骤 2：重构 `mcp_tools.py` 的 helper 函数

- `_path_error` → `<error type="invalid_file_path" field="...">` 格式
- `_collection_issue_text` → 根据 total==0 拆成 `missing_collection` / `empty_collection` 两种 type
- `_no_search_results_text` → `<error type="no_results" field="query">` 格式
- `_collection_presence_issue_text` → 同样拆 type
- 加 `_meta_file_path` / `_meta_chunk_index` 映射 helper

### 步骤 3：重构检索类函数返回

- `_format_search_results`（`nbrag_search` / `nbrag_search_only_bm25` / `nbrag_search_only_vector` 共用）
- `nbrag_search_and_fetch`（额外 `<fetched_raw>` section）
- `nbrag_grep`（`matched_line` → `line_start==line_end`）
- `nbrag_find_definition`（`methods_summary` 作为子元素）

### 步骤 4：重构 chunk 视图类函数返回

- `nbrag_get_file_chunks`（分页，根属性带 `start_chunk`/`max_chunks`/`has_more`）
- `nbrag_get_adjacent_chunks`（window 扩展，根属性带 `window`/`anchor_chunk_index`）
- `nbrag_get_chunks_by_lines`（按行范围，根属性带 `requested_line_start`/`requested_line_end`）
- `nbrag_read_more_original_text`（无 chunk 结构，直接 `<content>`）

### 步骤 5：重构清单类函数返回 + 清理 workflow skill

- `nbrag_find_files` / `nbrag_list` / `nbrag_stats` 改 XML，废弃 `chunk_count` 统一 `total_chunks`
- `nbrag_help` 保持散文，清理字段名提法
- `nbrag/skills/nbrag-workflow/SKILL.md` 清理废弃字段名提法

## 标签命名约定表

| 函数 | 根标签 | 集合标签 | 单条标签 |
|---|---|---|---|
| `nbrag_search` | `<nbrag_search>` | `<ranked_hits>` | `<hit>` |
| `nbrag_search_only_bm25` | `<nbrag_search_only_bm25>` | `<ranked_hits>` | `<hit>` |
| `nbrag_search_only_vector` | `<nbrag_search_only_vector>` | `<ranked_hits>` | `<hit>` |
| `nbrag_search_and_fetch` | `<nbrag_search_and_fetch>` | `<ranked_hits>` + `<fetched_raw>` | `<hit>` + `<raw>` |
| `nbrag_grep` | `<nbrag_grep>` | `<matches>` | `<match>` |
| `nbrag_find_definition` | `<nbrag_find_definition>` | `<definitions>` | `<definition>` |
| `nbrag_find_files` | `<nbrag_find_files>` | `<files>` | `<file>` |
| `nbrag_get_file_chunks` | `<nbrag_get_file_chunks>` | `<chunks>` | `<chunk>` |
| `nbrag_get_adjacent_chunks` | `<nbrag_get_adjacent_chunks>` | `<chunks>` | `<chunk>` |
| `nbrag_get_chunks_by_lines` | `<nbrag_get_chunks_by_lines>` | `<chunks>` | `<chunk>` |
| `nbrag_read_more_original_text` | `<nbrag_read_more_original_text>` | （无） | （根标签直接含 `<content>`） |
| `nbrag_list` | `<nbrag_list>` | `<documents>` | `<document>` |
| `nbrag_stats` | `<nbrag_stats>` | `<collections>` | `<collection>` |

## 风险点

1. **XML 标签和正文冲突**：正文里若出现 `</content>` 会破坏结构。概率极低，先不加 CDATA，遇真实 bug 再加。
2. **属性值里的引号**：`file_path`/`scope`/`aliases`/`tags` 不会含引号，先不转义，遇真实 bug 再加。
3. **改动面广容易漏**：13 个函数 + helper + server.py + workflow skill。缓解：按步骤 1-5 顺序改，每步用 grep 扫一遍确认无废弃字段名残留。
4. **`nbrag_add_document` / `nbrag_delete` 不改**：未暴露为 MCP tool，保持现状。

## 验证方式

**不依赖 Trae MCP 重连**，用独立端口 + Python 脚本自测：

1. 启动独立 MCP 实例（端口 9109，避免和 Trae 的 9101 冲突）：
   ```powershell
   D:/ProgramData/miniconda3/envs/py312/python.exe -m nbrag --transport streamable-http --port 9109
   ```

2. 写 Python 自测脚本（改造期间临时工具，不进 CI、不保留为正式测试），验证：
   - 每个函数返回是否是合法的 XML 标签结构
   - handle 字段名是否和 `server.py` 入参名完全一致
   - 关键 handle 流动路径：`search_and_fetch` 返回的 `file_path`/`doc_id`/`chunk_index`/`line_start`/`line_end` 能否直接填进 `get_adjacent_chunks` / `get_chunks_by_lines` / `get_raw_file` 并成功调用
   - 错误返回是否是 `<error type="..." field="...">` 格式

3. Trae MCP 验证留给用户手动做：改造完成后重启 Trae 的 MCP 服务（9101），在对话里实际用一下看效果。

## 完成定义

- 13 个 MCP 工具函数返回全部改成 XML 格式
- handle 字段名跨函数完全一致（`file_path` / `doc_id` / `chunk_index` / `total_chunks` / `line_start` / `line_end`）
- `server.py` Field description 和 docstring 无废弃字段名残留
- `nbrag-workflow/SKILL.md` 无废弃字段名残留
- 自测脚本验证 handle 流动路径零转换
- `nbrag_add_document` / `nbrag_delete` 保持现状未改
- `retrieval.py` 底层 dict key 未改
