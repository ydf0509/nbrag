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
        "D:/codes/funboost/funboost",
        "D:/codes/funboost/test_frame",
        "D:/codes/funboost/tests",
        "D:/codes/funboost_docs/source/articles/c0.md",
        "D:/codes/funboost_docs/source/articles/c1.md",
        "D:/codes/funboost_docs/source/articles/c2.md",
        "D:/codes/funboost_docs/source/articles/c3.md",
        "D:/codes/funboost_docs/source/articles/c4.md",
        "D:/codes/funboost_docs/source/articles/c4b.md",
        "D:/codes/funboost_docs/source/articles/c6.md",
        "D:/codes/funboost_docs/source/articles/c7.md",
        "D:/codes/funboost_docs/source/articles/c8.md",
        "D:/codes/funboost_docs/source/articles/c9.md",
        "D:/codes/funboost_docs/source/articles/c10.md",
        "D:/codes/funboost_docs/source/articles/c11.md",
        "D:/codes/funboost_docs/source/articles/c12.md",
        "D:/codes/funboost_docs/source/articles/c13.md",
        "D:/codes/funboost_docs/source/articles/c14.md",
        "D:/codes/funboost_docs/source/articles/c15.md",
        "D:/codes/funboost_docs/source/articles/c20.md",
    ],
    collection_name="funboost",
    file_extensions=[".py", ".md",".html"],
    max_workers = 1,
    delete_first=True,
    verbose=True,
    sleep_interval=1,
)
