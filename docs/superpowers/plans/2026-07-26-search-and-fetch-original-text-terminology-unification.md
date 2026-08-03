# `nbrag_search_and_fetch` 自动原文摘录术语与契约统一计划

> **历史接口快照**
>
> 本计划中的 `nbrag_search_and_fetch` 是旧 MCP 名称，当前映射为 `nbrag_retrieve`；旧 `fetch_top_n_original_text_excerpt` → `expand_top_n`，旧 `fetch_context_chars` → `expand_context_chars`。请以当前 `nbrag/server.py` 暴露的工具 schema 为准。

## 背景与目标

`nbrag_read_more_original_text()` 已采用 `original_text` 作为对外术语，但 `nbrag_search_and_fetch()` 的自动摘录仍同时出现 `raw`、`stored original content`、`raw-context`、`fetched raw excerpt`、`自动取证` 等说法。

这些说法指向的是同一种对外结果：围绕排序命中行、从知识库已导入快照中读取、按 `fetch_context_chars` 扩展并合并后的有限原文窗口。术语不一致会使 Agent 把该结果误解为完整文件、RAG chunk，或与 `nbrag_read_more_original_text()` 返回的 stored original text 无关的另一类数据。

本计划以 **减少 Agent 选择工具、理解返回标签、复用 handles 时的歧义** 为目标。对外统一使用 `original_text`，同时保留内部 `raw=True` / raw cache 等实现术语；它们表达的是底层读取方式，不是 MCP contract。

## 已确认的行为边界

### 1. 三类证据必须区分

| 对外概念 | 实际来源与范围 | 不能误解为 |
|---|---|---|
| RAG chunk | `<nbrag_chunk_content>`；受 chunk 边界限制，可能和相邻 chunk 重叠 | 完整原文或连续文件视图 |
| 自动原文摘录 | `nbrag_search_and_fetch()` 围绕排序命中自动生成；无 chunk overlap；受 `fetch_context_chars` 约束 | 整个文件、完整原文、一个 RAG chunk |
| 原文扩展读取 | `nbrag_read_more_original_text()` 读取知识库保存的原文快照，可按行范围扩大或省略范围取得全文件 | 实时本地文件系统读取 |

### 2. 自动摘录生成规则必须在工具描述中保留

当前实现的真实行为位于 `nbrag/mcp_tools.py:nbrag_search_and_fetch()`：

1. 仅查看前 `fetch_top_n_*` 个排序命中；
2. 同一 `doc_id` 的命中行范围会聚合；
3. 每个命中以 `fetch_context_chars` 为**每命中**的近似总字符预算扩展上下文；
4. 同一文件内重叠或相邻范围会合并；
5. 所以最终返回的摘录实体数可能小于参数值，且不是“前 N 个完整文件”。

这是一条关键的 Agent contract，不能只把参数改名而遗漏描述同步。

## 建议确定的术语与命名

| 概念 | 推荐对外名称 | 对应项 |
|---|---|---|
| 组合能力 | 检索与自动原文摘录 / search and auto-fetch original-text excerpts | `nbrag_search_and_fetch` |
| 自动摘录实体 | 自动原文摘录 / auto-fetched original-text excerpt | `<nbrag_original_text_excerpt>` |
| 自动摘录正文 | 自动原文摘录内容 / auto-fetched original-text excerpt content | `<nbrag_original_text_content>` |
| 候选命中数 | 自动原文摘录候选命中数 / number of ranked hits eligible for auto-fetch | `fetch_top_n_original_text_excerpt` |
| 上下文预算 | 每命中原文上下文字符预算 / per-hit original-text context-character budget | `fetch_context_chars` |
| 完整或扩大读取 | 存储原文扩展读取 / stored-original-text expansion read | `nbrag_read_more_original_text()` |

### XML 标签结构

自动摘录结果改为：

```xml
<nbrag_original_text_excerpt>
file_path = ...
doc_id = ...
line_start = ...
line_end = ...

<nbrag_original_text_content>
...
</nbrag_original_text_content>
</nbrag_original_text_excerpt>
```

