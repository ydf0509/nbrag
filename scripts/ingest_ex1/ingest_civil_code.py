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
from nbrag import batch_ingest, set_collection_profile

batch_ingest(
    paths=["D:/codes/nbrag/scripts/ingest_ex1"],
    collection_name="civil_code",
    file_extensions=[".md"],
    max_workers=1,
    delete_first=True,
    verbose=True,
    sleep_interval=1,
)

set_collection_profile(
    "civil_code",
    display_name="民法典知识库",
    description="包含《中华人民共和国民法典》全文及各分编章节，适合查询民事法律条文、合同、物权、人格权、婚姻家庭、继承、侵权责任等问题。",
    aliases=["民法典", "中华人民共和国民法典", "合同编", "物权编", "人格权编", "婚姻家庭编", "继承编", "侵权责任编"],
    tags=["法律", "民法", "法规"],
)
