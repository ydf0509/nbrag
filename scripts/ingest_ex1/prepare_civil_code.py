"""
清洗《中华人民共和国民法典》全文，按"编"拆分为独立文件，供 nbrag ingest 测试。
"""
import re
from pathlib import Path

RAW_FILE = Path(r"C:\Users\ydf19\.cursor\projects\d-codes-ai-proj\agent-tools\5584ca14-6ddd-4bb8-b565-890d6b6f6f16.txt")
OUTPUT_DIR = Path(__file__).parent

raw = RAW_FILE.read_text(encoding="utf-8")

lines = raw.splitlines()
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if "第一编 总则" in line and start_idx is None:
        if i > 0 and "目 录" not in lines[i - 2]:
            start_idx = i
    if line.strip().startswith("附件："):
        end_idx = i
        break

if start_idx is None:
    for i, line in enumerate(lines):
        if re.match(r"第一条\s", line):
            start_idx = i
            break

if end_idx is None:
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip().startswith("第一千二百六十条"):
            end_idx = i + 1
            break

body_lines = lines[start_idx:end_idx]
body = "\n".join(body_lines)

header = """中华人民共和国民法典
（2020年5月28日第十三届全国人民代表大会第三次会议通过）
自2021年1月1日起施行。

"""

split_pattern = re.compile(r"^(第[一二三四五六七]编\s+\S+)$")
parts = []
current_title = "前言"
current_lines = []

for line in body_lines:
    m = split_pattern.match(line.strip())
    if m and not current_lines:
        current_title = m.group(1)
        current_lines = [line]
    elif m:
        parts.append((current_title, current_lines))
        current_title = m.group(1)
        current_lines = [line]
    else:
        current_lines.append(line)

if current_lines:
    parts.append((current_title, current_lines))

part_names = {
    "第一编 总则": "01_总则.md",
    "第二编 物权": "02_物权.md",
    "第三编 合同": "03_合同.md",
    "第四编 人格权": "04_人格权.md",
    "第五编 婚姻家庭": "05_婚姻家庭.md",
    "第六编 继承": "06_继承.md",
    "第七编 侵权责任": "07_侵权责任.md",
}

saved = []
for title, plines in parts:
    fname = part_names.get(title, f"99_{title}.md")
    content = header + f"# {title}\n\n" + "\n".join(plines) + "\n"
    out = OUTPUT_DIR / fname
    out.write_text(content, encoding="utf-8")
    saved.append((fname, len(plines), len(content)))
    print(f"  {fname}: {len(plines)} lines, {len(content)} chars")

full_out = OUTPUT_DIR / "民法典_全文.md"
full_content = header + body + "\n"
full_out.write_text(full_content, encoding="utf-8")
print(f"\n  民法典_全文.md: {len(body_lines)} lines, {len(full_content)} chars")
print(f"\nTotal: {len(saved)} parts + 1 full text saved to {OUTPUT_DIR}")
