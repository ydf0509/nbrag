"""
将《中国通史(上、下2册)》傅乐成 向量化到 nbrag 知识库。

用法:
    # 先运行转换脚本生成 .md 文件
    D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/ingest_china_history/convert_zhongguotongshi.py
    
    # 再运行本脚本入库
    D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/ingest_china_history/ingest_zhongguotongshi.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import my_load_config  # noqa: F401

from nbrag import batch_ingest, set_collection_profile

SCRIPT_DIR = Path(__file__).resolve().parent
CHAPTERS_DIR = SCRIPT_DIR / "zhongguotongshi_chapters"
COLLECTION_NAME = "china_history_tongshi"


def main():
    if not CHAPTERS_DIR.exists() or not any(CHAPTERS_DIR.glob("*.md")):
        print(f"[error] No .md files in {CHAPTERS_DIR}. Run convert_zhongguotongshi.py first.")
        sys.exit(1)

    md_count = len(list(CHAPTERS_DIR.glob("*.md")))
    print(f"[ingest] importing {CHAPTERS_DIR} ({md_count} files) to collection '{COLLECTION_NAME}' ...")

    batch_ingest(
        paths=[str(CHAPTERS_DIR)],
        collection_name=COLLECTION_NAME,
        file_extensions=[".md"],
        chunk_size=2000,
        chunk_overlap=200,
        max_workers=4,
        delete_first=True,
        verbose=True,
        sleep_interval=0.1,
    )

    set_collection_profile(
        COLLECTION_NAME,
        display_name="中国通史知识库",
        description="包含傅乐成《中国通史（上下册）》全文，覆盖从远古到近代的中国历史，适合查询历代政治、经济、文化、制度、人物、事件等。",
        aliases=["中国通史", "傅乐成", "中国历史", "通史"],
        tags=["历史", "中国", "通史"],
    )

    print(f"[done] collection '{COLLECTION_NAME}' ready")



main()
