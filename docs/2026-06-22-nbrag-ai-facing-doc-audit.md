# nbrag AI-facing 文案 / 注释 / Skill 审核与优化建议

> 目的：**只记录问题和改进建议，不修改任何现有文件**。
>
> 审核范围：
> - `nbrag/server.py`
> - `nbrag/mcp_tools.py`
> - `nbrag/skills/nbrag-workflow/SKILL.md`
> - `README.md`
> - `README.zh-CN.md`
>
> 审核目标：
> 1. 面向 AI 大模型的工具描述是否**精确、稳定、无歧义**
> 2. 是否符合 **MCP 最佳实践 / compound skill 最佳实践 / RAG 实践 / BM25 实践**
> 3. 是否存在“AI 写代码式乱写”：想当然、变量名不严格、过度保守、过度死板、把心理话写进正式文案
> 4. 给出**建议替换文案**，供后续人工筛选采用

---

# 一、总评

当前 `nbrag` 的 AI-facing 文案总体已经具备较强的结构意识：
- 知道强调 `collection_name`
- 知道强调 `file_path/doc_id/chunk_index/line:N-M`
- 知道区分 `search / grep / raw_file / find_definition`
- 知道区分 `query` 与 `bm25_query`

但是，仍然存在若干类问题：

## 1. 最大问题：**不够“术语级精确”**
典型表现：
- 有时写 `read tools`，但产品里根本没有 `read()` 这种函数名
- 有时写“docs/laws/manuals/source code”像是穷举范围，暗示工具只适用于这些
- 有时写“chunks may overlap”，但从当前设计看，chunk 视图就是按 overlap chunk 来的，不能写得像偶发行为
- 有时 `bm25_query` 解释得太随意，容易让 AI 以为它只是“空格关键词列表”，而不是**词法锚点输入**

## 2. 第二大问题：**把对话里的心理活动写进正式文案**
典型表现：
- “This tool should not teach agents ...”
- “This is only a reminder ...”
- “just because ...”

这类句子不是规则说明，而是“写文案的人脑内纠偏”。
对 AI 大模型来说，这种话会污染正式规范边界。

## 3. 第三大问题：**太容易写成“保守但模糊”**
典型表现：
- “may overlap” 用得太多
- “may return ... fallback” 这种还能接受，但需要更清楚标注强弱等级
- 一些说明为了避免担责，写得像免责声明，而不是面向 AI 的操作规范

## 4. 第四大问题：**README 与 AI-facing 文档边界容易串台**
README 应该主要面向人类用户；
Skill / docstring / MCP tool description 才主要面向 AI。
现在历史上明显有串台痕迹。

---

# 二、总原则：后续所有 AI-facing 文案应遵守的规则

## 规则 A：只使用**真实存在**的函数名、字段名、返回标记名
坏例子：
- `read tools`
- `read method`
- `document handle`
- `range markers`

如果系统里实际规范名是：
- `file_path`
- `doc_id`
- `chunk_index`
- `line:N-M`

那就必须直接写这些，而不是写近义词。

## 规则 B：不要穷举业务领域来限制工具定义
坏例子：
- `docs, laws, manuals, articles, source code`
- `For law/docs/manuals ...`

这种写法有两个问题：
1. 暗示工具只适用于这些内容
2. 容易遗漏未来新场景

正确做法：
- 工具定义层写“imported text / stored original text / Python .py source”这样的能力边界
- 若要举例，用 `for example`，不要写成定义本体

## 规则 C：不要把“文案设计意图”写进文案本身
坏例子：
- `This tool should not teach agents ...`
- `This is only a reminder ...`

正确做法：
- 直接说规则
- 不要解释“我为什么要这样提醒你”

## 规则 D：不要为了保守而故意模糊
坏例子：
- `Chunks may overlap.`

如果当前工具语义就是：
- chunk 视图基于 chunked storage
- overlap 是默认 chunking 机制的一部分

那应该直接写：
- `Chunks in this view can overlap by design.`
或更硬：
- `This view is chunk-based and can include overlapping content by design.`

