"""把 ingest_finance 目录下的 PDF 转成 .md 文本。

用法：
    D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/ingest_finance/convert_finance_pdfs.py
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pdfplumber

PDF_DIR = Path(__file__).resolve().parent


def pdf_to_markdown(pdf_path: Path, md_path: Path) -> int:
    """把 PDF 转成 .md，返回总页数。"""
    lines = [f"# {pdf_path.stem}\n", f"> Source: {pdf_path.name}\n"]
    with pdfplumber.open(pdf_path) as pdf:
        n_pages = len(pdf.pages)
        for i, page in enumerate(pdf.pages, 1):
            lines.append(f"\n## Page {i}\n")
            text = page.extract_text() or ""
            if text.strip():
                lines.append(text.strip())
                lines.append("")
            for tbl_idx, tbl in enumerate(page.extract_tables() or []):
                if not tbl:
                    continue
                lines.append(f"\n### Page {i} Table {tbl_idx + 1}\n")
                for row in tbl:
                    cells = [(c or "").strip().replace("\n", " ") for c in row]
                    lines.append("| " + " | ".join(cells) + " |")
                lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return n_pages


def convert_all_pdfs() -> list[Path]:
    """把目录下所有 PDF 转成 .md，返回 .md 路径列表。"""
    md_paths = []
    for pdf in sorted(PDF_DIR.glob("*.pdf")):
        md = pdf.with_suffix(".md")
        if md.exists() and md.stat().st_mtime >= pdf.stat().st_mtime:
            print(f"[skip] {md.name} 已是最新")
        else:
            print(f"[conv] {pdf.name} -> {md.name} ...")
            n = pdf_to_markdown(pdf, md)
            print(f"       完成，{n} 页")
        md_paths.append(md)
    return md_paths


def main():
    md_paths = convert_all_pdfs()
    print(f"\n共 {len(md_paths)} 个 .md 文件")


if __name__ == "__main__":
    main()
