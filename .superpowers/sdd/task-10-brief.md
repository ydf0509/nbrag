# Task 10: 端到端验证 + 自测脚本

**Files:**
- Create: `scripts/test_xml_format.py`（临时自测脚本，验证 XML 格式正确性）

## 背景

9109 端口 MCP server 已由主 session 启动并确认监听（`netstat` 显示 `TCP 127.0.0.1:9109 LISTENING`）。本 task 写自测脚本验证 Task 1-9 的 XML 格式改动。

## 验证策略

**主验证方式：直接 import `nbrag.mcp_tools` 函数调用**（可靠、避开 MCP HTTP 协议握手复杂性、避开 OpenBLAS 端口冲突）。

**辅助验证：9109 端口已在监听**（主 session 已确认，证明 server 能启动且 `mcp_tools` 模块能被 FastMCP 加载）。

不要求脚本通过 HTTP 调用 MCP 接口——直接 import 调用函数已能覆盖 XML 格式正确性验证。

## 脚本逻辑 `scripts/test_xml_format.py`

脚本必须：
1. 设置 `OPENBLAS_NUM_THREADS=1` 环境变量（在 import nbrag 之前，避免 OpenBLAS 内存错误）
2. `import my_load_config` 加载 API key（脚本需要能调真实的 embedding/rerank）
3. `from nbrag.config import load_config; load_config()`
4. `from nbrag.mcp_tools import *`（或按需 import 13 个函数）
5. 按顺序调用并验证返回格式：

| 步骤 | 调用 | 验证点 |
|---|---|---|
| 1 | `nbrag_help()` | 返回含 `line_start, line_end`，不含 `line:N-M` / `chunk:X/Y` / `chunk_index:X` |
| 2 | `nbrag_stats()` | 返回以 `<nbrag_stats>` 开头、`</nbrag_stats>` 结尾；含 `<collections>` / `<collection `；若成功则提取第一个 `collection_name` 供后续步骤用 |
| 3 | `nbrag_search_and_fetch(query="...", collection_name=<step2的>, bm25_query="...")` | 返回含 `<nbrag_search_and_fetch` / `<ranked_hits>` / `<hit ` / `<fetched_raw>`；从第一个 `<hit>` 提取 `file_path` / `doc_id` / `chunk_index` / `line_start` / `line_end` 属性值 |
| 4 | `nbrag_search(query="...", collection_name=<...>, include_content=False)` | 返回含 `<nbrag_search` / `<ranked_hits>` / `<hit `（自闭合，无 `<content>`） |
| 5 | `nbrag_search_only_bm25(query="...", collection_name=<...>)` | 返回含 `<nbrag_search_only_bm25` |
| 6 | `nbrag_search_only_vector(query="...", collection_name=<...>)` | 返回含 `<nbrag_search_only_vector` |
| 7 | `nbrag_grep(pattern="...", collection_name=<...>)` | 返回含 `<nbrag_grep` / `<matches>` / `<match `；`<match>` 有 `line_start` 和 `line_end` 属性；提取一个 `file_path` / `doc_id` / `line_start` / `line_end` |
| 8 | `nbrag_find_definition(symbol="...", collection_name=<...>)` | 返回含 `<nbrag_find_definition` / `<definitions>` / `<definition `（若项目有 .py collection）；若该 collection 无 .py，返回 `<error type="not_found"` 或 `<error type="no_results"` 也算通过 |
| 9 | `nbrag_find_files(pattern="...", collection_name=<...>)` | 返回含 `<nbrag_find_files` / `<files>` / `<file `；`<file>` 有 `file_path` / `doc_id` / `total_chunks` 属性（不是 `chunk_count`） |
| 10 | `nbrag_list(collection_name=<...>)` | 返回含 `<nbrag_list` / `<documents>` / `<document `；`<document>` 有 `doc_id` / `file_path` / `total_chunks`（不是 `chunk_count`） |
| 11 | `nbrag_get_raw_file(file_path=<step3或7的>, collection_name=<...>)` | 返回含 `<nbrag_get_raw_file` / `<content>` |
| 12 | `nbrag_get_file_chunks(file_path=<...>, collection_name=<...>)` | 返回含 `<nbrag_get_file_chunks` / `<chunks>` / `<chunk `；`<chunk>` 有 `chunk_index` / `line_start` / `line_end` |
| 13 | `nbrag_get_adjacent_chunks(doc_id=<...>, chunk_index=<step3的>, collection_name=<...>)` | 返回含 `<nbrag_get_adjacent_chunks` / `anchor_chunk_index=` 属性 / `<chunks>` |
| 14 | `nbrag_get_chunks_by_lines(doc_id=<...>, line_start=<...>, line_end=<...>, collection_name=<...>)` | 返回含 `<nbrag_get_chunks_by_lines` / `requested_line_start=` / `requested_line_end=` |
| 15 | `nbrag_get_raw_file(file_path="INVALID_PATH", collection_name=<...>)` | 返回 `<error type="invalid_file_path" field="file_path">` |

