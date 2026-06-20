"""
将已抓取的《三国演义》章节向量化到 nbrag 知识库（不抓取）。

用法:
    set NBRAG_API_KEY=sk-xxx
    D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/inguest_novel/ingest_sanguo.py

前提: 先运行 scrape_sanguo.py 抓取章节到 sanguo_chapters/
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import my_load_config  # noqa: F401

from nbrag import batch_ingest, set_collection_profile

SCRIPT_DIR = Path(__file__).resolve().parent
CHAPTERS_DIR = SCRIPT_DIR / "sanguo_chapters"
COLLECTION_NAME = "sanguo"


def main():
    if not any(CHAPTERS_DIR.glob("*.md")):
        print(f"[error] No .md files in {CHAPTERS_DIR}. Run scrape_sanguo.py first.")
        sys.exit(1)

    print(f"[ingest] importing {CHAPTERS_DIR} to collection '{COLLECTION_NAME}' ...")
    batch_ingest(
        paths=[str(CHAPTERS_DIR)],
        collection_name=COLLECTION_NAME,
        file_extensions=[".md"],
        chunk_size=1000,
        chunk_overlap=150,
        max_workers=1,
        delete_first=True,
        verbose=True,
        sleep_interval=0.1,
    )
    set_collection_profile(
        COLLECTION_NAME,
        display_name="三国演义知识库",
        description="包含《三国演义》章节正文，适合查询刘备、关羽、张飞、曹操、诸葛亮、孙权等人物与经典情节。",
        aliases=["三国", "三国演义", "罗贯中", "刘备", "关羽", "张飞", "曹操", "诸葛亮", "孙权"],
        tags=["古典小说", "文学", "人物关系"],
    )
    print(f"[done] collection '{COLLECTION_NAME}' ready")


if __name__ == "__main__":
    main()