- 外层 `<nbrag_original_text_excerpt>` 表示一个有限范围的摘录实体，并承载可直接传给下游工具的 `file_path`、`doc_id`、`line_start`、`line_end`。
- 内层 `<nbrag_original_text_content>` 只表示该实体的文本载荷。
- `nbrag_read_more_original_text()` 的 `<nbrag_original_text>` 与 `<nbrag_original_text_content>` 保持不变：外层名称不同，明确区分“自动有限摘录”与“显式原文读取结果”。
- 保持 `key = value` handle 的当前序列化形式；本次不将 handles 改成 XML 属性，避免混入另一个返回格式重构。

## 实施范围

### A. 必须修改：运行时对外 MCP contract

#### 1. `nbrag/mcp_tools.py`

修改 `nbrag_search_and_fetch()` 及 `_search_and_fetch_follow_up_guidance()`：

- [ ] 参数名从 `fetch_top_n_raw` 改为 `fetch_top_n_original_text_excerpt`。
- [ ] 同步局部变量、条件判断和调用链中的同名引用；不改变默认值 `3`、`top_k` 的截取规则、按 `doc_id` 聚合规则、范围扩展规则或范围合并规则。
- [ ] 自动摘录实体标签从 `<nbrag_raw_excerpt>` 改为 `<nbrag_original_text_excerpt>`。
- [ ] 自动摘录正文标签从 `<nbrag_raw_content>` 改为 `<nbrag_original_text_content>`。
- [ ] 将 follow-up guidance 中的 `<nbrag_raw_content>` 改为同时说明外层和内层标签：
  - `<nbrag_original_text_excerpt>` 是带 handles 的、受 `fetch_context_chars` 限制的有限存储原文摘录；
  - `<nbrag_original_text_content>` 是该摘录的正文；
  - 它不是完整知识库文件。
- [ ] 将 `raw excerpt`、`raw file` 等仅用于自动摘录对外说明的词，替换为 `original-text excerpt` / `stored original-text excerpt`。
- [ ] 不改变 `get_file_chunks(..., raw=True)`、`raw_data`、`raw_content` 等内部实现变量或底层 API；它们不是 Agent-facing contract。

#### 2. `nbrag/server.py`

修改 `nbrag_search_and_fetch()` 的 MCP 签名、`Field` 描述、docstring，以及调用 mcp_tools 的关键字参数：

- [ ] 参数签名和转发关键字从 `fetch_top_n_raw` 改为 `fetch_top_n_original_text_excerpt`。
- [ ] 参数说明明确：它限制的是“参与自动摘录的排序命中数”；相同文档的范围会聚合并合并，因此最终 `<nbrag_original_text_excerpt>` 的数量可能少于该值。
- [ ] 保留 `0` 禁用自动摘录的行为。
- [ ] 将 “auto-fetched stored original content” 统一为 “auto-fetched stored original-text excerpts”。
- [ ] 将 “raw-context budget” 统一为 “per-hit original-text context-character budget”。
- [ ] docstring 的两段结果说明必须精确列出：
  1. `<nbrag_ranked_hit>` 内的 `<nbrag_chunk_content>` 是一个 RAG chunk；
  2. `<nbrag_original_text_excerpt>` 内的 `<nbrag_original_text_content>` 是有限自动原文摘录；
  3. 二者都不是完整文件；需要更宽上下文、完整引文或验证时，使用返回 handles 调 `nbrag_read_more_original_text()` 或相应 chunk 工具。
- [ ] `fetch_context_chars` 继续明确为 per-hit 预算，不是整个响应的总长度上限。

### B. 必须修改：AI workflow skill

#### 3. `nbrag/skills/nbrag-workflow/SKILL.md`

把此文件视作 AI runtime routing guidance，而不是人类 README。修改所有直接指导 Agent 的术语并保留真实行为边界：