## 规则 E：Query / bm25_query 必须讲清“职责分离”
应明确：
- `query` = 给向量检索 / rerank 的主语义问题
- `bm25_query` = 给 BM25 的词法锚点
- 二者可以相同，但职责不同
- `bm25_query` 不是“随便拆点关键词”这么简单

## 规则 F：面向 AI 的文案应该优先写“决策规则”，不是“人类解释”
例如：
- 什么时候用 `grep`
- 什么时候必须有 `chunk_index`
- 什么时候必须是完整绝对 `file_path`
- 哪些输出字段可以直接复用

---

# 三、按文件逐项审查

---

# 3.1 `nbrag/server.py` 的问题与建议

## A. `nbrag_help()` docstring

### 当前问题
当前版本：
- `Before calling any nbrag tool, this help function must be called first ...`

问题：
1. **过于绝对化**：如果 agent 已经明确知道策略，再强制 first-call 会造成机械重复
2. `must be called first` 对 MCP agent 来说太死
3. `know the usage strategy of nbrag` 不够专业，可以更像“tool-selection policy / retrieval strategy guide”

### 建议替换 docstring
```python
"""Workflow guide for AI agents using nbrag.

Call this when retrieval strategy or tool selection is still unclear.
Consult it before choosing among nbrag_stats(), nbrag_search(), nbrag_search_and_fetch(), nbrag_grep(), and follow-up file/chunk tools.
If strategy is already clear from prior nbrag_help() guidance, do not call it again.

The returned text explains retrieval strategy, path rules, and reusable follow-up fields such as file_path, doc_id, chunk_index, and line:N-M.
"""
```

---

## B. `FuncFields.query`

### 当前问题
当前描述：
- `keep it a question or statement, not a keyword list`

这句方向对，但还可以更强。
缺点：
1. 没明确指出它主要服务于**vector retrieval + rerank**
2. 没强调它可以根据对话上下文做语义归一

### 建议替换描述
```python
"Main semantic query used by vector retrieval and reranking. Keep it as a natural-language question or statement that captures the user's intent. Do not compress it into a keyword list; use bm25_query separately for lexical anchors."
```

---

## C. `FuncFields.bm25_query`

### 当前问题
当前描述：
- `Short keyword version of the query for BM25. Typically pass the user's key terms as space-separated anchors.`

问题：
1. 太容易误导成“机械拆关键词”
2. 没强调它是**词法锚点**，而不是另一个自然语言 query
3. 没强调它不必总是“space-separated keyword list”

### 建议替换描述
```python
"Lexical anchor query used only by BM25. Use this for exact terms, article numbers, abbreviations, codes, API/class names, or other high-precision lexical anchors. It does not affect vector retrieval or reranking."
```

---

## D. `nbrag_search()` docstring

### 当前问题
1. 开头 `docs, laws, manuals, articles, source code` 太像限制范围
2. `Returned text is plain text but intentionally structured` 可以，但后面应更强调字段名是稳定 follow-up handles
3. Python source workflow 那段是经验性描述，可保留，但应该避免让非 Python 场景看起来像次要用途

### 建议替换 docstring
```python
"""Search an imported knowledge base for relevant chunks.

Use this when you need ranked retrieval with fine-grained control over rerank, BM25, file filtering, or content inclusion.
If collection_name is unknown, call nbrag_stats() first. If retrieval strategy is still unclear, consult nbrag_help() first.

Query guidance:
- query is the main semantic query used by vector retrieval and reranking
- bm25_query is an optional lexical-anchor query used only by BM25
- setting bm25_query does not disable vector retrieval or reranking
- setting filter_file_path narrows retrieval to one stored file; in the current hybrid implementation this also disables cross-file BM25 fusion

Returned text is structured for follow-up calls. Each hit includes stable reusable fields such as:
- chunk:X/Y
- chunk_index:X
- total_chunks:Y
- line:N-M
- doc_id:...
- file_path:...

Typical follow-up tools:
- nbrag_get_raw_file(file_path, collection_name)
- nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name)
- nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name)
- nbrag_grep(keyword, collection_name)
- nbrag_find_definition(symbol, collection_name) for Python .py source
"""
```

---

## E. `nbrag_search_only_bm25()` docstring

