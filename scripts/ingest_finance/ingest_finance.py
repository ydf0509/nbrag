"""把 ingest_finance 目录下的 .md 文件批量导入 nbrag 知识库 finance_reports。

前置条件：先运行 convert_finance_pdfs.py 把 PDF 转为 .md。

用法：
    D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/ingest_finance/ingest_finance.py
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import my_load_config  # noqa: F401  加载 NBRAG_API_KEY
from nbrag import batch_ingest, set_collection_profile

MD_DIR = Path(__file__).resolve().parent
COLLECTION_NAME = "finance_reports"



md_paths = sorted(MD_DIR.glob("*.md"))
if not md_paths:
    print("没找到 .md 文件，请先运行 convert_finance_pdfs.py")
    raise FileNotFoundError("没找到 .md 文件，请先运行 convert_finance_pdfs.py")

print(f"开始导入 {len(md_paths)} 个 .md 到 nbrag collection={COLLECTION_NAME}")
batch_ingest(
    paths=[str(p) for p in md_paths],
    collection_name=COLLECTION_NAME,
    file_extensions=[".md"],
    max_workers=1,
    delete_first=True,
    verbose=True,
    sleep_interval=0.1,
)
set_collection_profile(
    COLLECTION_NAME,
    display_name="金融报告知识库",
    description="包含金融、理财或投资报告类文本，适合查询报告观点、投资主题、资产配置、市场分析等内容。",
    aliases=["金融报告", "理财", "财报", "投资", "资产配置"],
    tags=["金融", "投资", "报告"],
)
print("\n[OK] 完成")



