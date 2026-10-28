---
name: nbrag-test-mode
description: 本项目用户询问任何知识问题时使用，AI必须先用nbrag系列MCP工具检索后再回答，答案只能来自检索结果，最后附检索心得。这是对nbrag真实检索能力的实战测试，用户早已知晓答案，只看AI检索准不准。用户要求运行tests/retrieval_quality_check质检脚本做自动化回归时，改用nbrag-retrieval-quality-check，不激活本skill。
---

# nbrag-test-mode

## Goal

本项目内用户询问任何知识时，AI进入nbrag实战测试：先检索，后回答，最后附检索心得。

前提假设：用户早就知道问题答案，提问目的是看AI实际使用nbrag MCP检索并回答，检验回答准不准、检索好不好。

强制流程只有三步，按顺序完成才算做完：

1. **先检索**：用nbrag系列MCP工具多轮检索，拿到足够知识后再动笔。
2. **再回答**：答案只能来自nbrag检索命中，逐条可对应到命中与出处。
3. **最后附检索心得**：回答末尾必须加一段当前检索心得说明。

nbrag工具的具体用法（query与bm25_query怎么写、什么场景用哪个工具、命中后如何扩读原文）以nbrag_help()返回的使用指南为准，本skill不重复叙述。

## 先检索后回答

- 首次先调`nbrag_help()`拿指南，不确定库就调`nbrag_stats()`选`collection_name`。
- 核心路径是`nbrag_retrieve()`多轮检索 + `nbrag_read_more_original_text()`围绕有用命中扩读，直到知识收齐。
- 无可靠命中时改写`query`、补`bm25_query`、换`nbrag_grep` / `nbrag_find_files` / `nbrag_find_definition`再试，不跳过检索直接答。
- 没检索到就是没检索到：如实说nbrag未命中相关内容，不用通用知识兜底编答案，无命中本身就是一次有效的召回失败信号。

## 禁止绕过nbrag读本地文件

- 获取知识只用nbrag系列MCP工具：nbrag_help、nbrag_stats、nbrag_list、nbrag_retrieve、nbrag_retrieve_no_expand、nbrag_retrieve_only_bm25、nbrag_retrieve_only_vector、nbrag_grep、nbrag_find_files、nbrag_find_definition、nbrag_get_file_chunks、nbrag_get_adjacent_chunks、nbrag_get_chunks_by_lines、nbrag_read_more_original_text。
- 不用Read/Grep/SearchCodebase/Glob/LS/RunCommand等非nbrag工具读取知识库源文件来代替检索，否则测不出nbrag真实能力。
- host暴露名可能带前缀（例如nbrag_retrieve显示为mcp__nbrag__nbrag_retrieve），调用时以当前工具列表为准。

## 回答末尾的检索心得说明

每次回答末尾必须加检索心得，至少包含：

- 本次检索与扩读是否顺畅，命中了哪些关键文件
- query和bm25_query写法效果：哪些语句/关键词是有效锚点，哪次改写明显提升了召回
- 发现的检索问题：例如预期存在的内容搜不到、反复改写仍召不回、命中与问题明显不相关
- 对nbrag检索侧的可改进建议

检索出问题如实反馈，正是本skill要收集并暴露给nbrag检索侧改进的信号。

## When to Use

本项目内用户询问任何知识时激活，例如：

- 「用nbrag查一下XXX」「nbrag搜一下XXX」「用nbrag检索XXX」「试下nbrag检索XXX」「用nbrag回答XXX」
- 没点名nbrag，但问的是知识库里的知识、用法、概念、实现细节、文档内容
- 提出一个问题，并要求先检索再回答

## When NOT to Use

以下情况不激活本skill（AI可以正常使用所有工具）：

- 只讨论nbrag的架构设计、代码实现、改进方向，没有要求实际检索回答知识
- 要求修改nbrag的代码，或询问nbrag的配置与安装
- 常规编码任务，没有知识问答成分
- 要求运行tests/retrieval_quality_check/下的质检脚本做自动化回归，此时改用nbrag-retrieval-quality-check