### 当前问题
整体方向对，但可以更硬：
- 应明确这是**diagnostic retrieval mode**，不是默认入口
- `This is still ranked retrieval, not literal line matching.` 这句很好，应保留

### 建议替换 docstring
```python
"""BM25-only ranked retrieval.

Use this to isolate lexical recall when exact terms matter: article numbers, abbreviations, error codes, identifiers, exact phrases, or other high-precision wording.
This is ranked retrieval, not literal line matching.

Use instead:
- nbrag_grep() for literal line-by-line matching in stored original text
- nbrag_search_only_vector() to inspect semantic recall only
- nbrag_search() or nbrag_search_and_fetch() for the normal mixed retrieval pipeline
"""
```

---

## F. `nbrag_search_only_vector()` docstring

### 当前问题
基本可用，但应更清楚指出它是**semantic recall inspection tool**。

### 建议替换 docstring
```python
"""Vector-only ranked retrieval.

Use this to isolate semantic recall when meaning, intent, or paraphrase matters more than exact lexical overlap.
This is useful for inspecting embedding behavior without BM25 or reranking.

Use instead:
- nbrag_search_only_bm25() for lexical-only inspection
- nbrag_grep() for literal line-by-line matching
- nbrag_search() or nbrag_search_and_fetch() for the normal mixed retrieval pipeline
"""
```

---

## G. `nbrag_search_and_fetch()` docstring

### 当前问题
整体不错，但还可以更“RAG-native”：
1. 它其实是默认入口，应该更强地表达“one-call discovery + evidence”
2. `fetch_context_chars` 说明很好，但还可以更清楚点：这是**raw-content fetch budget**, 不是 search budget

### 建议替换 docstring
```python
"""Default one-call retrieval entry point for most user questions.

Use this when you want both ranked discovery and stored original-text evidence in the same call.
This is the normal default for questions about meaning, usage, examples, evidence, or source-backed answers.

Query guidance:
- query is the main semantic query used by vector retrieval and reranking
- bm25_query is an optional lexical-anchor query used only by BM25
- setting bm25_query does not disable vector retrieval or reranking
- setting filter_file_path narrows retrieval to one stored file; in the current hybrid implementation this also disables cross-file BM25 fusion

Returned text has two sections:
1. ranked search results
2. auto-fetched stored original content

Follow-up fields preserved in ranked hits include file_path, doc_id, chunk_index, and line:N-M.
fetch_context_chars is a per-hit raw-context budget used during original-text expansion, not a final total response budget.

Use nbrag_search() instead when you need fine-grained retrieval switches or metadata-only output.
"""
```

---

## H. `nbrag_grep()` docstring

### 当前问题
这段总体不错，但有一个问题：
- `Use this for exact wording in general text before treating it as a code tool` 这句没必要
- 容易显得作者在对 AI 讲“我怎么定义它”，而不是直接说能力边界

### 建议替换 docstring
```python
"""Literal text or regex search over stored original text, matched line by line.

Use this when exact wording matters: article numbers, headings, exact phrases, API names, class/function names, constants, imports, decorators, error strings, or other precise text.
Do not use it for concept search, synonym search, or paraphrase search.

Returned text includes reusable follow-up fields such as matched_line, line_range, doc_id, and file_path.
"""
```

---

## I. `nbrag_find_definition()` docstring

### 当前问题
总体还行，但可以更明确：
- 这是 **Python-source-specific** 工具
- regex fallback 是弱结果，不是“也挺行”的结果

### 建议替换 docstring
```python
"""Find complete Python class/function/method definitions by symbol name.

This tool is specialized for Python .py source. When possible it uses AST-aware symbol boundaries.
If a result comes from non-Python text, it should be clearly treated as regex fallback rather than as a strong symbol-definition result.

Use this after search or grep has already narrowed the symbol name.
Returned text includes doc_id, file_path, line range, and the definition body.
"""
```

---

## J. `nbrag_get_file_chunks()` docstring

### 当前问题
当前写的是：
- `Chunks may overlap.`

问题：
- 太弱
- 对当前产品来说，chunk view 本来就是建立在 overlap chunking 上

