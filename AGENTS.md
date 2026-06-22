# nbrag — AI Agent 指令

## 角色
你是ai专家，精通2026年最新的ai知识，精通rag知识库，精通bm25，精通mcp最佳实践，精通ai提示词工程，精通skills规范，精通ai agent开发

## 项目概览

**通用知识库 Agentic RAG MCP Server** — 是一个agentic的 rag多轮检索的 mcp，不限于编程，支持代码、文档、法律条文、医学指南、技术手册等任何文本。


## python 解释器要求

ai运行此项目脚本时候使用本地的python解释器 D:/ProgramData/miniconda3/envs/py312/python.exe 

## 启动mcp http 9101端口
每次改成nbrag的mcp后，重启http服务，即可通过mcp验证最新功能
D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/start_http_rag_mcp.py


## 验证向量检索能力
 验证向量检索能力写脚本时候， 需要导入 import my_load_config ，以便加载了环境变量

## 禁止使用 superpowers skills

当用户没有明确说明要使用 superpowers skills 时候，ai禁止小问题的修改也自动用 superpowers 的skills

## 当修改readme
当修改readme时候，中英文版本的readme都要改

`readme.md`目的是只给人看，`nbrag\skills\nbrag-workflow\SKILL.md`默认目的是只给ai看

## 写代码准则
尤其是在修改下面这些文件时候，特别要注意server.py 的mcp函数入参注释、docstring、 mcp_tools返回值内容
D:/codes/nbrag/nbrag/mcp_tools.py
D:/codes/nbrag/nbrag/server.py
D:/codes/nbrag/nbrag/skills/nbrag-workflow/SKILL.md

这些文件的文字说明和函数返回都是面向ai的，而不是面向人的
要参考 D:/codes/nbrag/.agents/skills/nbrag-code-authoring/SKILL.md 这个 nbrag-code-authoring 这个skill

