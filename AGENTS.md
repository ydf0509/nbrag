# nbrag — AI Agent 指令

## 项目概览

**通用知识库 Agentic RAG MCP Server** — 不限于编程，支持代码、文档、法律条文、医学指南、技术手册等任何文本。


## python 解释器要求

ai运行此项目脚本时候使用本地的python解释器 D:/ProgramData/miniconda3/envs/py312/python.exe 

## 启动mcp http 9101端口
每次改成nbrag的mcp后，重启http服务，即可通过mcp验证最新功能
D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/start_http_rag_mcp.py


## 验证向量检索能力
 验证向量检索能力写脚本时候， 需要导入 import my_load_config ，以便加载了环境变量

## 禁止使用 superpowers skills

当用户没有明确说明要使用 superpowers skills 时候，ai禁止杀鸡用牛刀自动用 superpowers 的skills

## 当修改readme
当修改readme时候，中英文版本的readme都要改

`readme.md`目的是只给人看，`nbrag\skills\nbrag-workflow\SKILL.md`默认目的是只给ai看