"""
示例：批量导入项目到 RAG 知识库。

用法:
    # 1. 设置 API Key
    export NBRAG_API_KEY=sk-xxx

    # 2. 运行导入
    python scripts/import_project.py
"""

import my_load_config
from nbrag.core import batch_ingest


batch_ingest(
    paths=[
        "D:/codes/funboost/funboost_all_docs_and_codes.md",
    ],
    collection_name="funboost_all_docs_and_codes",
    file_extensions=[".md",],
    max_workers = 10,
    delete_first=True,
    verbose=True,
)
