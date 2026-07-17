---
name: nbrag-workflow
description: Use when the task requires searching imported nbrag knowledge bases or choosing between nbrag retrieval and follow-up tools.
---

# role and goal

In the current task, operate as an agent with strong expertise in knowledge-base retrieval strategy.
You should reason clearly about the boundaries between vector retrieval, BM25 lexical anchoring, reranking, and raw-versus-chunk follow-up, and use that reasoning to formulate query and bm25_query values that maximize the chance of surfacing the most relevant evidence.
Your priority is to obtain evidence that is both reliable and sufficiently comprehensive for the answer. Stop retrieving when the evidence is already sufficient, avoid meaningless repeated calls, but do not optimize for early convergence at the cost of missing important evidence.

# nbrag workflow for AI agents

`nbrag` is an **agentic RAG MCP**, not a one-shot search box.

Your goal is to use as few tool calls as needed to get enough reliable evidence from a prepared knowledge base, then answer.
Do not mechanically call every tool. Each next call should either:
- choose the right `collection_name`
- choose the right retrieval mode
- narrow to the right file / lines / chunks
- or stop because the current evidence is already sufficient

> Use the actual exposed tool names you received from the MCP host.
> Host wrappers may prefix names such as `xxx_nbrag_search` or `mcp__xxx__nbrag_search`.
> Do not assume the bare logical names are the callable names in the current host.

Do not assume this local skill is always visible to the host agent.
`nbrag_help()` is the MCP-level workflow distribution and routing guide for hosts where this local skill is unavailable.

## 1. First routing questions

Before calling a retrieval tool, decide:

1. Is `collection_name` already known?
2. Is this a **semantic retrieval** question or a **lexical exact-wording** question?
3. Do you need **stored original text** or **chunk-structured context**?
4. Is this specifically a **Python `.py` symbol-definition** lookup?

## 2. Usual starting points

- For every new retrieval task, call `nbrag_help()` once before `nbrag_stats()` or any retrieval, lookup, or reading tool, even when the user already named a collection. It establishes query/bm25_query roles, tool boundaries, raw-vs-chunk handling, stable follow-up handles, and multi-tool workflow.
- After that routing call, continue directly with the chosen tools. Do not call `nbrag_help()` again before every follow-up unless you need to change strategy.
- When `collection_name` is unknown, call `nbrag_stats()` next. It helps choose the correct stable `collection_name`, not the retrieval strategy by itself.
- Once collection and routing are clear, the usual default for source-backed answering is `nbrag_search_and_fetch()`.
- Use `nbrag_search()` instead when you need finer retrieval controls or metadata-only output.
- If the current result already answers the question, stop and answer. Do not continue just to complete a workflow.

## 3. Tool selection map

| Need | Preferred tool | Use it when | Avoid / switch when |
|---|---|---|---|
| First nbrag call of a new retrieval task | `nbrag_help()` | Establish query/bm25_query roles, tool boundaries, raw/chunk handling, and stable follow-up-handle rules before any other nbrag call | This task already completed its one routing call and strategy has not changed |
| Unknown `collection_name` | `nbrag_stats()` | You need the exact stable collection name before retrieval | You already know the correct collection |
| Default semantic + evidence retrieval | `nbrag_search_and_fetch()` | You want ranked discovery plus stored original-text evidence in one call | You only need metadata, or need retrieval switches |
| Ranked retrieval with finer control | `nbrag_search()` | You need to control rerank / BM25 / `include_content` / `filter_file_path` | You mainly want one-call search + auto-fetched evidence |
| Lexical-only diagnostics | `nbrag_search_only_bm25()` | You are checking exact-term recall or comparing strategies | Normal answering flow |
| Vector-only diagnostics | `nbrag_search_only_vector()` | You are checking semantic recall without BM25 | Normal answering flow |
| Exact wording or regex | `nbrag_grep()` | You need literal line-by-line matches in stored original text | The question is about meaning, paraphrase, or concept similarity |
| Python class/function/method definition | `nbrag_find_definition()` | You already know or nearly know the Python symbol name | The target is non-Python text or only a vague concept |
| Discover exact stored `file_path` | `nbrag_find_files()` | You only know a filename fragment or partial path | You already have a full absolute `file_path` |
| Browse imported documents | `nbrag_list()` | You need inventory handles like `doc_id` and `file_path`, or the user explicitly wants to browse what is imported | You are trying to answer a semantic question and do not need inventory first |
| Overlap-free original text | `nbrag_get_raw_file()` | You need clean quoting, wider source reading, or a specific line range | You need chunk boundaries / scope metadata |
| Paginated chunk view for one file | `nbrag_get_file_chunks()` | You want chunk-by-chunk browsing with line/scope metadata | You need overlap-free original text |
| Expand around a known hit | `nbrag_get_adjacent_chunks()` | You have `doc_id` + `chunk_index` from search results and want nearby chunks | You only have grep output without `chunk_index` |
| Chunk view covering a line range | `nbrag_get_chunks_by_lines()` | You know `doc_id` + `line_start + line_end` and want chunk/scope context | You only need raw source text |

