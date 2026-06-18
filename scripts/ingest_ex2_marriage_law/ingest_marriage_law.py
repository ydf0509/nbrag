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
from nbrag import batch_ingest, set_collection_profile

batch_ingest(
    paths=["D:/codes/nbrag/scripts/ingest_ex2_marriage_law"],
    collection_name="marriage_law",
    file_extensions=[".md"],
    max_workers=1,
    delete_first=True,
    verbose=True,
    sleep_interval=1,
)

set_collection_profile(
    "marriage_law",
    display_name="婚姻家庭法知识库",
    description="包含婚姻家庭相关法律和司法解释文本，适合查询离婚、夫妻共同财产、子女抚养、婚姻家庭编解释等问题。",
    aliases=["婚姻法", "婚姻家庭法", "民法典婚姻家庭编", "夫妻共同财产", "离婚", "抚养"],
    tags=["法律", "婚姻家庭", "司法解释"],
)