### 建议替换 docstring
```python
"""Paginated chunk view for a stored file.

Use this when you want chunk-by-chunk browsing together with line and scope metadata.
This is a chunk-based view and can include overlapping content by design.
For overlap-free original text, use nbrag_get_raw_file() instead.

Returned text includes filename, doc_id, file_path, total_chunks, total_lines, and per-chunk line/scope markers.
"""
```

---

## K. `nbrag_get_chunks_by_lines()` docstring

### 当前问题
同样有：
- `may contain overlap`

建议直接强调“chunk view by design can overlap”。

### 建议替换 docstring
```python
"""Return all chunks covering a line range.

Use this when you already know a line range and want chunk-level context with scope metadata.
Compared with nbrag_get_raw_file(), this preserves chunk structure and can include overlapping content by design.

Returned text includes doc_id, file_path, requested line_range, and all overlapping chunks.
"""
```

---

## L. `nbrag_stats()` docstring

### 当前问题
当前版本：
- `Before calling the nbrag_stats tool, it is necessary to ensure that the nbrag_help tool has been called ...`

问题非常明显：
1. 英文不自然
2. 是强行写的“政策口号”
3. 不是 MCP tool description 应有的风格
4. 暗含“必须先 help 再 stats”，这未必总对

### 建议替换 docstring
```python
"""List available knowledge bases and routing hints.

Call this when collection_name is unknown or when you need to inspect available collections before retrieval.
Returned text includes each collection's stable collection_name and document/chunk counts, and may also include display_name, description, aliases, tags, chunk_size, chunk_overlap, and last_ingested_at.

Before retrieval, ensure that retrieval strategy is already clear. If strategy selection is still unclear, consult nbrag_help().
"""
```

---

# 3.2 `nbrag/mcp_tools.py` 的问题与建议

## A. `nbrag_help()` 返回正文太弱

### 当前问题
当前 `mcp_tools.nbrag_help()` 主体几乎只剩：
- `nbrag help: Agentic RAG knowledge-base MCP workflow guide`
- 然后直接拼 `skill_text`

问题：
1. MCP tool 自身帮助不应该完全依赖外部 skill 文本
2. 如果 skill 文本将来长、乱、漂移，`nbrag_help()` 就失去自己的最小稳定策略层

### 建议
`nbrag_help()` 最好有一个**稳定最小骨架**，再附 skill：

建议正文：
```text
nbrag help: Agentic RAG knowledge-base MCP workflow guide

Core strategy:
- Use nbrag_stats() when collection_name is unknown
- Use nbrag_search_and_fetch() as the default one-call retrieval entry for most questions
- Use nbrag_search() when you need retrieval controls or metadata-only output
- Use nbrag_grep() for exact wording in stored original text
- Use nbrag_find_definition() only for Python .py symbol definitions
- Use nbrag_get_raw_file() for overlap-free original text
- Use nbrag_find_files() when exact file_path is still unknown

Stable follow-up fields:
- file_path
- doc_id
- chunk_index
- line:N-M
```

然后再拼 skill 文本。

---

## B. `_format_search_results()` 中的 `bm25_query` 说明不够精准

### 当前问题
当前写法：
- `query remains the semantic question for vector retrieval/rerank; bm25_query only changes BM25 wording when BM25 is active.`

问题：
1. `changes BM25 wording` 这个表达太软
2. 更准确的说法应是：
   - `bm25_query` is the lexical-anchor query used by BM25

### 建议替换
```text
query is the main semantic query used by vector retrieval and reranking.
bm25_query, when provided, is the lexical-anchor query used only by BM25.
```

---

## C. `nbrag_search_only_bm25()` 实现层没有明确保留 “BM25-only” 语气

当前调用：
- `query=bm25_query`
- `use_vector=False`

实现没问题，但如果以后改文案，应在输出 header 或说明里更直接反映：
- `bm25-only ranked retrieval`

---

## D. `nbrag_search_and_fetch()` 的 auto-fetch 说明总体正确，但可以再硬一点

### 当前问题
- `Auto-fetched raw snippets are grouped by file/doc_id, and overlapping windows are merged ...`