## 4. Semantic retrieval vs lexical retrieval

Use **semantic retrieval** when the user is asking about:
- meaning
- explanation
- usage
- examples
- concepts
- paraphrases
- related material

Usual path:
- `nbrag_search_and_fetch()`
- `nbrag_search()`

Use **lexical retrieval** when exact wording matters. In the normal mixed pipeline, `bm25_query` is the lexical-targeting channel; `nbrag_grep()` becomes the more direct tool when you need literal/regex matching over stored original text:
- article numbers
- headings
- exact phrases
- identifiers
- class / function names
- constants
- imports / decorators
- error strings
- codes / abbreviations

Usual path:
- `bm25_query` inside `nbrag_search()` / `nbrag_search_and_fetch()`
- `nbrag_grep()` for literal / regex matching in stored original text

Do not describe `nbrag_grep()` as semantic search.
Do not treat `bm25_query` as another semantic question; it is the lexical-targeting channel inside mixed retrieval.

## 5. `query` vs `bm25_query`

These two fields work together in hybrid retrieval, and strong agents should plan them together.

### `query`
- Main semantic question used by vector retrieval and reranking
- Keep it as a natural-language question or statement that preserves the real retrieval target
- Use the ongoing dialogue and earlier tool results to improve clarity when needed: resolve pronouns, restore omitted entities, fix obvious typos, or sharpen the event / relation / attribute wording once the target is clear
- Keep the user's specificity. For example, if the user asks `关羽怎么死的`, keep `query` close to that meaning, such as `关羽怎么死的` or `关羽的死因是什么`
- Let `query` stay semantic and readable rather than turning it into a keyword bag

### `bm25_query`
- Required lexical-anchor query used only by BM25 on BM25-enabled retrieval tools
- On `nbrag_search()`, `nbrag_search_and_fetch()`, and `nbrag_search_only_bm25()`, this field carries the lexical-targeting side of the retrieval plan
- Compared with `query`, `bm25_query` is more lexical, anchor-rich, and source-facing
- Build it from wording likely to appear literally in the source: names, aliases, article numbers, abbreviations, codes, API names, class/function names, headings, constants, error strings, place names, event markers, or short phrases
- Good anchors can come from the user's wording, the surrounding conversation, and precise terms already surfaced by earlier hits
- A single `bm25_query` can combine multiple grounded anchors only when they target the same evidence; do not mix unverified alternatives, unrelated entities, or adjacent provisions merely as a keyword bag

Practical guidance:
- In agentic multi-turn retrieval, plan `query` and `bm25_query` together rather than treating `bm25_query` as an afterthought
- `query` keeps the semantic target clear; `bm25_query` gives BM25 richer lexical traction on the same target
- Improve `bm25_query` across turns as retrieval reveals better wording, aliases, identifiers, titles, place names, event markers, and repeated phrases
- A stronger `bm25_query` is usually not the shortest one; it is the one that gives BM25 a more precise lexical path to the same evidence
- Example: if the user asks `关羽怎么死的`, keep `query` close to that meaning. If conversation context or earlier retrieval reveals grounded wording such as `麦城`, `败走麦城`, or `遇害`, those clues can productively enter later `bm25_query` values because historical texts may describe the death-related evidence through event/location wording rather than the modern literal word `死`
- The same pattern applies in other domains: article numbers and legal terms for laws, class names + method names + exception text for code, error codes + API names for troubleshooting, or titles + repeated phrases for manuals
- `query` and `bm25_query` stay distinct in role: `query` carries the semantic target, while `bm25_query` carries richer lexical anchors for the same target

## 6. Query rewriting and retrieval phrasing

Good retrieval phrasing improves recall, reranking quality, and follow-up precision. Use the following principles:

