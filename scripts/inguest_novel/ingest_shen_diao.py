"""
将已抓取的《穿越神雕，从爱上黄蓉开始》章节向量化到 nbrag 知识库（不抓取）。

用法:
    set NBRAG_API_KEY=sk-xxx
    D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/inguest_novel/ingest_shen_diao.py

前提: 先运行 scrape_shen_diao.py 抓取章节到 shen_diao_chapters/
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import my_load_config  # noqa: F401

from nbrag import batch_ingest, set_collection_profile

SCRIPT_DIR = Path(__file__).resolve().parent
CHAPTERS_DIR = SCRIPT_DIR / "shen_diao_chapters"
COLLECTION_NAME = "shen_diao_huangrong"


def main():
    if not any(CHAPTERS_DIR.glob("*.md")):
        print(f"[error] No .md files in {CHAPTERS_DIR}. Run scrape_shen_diao.py first.")
        sys.exit(1)

    print(f"[ingest] importing {CHAPTERS_DIR} to collection '{COLLECTION_NAME}' ...")
    batch_ingest(
        paths=[str(CHAPTERS_DIR)],
        collection_name=COLLECTION_NAME,
        file_extensions=[".md"],
        chunk_size=1500,
        chunk_overlap=300,
        max_workers=1,
        delete_first=True,
        verbose=True,
        sleep_interval=0.1,
    )
    set_collection_profile(
        COLLECTION_NAME,
        display_name="神雕同人小说知识库",
        description="包含《穿越神雕，从爱上黄蓉开始》章节正文，适合查询黄蓉、郭靖、杨过、小龙女等人物和剧情。",
        aliases=["神雕", "黄蓉", "郭靖", "杨过", "小龙女", "神雕同人"],
        tags=["小说", "同人", "剧情"],
    )
    print(f"[done] collection '{COLLECTION_NAME}' ready")


if __name__ == "__main__":
    main()
