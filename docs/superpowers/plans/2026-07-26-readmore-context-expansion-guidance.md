# `nbrag_read_more_original_text` 上下文扩展指引改造计划

> **历史接口快照**
>
> 本计划中的 `nbrag_search` 和 `nbrag_search_and_fetch` 分别是旧 MCP 名称，当前映射为 `nbrag_retrieve_no_expand` 和 `nbrag_retrieve`；请以当前 `nbrag/server.py` 暴露的工具 schema 为准。

## 目标

将 `nbrag_read_more_original_text` 的 AI 使用契约统一为“有用 chunk 的主动扩读”：

1. Agent 从检索结果判断某个 chunk 对回答有帮助时，应使用该实体返回的真实 `file_path`、`line_start`、`line_end` 调用 `nbrag_read_more_original_text`，不能仅依赖 chunk 或自动摘录作答。
2. 默认阅读窗以命中 chunk 的**开始行**为锚点：
   - `read_start = max(1, chunk.line_start - 200)`；
   - `read_end = chunk.line_start + 400`；
   - 调用参数为 `line_start=read_start`、`line_end=read_end`。
3. 该默认窗覆盖命中位置前约 200 行、后约 400 行；文件开头会因 `max(1, ...)` 而缩短，实际行数可能少于 600 行。
4. 如果首次扩读后仍缺少回答所需的上下文，就根据缺失内容相对于当前阅读窗的位置，继续扩大读取范围。
5. 保留“只有真正需要整个文件时才省略行边界”的现有语义。

本次只改 AI-facing 的工具描述、工具返回引导和 workflow skill；不改 `nbrag_read_more_original_text()` 的参数、返回 handles、原文读取实现、chunking 或自动摘录算法。

## 设计原则

### 正向触发，而非负向限制

核心表达应是：**若检索到的 chunk 对当前回答有帮助，就主动扩读该 chunk 对应的 stored original text。**

不要把策略写成“不要对每个命中都扩读”之类的负向约束。是否有用由 Agent 基于当前问题与命中证据判断；一旦判定有用，扩读是默认后续动作。

### 锚点和字段契约

- 只复制结果实体实际返回的完整绝对路径 `file_path`，不得猜测、拼接或改用 basename。
- 命中 chunk 的锚点为 `line_start`，而不是 `chunk_index`，也不以 `line_end` 作为默认窗口的中心。
- `line_end` 是 inclusive；建议显式写出 `line_end = chunk.line_start + 400`，避免把“约 600 行”误读为 `line_start + 600`。
- `collection_name` 沿用当前检索所使用的集合名。
- `doc_id`、`chunk_index` 仍用于 chunk 工具，不应伪装成 `nbrag_read_more_original_text` 的入参。

### 原文与 chunk 视图的边界

- `nbrag_read_more_original_text` 返回的是入库时保存的、无 chunk overlap 的 original-text snapshot，不是实时文件系统读取。
- `nbrag_get_adjacent_chunks` 和 `nbrag_get_chunks_by_lines` 仍是需要 chunk boundary、scope 或 chunk 结构时的补充路径；它们不替代有用 chunk 的原文扩读。
- `search_and_fetch` 的自动 original-text excerpt 受 `fetch_context_chars` 限制，不能视作完整上下文。

## 修改范围

### 1. `nbrag/server.py`

#### 位置

- `nbrag_search()` 的 follow-up tools 段落，约第 147–154 行。
- `nbrag_search_and_fetch()` 的 follow-up tools 与中文后续引导，约第 260–274 行。
- `nbrag_read_more_original_text()` 的 `line_start` / `line_end` Field 描述和 docstring，约第 359–379 行。

#### 修改内容

- [ ] 将两个 search 工具里“500+ 行”或“默认 `line_end = line_start + 500`”的泛化描述，改为命中 chunk 的具体默认调用公式：

  ```text
  line_start = max(1, returned_chunk.line_start - 200)
  line_end = returned_chunk.line_start + 400
  ```

