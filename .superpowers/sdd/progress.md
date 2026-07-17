# SDD Progress Ledger — nbrag MCP XML Handle Consistency

Branch: optimize_ret_for_llm
Plan: docs/superpowers/plans/2026-07-16-mcp-xml-handle-consistency.md

## Completed Tasks

- Task 1: complete (commits 24b144a..4cf345b, review clean, 2 Minor findings deferred — L276 field list phrasing, L133-135 list redundancy, both inherited from brief)
- Task 2: complete (commits 4cf345b..207f4fb, review clean, implementer correctly preserved 3-branch logic in error helpers, 2 Minor observations deferred — bm25_query text may need SKILL.md补充, stats容错差异是原代码已有)
- Task 3: complete (commits 207f4fb..8fe9c24, review clean, _format_search_results XML化 + 3 search fns root_tag, nbrag_search_only_vector 改为直接调 _format_search_results)
- Task 4: complete (commits 8fe9c24..db0eaee, review clean, _format_hit_xml helper 抽取 + nbrag_search_and_fetch XML化含 fetched_raw section, _format_search_results 回改用 helper)
- Task 5: complete (commits db0eaee..f2f48a0, review clean, nbrag_grep XML化, matched_line/line_range 废弃)
- Task 6: complete (commits f2f48a0..a7f9a57, review clean, nbrag_find_definition XML化, methods_summary 子元素)
- Task 7: complete (commits a7f9a57..45f0456, review clean, 4 chunk view functions XML化, has_more/anchor_chunk_index/requested_line_* 根属性)
- Task 8: complete (commits 45f0456..374004e, review APPROVED, 3 listing functions XML化, chunk_count deprecated as output field, 3 Minor findings deferred — (a) attribute values not XML-escaped (consistent with earlier tasks, body-only escaping rule), (b) inconsistent str() wrapping of doc_id in nbrag_list (cosmetic), (c) asymmetric fallback defaults 0 vs "?" (intentional per brief))
- Task 9: complete (commits 374004e..8a48948, review APPROVED 0 findings, nbrag_help L266 skeleton + 5 SKILL.md deprecated forms cleaned, implementer flagged 4 concerns all adjudicated benign — (a) augmented grep pattern to catch letter-placeholder line:N-M, (b) Edit tool stripped UTF-8 BOM from SKILL.md (harmless, frontmatter still parses), (c) L220-221 rewrite chose two-item list form with source attribution, (d) out-of-scope chunk_count/.get() fallbacks + _merge_line_ranges function name remain as Task 1-8 leftovers)
- Task 10: complete (commits 8a48948..b369994, review APPROVED 0 Critical / 0 Important / 4 Minor, scripts/test_xml_format.py 自测脚本 15/15 passed, grep scan 发现 server.py L134+L353 有 chunk_index:X 残留)
- Task 10 fix: complete (commits b369994..d9aae5a, fix server.py 2 处 chunk_index:X 残留, Task 1 遗漏, import OK + grep 0 hits confirmed)

## Notes for downstream tasks
- `_collection_presence_issue_text` returns `""` (ok) / `<error type="missing_collection">` / `<error type="empty_collection">` — 3 branches preserved
- `_collection_issue_text` returns `""` (ok) / `<error type="missing_collection">` / `<error type="empty_collection">` — 2 branches preserved
- `get_stats()["collections"]` is a dict keyed by collection_name, not a list
- OpenBLAS memory error on import — set `OPENBLAS_NUM_THREADS=1` to work around
- `_meta_file_path(meta)` and `_meta_chunk_index(meta)` available for Tasks 3-8
