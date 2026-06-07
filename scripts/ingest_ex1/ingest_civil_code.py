"""
导入《中华人民共和国民法典》全文到 civil_code 知识库。
7 个分编 + 1 个全文，约 224K 字符。

用法:
    cd D:/codes/nbrag
    python scripts/ingest_ex1/ingest_civil_code.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import my_load_config
from nbrag.core import batch_ingest

batch_ingest(
    paths=["D:/codes/nbrag/scripts/ingest_ex1"],
    collection_name="civil_code",
    file_extensions=[".md"],
    max_workers=1,
    delete_first=True,
    verbose=True,
    sleep_interval=1,
)
