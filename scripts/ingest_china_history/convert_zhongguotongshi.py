"""
将《中国通史(上、下2册)》傅乐成.pdf 转换为结构化的 .md 文件。

用法:
    D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/ingest_china_history/convert_zhongguotongshi.py

输出:
    scripts/ingest_china_history/zhongguotongshi_chapters/ 目录下的多个 .md 文件（按篇/章拆分）
"""

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

PDF_PATH = SCRIPT_DIR / "《中国通史(上、下2册)》傅乐成.pdf"
OUT_DIR = SCRIPT_DIR / "zhongguotongshi_chapters"

import pdfplumber


def extract_all_text() -> list[tuple[int, str]]:
    """提取所有页的文本，返回 [(页码, 文本), ...]"""
    pages_text = []
    with pdfplumber.open(PDF_PATH) as pdf:
        total = len(pdf.pages)
        print(f"总页数: {total}")
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pages_text.append((i + 1, text))
            if (i + 1) % 50 == 0:
                print(f"  已提取 {i + 1}/{total} 页")
    return pages_text


def detect_chapter_breaks(pages_text: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """检测章节分界，返回 [(起始页码, "第X章 章节标题"), ...]
    
    策略：
    - 逐页检测 "第X章" 单独一行，下一行为标题
    - 同一页出现 >= 3 个章节标题的视为目录页，跳过
    - 只保留真实章节起始页
    """
    chapter_num_re = re.compile(r"^(第[一二三四五六七八九十百千\d]+[篇章编部节])$")

    # 收集每页上的所有命中：(页码, 章节号, 标题)
    page_hits: dict[int, list[tuple[str, str]]] = {}
    for page_num, text in pages_text:
        lines = text.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip().replace("\u3000", "")
            m = chapter_num_re.match(stripped)
            if not m:
                continue
            # 取下一行作为标题
            title_line = ""
            for j in range(i + 1, min(i + 4, len(lines))):
                next_line = lines[j].strip().replace("\u3000", "")
                # 跳过空行和页码行
                if not next_line or re.match(r"^\d+$", next_line):
                    continue
                title_line = next_line
                break
            page_hits.setdefault(page_num, []).append((stripped, title_line))

    # 过滤：同一页 >= 3 个章节标题 = 目录页，跳过
    # 同一页 1-2 个 = 真实章节起始页
    breaks = []
    for page_num in sorted(page_hits.keys()):
        hits = page_hits[page_num]
        if len(hits) >= 3:
            continue  # 目录页，跳过
        for chapter_num, title in hits:
            full_title = f"{chapter_num} {title}" if title else chapter_num
            breaks.append((page_num, full_title))

    return breaks


def main():
    print("=== 步骤1: 提取 PDF 文本 ===")
    pages_text = extract_all_text()

    print("\n=== 步骤2: 检测章节分界 ===")
    chapter_breaks = detect_chapter_breaks(pages_text)
    print(f"检测到 {len(chapter_breaks)} 个章节")
    for page_num, title in chapter_breaks:
        print(f"  第{page_num}页: {title[:60]}")

    print("\n=== 步骤3: 保存章节文件 ===")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 先清空旧章节文件
    for old in OUT_DIR.glob("*.md"):
        old.unlink()

    # 按章节拆分
    for i, (page_num, title) in enumerate(chapter_breaks):
        # 确定结束页：下一个章节的前一页，或最后一页
        if i + 1 < len(chapter_breaks):
            end_page = chapter_breaks[i + 1][0] - 1
        else:
            end_page = len(pages_text)

        # 收集该章节的所有文本
        safe_title = re.sub(r'[\\/*?:"<>|]', "", title)[:50]
        filename = f"第{page_num:03d}页-{safe_title}.md"

        lines = [f"# {title}\n"]
        for pn, text in pages_text:
            if pn < page_num:
                continue
            if pn > end_page:
                break
            if text.strip() and len(text.strip()) > 20:
                lines.append(f"\n## 第{pn}页\n")
                lines.append(text.strip())

        filepath = OUT_DIR / filename
        filepath.write_text("\n".join(lines), encoding="utf-8")
        chars = sum(len(t) for pn, t in pages_text if page_num <= pn <= end_page)
        print(f"  [save] {filename} ({chars} chars)")

    # 额外保存一个完整版
    print("\n=== 步骤4: 保存完整版 ===")
    full_lines = ["# 中国通史（傅乐成）全文\n"]
    for page_num, text in pages_text:
        if text.strip():
            full_lines.append(f"\n## 第{page_num}页\n")
            full_lines.append(text.strip())
    full_path = OUT_DIR.parent / "中国通史_傅乐成_全文.md"
    full_path.write_text("\n".join(full_lines), encoding="utf-8")
    total_chars = sum(len(t) for _, t in pages_text)
    print(f"  [save] 完整版: {full_path.name} ({total_chars} chars)")

    print(f"\n[done] 输出目录: {OUT_DIR}")


if __name__ == "__main__":
    main()
