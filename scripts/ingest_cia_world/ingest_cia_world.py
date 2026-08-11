"""把 ingest_cia_world/markdown 下的所有 .md 批量导入 nbrag 知识库 cia_world_factbook。

前置条件：先运行 convert_country_jsons_to_md.py 把 factbook.json 转成 .md。

用法:
    D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/ingest_cia_world/ingest_cia_world.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import my_load_config  # noqa: F401  加载 NBRAG_API_KEY
from nbrag import batch_ingest, set_collection_profile

SCRIPT_DIR = Path(__file__).resolve().parent
MD_DIR = SCRIPT_DIR / "markdown"
COLLECTION_NAME = "cia_world_factbook"


md_paths = sorted(MD_DIR.glob("*.md"))
if not md_paths:
    print(f"没找到 .md 文件，请先运行 convert_country_jsons_to_md.py")
    raise FileNotFoundError(f"目录 {MD_DIR} 为空")

print(f"开始导入 {len(md_paths)} 个 .md 到 nbrag collection={COLLECTION_NAME}")
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
    display_name="CIA World Factbook 各国概况知识库",
    description=(
        "包含 251 个国家/地区的 CIA World Factbook 完整档案 (CC0 公共领域)，"
        "覆盖 Introduction / Geography / People and Society / Environment / Government / "
        "Economy / Energy / Communications / Transportation / Military and Security / "
        "Space / Terrorism / Transnational Issues 等 13 个章节。"
        "适合查询各国地理、人口、政治、经济、军事、能源等基本信息。"
    ),
    aliases=["CIA", "World Factbook", "世界各国", "国家概况", "各国档案", "国情"],
    tags=["地理", "国际", "军事", "经济", "公共领域", "CC0"],
)
print("\n[OK] 完成")
