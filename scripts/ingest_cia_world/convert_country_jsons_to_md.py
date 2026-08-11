"""把 factbook.json-master 下各 region 目录里的 country JSON 批量转成 markdown。

数据源: https://github.com/factbook/factbook.json (CC0 公共领域)。
SUMMARY.md 里维护了 GEC code → country name 映射，会被解析后用作输出文件名
和 markdown 标题。

用法:
    D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/ingest_cia_world/convert_country_jsons_to_md.py
"""

import json
import re
import sys
from html import unescape
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR / "factbook.json-master"
MD_OUT_DIR = SCRIPT_DIR / "markdown"
SUMMARY_PATH = REPO_DIR / "SUMMARY.md"

# factbook.json 用 GEC (FIPS 10-4) 双字母国家代码，例如 rs=俄罗斯、us=美国、ch=中国、ja=日本。
EXCLUDED_TOP_DIRS = {"meta", "world", "oceans", "antarctica"}

# 不需要进知识库的目录（与 country profiles 无关）。
EXCLUDED_TOP_FILES = {"ALMANAC.md", "SUMMARY.md", "NOTES.md", "MONGO.md", "README.md", "LICENSE.md"}


def parse_code_to_name(summary_path: Path) -> dict[str, str]:
    """解析 SUMMARY.md 里的 `\\`xx\\` Country` 行，拿到 GEC code → 国家名。"""
    code_to_name: dict[str, str] = {}
    pattern = re.compile(r"`([a-z]{2})`\s+(.+)")
    for line in summary_path.read_text(encoding="utf-8").splitlines():
        m = pattern.match(line.strip())
        if m:
            code, name = m.group(1), m.group(2).strip()
            # 去掉 `*` 等 markdown 装饰
            name = name.strip("*").strip()
            code_to_name[code] = name
    return code_to_name


def clean_html(text: str) -> str:
    """去掉 factbook text 字段里的简单 HTML 标签（<b>、<br>、<a>、&eacute; 等），保留可读文本。"""
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?strong>", "**", text, flags=re.IGNORECASE)
    text = re.sub(r"</?em>", "*", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    return text.strip()


def render_node(value, indent: int) -> str:
    """递归把一个 JSON 节点渲染成 markdown 片段。"""
    if isinstance(value, dict):
        # 标准字段：{text, note}
        if "text" in value and isinstance(value["text"], str):
            text = clean_html(value["text"])
            note = value.get("note")
            chunks = [text]
            if isinstance(note, str) and note.strip():
                chunks.append(f"> note: {clean_html(note)}")
            return "\n".join(chunks)
        # 否则把它当子字段集合继续递归
        sub_lines = []
        for k, v in value.items():
            rendered = render_node(v, indent + 1)
            if rendered:
                sub_lines.append(f"- **{k}:** {rendered}" if "\n" not in rendered and len(rendered) < 400
                                 else f"- **{k}:**\n{rendered}")
        return "\n".join(sub_lines)
    if isinstance(value, list):
        return "\n".join(f"- {clean_html(str(v))}" for v in value if v is not None)
    if value is None:
        return ""
    return clean_html(str(value))


def render_country_md(code: str, name: str, region: str, data: dict) -> str:
    """把单个国家 JSON 渲染成完整 markdown 文档。"""
    lines = [
        f"# {name}",
        "",
        f"> GEC code: `{code}` · Region: {region} · Source: CIA World Factbook (factbook.json, CC0)",
        "",
    ]
    for section_name, section_value in data.items():
        if not isinstance(section_value, dict):
            continue
        lines.append(f"## {section_name}")
        lines.append("")
        for field_name, field_value in section_value.items():
            rendered = render_node(field_value, indent=2)
            if not rendered:
                continue
            # 长字段用 block，短字段用紧凑 bullet
            if len(rendered) < 400 and "\n" not in rendered:
                lines.append(f"- **{field_name}:** {rendered}")
            else:
                lines.append(f"### {field_name}")
                lines.append("")
                lines.append(rendered)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def safe_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()


def convert_all() -> list[Path]:
    code_to_name = parse_code_to_name(SUMMARY_PATH)
    if not code_to_name:
        raise RuntimeError(f"无法从 {SUMMARY_PATH} 解析任何国家映射，请检查文件。")

    MD_OUT_DIR.mkdir(exist_ok=True)
    md_paths: list[Path] = []

    for region_dir in sorted(REPO_DIR.iterdir()):
        if not region_dir.is_dir() or region_dir.name in EXCLUDED_TOP_DIRS:
            continue
        for json_path in sorted(region_dir.glob("*.json")):
            code = json_path.stem
            name = code_to_name.get(code)
            if not name:
                # 跳过 SUMMARY 没列出的 code（例如某些 territories）
                print(f"[skip] {region_dir.name}/{json_path.name}  在 SUMMARY.md 里找不到 code={code}")
                continue
            with json_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            md = render_country_md(code, name, region_dir.name, data)
            out = MD_OUT_DIR / f"{safe_filename(name)}.md"
            out.write_text(md, encoding="utf-8")
            md_paths.append(out)
            print(f"[conv] {region_dir.name}/{json_path.name} -> {out.name} ({len(md)} chars)")
    return md_paths


def main():
    md_paths = convert_all()
    print(f"\n共 {len(md_paths)} 个 .md 文件，输出到 {MD_OUT_DIR}")


if __name__ == "__main__":
    main()
