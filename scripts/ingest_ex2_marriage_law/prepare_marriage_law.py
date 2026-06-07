"""
清洗婚姻家庭相关法律文本，保存到当前目录，供 nbrag ingest 测试。
包含：
  1. 民法典 第五编 婚姻家庭（已在 ingest_ex1 中，此处复用）
  2. 婚姻家庭编司法解释（一）—— 91条，2021年施行
  3. 婚姻家庭编司法解释（二）—— 23条，2025年施行
  4. 解释（二）新闻发布会背景介绍 + 典型案例 + 记者问答
"""
import re
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent

# === 解释（一） ===
raw1 = Path(r"C:\Users\ydf19\.cursor\projects\d-codes-ai-proj\agent-tools\59d059a2-7b7e-4095-837b-859f4e84a866.txt").read_text(encoding="utf-8")
lines1 = raw1.splitlines()

start1 = None
end1 = None
for i, line in enumerate(lines1):
    if "为正确审理婚姻家庭纠纷案件" in line and start1 is None:
        start1 = i
    if "第九十一条" in line and "本解释自" in line:
        end1 = i + 1
        break

body1 = "\n".join(lines1[start1:end1]) if start1 and end1 else ""

header1 = """# 最高人民法院关于适用《中华人民共和国民法典》婚姻家庭编的解释（一）

法释〔2020〕22号
2020年12月25日审判委员会第1825次会议通过，自2021年1月1日起施行。

"""

out1 = OUTPUT_DIR / "司法解释_一_婚姻家庭编.md"
out1.write_text(header1 + body1 + "\n", encoding="utf-8")
print(f"  {out1.name}: {len(body1)} chars")

# === 解释（二）：正文 + 发布背景 + 典型案例 + 记者问答 ===
raw2 = Path(r"C:\Users\ydf19\.cursor\projects\d-codes-ai-proj\agent-tools\e0c6efff-1207-488d-a611-b6a6f3012eda.txt").read_text(encoding="utf-8")
lines2 = raw2.splitlines()

# 发布会背景介绍（解释正文之前的内容）
bg_start = None
bg_end = None
for i, line in enumerate(lines2):
    if "一、《解释（二）》的制定背景" in line and bg_start is None:
        bg_start = i
    if line.strip().startswith("法释〔2025〕1号"):
        bg_end = i
        break

if bg_start and bg_end:
    bg_body = "\n".join(lines2[bg_start:bg_end])
    header_bg = """# 婚姻家庭编司法解释（二）—— 新闻发布会介绍

最高人民法院 2025年1月15日

"""
    out_bg = OUTPUT_DIR / "解释二_发布会背景介绍.md"
    out_bg.write_text(header_bg + bg_body + "\n", encoding="utf-8")
    print(f"  {out_bg.name}: {len(bg_body)} chars")

# 解释（二）正文
start2 = None
end2 = None
for i, line in enumerate(lines2):
    if "为正确审理婚姻家庭纠纷案件" in line and i > 50 and start2 is None:
        start2 = i
    if "第二十三条" in line and "本解释自" in line:
        end2 = i + 1
        break

body2 = "\n".join(lines2[start2:end2]) if start2 and end2 else ""

header2 = """# 最高人民法院关于适用《中华人民共和国民法典》婚姻家庭编的解释（二）

法释〔2025〕1号
2024年11月25日审判委员会第1933次会议通过，自2025年2月1日起施行。

"""

out2 = OUTPUT_DIR / "司法解释_二_婚姻家庭编.md"
out2.write_text(header2 + body2 + "\n", encoding="utf-8")
print(f"  {out2.name}: {len(body2)} chars")

# 记者问答和典型案例
qa_start = None
for i, line in enumerate(lines2):
    if "答记者问" in line and i > end2:
        qa_start = i
        break

if qa_start:
    qa_end = len(lines2)
    for i in range(len(lines2) - 1, qa_start, -1):
        stripped = lines2[i].strip()
        if stripped and not any(kw in stripped for kw in ["版权", "法律法规", "©", "备案", "ICP", "导航", "友情链接", "深圳"]):
            qa_end = i + 1
            break

    qa_body = "\n".join(lines2[qa_start:qa_end])
    header_qa = """# 婚姻家庭编司法解释（二）—— 记者问答与典型案例

最高人民法院 2025年1月15日

"""
    out_qa = OUTPUT_DIR / "解释二_记者问答与典型案例.md"
    out_qa.write_text(header_qa + qa_body + "\n", encoding="utf-8")
    print(f"  {out_qa.name}: {len(qa_body)} chars")

# === 复制 民法典 第五编 婚姻家庭 ===
src_marriage = Path(r"D:\codes\nbrag\scripts\ingest_ex1\05_婚姻家庭.md")
if src_marriage.exists():
    dst_marriage = OUTPUT_DIR / "民法典_第五编_婚姻家庭.md"
    dst_marriage.write_text(src_marriage.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"  {dst_marriage.name}: copied from ingest_ex1")

print(f"\nDone! Files saved to {OUTPUT_DIR}")