- [ ] 工具表中将 `ranked discovery + 局部 original-text excerpt` 固定为“排序发现 + 自动原文摘录”；将“自动取证”替换为同一术语。
- [ ] 将 `chunk vs raw — 三层 evidence` 改为 `chunk vs original text — 三层 evidence`。
- [ ] 三层表中的 `fetched raw excerpt` 改为 “auto-fetched original-text excerpt”，标签同步为 `<nbrag_original_text_content>` under `<nbrag_original_text_excerpt>`。
- [ ] 保留它受 `fetch_context_chars` 限制、不是完整文件、且不同于 RAG chunk 的说明。
- [ ] “raw-file” 改为“stored original-text snapshot”；“fetched raw excerpt”改为“auto-fetched original-text excerpt”。
- [ ] Pattern A 中错误的 ``fetched_raw_excerpt`` 改为精确、可复制的 `<nbrag_original_text_excerpt>`；说明优先检查其范围和 handles，但仍应基于证据需要决定是否调用 `nbrag_read_more_original_text()`。
- [ ] budget 章节将参数名改为 `fetch_top_n_original_text_excerpt`（如涉及），并说明“候选命中数”与“最终摘录实体数”不必相等。
- [ ] 不扩大为 README 文案重写；若 README 不含此运行时标签或参数，则不修改 README。

### C. 必须修改：直接测试和验证入口

#### 4. `tests/test_mcp_contracts.py`

- [ ] 将 `fetch_top_n_raw` 调用参数改为 `fetch_top_n_original_text_excerpt`。
- [ ] 将 `<nbrag_raw_excerpt>` / `<nbrag_raw_content>` 断言改为 `<nbrag_original_text_excerpt>` / `<nbrag_original_text_content>`。
- [ ] 测试名由 `test_search_and_fetch_auto_fetches_original_content` 改为能够表达“自动原文摘录”的名称。
- [ ] 增加或更新断言，验证 `0` 仍然禁用自动摘录。
- [ ] 增加或更新一个同文档多命中场景：确认参数限制的是候选 ranked hits，而合并后摘录实体数可以更少，避免未来实现或描述回退为“抓取 N 个文件”。
- [ ] 保留对 `file_path`、`doc_id`、`line_start`、`line_end` 的精确字段断言，确保下游 `nbrag_read_more_original_text()`、`nbrag_get_chunks_by_lines()` 能直接复用返回 handles。

#### 5. `tests/retrieval_quality_check/07_nbrag_search_and_fetch.py`

- [ ] 文件 docstring 从“搜索+抓原文”改为“检索 + 自动原文摘录”。
- [ ] 调用参数改为新参数名。
- [ ] 保留端口、默认上下文预算以及通过 MCP 调用的测试目的，不引入新的行为断言。

#### 6. `tests/retrieval_quality_check/retrieval_report.py`

- [ ] 调用参数改为 `fetch_top_n_original_text_excerpt`。
- [ ] case 标题/记录文本使用“自动原文摘录”或对应英文，不再把对外参数称作 raw。

#### 7. `scripts/_test_mcp_call.py`

- [ ] 更新 MCP 调用样例的参数名。
- [ ] 若展示性文本提及自动摘录，同步采用统一名称。

#### 8. `scripts/test_xml_format.py`

这是独立于本次术语改名、但必须一并处理的**陈旧验证契约**：当前它断言 `<ranked_hits>`、`<hit ...>`、`<fetched_raw>`，而现行运行时早已输出 `<nbrag_ranked_hit>` 和自动摘录实体标签。

- [ ] 先依据当前 `_contract_tool` 包装后的真实响应调整 Step 3 与 Step 4 的结构检查，不以旧计划或旧 spec 的 XML 草图为准。
- [ ] Step 3 改为验证 `<nbrag_search_and_fetch`、`<nbrag_ranked_hit>`、`<nbrag_original_text_excerpt>`，并用能解析当前 `key = value` 实体格式的方式提取 `file_path`、`doc_id`、`chunk_index`、`line_start`、`line_end`。
- [ ] Step 4 改为验证 `<nbrag_search` 与 `<nbrag_ranked_hit>`；`include_content=False` 时验证没有 `<nbrag_chunk_content>`，而不是验证旧 `<content>`。
- [ ] 不在本次顺手把所有脚本改成通用 XML parser；只修正它与当前 contract 的确定性漂移。

## 需要有意识地保持不变

