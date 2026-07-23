---
name: nbrag-workflow
description: 当任务需要检索已导入的 nbrag 知识库，或在 nbrag 检索工具与后续扩展工具之间做选择时使用。
---

# nbrag workflow

nbrag 是 agentic RAG MCP，不是 one-shot search box。

单次检索几乎永远不够。chunk 是 incomplete fragment，context 止于 chunk boundary。直接拿 chunk 回答，会漏掉边界外的 evidence。

> 实际能调用和文档里的不一样和文档里的不一样，很可能带前缀，例如`nbrag_help`可能对应 `mcp__nbrag__nbrag_help`。
> 以你拿到的工具列表为准。

nbrag最常用工具：
`nbrag` 最常用的除了 `nbrag_help` `nbrag_stats`必须使用到，`nbrag_search_and_fetch`是最常用的检索工具，基于检索到的chunk后，请必须使用 `nbrag_get_raw_file` 继续获取更大范围的原始内容。

调用nbrag的原则：
你的首要目的是通过nbrag一系列工具，检索足够的rag知识库内容，然后回答用户问题。严禁偷懒为了节约tokens，而不使用nbrag的一组工具配合打组合拳。
`nbrag_search_and_fetch`虽然能语义向量和bm25检索到多条chunk内容，但是必须配合`nbrag_get_raw_file`打组合拳获取chunk周围大范围的原始内容。

最重要原则是，要准确回答用户问题。比起浪费tokens和调用多次工具造成的耗时，没有检索足够的知识内容就开始胡说八道回答用户问题，后者的方式行为会更让用户更加痛恨你。

---

## 启动

首次使用 nbrag 前，调 `nbrag_help()` 获取路由指南。
一次成功响应在同一会话内可复用。如果 context 被压缩或不确定还在不在，就再调一次。
如果指南已经在上下文里，直接用工具，别重复调 help。

如果 `collection_name` 未知，就调 `nbrag_stats()` 拿确切的 collection 名。
collection 和 routing 都清楚后，默认用 `nbrag_search_and_fetch()`。
如果需要更细的控制或只要 metadata，就用 `nbrag_search()`。

---

## 工具表

| 需求 | 工具 | 何时用 | 何时换 |
|---|---|---|---|
| 路由指南不在上下文 | `nbrag_help()` | 首次 nbrag 调用前 | 会话已有 help 响应 |
| `collection_name` 未知 | `nbrag_stats()` | 检索前拿确切 collection 名 | 已知 collection |
| 默认 semantic 检索 | `nbrag_search_and_fetch()` | ranked discovery + 局部 original-text excerpt | 需要 full original text 或 line range |
| 更细控制 | `nbrag_search()` | 控制 rerank / BM25 / `include_content` / `filter_file_path` | 想一次拿 hit + 自动取证 |
| lexical-only 诊断 | `nbrag_search_only_bm25()` | 检查 exact-term recall | 正常作答 |
| vector-only 诊断 | `nbrag_search_only_vector()` | 检查 semantic recall（无 BM25） | 正常作答 |
| literal/regex matching | `nbrag_grep()` | 在 stored original text 逐行匹配 | 问题关于 semantics 或 paraphrase |
| Python class/function/method | `nbrag_find_definition()` | 已知或近乎知道 symbol 名 | 非 Python 或模糊概念 |
| 只知文件名片段 | `nbrag_find_files()` | 知道 filename fragment 或 partial path | 已有 full `file_path` |
| 浏览已导入文档 | `nbrag_list()` | 需要 `doc_id` 和 `file_path` 清单 | 回答语义问题 |
| overlap-free original text | `nbrag_get_raw_file()` | clean quoting、更宽 source context 或 line range — **补全 chunk 的主力** | 需要 chunk boundaries 或 scope |
| 分页 chunk view | `nbrag_get_file_chunks()` | chunk-by-chunk 浏览 | 需要 overlap-free 原文 |
| 在 hit 周围扩展 | `nbrag_get_adjacent_chunks()` | 有 `doc_id` + `chunk_index` | 只有 grep 输出，没有 `chunk_index` |
| 按 line range 取 chunk | `nbrag_get_chunks_by_lines()` | 有 `doc_id` + `line_start` + `line_end` | 只需要 raw text |

