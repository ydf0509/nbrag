---
name: nbrag-workflow
description: Use when the user asks a question that requires searching imported knowledge bases
---

> **注意**：本文档中的函数名是 nbrag MCP 自身的函数名。当 nbrag 被接入其他 Agent 框架时，
> 实际暴露的 function 名称可能带前缀（例如 `xxx_nbrag_search` 或 `mcp__xxx__nbrag_search`），AI 应以实际接收到的 function 名称为准。

# nbrag agentic RAG 工作流

nbrag 是一组 MCP 检索工具。你的目标不是机械调用，而是用最少轮次拿到足够证据回答。

## 决策框架（不是流程）

每一轮问自己三件事：
1. 我现在有什么信息？（用户原话、历史上下文、上一轮返回）
2. 还缺什么？（精确条文？完整上下文？文件路径？）
3. 哪个工具能最快补上？

补够了就回答。没够就继续，但继续时应该比上一轮更聚焦。

## 部分工具速查

| 你需要什么 | 工具 | 备注 |
|---|---|---|
| 列出可用知识库 | nbrag_stats | 永远是第一步 |
| 语义检索 + 自动取原文 | nbrag_search_and_fetch | 默认检索入口 |
| 精确字面匹配 | nbrag_grep | 条文号、符号名、错误码 |
| 只看 metadata 或控制检索参数 | nbrag_search | 能精细化控制更多入参 |
| 找到完整文件路径 | nbrag_find_files | 知道文件名但没路径时 |
| 查看完整原文 | nbrag_get_raw_file | 需要全文或大段上下文时 |
| 查找函数 类的定义| nbrag_find_definition|只对python源码生效|

## 关于nbrag_search_and_fetch的 query 和 bm25_query 入参

query 是给向量检索和 rerank 的主语义问句，bm25_query 是给 BM25 的词法查询。
两者职责不同，可以不同。

典型用法：
- query: 保持自然语言语义，可以基于用户原话、对话上下文或检索中发现来组织
- bm25_query: 简短的词法锚点——用户原话关键词、上下文中确认的术语、高置信的拼写变体/同义词

bm25_query 留空也没问题，BM25 此时会回退使用 query的值，nbrag内部自身本身就会使用分词再bm25检索。

## 多轮策略

每一轮都基于已有的信息更精确地提问：
- 如果第一轮返回了相关 chunk，从 chunk 里提取出现过的精确术语用于后续 grep/bm25_query
- 如果结果太泛，缩小范围：加 file_path filter、换更精确的术语
- 如果结果相关但不完整，用 get_raw_file 或 get_adjacent_chunks 扩展上下文
- 如果完全搜不到，尝试不同术语或切到 grep 验证原文里有没有这些词

## 停止条件

能回答时停止。具体来说：
- 原文证据直接回答了用户问题
- 多个来源互相印证
- 继续搜只会重复已有信息


# ai要灵活使用 nbrag 的函数和传参

这个skill用法指南不能穷举，ai要灵活发挥，使用不同的函数进行组合使用。
ai要把自己当做是 精通rag知识库用法的专家，精通向量检索召回 重排 bm25检索 这些ai rag知识，然后才懂nbrag怎么调用，才知道query怎么写， bm25_query 怎么写。