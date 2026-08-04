---
name: nbrag-workflow
description: 当任务需要从 nbrag 知识库检索知识，或需要精通 nbrag 工具怎么使用时候使用。
---

# nbrag workflow

nbrag 是给 Agent 使用的通用 Agentic RAG MCP。知识库可以包含代码、文档、法规、医学指南、技术手册或其他文本。

工具列表里实际可调用的名称可能带前缀。例如，`nbrag_help` 可能显示为 `mcp__nbrag__nbrag_help`。调用时以当前工具列表为准。

## 开始使用

首次使用 nbrag 前，调 `nbrag_help()` 获取 nbrag 工具使用指南。成功响应可在同一会话内复用。如果该响应因 context compaction 丢失，或无法确认它是否仍在上下文中，就再次调用。

如果 `collection_name` 未知，就调 `nbrag_stats()` 获取准确名称。

## 核心工具

nbrag MCP 提供了十几个工具，但最核心的检索路径由 `nbrag_retrieve()` 和 `nbrag_read_more_original_text()` 组成：先检索多个内容块，再围绕有价值的命中读取相邻、更大范围的连续原文。

`nbrag_retrieve()` 是默认的检索工具。它返回的 chunk 和 auto-expanded original-text block 都是有限范围的检索内容，不是完整文件。

如果需要控制 rerank、BM25、文件过滤或 metadata-only 输出，就使用 `nbrag_retrieve_no_expand()`。

如果某个 ranked hit 对回答有用，就复制该 hit 的 `file_path` 和 `line_start`。把复制出的 `line_start` 记作 `hit_line_start`，然后调用：

```text
nbrag_read_more_original_text(
    file_path,
    collection_name,
    line_start=max(1, hit_line_start - 200),
    line_end=hit_line_start + 400,
)
```

如果缺少前文，就把 `line_start` 往前调小；如果缺少后文，就把 `line_end` 往后调大。如果需要完整文件，就省略 `line_start` 和 `line_end`。

## 工具表

| 场景 | 工具 | 用途 |
|---|---|---|
| nbrag 工具使用指南不在上下文 | `nbrag_help()` | 获取工具选择、参数和后续读取说明 |
| `collection_name` 未知 | `nbrag_stats()` | 查看已准备的知识库 |
| semantic 或 hybrid retrieval | `nbrag_retrieve()` | 返回 ranked hits 和auto-expanded original-text blocks |
| 需要检索开关或 metadata-only | `nbrag_retrieve_no_expand()` | 控制 rerank、BM25、文件过滤和 chunk content |
| lexical-only 诊断 | `nbrag_retrieve_only_bm25()` | 单独检查 BM25 recall |
| vector-only 诊断 | `nbrag_retrieve_only_vector()` | 单独检查 vector recall |
| literal 或 regex matching | `nbrag_grep()` | 在 stored original text 中逐行匹配 |
| 已知 Python symbol | `nbrag_find_definition()` | 查找 Python class、function 或 method definition |
| 只知道文件名或路径片段 | `nbrag_find_files()` | 获取准确的 full absolute `file_path` |
| 浏览已导入文件 | `nbrag_list()` | 获取 document inventory、`doc_id` 和 `file_path` |
| 读取连续原文 | `nbrag_read_more_original_text()` | 读取 overlap-free stored original text，支持指定 line range 或完整文件 |
| 检查 chunk 结构 | `nbrag_get_file_chunks()` | 分页查看 chunk boundaries 和 scope metadata |
| 检查某个 hit 周围的 chunk 结构 | `nbrag_get_adjacent_chunks()` | 查看相邻 chunk boundaries、scope 和 overlap |
| 检查某个 line range 覆盖哪些 chunks | `nbrag_get_chunks_by_lines()` | 返回与该行范围重叠的 chunks |

## `query` 和 `bm25_query`

`query` 是 vector retrieval 和 reranking 使用的 semantic query。使用语义完整、可读的自然语言问题或陈述。如果知识库是英文内容，请使用英文检索

`bm25_query` 是可选的 lexical-anchor query，只供 BM25 使用。没有可靠 lexical anchors 时可以省略。。如果知识库是英文内容，请使用英文检索


