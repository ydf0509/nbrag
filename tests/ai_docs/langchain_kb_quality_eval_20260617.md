# LangChain 知识库检索质量评测

日期：2026-06-17

对象：`langchain_ai_codes_and_docs`

## 结论

整体表现很强，尤其适合 LangChain / LangGraph 这类“文档 + 源码 + 迁移指南”混合知识库。

优点：

- `nbrag_search_and_fetch` 很适合“怎么用”类问题，能同时拉出文档和源码证据。
- `nbrag_find_definition` 对源码符号定位非常稳，`create_agent`、`RunnableWithMessageHistory`、`trim_messages` 都能直接回完整定义。
- 完整绝对 `file_path` 过滤有效，适合把大库缩到单文件/单模块。

短板：

- 公共符号有时会带出“源码 + 相关文档”双结果，信息有点多，`max_results=1` 更稳。
- 语义搜索会把“平台迁移/发布说明”也召回来，属于正常现象，但需要 AI 自己选主证据。
- 某些问法太宽时，结果会偏向“最像的解释页”，不是最底层源码页。

## 实测片段

### 1. `create_agent` 用法

问题：`LangChain create_agent system_prompt tools response_format example usage`

结果：

- 命中 `factory.py` 的 `create_agent` 完整源码。
- 同时命中 `agents.mdx` 的文档说明和结构化输出示例。

判断：

- 适合回答“怎么构造 agent、参数有哪些、系统提示怎么配”。
- 文档和源码互相补证，质量高。

### 2. `RunnableWithMessageHistory`

问题：`RunnableWithMessageHistory session_id configurable chat history example usage`

结果：

- 命中 `history.py` 的类定义和多个示例段。
- 还命中了 `nvidia_ai_endpoints.mdx` 的实际使用示例。

判断：

- 适合回答“session_id 怎么传、history_factory_config 怎么写”。
- 这类问题最好再配合 `nbrag_find_definition`，直接拿完整类定义。

### 3. `trim_messages`

问题：`trim chat history before model token limit remove old messages example`

结果：

- 命中 `trim_messages` 源码。
- 命中短期记忆文档里的 `before_model`/`trimMessages` 示例。

判断：

- 适合回答“怎么裁剪消息历史、保留最近消息、控制 token 上限”。
- 说明这个库对记忆类问题覆盖很好。

### 4. `create_agent` vs `create_react_agent`

问题：`difference between create_agent and create_react_agent LangChain LangGraph`

结果：

- 命中 LangChain v1 迁移说明。
- 命中 LangGraph v1 的弃用说明。
- 还命中旧的 `create_react_agent` 源码。

判断：

- 适合回答升级迁移类问题。
- `nbrag` 很擅长把“新 API、旧 API、迁移表”拼到一块。

### 5. 路径过滤

问题：先搜，再按完整 `file_path` 过滤到 `history.py`

结果：

- 过滤后结果明显更干净。
- 这对源码库尤其重要，能压住无关文档噪声。

判断：

- 长路径策略是对的。
- 对 LangChain 这种超大库，先定位文件，再限制文件，是高收益操作。

## 推荐工作流

1. 先用 `nbrag_search_and_fetch` 取概念、示例、迁移说明。
2. 再用 `nbrag_find_definition` 取源码符号完整定义。
3. 需要细节时，用 `filter_file_path` 缩到单文件。
4. 公共符号尽量先用 `max_results=1`。

## 总评

`langchain_ai_codes_and_docs` 的检索质量可以直接拿来做 agent 实战，已经不是“只会找文档”的水平了。  
它更像是一个能把“官方文档、迁移说明、源码定义、示例代码”拼起来的知识库。