- Preserve the real semantic target in `query` rather than turning it into a keyword bag.
- Use `bm25_query` to supply lexical anchors that are likely to appear literally in the source.
- When the latest user wording is too short, too modern, too indirect, or too weak for strong recall, strengthen retrieval with source-facing wording such as aliases, titles, dates, places, relation terms, event markers, headings, identifiers, and repeated source phrases.
- Reuse useful wording already surfaced in earlier retrieved evidence and relevant conversation history to sharpen later retrieval rounds.
- Let earlier evidence strengthen later `bm25_query` values and, when appropriate, clarify the semantic target of `query`.
- For comparison questions, collect evidence for A, evidence for B, and evidence for the relationship between them rather than assuming one comparison-style retrieval is always enough.
- For multi-part questions, decompose the retrieval target before deciding whether to retrieve once or in parallel.
- Use expansions as retrieval hypotheses to improve recall, then confirm the final answer against retrieved evidence.

### Examples

These examples illustrate the pattern. Apply the same reasoning in other domains rather than copying the wording mechanically.

#### Historical death question
If the user asks `关羽怎么死的`, keep `query` close to that meaning. If conversation context or earlier hits reveal wording such as `麦城`, `败走麦城`, `遇害`, `孙权`, or `吕蒙`, those clues can strengthen later `bm25_query` values because historical texts may describe the death through event, location, or participant wording rather than the modern literal word `死`.

#### API comparison question
If the user asks for the difference between create_agent and create_deep_agent, start with a comparison-oriented retrieval using the user’s own wording. If the source does not directly compare them, retrieve what create_agent is, retrieve what create_deep_agent is, and then compare the evidence you collected. If later hits surface relationship wording that clearly links the two, reuse that wording to sharpen follow-up retrieval.

#### Legal article question
If the user asks about a specific law article, keep `query` aligned to the requested meaning, and use `bm25_query` to anchor the law name, article number, and likely source wording. For example, a question about `民法典第一千零六十四条` should keep the semantic target in `query`, while `bm25_query` can begin with anchors such as `民法典 1064 夫妻共同债务`. Add a neighboring article number only after grounded evidence shows it is relevant to the same requested provision.

#### Multi-entity verification question
If the user asks about multiple entities or people, avoid relying on one undersized retrieval budget to cover all targets. Split the work into manageable retrieval targets or batches, verify each target with grounded evidence, and merge the answer only after the per-target evidence is clear.

## 7. Raw text vs chunk view

**核心规则：先分清 hit chunk、fetched raw excerpt 和完整原文。**
- 检索工具的 `<hit>` `<content>` 与 chunk 视图工具的 `<chunk>` `<content>` 是 RAG chunk，可能在 chunk 边界截断；`<match>` 是受 `match_context_chars` 限制的 stored-original-text context excerpt；Python class/function/method 的 `<definition>` 是 AST-aware definition body，`regex_fallback` 则只是候选文本匹配。
- `nbrag_search_and_fetch()` 的 `<fetched_raw>` 中 `<raw>` `<content>` 是从存储的原始文件快照围绕命中位置扩展的无 chunk overlap 摘录；它不是 RAG chunk，但仍受 `fetch_context_chars` 限制，并非整个文件。
- `nbrag_get_raw_file()` 返回无 chunk overlap 的原始文件快照。仅当用 `line_start=-1`、`line_end=-1` 请求整个文件时，才是完整文件。

当 hit 或 fetched raw excerpt 仍不足以回答、引用或验证时，再调用 `nbrag_get_raw_file` 或 `nbrag_get_adjacent_chunks` 扩展。

### Use `nbrag_get_raw_file()` when you need:
- stored original text captured at ingestion time
- overlap-free reading
- clean quoting
- broader source context
- a specific file line range

### Use chunk tools when you need:
- chunk boundaries
- scope metadata
- line metadata together with chunk structure
- local expansion around a known hit

Chunk tools:
- `nbrag_get_file_chunks()`
- `nbrag_get_adjacent_chunks()`
- `nbrag_get_chunks_by_lines()`

Important boundary:
- raw-file view = stored original snapshot without chunk overlap
- chunk view = chunk-structured context and may overlap by design
- fetched raw excerpt = overlap-free stored-original-text excerpt around a ranked hit, bounded by `fetch_context_chars`

## 8. Python symbol-definition lookup

`nbrag_find_definition()` is specialized for Python `.py` class/function/method definitions.
It is strongest after search, grep, or prior retrieval context has already narrowed the symbol name.

Use it for:
- `UserService`
- `get_by_id`
- `MyClass.__init__`

