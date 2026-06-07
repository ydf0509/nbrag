"""
导入婚姻家庭法相关法律文本到 marriage_law 知识库。
包含：
  - 民法典 第五编 婚姻家庭
  - 婚姻家庭编司法解释（一）—— 91条，2021年施行
  - 婚姻家庭编司法解释（二）—— 23条，2025年施行
  - 解释（二）新闻发布会背景介绍
  - 解释（二）记者问答与典型案例

用法:
    cd D:/codes/nbrag
    python scripts/ingest_ex2_marriage_law/ingest_marriage_law.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import my_load_config
from nbrag.core import batch_ingest

batch_ingest(
    paths=["D:/codes/nbrag/scripts/ingest_ex2_marriage_law"],
    collection_name="marriage_law",
    file_extensions=[".md"],
    max_workers=1,
    delete_first=True,
    verbose=True,
    sleep_interval=1,
)