如果填写 `bm25_query`，就使用用户原话、可靠的对话上下文或先前检索结果支持的措辞。选择 source text 中可能原样出现、并能区分目标与相近内容的 lexical anchors；它承载的是 source-facing wording。

如果先前结果揭示了更准确的 source wording，就可以在后续检索中更新 `bm25_query`。

如果对话上下文足以确定代词所指对象或明显笔误，就可以在保持用户原意的前提下补全 `query`。如果指代仍不明确，就保留用户当前表达继续检索。

## 检索内容边界

| 返回内容 | 真实边界 |
|---|---|
| `<nbrag_chunk_content>` | 一个 RAG chunk，止于 chunk boundary；相邻 chunks 按 ingestion 时配置的 overlap 重叠 |
| `<nbrag_original_text_content>` under `<nbrag_original_text_expand>` | `nbrag_retrieve()` 自动读取的局部原文，受 `expand_context_chars` 限制 |
| `<nbrag_original_text_content>` under `<nbrag_match>` | grep 命中行附近的局部原文，受 `match_context_chars` 限制 |
| `<nbrag_original_text_content>` under `<nbrag_original_text>` | `nbrag_read_more_original_text()` 明确请求的原文窗口；省略两个 line bounds 时才是完整 stored file |
| `<nbrag_definition_content>` | Python 结果通常是 AST definition；`symbol_type="regex_fallback"` 只是非 Python candidate text |

Chunk overlap 用于提高 retrieval recall。需要连续上下文、引用原文或阅读大文件时，使用 `nbrag_read_more_original_text()`。Chunk tools 用于检查 chunk boundaries、scope metadata、overlap 或 chunking 质量。

## 扩读原文

如果某个 ranked hit 对回答有用，就从该 `<nbrag_ranked_hit>` 的 XML attributes 取 `file_path` 和 `line_start`。把返回的 `line_start` 记作 `hit_line_start`，然后调用：

```text
nbrag_read_more_original_text(
    file_path,
    collection_name,
    line_start=max(1, hit_line_start - 200),
    line_end=hit_line_start + 400,
)
```

如果缺少前文，就把下一次调用的 `line_start` 调小。如果缺少后文，就把 `line_end` 调大。如果需要完整 stored file，就省略 `line_start` 和 `line_end`。

对于大文件或大范围内容，使用 `nbrag_read_more_original_text()` 按连续 line ranges 阅读。

`expand_context_chars` 控制 `nbrag_retrieve()` 自动返回的 original-text excerpt 长度，不会扩大 chunk。已有相关 hit 后需要更多内容时，调用 `nbrag_read_more_original_text()` 扩大原文范围。

## 复用 XML attributes

结果实体把可复用 metadata 放在 XML attributes 中。调用下一个工具时，使用该工具声明的参数和对应的 attributes。

| 来源实体 | 可用于后续调用的 attributes |
|---|---|
| `<nbrag_ranked_hit>` | `file_path`, `doc_id`, `chunk_index`, `line_start`, `line_end` |
| `<nbrag_original_text_expand>` | `file_path`, `doc_id`, `line_start`, `line_end` |
| `<nbrag_match>` | `file_path`, `doc_id`, `line_start`, `line_end`；行号表示匹配行，不是 excerpt 的完整边界 |
| `<nbrag_definition>` | `file_path`, `doc_id`, `line_start`, `line_end`；没有 `chunk_index` |
| `<nbrag_file>` / `<nbrag_document>` | `file_path`, `doc_id` |
| `<nbrag_chunk>` | `file_path`, `doc_id`, `chunk_index`, `line_start`, `line_end` |

`collection_name` 继续使用当前知识库的值。

`file_path` 使用 nbrag 返回的 full absolute path。如果只知道一部分文件名或路径，就先调 `nbrag_find_files()`。

## `filter_file_path`

`filter_file_path` 会把 retrieval 收窄到一个 stored file。它不是轻量的 ranking preference。

在 hybrid search 中，设置 `filter_file_path` 后，vector retrieval 会限定到该文件，并跳过 cross-file BM25 fusion。返回内容不会额外提供 `bm25="off"` 属性。