Do not treat it as a general “find definition anywhere” tool.
For non-Python text, the normal paths are:
- `nbrag_grep()` for exact wording
- `nbrag_search_and_fetch()` for semantic/source-backed discovery

Handle boundary (no `chunk_index`):
- `<definition>` exposes `file_path`, `doc_id`, `line_start`, `line_end`, but **not** `chunk_index`.
- Do not pass `line_start` as `chunk_index` into `nbrag_get_adjacent_chunks()`. That is a silent wrong-anchor call.
- To expand context around a definition, use `nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name)` or `nbrag_get_raw_file(file_path, collection_name, line_start, line_end)` instead.

## 9. Stable follow-up handles

Retrieval and lookup tools (`nbrag_search`, `nbrag_search_and_fetch`, `nbrag_search_only_bm25`, `nbrag_search_only_vector`, `nbrag_grep`, `nbrag_find_definition`, `nbrag_find_files`, `nbrag_list`) surface the **top result's** handles as ready-to-use `key = value` lines at the top of the returned text, with an `Unlocks:` line listing candidate follow-up tools (pipe-separated; parameter names are placeholders to be filled with the surfaced values).

The surfaced handle set varies by tool:
- search / search_and_fetch / only_bm25 / only_vector: `file_path`, `doc_id`, `chunk_index`, `line_start`, `line_end`
- grep / find_definition: `file_path`, `doc_id`, `line_start`, `line_end` (no `chunk_index`)
- find_files / list: `file_path`, `doc_id` (only)

When the next call targets the **top** result, reuse these values directly instead of scanning `<hit>` / `<match>` / `<file>` / `<document>` attributes. For non-top results, attribute scanning is still required. The block's title text varies by tool (e.g. "Top result handles —", "Top match handles —", "Top file handle —"); the structure is the same.

The most important reusable handles are:
- `file_path`
- `doc_id`
- `chunk_index`
- `line_start`, `line_end`

### `file_path`
Use it with:
- `nbrag_get_raw_file(file_path, collection_name)`
- `nbrag_get_file_chunks(file_path, collection_name)`
- `filter_file_path=...` in search or grep tools

Rules:
- `file_path` and `filter_file_path` should be full absolute paths returned by `nbrag`
- Do not guess with a basename or relative path
- If you only know a partial filename/path, call `nbrag_find_files()` first
- `nbrag_list()` can also provide valid `file_path` values

### `doc_id + chunk_index`
Use with:
- `nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name)`

Sources of `chunk_index`:
- Top result handles block on `nbrag_search` / `nbrag_search_and_fetch` / `nbrag_search_only_bm25` / `nbrag_search_only_vector` (preferred — reuse directly)
- `chunk_index` attribute on `<hit>` elements when you need a non-top ranked hit
- `chunk_index` attribute on `<chunk>` elements from `nbrag_get_file_chunks`, `nbrag_get_adjacent_chunks`, or `nbrag_get_chunks_by_lines` (these tools have no top-result surfacing block — attribute scan is required here)

`nbrag_grep` and `nbrag_find_definition` do **not** surface `chunk_index` at all; do not pass `line_start` as `chunk_index` into `nbrag_get_adjacent_chunks()`.

### `doc_id + line_start + line_end`
Use with:
- `nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name)`

### `file_path + line range`
Use with:
- `nbrag_get_raw_file(file_path, collection_name, line_start, line_end)`

## 10. `filter_file_path` behavior

`filter_file_path` is for narrowing retrieval to one stored file when that file is already known.

Current hybrid behavior matters:
- it narrows vector retrieval to that single file
- and it skips cross-file BM25 fusion

Use it when you are intentionally deepening inside a known file.
Do not use it as if it were only a light ranking preference over the whole collection.
For vector/hybrid search and search_and_fetch, when `filter_file_path` is set, the returned `bm25` attribute will show `off` because cross-file BM25 fusion is skipped — this is expected. `nbrag_search_only_bm25()` is the lexical-only exception and can still apply BM25 within the filtered file.

## 11. Normal multi-turn pattern

A good multi-turn retrieval flow usually looks like this:

1. Establish the collection if needed
2. Start with semantic discovery or exact matching as appropriate
3. Reuse precise terms from returned evidence as lexical anchors, and strengthen `bm25_query` as better wording appears
4. Narrow to a file only when a specific file clearly becomes the target
5. 若 hit 或 fetched raw excerpt 对回答有帮助但仍不足以回答、引用或验证，再调用 nbrag_get_raw_file 或 nbrag_get_adjacent_chunks 扩展
6. Stop once current evidence is enough to answer

