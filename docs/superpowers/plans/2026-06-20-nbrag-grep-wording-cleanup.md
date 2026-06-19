# nbrag_grep Wording Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `nbrag_grep` documentation consistently AI-friendly and technically accurate across MCP docstrings, built-in help, and the workflow skill, without changing grep runtime behavior.

**Architecture:** Keep the current anti-misuse guidance but replace inaccurate `byte-for-byte` / `byte-level` phrasing with one shared mental model: `nbrag_grep` performs line-by-line literal text or regex matching on stored original text. Update all three user-facing surfaces together so agents receive the same guidance regardless of entry point.

**Tech Stack:** Python docstrings and Pydantic `Field` descriptions, Markdown skill documentation, pytest for lightweight regression verification

---

## File Map

- Modify: `nbrag/server.py`
  - MCP tool parameter descriptions and docstring for `nbrag_grep`
- Modify: `nbrag/mcp_tools.py`
  - `nbrag_help` guidance lines for grep usage
  - `nbrag_grep` no-match hint text
- Modify: `nbrag/skills/nbrag-workflow/SKILL.md`
  - quick-decision table grep guidance
  - Strategy C grep explanation
- Verify: `tests/test_server_contracts.py`
  - Existing contract tests should still pass because behavior is unchanged and text remains coherent

### Task 1: Update `nbrag/server.py` MCP wording

**Files:**
- Modify: `nbrag/server.py`
- Test: `tests/test_server_contracts.py`

- [ ] **Step 1: Write the target wording into the `keyword` Field description**

Replace the existing `keyword` field description in `nbrag/server.py` with this exact text:

```python
keyword: str = Field(
    description="Plain text or regex pattern to search in stored original text lines. "
                "This is line-by-line literal/regex matching — NOT semantic/concept search. "
                "If you pass plain text, that wording must appear literally in the source text "
                "(for example, '试用期' will not match text that only says '见习期'). "
                "If you pass a valid regex, regex rules apply. "
                "Examples: '第四十二条', 'MAX_RETRIES', 'UserService', 'Article 42'. "
                "When in doubt about exact wording, use nbrag_search_and_fetch instead."
)
```

- [ ] **Step 2: Rewrite the `nbrag_grep` docstring with the shared mental model**

Replace the current `nbrag_grep` docstring in `nbrag/server.py` with this exact block:

```python
"""Literal text / regex search in stored original text, matched line by line with re.search — NOT semantic or concept search.

⚠️ CRITICAL: This tool only matches wording that literally appears in the stored text, unless you provide a valid regex pattern.
It does NOT understand concepts, aliases, synonyms, paraphrases, or summarized labels.
For example, searching '空城计' will find nothing if the original text only says '焚香操琴' and '大开四门' but never uses the exact term '空城计'.
When in doubt about exact wording, use nbrag_search_and_fetch (semantic search) instead.

Best for exact known strings:
  - 法律条文号 ('第四十二条'), 标题 headings, 专业术语 exact terms, 日期 dates, 编号 codes
  - Code: class/function names ('UserService'), constants ('MAX_RETRIES'), imports ('from myproject'), error strings

Important limits:
  - Plain text only matches wording that literally appears in the source text.
  - Valid regex patterns follow regex rules rather than literal matching.
  - Matching is line-based, so cross-line phrases may not match as expected.

NOT suitable for (use nbrag_search_and_fetch instead):
  - Conceptual queries ('劳动法对试用期有什么规定' → search, not grep)
  - Summarized plot points ('空城计', '草船借箭' — these may not appear verbatim)
  - Paraphrased or vague terms

Python source workflow: after nbrag_search_and_fetch discovers relevant files, use nbrag_grep for exact
names/imports/constants/decorators/error strings, then nbrag_find_definition for complete Python .py symbols,
and nbrag_get_raw_file for full source context.

Tip: use context_lines=15 to see surrounding context around the match.
Common pattern when extra evidence is needed: semantic discovery → exact-term grep → raw file context."""
```

- [ ] **Step 3: Run the targeted server contract tests**

Run:

```bash
D:/ProgramData/miniconda3/envs/py312/python.exe -m pytest tests/test_server_contracts.py -q
```

Expected: PASS

- [ ] **Step 4: Commit the server wording update**

```bash
git add nbrag/server.py tests/test_server_contracts.py
git commit -m "docs: clarify nbrag_grep server wording"
```

### Task 2: Align `nbrag/mcp_tools.py` help and no-match guidance

**Files:**
- Modify: `nbrag/mcp_tools.py`
- Test: `tests/test_server_contracts.py`

- [ ] **Step 1: Rewrite the grep guidance lines in `nbrag_help`**

