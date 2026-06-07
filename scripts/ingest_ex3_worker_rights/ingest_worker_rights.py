"""
导入"打工人法律百科"知识库 — 18 部劳动/社保/税务法律法规。

涵盖：劳动法、劳动合同法、社会保险法、个人所得税法、工伤/失业/公积金、
      带薪年休假、工资支付、女职工保护、职业病防治、劳动争议仲裁等。

用法:
    cd D:/codes/nbrag
    D:/ProgramData/miniconda3/envs/py312/python.exe scripts/ingest_ex3_worker_rights/ingest_worker_rights.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import my_load_config
from nbrag.core import batch_ingest

batch_ingest(
    paths=["D:/codes/nbrag/scripts/ingest_ex3_worker_rights"],
    collection_name="worker_rights",
    file_extensions=[".md"],
    max_workers=1,
    delete_first=True,
    verbose=True,
    sleep_interval=1,
)