`nbrag_retrieve_only_bm25()` 的文件过滤是先做 collection-level BM25 recall，再过滤到目标文件，因此它不等同于真正的 file-local BM25 index。

## Python definition

如果用户已经给出准确的 Python symbol，就可以直接调用 `nbrag_find_definition()`。如果 symbol 名不确定，就先用 `nbrag_retrieve()` 或 `nbrag_grep()` 定位。

`nbrag_find_definition()` 的主要能力是 Python AST definition lookup。非 Python 结果会标记为 `regex_fallback`，只能视为 candidate text。

`<nbrag_definition>` 提供 `file_path`、`doc_id`、`line_start` 和 `line_end`。如果需要 definition 周围的连续原文，就用 `file_path` 和 line range 调 `nbrag_read_more_original_text()`。

## 常用流程

### Semantic discovery 后扩读原文

1. 调 `nbrag_retrieve(query, collection_name)`。
2. 选择与问题相关的 `<nbrag_ranked_hit>`。
3. 用该 hit 的 `file_path` 和行号调 `nbrag_read_more_original_text()`。
4. 如果仍缺前文或后文，就继续扩大 line range。

### 已知文件后检索

1. 如果只有文件名片段，就调 `nbrag_find_files()` 获取 `file_path`。
2. 如果问题是 semantic，就在 `nbrag_retrieve()` 或 `nbrag_retrieve_no_expand()` 中传 `filter_file_path`。
3. 如果需要 exact wording，就调 `nbrag_grep(..., filter_file_path=file_path)`。
4. 如果需要更宽的连续原文，就调 `nbrag_read_more_original_text()`。

### 阅读大文件

1. 调 `nbrag_read_more_original_text(file_path, collection_name, line_start=1, line_end=<reading window end>)`。
2. 从 `<nbrag_original_text total_lines="..." line_start="..." line_end="...">` 获取当前范围和文件总行数。
3. 如果还需要后文，就把下一次 `line_start` 设到当前 `line_end` 之后，并继续向后读取。
4. 如果需要整个文件，就省略 `line_start` 和 `line_end`。

阅读大文件时，使用 `nbrag_read_more_original_text()` 按连续 line ranges 扩读。`nbrag_get_file_chunks()` 用于检查 chunk boundaries、scope metadata、overlap 或 chunking 质量。

### 检查 chunk structure

需要检查 chunk structure 时，使用以下工具：

- `nbrag_get_file_chunks()`：分页检查某个文件的 chunks；根据 `has_more` 和 `next_start_chunk` 继续。
- `nbrag_get_adjacent_chunks()`：检查已知 `doc_id + chunk_index` 周围的 chunks。
- `nbrag_get_chunks_by_lines()`：检查某个 `doc_id + line range` 与哪些 chunks 重叠。

这些工具返回的相邻 chunks 一定按 ingestion 时配置的 overlap 重叠，连续原文读取使用 `nbrag_read_more_original_text()`。

## Recovery

| 当前问题 | 下一步 |
|---|---|
| `collection_name` 未知或不确定 | `nbrag_stats()` |
| semantic search 没找到结果 | 保持用户原意改写 `query`；有可靠 lexical anchors 时补 `bm25_query` |
| 需要 exact wording、编号或原文措辞 | `nbrag_grep()` |
| grep 没找到，但问题可能是 paraphrase 或 concept | `nbrag_retrieve()` |
| 只知道部分文件名或路径 | `nbrag_find_files()` |
| 当前检索结果有用但上下文太短 | `nbrag_read_more_original_text()` |
| 需要检查 chunk boundaries 或 scope metadata | 选择对应 chunk tool |
| 需要比较 lexical-only 和 vector-only recall | `nbrag_retrieve_only_bm25()` / `nbrag_retrieve_only_vector()` |

## 作答前检查

直接回答前，确认当前检索内容的边界，并判断答案、引用或核查是否依赖边界外内容。

如果依赖边界外内容，就用 `nbrag_read_more_original_text()` 读取缺失的连续原文。根据回答、引用和核查所需的知识范围继续检索与扩读。