Update the grep-related lines in `nbrag_help()` so they read exactly as follows:

```python
"- Exact law articles, document headings, terms, phrases, API names, or constants? use nbrag_grep.",
"  ⚠️ grep does line-by-line literal text or regex matching on stored text — it does NOT infer concepts.",
"  '空城计' will NOT match if the file only says '焚香操琴' instead. When unsure about exact wording, prefer nbrag_search_and_fetch (semantic search).",
```

- [ ] **Step 2: Strengthen the no-match hint for conceptual wording failures**

Replace the `if not results:` return string in `nbrag_grep()` with this exact block:

```python
return (
    f"No matches for '{keyword}' (collection: {collection_name}).\n"
    "Possible adjustments: use a simpler literal term, check spelling/article number, remove regex anchors, "
    "or switch to nbrag_search_and_fetch for semantic discovery if this is a concept, alias, or paraphrase rather than exact source wording."
)
```

- [ ] **Step 3: Run the targeted server contract tests again**

Run:

```bash
D:/ProgramData/miniconda3/envs/py312/python.exe -m pytest tests/test_server_contracts.py -q
```

Expected: PASS

- [ ] **Step 4: Commit the help-text alignment**

```bash
git add nbrag/mcp_tools.py tests/test_server_contracts.py
git commit -m "docs: align nbrag grep help guidance"
```

### Task 3: Align `nbrag-workflow` skill wording

**Files:**
- Modify: `nbrag/skills/nbrag-workflow/SKILL.md`
- Test: `tests/test_server_contracts.py`

- [ ] **Step 1: Update the quick-decision table grep note**

Replace the grep note in the quick-decision table with this exact text:

```markdown
| 精确字符串/术语/条文编号（"第一千零七十七条" / "ThreadPool"） | `nbrag_grep` | 逐行字面文本 / 正则匹配，返回上下文。⚠️ 只匹配原文中实际出现的 wording，不支持概念理解（'空城计'搜不到原文中的'焚香操琴'） |
```

- [ ] **Step 2: Rewrite Strategy C to match the MCP wording**

Replace the Strategy C bullet list with this exact block:

```markdown
- 在已存储的原始文本中进行逐行字面文本 / 正则匹配（re.search），不是语义搜索
- ⚠️ 只匹配原文中实际出现的 wording；如果传的是合法 regex，则按 regex 规则匹配
- 概念性提问（如"空城计"）很可能搜不到，尤其当原文只写了具体描写而没写这个概括词；这种情况改用 `nbrag_search_and_fetch`
- 匹配是按行进行的，跨行短语可能无法按预期命中
- `context_lines=10` 控制上下文（默认 10，匹配行前后各 N 行）
- 可选 `case_sensitive=True`、`filter_file_path="D:/docs/labor_law/劳动合同法.md"`（必须是完整绝对路径）
- `>>>` 标记匹配行
```

- [ ] **Step 3: Run the same lightweight regression test suite**

Run:

```bash
D:/ProgramData/miniconda3/envs/py312/python.exe -m pytest tests/test_server_contracts.py -q
```

Expected: PASS

- [ ] **Step 4: Commit the skill wording update**

```bash
git add nbrag/skills/nbrag-workflow/SKILL.md tests/test_server_contracts.py
git commit -m "docs: clarify nbrag grep workflow guidance"
```

### Task 4: Final consistency review

**Files:**
- Modify: `nbrag/server.py`
- Modify: `nbrag/mcp_tools.py`
- Modify: `nbrag/skills/nbrag-workflow/SKILL.md`
- Test: `tests/test_server_contracts.py`

- [ ] **Step 1: Manually inspect the final wording for consistency**

Open the three modified files and confirm all three surfaces use the same model:

- `nbrag_grep` is line-by-line literal text or regex matching
- plain text must literally appear in stored text
- valid regex follows regex rules
- concept / alias / paraphrase questions should prefer `nbrag_search_and_fetch`
- line-based matching may miss cross-line phrases

- [ ] **Step 2: Run the final verification command**

Run:

```bash
D:/ProgramData/miniconda3/envs/py312/python.exe -m pytest tests/test_server_contracts.py -q
```

Expected: PASS

- [ ] **Step 3: Commit the final consistency pass**

```bash
git add nbrag/server.py nbrag/mcp_tools.py nbrag/skills/nbrag-workflow/SKILL.md tests/test_server_contracts.py docs/superpowers/specs/2026-06-20-nbrag-grep-wording-design.md docs/superpowers/plans/2026-06-20-nbrag-grep-wording-cleanup.md
git commit -m "docs: finalize nbrag grep wording"
```
