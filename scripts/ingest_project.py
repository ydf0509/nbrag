"""
示例：批量导入项目到 RAG 知识库。

用法:
    # 1. 设置 API Key
    export NBRAG_API_KEY=sk-xxx

    # 2. 运行导入
    python scripts/ingest_project.py
"""

from nbrag.core import batch_ingest

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