- [ ] 说明 `line_end` 为包含边界，且默认阅读窗围绕命中 chunk 的开始位置向前约 200 行、向后约 400 行。
- [ ] 在 `nbrag_read_more_original_text()` 的 `line_start` 参数描述中，说明它通常应取命中 chunk 的 `line_start - 200`，并在必要时限制为 1。
- [ ] 在 `line_end` 参数描述中，说明它通常应取**原始命中 chunk**的 `line_start + 400`；不要错误写成“传入后的 `line_start + 400`”，否则当 `line_start` 已经前移 200 行时窗口会只覆盖到命中点后 200 行。
- [ ] 用正向文字强化调用条件：当 chunk 对回答有帮助时，复制该 chunk 返回的 `file_path` 和行号，立即扩读其周边 original text；不能只根据 chunk / auto-fetched excerpt 形成最终结论。
- [ ] 说明：如果首次扩读后仍缺少回答所需的上下文，就根据缺失内容相对于当前阅读窗的位置，继续扩大读取范围。
- [ ] 保留省略两个 bounds 时读取完整 stored file 的能力；明确它只适用于确实需要整份文件的情况。

#### 不修改

- [ ] 不改函数签名：`file_path`、`collection_name`、`line_start`、`line_end`。
- [ ] 不在 server 层添加自动计算或隐式参数变换；该公式是给 Agent 的明确调用策略。
- [ ] 不改 XML 返回标签和 handles：`file_path`、`doc_id`、`total_lines`、`line_start`、`line_end`。

### 2. `nbrag/mcp_tools.py`

#### 位置

- `_search_and_fetch_follow_up_guidance()`，约第 367–381 行。

#### 修改内容

- [ ] 更新 `file_path -> nbrag_read_more_original_text(...)` 的 expansion route，明确使用命中 `<nbrag_ranked_hit>` 的 `line_start` 计算默认窗口：

  ```text
  line_start = max(1, hit.line_start - 200)
  line_end = hit.line_start + 400
  ```

- [ ] 清楚区分“源命中行号 `hit.line_start`”和调用参数 `line_start`，以免 Agent 将 `line_end` 错算为前移后的 `line_start + 400`。
- [ ] 用输出契约中的真实字段名表达：`file_path`、`line_start`、`line_end`；不要引入 `chunk_start`、`read_start` 等不存在的 returned handle。公式中的临时变量仅作解释，调用仍使用真实参数名。
- [ ] 将当前“只要范围外依赖就选择扩展路径”的描述补充为：对回答有帮助的 chunk 应优先走 original-text 扩读；自动摘录和 chunk 都只是有边界的证据片段。
- [ ] 在中文强引导中替换“超大范围 / 500+ 行”的笼统说法，写成前 200 + 后 400 的可执行策略，并加入“如果首次扩读后仍缺少回答所需的上下文，就根据缺失内容相对于当前阅读窗的位置，继续扩大读取范围”。
- [ ] 保持 chunk tools 的路由边界：需要相邻 chunk 结构才用 `doc_id + chunk_index`；需要覆盖已知行范围的 chunk 结构才用 `doc_id + line_start + line_end`。

#### 不修改

- [ ] 不改 `_search_and_fetch_follow_up_guidance()` 的 XML 根标签 `nbrag_follow_up`。
- [ ] 不改 search/search-and-fetch 结果实体和自动 original-text excerpt 的结构。
- [ ] 不改 `nbrag_read_more_original_text()` 的底层行号清洗、文件定位或读取逻辑。

### 3. `nbrag/skills/nbrag-workflow/SKILL.md`

#### 位置

- 开头的常用工具与组合拳说明，约第 15–22 行。
- `chunk vs original text — 三层 evidence`，约第 114–139 行。
- `何时用 nbrag_read_more_original_text()`，约第 132–139 行。
- `复用 returned fields` 与 `file_path` 的后续调用指引，约第 177–192 行。
- Python definition follow-up 的原文扩读示例，约第 170–173 行。

#### 修改内容

- [ ] 在“三层 evidence”后增加标准调用模板：从有用 `<nbrag_ranked_hit>` 的真实字段取值，按 `max(1, line_start - 200)` 到 `line_start + 400` 读取。
- [ ] 把“chunk 必须扩展”的语言调整为更精确的策略：**有用 chunk 必须扩展**；不要求机械处理所有 hit，但避免加入“不要扩读每一个命中”的禁止性规则。
- [ ] 将 `line_start + 500` 的旧策略替换为前 200 / 后 400 的锚定策略，并解释实际窗口在文件开头可能小于 600 行。
- [ ] 增加通用的“首次扩读后继续扩大”决策指引：如果首次扩读后仍缺少回答所需的上下文，就根据缺失内容相对于当前阅读窗的位置，继续扩大读取范围；不枚举或限定知识领域。
- [ ] 在 `file_path` 小节中加入完整示例，展示 `file_path` 和该 hit 的 `line_start` 如何共同用于 readmore；仍强调 file_path 必须来自返回结果且为完整绝对路径。
- [ ] 对 grep / find_definition 等没有 `chunk_index` 的结果维持原有边界：它们可基于自身返回的 `file_path`、`line_start`、`line_end` 扩读，但“前 200、后 400”的标准锚点首先针对检索命中的 chunk。对于非 chunk 命中，应按其返回范围和问题需要选择扩大范围，不能伪造 chunk metadata。
- [ ] 保持工具表中 raw/original-text 与 chunk tool 的职责区分，确保 workflow 不把 adjacent chunks 描述成 readmore 的等价替代。