这句是对的，但要再强调：
- fetch_top_n_raw 是**top hits before merging**, not final file count

建议补成：
```text
fetch_top_n_raw applies to ranked hits before raw-window merging, so the final number of returned raw-file groups can be smaller.
```

---

## E. `nbrag_get_file_chunks()` / `nbrag_get_chunks_by_lines()` 输出里的 overlap 表述过软

### 当前问题
- `may contain overlap`
- `may overlap with neighboring chunks`

建议统一为：
- `This is a chunk-based view and can include overlapping content by design.`

---

## F. `nbrag_stats()` 返回正文现在太弱

当前返回：
```text
collections:
Use collection_name(知识库名字) exactly as shown below when calling retrieval tools.
```

问题：
1. 没有 help-first 的策略骨架
2. 没有“collection_name 是稳定机器名”的明确信号
3. 没有提醒 display_name / aliases / tags 是辅助选择字段

建议替换为：
```text
collections:
Use collection_name(知识库名字) exactly as shown below when calling retrieval tools.
collection_name is the stable machine-facing identifier.
Use display_name, description, aliases, and tags only to choose the correct collection.
If retrieval strategy is still unclear, consult nbrag_help() before retrieval.
```

---

# 3.3 `nbrag/skills/nbrag-workflow/SKILL.md` 的问题与建议

## A. `nbrag_stats | 永远是第一步` 是错误的

### 当前问题
```md
| 列出可用知识库 | nbrag_stats | 永远是第一步 |
```

这是硬伤。
因为：
- 如果 collection_name 已知，就不该“永远第一步”
- 这会把 AI 教成机械流程，而不是策略判断

### 建议替换
```md
| 列出可用知识库 | nbrag_stats | 仅当 collection_name 未知或需要比较多个知识库时使用 |
```

---

## B. `部分工具速查` 过于流程化、过于死板

建议把标题从：
- `部分工具速查`

改成：
- `工具选择速查（按需求，不是固定流程）`

---

## C. `bm25_query` 说明还不够硬

### 当前问题
写了：
- `简短的词法锚点——用户原话关键词、上下文中确认的术语、高置信的拼写变体/同义词`

这段方向是对的，但建议再强调：
- `bm25_query` 不需要忠实复制用户自然语言句子
- 它的目标是 lexical anchors, not semantic completeness

建议补充：
```md
bm25_query 的目标不是完整表达用户问题，而是给 BM25 提供高精度词法锚点。
```

---

## D. `ai要把自己当做是 精通rag知识库用法的专家...` 这种句子不够专业

### 当前问题
```md
ai要把自己当做是 精通rag知识库用法的专家...
```

问题：
- 太像 prompt 口号
- 不像 skill 规范
- 缺乏可操作性

### 建议替换
```md
AI should reason explicitly about retrieval mode, lexical anchoring, and follow-up evidence expansion instead of mechanically chaining tools.
```

对应中文版可以写：
```md
AI 应显式判断检索模式、词法锚点和后续证据扩展方式，而不是机械串联工具。
```

---

# 3.4 README 的问题与建议（只记录，不建议作为 AI-facing 规范来源）

README 现在比之前已经收敛了很多，但仍有一些不严谨点：

## A. `convert it to .md, .txt, or .html` / `转换成 .md/.txt/.html`

问题：
- 容易给人“html 也是推荐主格式”的感觉
- 但人类用户最稳定的输入表述其实应是：
  - `clean Markdown or plain text`

建议统一写法：
- English: `extract it into clean Markdown or plain text before ingestion`
- 中文：`先整理成干净的 Markdown 或纯文本再导入`

## B. `delete_first=True` 的人类说明还有点 AI 味

当前：
- 英文和中文都出现了“如果增量导入支持，那就别先删除”这种半口语式说明

建议改得更人类、更直：
- `Use delete_first=True when you want to rebuild the collection from scratch.`
- `当你希望从头重建整个 collection 时，使用 delete_first=True。`

---

# 四、建议统一的术语表（必须固定）

后续所有 AI-facing 文案建议统一使用下列术语，不要再换近义词：

## 输入侧
- `collection_name`
- `query`
- `bm25_query`
- `file_path`
- `doc_id`
- `chunk_index`
- `line_start`
- `line_end`

