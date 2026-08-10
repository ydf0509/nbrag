"""
将 lc-agent 项目源码与文档导入到 nbrag 知识库。

用法:
    D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/ingest_lc_agent.py
"""

import my_load_config
from nbrag import batch_ingest, set_collection_profile


batch_ingest(
    paths=[
        r"D:\codes\lc-agent\lc_agent",
        r"D:\codes\lc-agent\frontend",
        # r"D:\codes\lc-agent\docs",
        # r"D:\codes\lc-agent\tests",
        r"D:\codes\lc-agent\README.md",
        r"D:\codes\lc-agent\AGENTS.md",
        r"D:\codes\lc-agent\FEATURES.md",
        r"D:\codes\lc-agent\pyproject.toml",
        r"D:\codes\lc-agent\alembic.ini",
    ],
    collection_name="lc-agent",
    file_extensions=[".py", ".md", ".ts", ".vue", ".js", ".json", ".yaml", ".yml", ".toml", ".ini", ".mako", ".html", ".css", ".sh", ".ps1"],
    excluded_paths=[
        r"D:\codes\lc-agent\lc_agent\web\dist",
        r"D:\codes\lc-agent\frontend\dist",
        r"D:\codes\lc-agent\frontend\node_modules",
        r"D:\codes\lc-agent\frontend\.vite",
        r"D:\codes\lc-agent\my_dir",
        r"D:\codes\lc-agent\.agents",
        r"D:\codes\lc-agent\.codegraph",
        r"D:\codes\lc-agent\.serena",
        r"D:\codes\lc-agent\.superpowers",
        r"D:\codes\lc-agent\.vscode",
    ],
    delete_first=True,
    verbose=True,
    chunk_size=1000,
    chunk_overlap=150,
    sleep_interval=0.1,
)

set_collection_profile(
    "lc-agent",
    display_name="lc-agent",
    description="lc-agent 全栈项目：Python 后端（lc_agent 包，含 core 引擎、auth、memory、permissions、MCP manager、skills、tools、SSE 流式服务）与 Vue3 + TypeScript 前端（frontend），以及 docs 设计与测试",
    aliases=["lc-agent", "lc agent", "lcagent", "本地agent", "llm-facing"],
    tags=["Python", "FastAPI", "Vue3", "TypeScript", "Agent", "SSE", "MCP", "Skills", "全栈"],
)
