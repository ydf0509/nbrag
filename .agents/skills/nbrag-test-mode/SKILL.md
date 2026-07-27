---
name: nbrag-test-mode
description: "When user explicitly requests to query/retrieve knowledge using nbrag, this is a test of nbrag's real retrieval capability—AI MUST ONLY use nbrag MCP tools (nbrag_search_*, nbrag_find_*, nbrag_read_more_*, etc.) and NO other tools like Read/Grep/SearchCodebase/Glob/LS/RunCommand."
---

# nbrag-test-mode

## Goal

当用户明确要求「用 nbrag 检索/查一下/搜一下」某些知识时，这是在对 nbrag 的检索能力做**实战测试**。

AI **绝对不能**绕过 nbrag 去读用户本地文件，必须全程只走 nbrag MCP 工具链，让用户看到 nbrag 的真实检索效果。

---

## When to Use

本 skill **只在以下情况强制激活**：

- 用户说「用 nbrag 查一下 XXX」
- 用户说「nbrag 搜一下 XXX」
- 用户说「用 nbrag 检索 XXX」
- 用户说「试下 nbrag 检索 XXX」
- 用户说「用 nbrag 回答 XXX」
- 用户提出一个问题，并要求先用 nbrag 来检索

一句话：**用户明确点出要用 nbrag 来检索时**。

---

## When NOT to Use

以下情况**不激活**本 skill（AI 可以正常使用所有工具）：

- 用户只是讨论 nbrag 的架构设计、代码实现、改进方向，没有要求实际检索
- 用户要求修改 nbrag 的代码
- 用户问 nbrag 的配置或安装
- 用户要求常规的编码任务，没有提及 nbrag 检索
