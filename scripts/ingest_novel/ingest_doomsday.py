"""
将已抓取的《末日之太阳熄灭后》章节向量化到 nbrag 知识库（不抓取）。

用法:
    D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/inguest_novel/ingest_doomsday.py

前提: 先运行 scrape_doomsday.py 抓取章节到 doomsday_chapters/
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import my_load_config  # noqa: F401

from nbrag import batch_ingest

SCRIPT_DIR = Path(__file__).resolve().parent
CHAPTERS_DIR = SCRIPT_DIR / "doomsday_chapters"
COLLECTION_NAME = "doomsday_sun"


def main():
    if not any(CHAPTERS_DIR.glob("*.md")):
        print(f"[error] No .md files in {CHAPTERS_DIR}. Run scrape_doomsday.py first.")
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
    print(f"[done] collection '{COLLECTION_NAME}' ready")


if __name__ == "__main__":
    main()