---

## semantic vs lexical

**semantic retrieval** → meaning / explanation / usage / examples / concepts / paraphrases
- `nbrag_search_and_fetch()`
- `nbrag_search()`

**lexical retrieval** → exact wording matters
- `bm25_query` 在 search 工具内做 lexical anchor
- `nbrag_grep()` 在 stored original text 上做 literal/regex

bm25_query 适合的 token: article numbers / headings / exact phrases / identifiers / class names / function names / constants / imports / decorators / error strings / codes

`nbrag_grep()` 不是 semantic search。
`bm25_query` 不是另一个 semantic question。

---

## `query` vs `bm25_query`

这两个要一起规划，不是事后补充。

### `query`
- semantic question，vector retrieval + reranking 用
- 保持是一个真实问题，不是 keyword 堆砌
- 如果用户说"他/它/这个"，就搞清楚指谁，补上漏掉的名字，顺手修错别字
- 保留用户具体性。例如 `关羽怎么死的` → `query` 用 `关羽怎么死的` 或 `关羽的死因是什么`
- 别变成 keyword bag

### `bm25_query`
- lexical anchor，BM25 用
- 比 `query` 更 lexical、更 anchor-rich、更 source-facing
- 用源文里可能字面出现的词：names / aliases / article numbers / codes / API names / class names / function names / headings / constants / error strings / places / event markers
- 如果多个 anchor 指向同一 evidence，可以组合


跨轮改进 `bm25_query`：如果检索揭示了更好的措辞，就更新 anchors。

示例：用户问 `关羽怎么死的`，`query` 贴近原意。如果先前命中浮现了 `麦城` `败走麦城` `遇害`，就把这些加到后续的 `bm25_query`，因为史书用事件/地点措辞描述死亡，而不是用现代词 `死`。

同理：法律用 article numbers + 法律术语，代码用 class + method + exception text，排错用 error codes + API names，手册用 titles + 重复短语。

---

## query rewriting

- `query` 保留语义目标，别变 keyword bag
- `bm25_query` 提供 lexical anchors
- 如果用户措辞太短或太弱，就加 source-facing 措辞：aliases / titles / dates / places / event markers / headings / identifiers
- 先前命中的有用词用到后续检索
- 如果是比较类问题，分别取 A 证据、B 证据、关系证据
- 如果是多部分问题，先分解，再决定单次或并行检索
- 多查是为了找更多证据，但最终答案要对照证据确认

---

## chunk vs raw — 三层 evidence

| 层级 | 来源 | 边界 |
|---|---|---|
| chunk fragment | `<nbrag_chunk_content>` under `<nbrag_ranked_hit>` / `<nbrag_chunk>` | 止于 chunk boundary, incomplete |
| fetched raw excerpt | `<nbrag_raw_content>` under `<nbrag_raw_excerpt>` | 受 `fetch_context_chars` 限制, 不是整个文件 |
| complete original text | `nbrag_get_raw_file()` | stored original file snapshot, overlap-free |

其他边界：
- `<nbrag_match>` 下的 `<nbrag_original_text_content>` 受 `match_context_chars` 限制
- `<nbrag_definition_content>` 是 AST-aware definition body；`regex_fallback` 只是 candidate text match

**chunk 必须扩展。** 如果 chunk 对回答有用，就用其 `file_path` 和 line 调 `nbrag_get_raw_file` 取更大范围的 original text。不能只靠 chunk 回答。

`nbrag_get_raw_file` 默认有限范围读取：如果同时传了 `line_start` 和 `line_end`，就把 `line_end` 设为 `line_start + 500`。别为了省 token 选更小窗口。例外是用户明确要求 exact quote、field 或特定 line。如果需要完整文件，就省略两个 bounds。

---

## 何时用 `nbrag_get_raw_file()`