#### 不修改

- [ ] 不将 SKILL 改成固定的全工具调用仪式；它只给出“命中有用时的扩读策略”和真实路由边界。
- [ ] 不改 semantic / lexical、`query` / `bm25_query`、Python definition lookup 等无关策略。

## 一致性矩阵

| Surface | 必须表达 | 不应表达 |
|---|---|---|
| `server.py` 参数与 docstring | 命中 chunk 开始行前 200、后 400；有用 chunk 主动扩读；可继续扩大；完整文件读取条件 | 底层自动扩读；不存在的返回字段；把 chunk_index 作为 readmore 入参 |
| `server.py` search docstring | search 命中后使用 `file_path` + 行号进入原文扩读 | 仅说“500+ 行”而没有锚点公式 |
| `mcp_tools.py` runtime guidance | 返回 handles 的直接复用、明确公式、chunk/auto excerpt 不完整 | 与 server/skill 不一致的默认行数或禁止性懒惰约束 |
| `SKILL.md` workflow | 判断 chunk 有用后扩读、首次不足继续扩大、raw/chunk 边界 | 要求对每个 hit 无差别调用；虚构 handles |

## 验证计划

### 静态一致性检查

- [ ] 搜索所有 AI-facing 文案中的 `line_start + 500`、`500+ 行` 与“前后超大范围”，确保 readmore 的默认策略全部统一为“源 chunk 开始行前 200、后 400”。
- [ ] 搜索 `nbrag_read_more_original_text` 的所有直接说明，确认没有一个 surface 将 `line_end` 错写成“前移后调用参数的 `line_start + 400`”。
- [ ] 检查每处都只使用真实字段：`file_path`、`doc_id`、`chunk_index`、`line_start`、`line_end`。
- [ ] 检查 search docstring、runtime follow-up guidance 与 SKILL 的“有用 chunk”触发条件措辞一致。
- [ ] 检查原文快照、自动摘录和 chunk view 的边界未被混淆。

### MCP 回归验证

- [ ] 用项目指定的 Python 解释器启动或重启 HTTP MCP 服务。
- [ ] 调用 `nbrag_help()`，确认返回的 runtime guidance 和嵌入的 workflow 文本都出现前 200 / 后 400 策略。
- [ ] 调用 `nbrag_search_and_fetch()`，从一个 `<nbrag_ranked_hit>` 记录其 `file_path` 与源 `line_start`。
- [ ] 使用 `line_start=max(1, hit.line_start - 200)`、`line_end=hit.line_start + 400` 调用 `nbrag_read_more_original_text()`，确认响应保留既有 `file_path`、`doc_id`、`total_lines`、`line_start`、`line_end` handles，且返回范围符合文件边界裁剪规则。
- [ ] 对需要更远上下文的样例再次调用 readmore 并扩大范围，确认工具支持多轮扩读，且不会把前一次窗口误当作完整文件。
- [ ] 运行仓库已存在的与 MCP contract / readmore 直接相关测试；若项目没有对应测试命令，至少执行与改动文件相关的 import/compile 检查。

## 完成标准

1. 三个 AI-facing surface 对同一策略给出完全一致的公式：源命中 chunk 的 `line_start` 前 200 行、后 400 行。
2. Agent 能看懂应复用哪一个 result entity 的哪些真实字段，并能正确处理 `line_start <= 200` 的文件开头边界。
3. 策略明确鼓励对有用 chunk 扩读，且允许在证据仍不足时继续扩大，而不是把 Agent 限制为一次短读或固定一轮。
4. 工具参数、返回 XML 契约、内部原文读取行为、README 和无关检索逻辑均不发生改动。
