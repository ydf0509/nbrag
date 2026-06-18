"""把 inguest_licai 目录下的 PDF 转成 .md 文本，再批量导入 nbrag 知识库 finance_reports。

流程：
    1. 扫描 PDF 文件
    2. 用 pdfplumber 逐页提取文字（含表格按行拼接）
    3. 写到同名 .md 文件（同目录）
    4. 调 batch_ingest 导入 nbrag

用法：
    D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/inguest_licai/ingest_licai.py
"""

import os
import sys
from pathlib import Path

# 项目根加入 sys.path（容忍任意 cwd 启动）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import my_load_config  # noqa: F401  加载 NBRAG_API_KEY
import pdfplumber
from nbrag import batch_ingest, set_collection_profile


PDF_DIR = Path(__file__).resolve().parent
COLLECTION_NAME = "finance_reports"


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
    if not md_paths:
        print("没找到 PDF")
        return

    print(f"\n开始导入 {len(md_paths)} 个 .md 到 nbrag collection={COLLECTION_NAME}")
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


if __name__ == "__main__":
    main()
