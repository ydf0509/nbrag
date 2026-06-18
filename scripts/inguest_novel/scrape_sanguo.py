"""
抓取《三国演义》全文，保存为 .md 文件（不向量化）。

用法:
    D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/inguest_novel/scrape_sanguo.py

来源: m.shangshiwen.com (古诗文网)
章节 URL 规律: bookchapter_9921 ~ bookchapter_10040 (120回)
"""

import re
import time
import sys
from pathlib import Path

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
CHAPTERS_DIR = SCRIPT_DIR / "sanguo_chapters"

BASE_URL = "http://m.shangshiwen.com"
START_ID = 9921

client = httpx.Client(timeout=30, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})


def fetch_chapter(chapter_id: int, index: int) -> tuple[str, str]:
    """抓取单回，返回 (标题, 正文)。"""
    url = f"{BASE_URL}/bookchapter_{chapter_id}.html"
    resp = client.get(url)
    resp.raise_for_status()

    h2_match = re.search(r"<h2>(.+?)</h2>", resp.text, re.DOTALL)
    raw_title = h2_match.group(1).strip() if h2_match else f"第{index}回"
    title = raw_title.replace("三国演义·", "").strip()

    con2_match = re.search(r'<div id="con2"[^>]*>(.*?)</div>', resp.text, re.DOTALL)
    if not con2_match:
        return title, ""
    body_html = con2_match.group(1)

    body = re.sub(r"<br\s*/?>", "\n", body_html)
    body = re.sub(r"</p>\s*<p[^>]*>", "\n\n", body)
    body = re.sub(r"<[^>]+>", "", body)
    body = re.sub(r"&nbsp;", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = body.strip()

    return title, body


def main():
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    for i in range(120):
        index = i + 1
        chapter_id = START_ID + i

        existing = list(CHAPTERS_DIR.glob(f"第{index:03d}回-*.md"))
        if existing:
            print(f"  [skip] 第{index:03d}回 (cached)")
            continue

        try:
            title, body = fetch_chapter(chapter_id, index)
            if len(body) < 100:
                print(f"  [warn] 第{index:03d}回: too short ({len(body)} chars)")
                continue
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
            filename = f"第{index:03d}回-{safe_title}.md"
            filepath = CHAPTERS_DIR / filename
            filepath.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
            print(f"  [saved] {filename}  ({len(body)} chars)")
        except Exception as e:
            print(f"  [error] 第{index:03d}回 (id={chapter_id}): {e}")
            continue

        time.sleep(0.5)

    total = len(list(CHAPTERS_DIR.glob("*.md")))
    print(f"\n[done] {total} chapters in {CHAPTERS_DIR}")


if __name__ == "__main__":
    main()
