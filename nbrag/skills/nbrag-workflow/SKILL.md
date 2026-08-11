---
name: nbrag-workflow
description: 当任务需要从 nbrag 知识库检索知识，或需要精通 nbrag 工具怎么使用怎么传参时候使用。nbrag最常见流程的用法是 nbrag_help -> nbrag_stats -> nbrag_retrieve -> nbrag_read_more_original_text ,其中nbrag_help和nbrag_stats只需要开头调用一次。nbrag_retrieve 和 nbrag_read_more_original_text 检索知识的主力工具。
---

# nbrag 功能说明

nbrag 是给 Agent 使用的万能通用 Agentic RAG MCP。知识库可以包含代码、文档、法规、医学指南、技术手册或其他文本。
llm 通过多轮使用 nbrag的多个工具，自由发挥，从rag知识库中检索知识，然后胡嗲用户问题。。
工具列表里实际可调用的名称可能带前缀。例如，`nbrag_help` 可能显示为 `mcp__nbrag__nbrag_help`。调用时以当前提供给你的工具列表为准。


## 开始使用

首次使用 nbrag 前，调 `nbrag_help()` 获取 nbrag 工具使用指南。

如果不知道用户的提问应该在什么知识库(collection_name) 中去检索，就使用`nbrag_stats()`查看已准备的知识库，这能有效帮助你决定在哪个知识库（collection_name ）中去检索知识。


## 核心检索工具

nbrag MCP 提供了十几个工具，但最核心的检索路径由 `nbrag_retrieve()` 和 `nbrag_read_more_original_text()` 组成：先检索多个内容块，再围绕有价值的命中读取相邻、更大范围的连续原文。

`nbrag_retrieve()` 是默认的检索工具。它返回的 chunk 和 auto-expanded original-text block 都是有限范围的检索内容，不是完整文件。

如果需要精确控制 rerank、BM25、文件过滤或 metadata-only 输出，就使用 `nbrag_retrieve_no_expand()`。

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



## `query` 和 `bm25_query` 参数的说明

`query` 是 vector retrieval 和 reranking 使用的 semantic query。使用语义完整、可读的自然语言问题或陈述。如果知识库是英文内容，请使用英文检索

`bm25_query` 是可选的 lexical-anchor query，只供 BM25 使用。没有可靠 lexical anchors 时可以省略。如果知识库是英文内容，请使用英文检索。


## 复用 XML attributes

结果实体把可复用 metadata 放在 XML attributes 中。调用下一个工具时，使用该工具声明的参数和对应的 attributes。

| 来源实体 | 可用于后续调用的 attributes |
|---|---|
| `<nbrag_ranked_hit>` | `file_path`, `doc_id`, `chunk_index`, `line_start`, `line_end` |
| `<nbrag_original_text_expand>` | `file_path`, `doc_id`, `line_start`, `line_end` |
| `<nbrag_match>` | `file_path`, `doc_id`, `line_start`, `line_end`；行号表示匹配行，不是 excerpt 的完整边界 |
| `<nbrag_definition>` | `file_path`, `doc_id`, `line_start`, `line_end`；没有 `chunk_index` |
| `<nbrag_file>` / `<nbrag_document>` | `file_path`, `doc_id` |

`collection_name` 继续使用当前知识库的值。

`file_path` 使用 nbrag 返回的 full absolute path。如果只知道一部分文件名或路径，就先调 `nbrag_find_files()`。



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



## 示例：双通道、多轮检索与原文扩读

假设一个知识库里面介绍了世界上各国的详细的历史、文化、经济、政治、地理、人口、面积、军事等情况

### 用户在知识库提问 `俄罗斯和美国谁的军事厉害?`

以下示意展示 `query` 与 `bm25_query` 的写法差异、handle 复用和多轮检索。


如果同一对象包含多个相对独立的方面，就可以分别构造 `query` 和 `bm25_query` 继续检索。例如，知识库原文可能分别介绍一个国家的武器装备和兵力规模，因此可以针对这两个方面分别检索。

1. 检索俄罗斯的武器装备：
   ```text
   nbrag_retrieve(
       collection_name="<collection>",
       query="俄罗斯的武器",
       bm25_query="俄罗斯 潜艇 轰炸机 航母",
   )
   ```

2. 如果还需要俄罗斯的兵力规模，就为这个方面构造另一组 `query` 和 `bm25_query`：
   ```text
   nbrag_retrieve(
       collection_name="<collection>",
       query="俄罗斯的部队人数",
       bm25_query="俄罗斯 空军 海军 陆军",
   )
   ```
   - `query` 是语义完整的自然语言表达，供 vector retrieval 和 reranking 使用。
   - `bm25_query` 使用原文中可能原样出现、且与当前检索方面相关的一组关键词锚点，供 BM25 使用；使用多个原文中出现的相关关键词锚点可以覆盖更多原文措辞，增强召回相关度。
   - 你可以多轮调用工具，根据已检索到知识内容，继续优化拟写使用更好更能提高召回质量的 `query` 和 `bm25_query` 参数 再次调用nbrag相关工具。

3. 如果某个 `<nbrag_ranked_hit file_path="..." line_start="..." ...>` 对回答有用，就复制其 `file_path` 和 `line_start`，调用 `nbrag_read_more_original_text()` 扩读命中点周围的连续原文：
   ```text
   nbrag_read_more_original_text(
       file_path="<hit 的 file_path>",
       collection_name="<collection>",
       line_start=max(1, <hit 的 line_start> - 200),
       line_end=<hit 的 line_start> + 400,
   )
   ```

4. 如果还缺另一方的知识，就针对另一方重复上述检索（先查武器，再查部队人数）与扩读。例如：
   ```text
   nbrag_retrieve(
       collection_name="<collection>",
       query="美国的武器",
       bm25_query="美国 潜艇 轰炸机 航母",
   )
   ```



## Recovery

| 当前问题 | 下一步 |
|---|---|
| `collection_name` 未知或不确定 | `nbrag_stats()` |
| semantic search 没找到结果 | 保持用户原意改写 `query`；有可靠 lexical anchors 时补 `bm25_query` |
| 如果需要 exact wording、编号或原文措辞 | `nbrag_grep()` |
| 如果grep 没找到，但问题可能是 paraphrase 或 concept | `nbrag_retrieve()` |
| 如果只知道部分短文件名或路径 | `nbrag_find_files()` |
| 如果当前检索结果有用但上下文太短 | `nbrag_read_more_original_text()` |
| 如果需要比较 lexical-only 和 vector-only recall 哪个召回质量更好 | `nbrag_retrieve_only_bm25()` / `nbrag_retrieve_only_vector()` |

## 写答案前

写答案前，按顺序自检：

1. ai回答用户问题所需的全部知识内容，是否已经通过nbrag检索工具检索完全？
2. 如果某个检索到的hit对回答有用，就用 `nbrag_read_more_original_text()` 扩读命中点周围的连续原文。
3. 扩读后还缺，就继续检索或再扩读，直到检索足够的知识库内容。
