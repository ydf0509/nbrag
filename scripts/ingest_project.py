"""
示例：批量导入项目到 RAG 知识库。

用法:
    # 1. 设置 API Key
    export NBRAG_API_KEY=sk-xxx

    # 2. 运行导入
    python scripts/ingest_project.py
"""

from nbrag import batch_ingest, set_collection_profile

batch_ingest(
    paths=[
        # 替换为你要导入的项目路径
        # "D:/codes/your_project/src",
        # "D:/codes/your_project/docs",
    ],
    collection_name="your_project",
    delete_first=True,
    verbose=True,
)

set_collection_profile(
    "your_project",
    display_name="你的项目知识库",
    description="替换为这个 collection 覆盖的项目、文档、业务范围，以及 AI 什么时候应该选择它。",
    aliases=["替换为项目名", "替换为业务名", "替换为常见简称"],
    tags=["项目", "文档"],
)
