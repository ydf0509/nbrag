# nbrag_grep Wording Cleanup Design

## Goal

Tighten the `nbrag_grep` wording so AI agents understand exactly when to use it and what it actually does, without changing any implementation logic.

## Context

Recent edits already improved `nbrag_grep` substantially by warning that it is not semantic search and by giving a strong failure example such as searching for `空城计` when the source text only contains `焚香操琴` and `大开四门`.

The remaining issue is technical precision. Current wording still uses phrases such as `byte-for-byte`, `byte-level`, and broad `exact matching`, but the implementation actually compiles the input as regex when valid, falls back to escaped literal text otherwise, and applies `re.search()` to stored text one line at a time.

That mismatch is small but important. The goal of this cleanup is to preserve the new anti-misuse guidance while making the wording technically correct and consistent across MCP docstrings, built-in help, and the workflow skill.

## Requirements

- Change documentation only; do not modify runtime grep behavior.
- Keep the strong warning that `nbrag_grep` is not semantic or concept search.
- Keep at least one concrete failure example that shows why conceptual labels may not match source wording.
- Replace inaccurate `byte-for-byte` / `byte-level` wording with wording that matches the implementation.
- Explicitly distinguish plain-text matching from valid regex matching.
- Explicitly mention that matching is line-based, so cross-line phrases may fail to match.
- Keep all three user-facing surfaces aligned:
  - `nbrag/server.py` MCP tool description
  - `nbrag/mcp_tools.py` built-in help / no-match guidance
  - `nbrag/skills/nbrag-workflow/SKILL.md` workflow guidance

## Recommended Approach

Use one shared conceptual model everywhere:

- `nbrag_grep` performs **line-by-line literal text or regex matching** on stored original text.
- If the input is plain text, that wording must appear literally in the source text.
- If the input is a valid regex pattern, regex rules apply.
- The tool does not infer concepts, aliases, synonyms, paraphrases, or summarized plot labels.
- Conceptual or wording-uncertain questions should go to `nbrag_search_and_fetch` first.

This keeps the explanation simple for AI agents while staying faithful to the implementation.

## File-by-File Design

### 1. `nbrag/server.py`

Update the `keyword` field description and `nbrag_grep` docstring.

Key wording changes:

- Replace `byte-for-byte exact matching` with `line-by-line literal text or regex matching`.
- Replace `byte-level matching (re.search) on raw file content` with `matched line by line with re.search on stored original text`.
- Add one sentence that separates plain text from valid regex behavior.
- Add one sentence that states matching is line-based and cross-line phrases may not match.
- Preserve the `空城计` example and the guidance to use `nbrag_search_and_fetch` when exact wording is unknown.

### 2. `nbrag/mcp_tools.py`

Update the built-in `nbrag_help` wording for grep so it matches the MCP docstring terminology.

Also strengthen the no-match guidance slightly so it does not only suggest simpler exact terms and semantic discovery, but also makes it clear that conceptual labels or paraphrases may fail because grep only matches literal wording or regex patterns found in the stored text.

### 3. `nbrag/skills/nbrag-workflow/SKILL.md`

Update the grep guidance in both the quick-decision table and Strategy C.

Key wording changes:

- Replace `精确字节匹配` with wording equivalent to `逐行字面文本 / 正则匹配`.
- Preserve the conceptual-failure example for `空城计`.
- Add a short note that cross-line phrases may not match.
- Keep the recommendation to switch to `nbrag_search_and_fetch` for concept-level or wording-uncertain queries.

## Trade-Offs

A stricter technical description is slightly longer than the current text, but the extra length is justified because `nbrag_grep` is easy for AI agents to misuse. The wording should optimize for correct tool selection over maximum brevity.

The design intentionally does not mention every implementation detail, such as fallback escaping after invalid regex compilation, in every surface. The MCP docstring can mention that clearly, while help and skill text can stay shorter as long as they preserve the same mental model.

## Testing / Verification

Verification is documentation-focused:

- Read the updated text in all three files and confirm they use the same conceptual model.
- Confirm there are no remaining claims of byte-level matching unless they are technically true.
- Confirm the wording still strongly steers AI away from using grep for concept questions.
- Optionally run existing retrieval-quality checks if desired, but no runtime behavior change is expected.
