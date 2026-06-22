"""
抓取《末日之太阳熄灭后》全文，保存为 .md 文件（不向量化）。

用法:
    D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/inguest_novel/scrape_doomsday.py

来源: www.readnovel.com (红袖添香)
"""

import re
import time
import sys
from pathlib import Path

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
CHAPTERS_DIR = SCRIPT_DIR / "doomsday_chapters"

CATALOG_URL = "https://www.readnovel.com/chapterlist/17821913206588004"
BASE_URL = "https://www.readnovel.com"

client = httpx.Client(timeout=30, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Referer": "https://www.readnovel.com/",
})


def fetch_catalog() -> list[tuple[str, str]]:
    """抓取目录，返回 [(标题, 章节URL), ...] 列表。"""
    print(f"[catalog] fetching {CATALOG_URL} ...")
    resp = client.get(CATALOG_URL)
    resp.raise_for_status()

    # 提取章节链接和标题
    pattern = re.compile(
        r'<a[^>]*href=["\'](/chapter/17821913206588004/\d+)["\'][^>]*>([^<]+)</a>'
    )
    matches = pattern.findall(resp.text)

    # 去重并保持顺序
    seen = set()
    chapters = []
    for url_path, title in matches:
        if url_path in seen:
            continue
        seen.add(url_path)
        chapters.append((title.strip(), url_path))

    print(f"[catalog] found {len(chapters)} chapters")
    return chapters


def fetch_chapter(url_path: str, title: str, index: int) -> str:
    """抓取单章正文，返回纯文本。"""
    full_url = BASE_URL + url_path
    for attempt in range(3):
        try:
            resp = client.get(full_url)
            if resp.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"  [{index}] HTTP 429, retry in {wait}s ...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            break
        except Exception as e:
            if attempt < 2:
                wait = 3 * (attempt + 1)
                print(f"  [{index}] error: {e}, retry in {wait}s ...")
                time.sleep(wait)
                continue
            raise

    # 提取 read-content 内的正文
    m = re.search(
        r'<div[^>]*class=["\'][^"\']*read-content[^"\']*["\'][^>]*>.*?<div[^>]*class=["\']ywskythunderfont["\'][^>]*>(.*?)</div>\s*</div>',
        resp.text,
        re.DOTALL,
    )
    if not m:
        # 降级：直接找 ywskythunderfont
        m = re.search(
            r'<div[^>]*class=["\']ywskythunderfont["\'][^>]*>(.*?)</div>',
            resp.text,
            re.DOTALL,
        )

    if not m:
        print(f"  [{index}] warning: no content found for {title}")
        return ""

    body_html = m.group(1)

    # 清理 HTML
    body = re.sub(r"<br\s*/?>", "\n", body_html)
    body = re.sub(r"<p[^>]*>", "\n", body)
    body = re.sub(r"</p>", "\n", body)
    body = re.sub(r"<[^>]+>", "", body)
    body = re.sub(r"&nbsp;", " ", body)
    body = re.sub(r"&lt;", "<", body)
    body = re.sub(r"&gt;", ">", body)
    body = re.sub(r"&amp;", "&", body)
    body = re.sub(r"[\n]{3,}", "\n\n", body)
    body = body.strip()

    return body


def main():
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    chapters = fetch_catalog()
    if not chapters:
        print("[error] no chapters found")
        sys.exit(1)

    total = len(chapters)
    fetched = 0
    skipped = 0

    for idx, (title, url_path) in enumerate(chapters, start=1):
        filename = f"第{idx:03d}章-{title.replace(' ', '_')}.md"
        filepath = CHAPTERS_DIR / filename

        if filepath.exists():
            skipped += 1
            continue

        print(f"[{idx}/{total}] {title}")
        body = fetch_chapter(url_path, title, idx)

        content = f"# {title}\n\n{body}\n"
        filepath.write_text(content, encoding="utf-8")
        fetched += 1

        # 间隔 2 秒，避免触发反爬
        if idx < total:
            time.sleep(2)

    print(f"[done] total={total}, fetched={fetched}, skipped={skipped}")


if __name__ == "__main__":
    main()