## 输出侧
- `file_path`
- `doc_id`
- `chunk_index`
- `line:N-M`
- `matched_line`
- `line_range`
- `chunk:X/Y`
- `total_chunks`

## 不建议再使用的模糊词
- `read method`
- `read tools`
- `document handle`
- `context marker`
- `path handle`
- `range marker`

---

# 五、建议统一的能力边界写法

## 推荐写法 1：`nbrag_search`
- `Search an imported knowledge base for relevant chunks.`

不要写：
- `Search docs, laws, manuals, articles, source code ...`

## 推荐写法 2：`nbrag_grep`
- `Literal text or regex search over stored original text, matched line by line.`

不要写：
- `for law/docs/manuals before treating it as a code tool`

## 推荐写法 3：`nbrag_get_file_chunks`
- `This is a chunk-based view and can include overlapping content by design.`

不要写：
- `Chunks may overlap.`

## 推荐写法 4：`nbrag_find_definition`
- `This tool is specialized for Python .py source.`

不要写：
- 太长的“law/docs/manuals 请用别的工具”式举例作为定义主体

---

# 六、建议直接采用的新文案（可供后续替换）

下面给出一个可直接参考的“更稳版本”集合。

---

## 6.1 建议版 `nbrag_help()` docstring

```python
"""Workflow guide for AI agents using nbrag.

Call this when retrieval strategy or tool selection is still unclear.
Consult it before choosing among nbrag_stats(), nbrag_search(), nbrag_search_and_fetch(), nbrag_grep(), and follow-up file/chunk tools.
If strategy is already clear from prior nbrag_help() guidance, do not call it again.

The returned text explains retrieval strategy, path rules, and reusable follow-up fields such as file_path, doc_id, chunk_index, and line:N-M.
"""
```

---

## 6.2 建议版 `nbrag_stats()` docstring

```python
"""List available knowledge bases and routing hints.

Call this when collection_name is unknown or when you need to inspect available collections before retrieval.
Returned text includes each collection's stable collection_name and document/chunk counts, and may also include display_name, description, aliases, tags, chunk_size, chunk_overlap, and last_ingested_at.

Before retrieval, ensure that retrieval strategy is already clear. If strategy selection is still unclear, consult nbrag_help().
"""
```

---

## 6.3 建议版 `nbrag_search()` docstring

```python
"""Search an imported knowledge base for relevant chunks.

Use this when you need ranked retrieval with fine-grained control over rerank, BM25, file filtering, or content inclusion.
If collection_name is unknown, call nbrag_stats() first. If retrieval strategy is still unclear, consult nbrag_help() first.

Query guidance:
- query is the main semantic query used by vector retrieval and reranking
- bm25_query is an optional lexical-anchor query used only by BM25
- setting bm25_query does not disable vector retrieval or reranking
- setting filter_file_path narrows retrieval to one stored file; in the current hybrid implementation this also disables cross-file BM25 fusion

Returned text is structured for follow-up calls. Each hit includes stable reusable fields such as:
- chunk:X/Y
- chunk_index:X
- total_chunks:Y
- line:N-M
- doc_id:...
- file_path:...

Typical follow-up tools:
- nbrag_get_raw_file(file_path, collection_name)
- nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name)
- nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name)
- nbrag_grep(keyword, collection_name)
- nbrag_find_definition(symbol, collection_name) for Python .py source
"""
```

---

## 6.4 建议版 `nbrag_search_and_fetch()` docstring

```python
"""Default one-call retrieval entry point for most user questions.

Use this when you want both ranked discovery and stored original-text evidence in the same call.
This is the normal default for questions about meaning, usage, examples, evidence, or source-backed answers.

Query guidance:
- query is the main semantic query used by vector retrieval and reranking
- bm25_query is an optional lexical-anchor query used only by BM25
- setting bm25_query does not disable vector retrieval or reranking
- setting filter_file_path narrows retrieval to one stored file; in the current hybrid implementation this also disables cross-file BM25 fusion

Returned text has two sections:
1. ranked search results
2. auto-fetched stored original content

Follow-up fields preserved in ranked hits include file_path, doc_id, chunk_index, and line:N-M.
fetch_context_chars is a per-hit raw-context budget used during original-text expansion, not a final total response budget.

Use nbrag_search() instead when you need fine-grained retrieval switches or metadata-only output.
"""
```