- 需要 stored original text
- 需要 overlap-free 读取，（无重叠的原始内容）
- 需要 clean quoting
- 需要更宽的 source context
- 需要特定 line range
- 需要补全 chunk

## 何时用 chunk tools

- 需要 chunk boundaries
- 需要 scope metadata
- 需要 line metadata + chunk structure
- 需要在 hit 周围做 local expansion

Chunk tools:
- `nbrag_get_file_chunks()`
- `nbrag_get_adjacent_chunks()`
- `nbrag_get_chunks_by_lines()`

边界：
- raw-file = overlap-free 的 stored original snapshot
- chunk view = chunk-structured，neighboring chunks 包含 configured overlap
- fetched raw excerpt = overlap-free excerpt，受 `fetch_context_chars` 限制

---

## Python symbol lookup

`nbrag_find_definition()` 专门处理 Python `.py` 的 class/function/method。
先用 search 或 grep 确定 symbol 名，再用 find_definition。

适用于：`UserService` / `get_by_id` / `MyClass.__init__`

它不是通用的"在任何地方 find definition"工具。
如果是非 Python 文本，用 `nbrag_grep()`（exact wording）或 `nbrag_search_and_fetch()`（semantic discovery）。

无 `chunk_index`：
- `<nbrag_definition>` 暴露 `file_path`、`doc_id`、`line_start`、`line_end`，不含 `chunk_index`
- 别把 `line_start` 当 `chunk_index` 传给 `nbrag_get_adjacent_chunks()`
- 如果要在定义周围扩展，用 `nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name)` 或 `nbrag_get_raw_file(file_path, collection_name, line_start, line_end)`

---

## 复用 returned fields

结果实体自带 `key = value` fields。选一个实体，把它的 fields 复制进下一次调用。

| 来源实体 | 可复用 fields |
|---|---|
| `<nbrag_ranked_hit>` (search / search_and_fetch / only_bm25 / only_vector) | `file_path`, `doc_id`, `chunk_index`, `line_start`, `line_end` |
| `<nbrag_match>` (grep) / `<nbrag_definition>` (find_definition) | `file_path`, `doc_id`, `line_start`, `line_end`（无 `chunk_index`） |
| `<nbrag_file>` (find_files) / `<nbrag_document>` (list) | `file_path`, `doc_id` |

### `file_path`
- 可以调 `nbrag_get_raw_file(file_path, collection_name)`
- 可以调 `nbrag_get_file_chunks(file_path, collection_name)`
- 可以在 search 或 grep 里传 `filter_file_path=...`

规则：`file_path` 必须是 nbrag 返回的 full absolute path。别用 basename、relative 或 guessed path。如果只知片段，先调 `nbrag_find_files()`。

### `doc_id + chunk_index`
- 可以调 `nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name)`

`chunk_index` 来源：search 的 `<nbrag_ranked_hit>`，或 chunk tools 的 `<nbrag_chunk>`。
grep 和 find_definition 不暴露 `chunk_index`。

### `doc_id + line_start + line_end`
- 可以调 `nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name)`

### `file_path + line range`
- 可以调 `nbrag_get_raw_file(file_path, collection_name, line_start, line_end)`

---

## `filter_file_path`

收窄检索到一个存储文件。它不是轻量的 ranking preference。
当前 behavior：
- vector retrieval 收窄到单文件
- 跳过 cross-file BM25 fusion

如果设了 `filter_file_path`，返回的 `bm25` 属性会显示 `off`，因为跳过了 cross-file BM25。这是预期行为。
`nbrag_search_only_bm25()` 是例外，仍可在过滤文件内用 BM25。

---

## 多轮检索正常流程

1. 如果需要，先确定 collection
2. 用 semantic discovery（`nbrag_search_and_fetch`）或 exact matching（`nbrag_grep`）定位候选
3. 把返回证据中的精确术语复用为 lexical anchors，加强 `bm25_query`
4. 如果某文件明确成为目标，就收窄到该文件
5. 用 `nbrag_get_raw_file` 取更宽的 overlap-free 原文 — 这一步几乎总要走。有了线索不等于有了完整证据。

