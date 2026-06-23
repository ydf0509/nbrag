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
    file_extensions=[".py", ".md", ".sql"],
    max_workers=4,
    delete_first=True,
    verbose=True,
    chunk_size=2000,
    chunk_overlap=200,
    sleep_interval=0.1,
)

set_collection_profile(
    "feapder",
    display_name="feapder 爬虫框架知识库",
    description="包含 feapder 爬虫框架源码、测试用例和 README 文档，适合查询空气爬虫、线程爬虫、批量爬虫、任务爬虫、下载中间件、数据管道、布隆去重、框架配置等实现细节。",
    aliases=["feapder", "feapder 爬虫", "空气爬虫", "Spider", "AirSpider", "BatchSpider", "任务爬虫", "爬虫框架"],
    tags=["Python", "爬虫", "源码"],
)
