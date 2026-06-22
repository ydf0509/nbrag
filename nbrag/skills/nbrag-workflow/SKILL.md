---
name: nbrag-workflow
description: Use when the task requires searching imported nbrag knowledge bases or choosing between nbrag retrieval and follow-up tools.
---

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
When routing is unclear inside the current task, `nbrag_help()` is the MCP-level fallback guide.

## 1. First routing questions

Before calling a retrieval tool, decide:

1. Is `collection_name` already known?
2. Is this a **semantic retrieval** question or a **lexical exact-wording** question?
3. Do you need **stored original text** or **chunk-structured context**?
4. Is this specifically a **Python `.py` symbol-definition** lookup?

## 2. Usual starting points

- When this is your first `nbrag` call in the current task and collection/tool routing is still unclear, call `nbrag_help()`.
- When `collection_name` is unknown, call `nbrag_stats()` next. It helps choose the correct stable `collection_name`, not the retrieval strategy by itself.
- Once collection and routing are clear, the usual default for source-backed answering is `nbrag_search_and_fetch()`.
- Use `nbrag_search()` instead when you need finer retrieval controls or metadata-only output.
- If the current result already answers the question, stop and answer. Do not continue just to complete a workflow.

## 3. Tool selection map

| Need | Preferred tool | Use it when | Avoid / switch when |
|---|---|---|---|
| First nbrag call or routing unclear | `nbrag_help()` | You need the MCP-level routing guide and stable follow-up-handle reminders | Collection and tool path are already clear |
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
| Chunk view covering a line range | `nbrag_get_chunks_by_lines()` | You know `doc_id` + `line:N-M` and want chunk/scope context | You only need raw source text |

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
- A single `bm25_query` can combine multiple grounded anchors when they all help target the same evidence

Practical guidance:
- In agentic multi-turn retrieval, plan `query` and `bm25_query` together rather than treating `bm25_query` as an afterthought
- `query` keeps the semantic target clear; `bm25_query` gives BM25 richer lexical traction on the same target
- Improve `bm25_query` across turns as retrieval reveals better wording, aliases, identifiers, titles, place names, event markers, and repeated phrases
- A stronger `bm25_query` is usually not the shortest one; it is the one that gives BM25 a more precise lexical path to the same evidence
- Example: if the user asks `关羽怎么死的`, keep `query` close to that meaning. If conversation context or earlier retrieval reveals grounded wording such as `麦城`, `败走麦城`, or `遇害`, those clues can productively enter later `bm25_query` values because historical texts may describe the death-related evidence through event/location wording rather than the modern literal word `死`
- The same pattern applies in other domains: article numbers and legal terms for laws, class names + method names + exception text for code, error codes + API names for troubleshooting, or titles + repeated phrases for manuals
- `query` and `bm25_query` stay distinct in role: `query` carries the semantic target, while `bm25_query` carries richer lexical anchors for the same target

## 6. Raw text vs chunk view

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

## 7. Python symbol-definition lookup

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

## 8. Stable follow-up handles

The most important reusable handles are:
- `file_path`
- `doc_id`
- `chunk_index`
- `line:N-M`

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

Get `chunk_index` from search results such as:
- `chunk:X/Y`
- `chunk_index:X`

Do not try this from grep output alone, because grep does not provide `chunk_index`.

### `doc_id + line:N-M`
Use with:
- `nbrag_get_chunks_by_lines(doc_id, line_start, line_end, collection_name)`

### `file_path + line range`
Use with:
- `nbrag_get_raw_file(file_path, collection_name, line_start, line_end)`

## 9. `filter_file_path` behavior

`filter_file_path` is for narrowing retrieval to one stored file when that file is already known.

Current hybrid behavior matters:
- it narrows vector retrieval to that single file
- and it skips cross-file BM25 fusion

Use it when you are intentionally deepening inside a known file.
Do not use it as if it were only a light ranking preference over the whole collection.

## 10. Normal multi-turn pattern

A good multi-turn retrieval flow usually looks like this:

1. Establish the collection if needed
2. Start with semantic discovery or exact matching as appropriate
3. Reuse precise terms from returned evidence as lexical anchors, and strengthen `bm25_query` as better wording appears
4. Narrow to a file only when a specific file clearly becomes the target
5. Expand with raw text or chunk context only when the current excerpt is insufficient
6. Stop once the evidence is enough to answer

Good behavior:
- each new call changes the retrieval condition in a useful way
- later rounds are more focused than earlier rounds
- returned handles are reused instead of guessed

Bad behavior:
- repeating the same retrieval without changing the query or scope
- using grep for concept search
- forcing every task through every tool
- continuing after the evidence is already sufficient

## 11. Recovery hints

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

## 12. Budget awareness

Context-size knobs are per-result budgets, not global response caps:
- `fetch_context_chars` in `nbrag_search_and_fetch()` is per ranked hit
- `match_context_chars` in `nbrag_grep()` is per grep match

Increase them only when more source context is necessary.
Large values combined with many hits can create unnecessarily large outputs.

## One-line summary

Use `nbrag` as a retrieval workflow, not as a rigid script: choose the right collection, choose semantic vs lexical retrieval, keep `query` and `bm25_query` roles distinct, reuse stable follow-up handles, and stop once the evidence is enough to answer.