良好做法：每次调用都改变检索条件或扩展 evidence 范围，后续比前序更聚焦，复用 returned fields。


---

## 组合 pattern

### Pattern A — semantic hit → expand original text（最常用）
1. 调 `nbrag_search_and_fetch(query, collection_name)`，检查 `fetched_raw_excerpt`，取 `<nbrag_ranked_hit>` 的 `file_path`、`line_start`、`line_end`
2. 调 `nbrag_get_raw_file(file_path, collection_name, line_start, line_end)` 拿 overlap-free original text
3. 如果还想要 neighboring chunk structure，就调 `nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name)`

### Pattern B — semantic hit → expand neighboring chunks
1. 调 `nbrag_search_and_fetch(query, collection_name)`，取 `doc_id`、`chunk_index`
2. 调 `nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name)` 看 nearby `<nbrag_chunk>`
3. 如果仍需原文，就调 `nbrag_get_raw_file` 读对应行范围

### Pattern C — 只知文件名 → locate exact wording
1. 调 `nbrag_find_files(pattern, collection_name)`，`<nbrag_file>` 给出 `file_path`
2. 调 `nbrag_grep(keyword, collection_name, filter_file_path=<file_path>)`，`<nbrag_match>` 给出 `line_start`、`line_end`
3. 如果需要更宽 context，就调 `nbrag_get_raw_file(file_path, collection_name, line_start, line_end)`

### Pattern D — Python symbol → find call sites
1. 调 `nbrag_find_definition(symbol, collection_name)`，`<nbrag_definition>` 给出 `file_path`、`line_start`、`line_end`（无 `chunk_index`）
2. 调 `nbrag_grep(symbol, collection_name)` 找 call-site candidates。如果只要 local same-file usage，就传 `filter_file_path=<file_path>`
3. 如果要定义的完整原文，就调 `nbrag_get_raw_file(file_path, collection_name, line_start, line_end)`

### Pattern E — page-by-page 浏览大文件
1. 调 `nbrag_get_file_chunks(file_path, collection_name, start_chunk=0)`，根标签有 `has_more`
2. 如果 `has_more="true"`，就设 `start_chunk=<last chunk_index + 1>` 再调，直到 `has_more="false"`
3. 发现关键 chunk 后，用其 `file_path` 和 line 调 `nbrag_get_raw_file`

---

## Recovery

| 问题 | 下一步 |
|---|---|
| `collection_name` 未知或可疑 | `nbrag_stats()` |
| ranked search 漏掉确切引用或 identifier | 加 grounded anchors 到 `bm25_query`，或用 `nbrag_grep()` |
| grep 漏了 — 措辞是 paraphrase | 回 `nbrag_search_and_fetch()` |
| 只知部分文件名或路径 | `nbrag_find_files()` |
| 只需 inventory handles | `nbrag_list()` |
| 要对比 lexical-only vs semantic-only | `nbrag_search_only_bm25()` / `nbrag_search_only_vector()` |

结果相关但太小：
- 用 `nbrag_get_raw_file()` — 别因为已经有了一个小 chunk 就停
- 用 `nbrag_get_adjacent_chunks()` 取 neighboring chunk context
- 行范围已知时用 `nbrag_get_chunks_by_lines()`

---

## 作答前自检

直接用检索结果回答前，确认：

- [ ] 引用来自 complete original text 还是 chunk fragment?
- [ ] 如果需要完整的一段、function 或 article，已用 `nbrag_get_raw_file` 取到完整原文了吗?


任一项为否，就先调 `nbrag_get_raw_file` 补全，再回答。

---

## budget

`fetch_context_chars` 是 per ranked hit。`match_context_chars` 是 per grep match。
别为了省 token 牺牲证据完整性。如果某 chunk 重要，就调大 `fetch_context_chars` 或改用 `nbrag_get_raw_file`。
大输出比不完整 evidence 导致错误答案好。