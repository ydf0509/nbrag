"""
示例：批量导入项目到 RAG 知识库。

用法:
    # 1. 设置 API Key
    export NBRAG_API_KEY=sk-xxx

    # 2. 运行导入
    python scripts/import_project.py
"""

import my_load_config
from nbrag import batch_ingest, set_collection_profile


