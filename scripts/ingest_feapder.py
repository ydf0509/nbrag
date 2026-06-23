"""
将 feapder 爬虫框架源码、测试用例和 README 导入到 feapder 知识库。

用法:
    D:/ProgramData/miniconda3/envs/py312/python.exe d:/codes/nbrag/scripts/ingest_feapder.py
"""

import my_load_config
from nbrag import batch_ingest, set_collection_profile


batch_ingest(
    paths=[
        r"D:\codes\feapder\feapder",
        r"D:\codes\feapder\tests",
        r"D:\codes\feapder\README.md",
    ],
    collection_name="feapder",
    file_extensions=[".py", ".md", ],
    max_workers=4,
    delete_first=True,
    verbose=True,
    chunk_size=1000,
    chunk_overlap=150,
    sleep_interval=0.1,
)

set_collection_profile(
    "feapder",
    display_name="feapder 爬虫框架知识库",
    description="包含 feapder 爬虫框架源码、README 和教程文档",
    aliases=["feapder", "feapder 爬虫",  "Spider", "AirSpider", "BatchSpider", "任务爬虫", "爬虫框架"],
    tags=["Python", "爬虫", "项目源码","教程"],
)