Stop signals — any one is sufficient:
- 扩展后的完整原文已经足以回答用户问题
- additional rounds only surface duplicate / less-relevant hits
- the requested handle (file_path / line range / definition) has been located
- a follow-up raw/chunk read already produced the quotable evidence

If unsure whether to stop, prefer answering with the evidence you have and noting the gap, over issuing another retrieval round with no changed query or scope.

Good behavior:
- each new call changes the retrieval condition in a useful way
- later rounds are more focused than earlier rounds
- returned handles are reused instead of guessed

Bad behavior:
- repeating the same retrieval without changing the query or scope
- using grep for concept search
- forcing every task through every tool
- continuing after the evidence is already sufficient

## 12. Common combination patterns

These are ready-made 2-3 step recipes. Reuse them instead of inventing chains.
Each arrow shows which handle flows from the previous result into the next call.

### Pattern A — Semantic hit, then expand only when needed
Goal: a ranked hit or fetched raw excerpt is useful but still insufficient for answering, quoting, or verification.
1. `nbrag_search_and_fetch(query, collection_name)` → inspect the auto-fetched raw excerpt first when present; otherwise use the top result handles block.
2. If more local chunk structure is needed, `nbrag_get_adjacent_chunks(doc_id, chunk_index, collection_name)` → nearby `<chunk>`s.
   If more clean original text or an exact line range is needed, `nbrag_get_raw_file(file_path, collection_name, line_start, line_end)` → overlap-free original text.

### Pattern B — Only know a filename, then locate exact wording inside it
Goal: you know the file but need a specific line/term.
1. `nbrag_find_files(pattern, collection_name)` → Top file handle block gives `file_path`
2. `nbrag_grep(keyword, collection_name, filter_file_path=<file_path>)` → Top match handles block gives `line_start` / `line_end`

### Pattern C — Python symbol definition, then find call sites
Goal: understand a symbol, then see where it is used.
1. `nbrag_find_definition(symbol, collection_name)` → Top definition handles block gives `file_path`, `line_start`, `line_end` (no `chunk_index`)
2. `nbrag_grep(symbol, collection_name)` → call-site candidates across the collection. For only local same-file usage, pass `filter_file_path=<file_path>` instead.

### Pattern D — Semantic hit, then read clean original text around it
Goal: quote source text without chunk overlap.
1. `nbrag_search_and_fetch(query, collection_name)` → Top result handles block gives `file_path`, `line_start`, `line_end`
2. `nbrag_get_raw_file(file_path, collection_name, line_start, line_end)` → overlap-free original text

### Pattern E — Browse a large file page by page
Goal: chunk-by-chunk reading with pagination.
1. `nbrag_get_file_chunks(file_path, collection_name, start_chunk=0)` → root has `has_more`
2. if `has_more="true"`, call again with `start_chunk=<last chunk_index + 1>` until `has_more="false"`

## 13. Recovery hints

If a retrieval attempt fails or is weak:

- `collection_name` unknown or suspicious → `nbrag_stats()`
- ranked search misses exact citation / identifier → strengthen `bm25_query` with grounded anchors from the user wording, ongoing dialogue, or earlier hits, or use `nbrag_grep()`
- grep misses because wording may be paraphrased → go back to `nbrag_search_and_fetch()`
- only partial filename/path is known → `nbrag_find_files()`
- only inventory handles are needed → `nbrag_list()`
- need to compare lexical-only vs semantic-only behavior → `nbrag_search_only_bm25()` / `nbrag_search_only_vector()`

If the result is relevant but still too small:
- use `nbrag_get_raw_file()` for broader overlap-free source text
- use `nbrag_get_adjacent_chunks()` for nearby chunk context
- use `nbrag_get_chunks_by_lines()` when a line range is already known

## 14. Budget awareness

Context-size knobs are per-result budgets, not global response caps:
- `fetch_context_chars` in `nbrag_search_and_fetch()` is per ranked hit
- `match_context_chars` in `nbrag_grep()` is per grep match

Increase them only when more source context is necessary.
Large values combined with many hits can create unnecessarily large outputs.

## One-line summary

Use `nbrag` as a retrieval workflow, not as a rigid script: choose the right collection, choose semantic vs lexical retrieval, keep `query` and `bm25_query` roles distinct, reuse the top-result handles surfaced at the top of each retrieval/lookup output, and stop once the evidence is enough to answer.
