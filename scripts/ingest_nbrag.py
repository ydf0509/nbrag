"""
将 nbrag 自身源码导入到 nbrag 知识库。

用法:
    D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/ingest_nbrag.py
"""

import my_load_config
from nbrag import batch_ingest, set_collection_profile


batch_ingest(
    paths=[
        r"D:\codes\nbrag\nbrag",
        # r"D:\codes\nbrag\tests",
        # r"D:\codes\nbrag\scripts",
        r"D:\codes\nbrag\README.md",
        r"D:\codes\nbrag\README.zh-CN.md",
    ],
    collection_name="nbrag",
    file_extensions=[".py", ".md"],
    max_workers=1,
    delete_first=True,
    verbose=True,
    chunk_size=1000,
    chunk_overlap=150,
    sleep_interval=0.1,
)

set_collection_profile(
    "nbrag",
    display_name="nbrag RAG MCP 知识库",
    description="包含 nbrag 自身源码、文档",
    aliases=["nbrag", "RAG", "MCP", "Agentic RAG", "知识库", "向量检索","bm25检索"],
    tags=["Python", "RAG", "MCP", "项目源码"],
)