---

## 6.5 建议版 `nbrag_grep()` docstring

```python
"""Literal text or regex search over stored original text, matched line by line.

Use this when exact wording matters: article numbers, headings, exact phrases, API names, class/function names, constants, imports, decorators, error strings, or other precise text.
Do not use it for concept search, synonym search, or paraphrase search.

Returned text includes reusable follow-up fields such as matched_line, line_range, doc_id, and file_path.
"""
```

---

## 6.6 建议版 `nbrag_find_definition()` docstring

```python
"""Find complete Python class/function/method definitions by symbol name.

This tool is specialized for Python .py source. When possible it uses AST-aware symbol boundaries.
If a result comes from non-Python text, it should be treated as regex fallback rather than as a strong symbol-definition result.

Use this after search or grep has already narrowed the symbol name.
Returned text includes doc_id, file_path, line range, and the definition body.
"""
```

---

## 6.7 建议版 `nbrag_get_file_chunks()` docstring

```python
"""Paginated chunk view for a stored file.

Use this when you want chunk-by-chunk browsing together with line and scope metadata.
This is a chunk-based view and can include overlapping content by design.
For overlap-free original text, use nbrag_get_raw_file() instead.

Returned text includes filename, doc_id, file_path, total_chunks, total_lines, and per-chunk line/scope markers.
"""
```

---

## 6.8 建议版 `nbrag_get_chunks_by_lines()` docstring

```python
"""Return all chunks covering a line range.

Use this when you already know a line range and want chunk-level context with scope metadata.
Compared with nbrag_get_raw_file(), this preserves chunk structure and can include overlapping content by design.

Returned text includes doc_id, file_path, requested line_range, and all overlapping chunks.
"""
```

---

## 6.9 建议版 skill 速查表

```md
| 你需要什么 | 工具 | 备注 |
|---|---|---|
| 列出可用知识库 | nbrag_stats | 仅当 collection_name 未知或需要比较多个知识库时使用 |
| 语义检索 + 自动取原文 | nbrag_search_and_fetch | 默认检索入口 |
| 精确字面匹配 | nbrag_grep | 条文号、符号名、错误码、精确短语 |
| 只看 metadata 或控制检索参数 | nbrag_search | 需要更细的检索开关时 |
| 找到完整文件路径 | nbrag_find_files | 知道文件名但没有 file_path 时 |
| 查看无 overlap 原文 | nbrag_get_raw_file | 需要引用、长上下文、原文核对时 |
| 查 Python 定义 | nbrag_find_definition | 只对 Python .py 源码定义有效 |
```

---

# 七、结论

最需要优先修的不是“多写一些说明”，而是：

1. **删掉想当然、口语化、心理活动式文案**
2. **把变量名、字段名、返回标记名写到术语级精确**
3. **把 overlap / fallback / BM25 / query 职责分离讲硬讲准**
4. **把 skill 从机械流程改成策略决策文档**
5. **把 README 和 AI-facing 文档边界彻底分开**

如果后续继续优化，我建议优先级是：

1. `server.py` docstring 全面收紧术语
2. `mcp_tools.py` 返回文本统一字段语言
3. `nbrag-workflow/SKILL.md` 去机械流程化
4. README 继续去 AI 腔，保持面向人类用户

---

# 八、附加提醒（最重要）

后续任何 AI-facing 文案审核，都建议用下面这条硬规则：

> **如果一句话里出现了产品里不存在的函数名、字段名、返回标记名，或者使用了模糊近义词代替正式名词，这句话就应判定为不合格。**

例如：
- 写 `read method`，不合格
- 写 `path handle`，不合格
- 写 `document id` 而不是 `doc_id`，不合格
- 写 `chunk range marker` 而不是 `chunk:X/Y` / `chunk_index:X`，不合格

这条规则能直接挡掉一大半“AI 乱写注释”的问题。