6. 每步 print `PASS` / `FAIL <原因>`，不 assert（用户明确说不用管测试断言）
7. 末尾 print 汇总：`X/15 passed`

## query/pattern 选择

- `nbrag_search_and_fetch` / `nbrag_search`：用通用 query 如 `"什么是"` 或 `"历史"`（取决于 collection 内容）。脚本应先从 `nbrag_stats()` 拿到 collection_name 后，可用 `nbrag_list()` 拿一个 `filename`，再用 filename 里的词当 query。
- `nbrag_grep` pattern：用一个常见字如 `"的"` 或 `"是"`（保证有匹配）
- `nbrag_find_definition` symbol：若 collection 有 .py 文件用 `"main"`；否则预期 `<error type="not_found">`
- `nbrag_find_files` pattern：从 `nbrag_list()` 拿一个 filename 的片段

脚本应该**自适应**：先 `nbrag_stats()` 拿 collection，再 `nbrag_list()` 拿文件列表，从文件列表推导 query/pattern，不要硬编码。

## Steps

- [ ] **Step 1: 写 `scripts/test_xml_format.py`**

按上述逻辑写脚本。脚本顶部：
```python
import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import my_load_config
from nbrag.config import load_config
load_config()
from nbrag.mcp_tools import (
    nbrag_help, nbrag_stats, nbrag_search, nbrag_search_and_fetch,
    nbrag_search_only_bm25, nbrag_search_only_vector, nbrag_grep,
    nbrag_find_definition, nbrag_find_files, nbrag_list,
    nbrag_get_raw_file, nbrag_get_file_chunks, nbrag_get_adjacent_chunks,
    nbrag_get_chunks_by_lines,
)
```

- [ ] **Step 2: 运行脚本**

```powershell
D:/ProgramData/miniconda3/envs/py312/python.exe scripts/test_xml_format.py
```
记录输出。目标：15/15 passed。若某步 FAIL，记录原因（可能是 collection 无 .py 文件导致 find_definition 返回 error——这种按 brief 第 8 步说明算通过）。

- [ ] **Step 3: 全局 grep 扫描确认 nbrag/ 无废弃字段名残留**

Run Grep:
```
pattern: "line:N-M|chunk:X/Y|chunk_index:X|matched_line|line_range"
path: nbrag/
glob: "*.py"
output_mode: content, -n=true
```
Expected: 0 命中（`_merge_line_ranges` 函数名包含 `line_range` 子串，但这是内部函数名不是 AI-facing 字段，可接受——记录到 report 里即可）

再扫 SKILL.md：
```
pattern: "line:N-M|chunk:X/Y|chunk_index:X|matched_line|line_range|chunk_count"
path: nbrag/skills/nbrag-workflow/SKILL.md
```
Expected: 0 命中

- [ ] **Step 4: Commit**

```bash
git add scripts/test_xml_format.py
git commit -m "test: add XML format verification script for 9109 port + direct import"
```

## Global Constraints

- **Python 解释器**：`D:/ProgramData/miniconda3/envs/py312/python.exe`
- **OPENBLAS_NUM_THREADS=1**：必须在 import nbrag 之前设置
- **不 assert**：脚本只 print PASS/FAIL，不 raise
- **脚本自适应**：不硬编码 collection_name / query / pattern，从 `nbrag_stats()` + `nbrag_list()` 推导
- **9109 端口已启动**：主 session 已确认监听，implementer 不需要启动 server，只需要写脚本并运行
- **临时脚本**：保留 commit（用户可能想后续回归），最终是否删除由用户在 final review 时决定
- **canonical handle 字段集**：`file_path` / `doc_id` / `chunk_index` / `total_chunks` / `line_start` / `line_end`
- **禁止变体**（在 AI-facing 输出中）：`line:N-M` / `chunk:X/Y` / `chunk_index:X` / `matched_line` / `line_range` / `chunk_count`（作为输出字段名）