- `fetch_context_chars` 参数名称、默认值和“每命中近似总字符预算”的实现。
- `match_context_chars`、grep 返回契约和 `<nbrag_match>` 下的 `<nbrag_original_text_content>`。
- `nbrag_read_more_original_text()` 当前函数名、参数、外层 `<nbrag_original_text>`、内层 `<nbrag_original_text_content>` 及其已完成的契约。
- 任何内部 raw 术语：`raw=True`、`raw_data`、`raw_content`、底层 raw cache / raw files / retrieval API。
- canonical handles：`file_path`、`doc_id`、`chunk_index`、`line_start`、`line_end`、`total_chunks` 的名称、形态和 `key = value` 表示法。
- 不修改 `query` / `bm25_query` 的语义、检索排序、BM25、rerank 或 range 扩展算法。
- 不修改历史计划、历史 spec、ADR、审计文档。它们应保留当时的设计事实；不能将其当作现行 contract。若未来需要整理历史资料，应单独立项，明确采用“追加迁移说明”还是“保留历史快照”的策略。
- 不因 Agent 调用而保留旧 MCP 参数或旧 XML 标签的兼容别名。当前目标是单一、可学习的工具 schema；双参数和双标签只会制造更多歧义。

## 实施顺序

1. 先修改 `mcp_tools.py` 的参数、标签和 follow-up guidance，确定唯一运行时 contract。
2. 紧接着修改 `server.py` 签名、Field 描述、docstring 和参数转发，使 MCP schema 与运行时实现同名。
3. 同步修改 `SKILL.md`，确保 Agent 的工具选择、证据层级和精确标签与运行时 contract 相同。
4. 更新单元契约测试，先覆盖新标签、新参数、`0` 禁用和合并语义。
5. 更新 MCP 质量脚本、报告和调用样例。
6. 修复 `scripts/test_xml_format.py` 现有的过期结构断言。
7. 搜索运行时代码、skill、tests、scripts 中的旧对外术语，确认不再有 `fetch_top_n_raw`、`nbrag_raw_excerpt`、`nbrag_raw_content`、`fetched_raw_excerpt`；内部 retrieval 实现和历史文档是明确排除项。

## 验证方案

使用项目规定的解释器：

```powershell
D:/ProgramData/miniconda3/envs/py312/python.exe
```

### 自动验证

- [ ] 运行 `tests/test_mcp_contracts.py` 的完整测试集。
- [ ] 运行更新后的 `scripts/test_xml_format.py`。
- [ ] 运行 `tests/retrieval_quality_check/07_nbrag_search_and_fetch.py`（它依赖 HTTP MCP 服务时，先按项目方式重启服务）。
- [ ] 运行项目已有 lint / typecheck 命令；实施前先从项目配置或 README 确认准确命令，不假设工具链。

### MCP 实测

改动 `nbrag` MCP 后重启 HTTP 服务：

```powershell
D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/start_http_rag_mcp.py
```

随后用实际已导入 collection 调用 `nbrag_search_and_fetch()`，确认：

- [ ] MCP tool schema 只暴露 `fetch_top_n_original_text_excerpt`，不再暴露 `fetch_top_n_raw`。
- [ ] 返回同时包含 `<nbrag_ranked_hit>` 与 `<nbrag_original_text_excerpt>`。
- [ ] 自动摘录正文为 `<nbrag_original_text_content>`。
- [ ] `<nbrag_original_text_excerpt>` 中返回的 `file_path`、`doc_id`、`line_start`、`line_end` 可以原样用于 `nbrag_read_more_original_text()` 和 `nbrag_get_chunks_by_lines()`。
- [ ] `fetch_top_n_original_text_excerpt=0` 时没有自动摘录实体。
- [ ] 多个前序命中来自同一文档且窗口重叠/相邻时，输出的自动摘录实体数少于候选命中数，且范围已合并。
- [ ] follow-up guidance 明确区分 chunk、自动原文摘录、显式原文扩展读取，且没有把自动摘录说成完整文件。

## 完成标准

1. Agent 在 MCP schema、工具说明、返回标签、workflow skill 和验证脚本中，只会看到一套自动摘录术语：`original_text_excerpt` / `original_text_content`。
2. `fetch_top_n_original_text_excerpt` 的名称和说明反映真实行为：限制候选命中，而非承诺返回 N 个完整文件或 N 个摘录。
3. 自动摘录与 `nbrag_read_more_original_text()` 的层级边界明确：前者是受预算限制的自动有限摘录，后者是显式的扩大或完整原文读取。
4. 现有 handles 不发生漂移，可直接串联到下游工具。
5. 内部 raw 实现保持不动，历史资料不被误改；过期的活动验证脚本得到修复。
