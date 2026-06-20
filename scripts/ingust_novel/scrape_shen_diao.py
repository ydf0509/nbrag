"""
抓取《穿越神雕，从爱上黄蓉开始》全文，保存为 .md 文件（不向量化）。

用法:
    D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/inguest_novel/scrape_shen_diao.py

来源: m.zongheng.com (纵横中文网)
"""

import re
import time
import sys
from pathlib import Path

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
CHAPTERS_DIR = SCRIPT_DIR / "shen_diao_chapters"

CATALOG_URL = "https://m.zongheng.com/chapter/list/1519240"
CHAPTER_LINK_RE = re.compile(r"/chapter/1519240/\d+")

client = httpx.Client(timeout=30, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})


def fetch_catalog() -> list[str]:
    """从目录页提取所有章节链接。"""
    print(f"[fetch] catalog: {CATALOG_URL}")
    resp = client.get(CATALOG_URL)
    resp.raise_for_status()
    links = CHAPTER_LINK_RE.findall(resp.text)
    seen = set()
    unique = []
    for link in links:
        if link not in seen:
            seen.add(link)
            unique.append(link)
    print(f"[fetch] found {len(unique)} chapters")
    return unique


def fetch_chapter(chapter_url: str, index: int) -> tuple[str, str]:
    """抓取单章，返回 (标题, 正文)。失败时重试最多 3 次。"""
    full_url = "https://m.zongheng.com" + chapter_url
    for attempt in range(3):
        try:
            resp = client.get(full_url, headers={
                "Referer": "https://m.zongheng.com/chapter/list/1519240",
                "Accept": "text/html,application/xhtml+xml",
            })
            if resp.status_code == 405:
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                return "", f"HTTP 405 after 3 retries"
            resp.raise_for_status()
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            raise

    title_match = re.search(r"<title>(.+?)</title>", resp.text, re.DOTALL)
    raw_title = title_match.group(1).strip() if title_match else f"第{index}章"
    title = raw_title.split("_")[0].strip()

    article_match = re.search(r"<article[^>]*>(.*?)</article>", resp.text, re.DOTALL)
    if article_match:
        body = article_match.group(1)
    else:
        body = resp.text

    body = re.sub(r"<br\s*/?>", "\n", body)
    body = re.sub(r"<p[^>]*>", "\n", body)
    body = re.sub(r"</p>", "\n", body)
    body = re.sub(r"<[^>]+>", "", body)
    body = re.sub(r"&nbsp;", " ", body)
    body = re.sub(r"&lt;", "<", body)
    body = re.sub(r"&gt;", ">", body)
    body = re.sub(r"&amp;", "&", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = body.strip()

    return title, body


def main():
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    chapter_links = fetch_catalog()

    for i, link in enumerate(chapter_links, start=1):
        existing = list(CHAPTERS_DIR.glob(f"第{i:03d}章-*.md"))
        if existing:
            print(f"  [skip] 第{i:03d}章 (cached)")
            continue

        try:
            title, body = fetch_chapter(link, i)
            if len(body) < 100:
                print(f"  [warn] 第{i:03d}章: too short ({len(body)} chars)")
                continue
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
            filename = f"第{i:03d}章-{safe_title}.md"
            filepath = CHAPTERS_DIR / filename
            filepath.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
            print(f"  [saved] {filename}  ({len(body)} chars)")
        except Exception as e:
            print(f"  [error] 第{i:03d}章: {e}")
            continue

        time.sleep(0.5)

    total = len(list(CHAPTERS_DIR.glob("*.md")))
    print(f"\n[done] {total} chapters in {CHAPTERS_DIR}")


if __name__ == "__main__":
    main()
