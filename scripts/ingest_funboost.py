"""
示例：批量导入项目到 RAG 知识库。

用法:
    # 1. 设置 API Key
    export NBRAG_API_KEY=sk-xxx

    # 2. 运行导入
    python scripts/import_project.py
"""

import my_load_config
from nbrag import batch_ingest, set_collection_profile


batch_ingest(
    paths=[
        "D:/codes/funboost/funboost",
        "D:/codes/funboost/test_frame",
        "D:/codes/funboost/tests",
        "D:/codes/funboost_docs/source/articles/c0.md",
        "D:/codes/funboost_docs/source/articles/c1.md",
        "D:/codes/funboost_docs/source/articles/c2.md",
        "D:/codes/funboost_docs/source/articles/c3.md",
        "D:/codes/funboost_docs/source/articles/c4.md",
        "D:/codes/funboost_docs/source/articles/c4b.md",
        "D:/codes/funboost_docs/source/articles/c6.md",
        "D:/codes/funboost_docs/source/articles/c7.md",
        "D:/codes/funboost_docs/source/articles/c8.md",
        "D:/codes/funboost_docs/source/articles/c9.md",
        "D:/codes/funboost_docs/source/articles/c10.md",
        "D:/codes/funboost_docs/source/articles/c11.md",
        "D:/codes/funboost_docs/source/articles/c12.md",
        "D:/codes/funboost_docs/source/articles/c13.md",
        "D:/codes/funboost_docs/source/articles/c14.md",
        "D:/codes/funboost_docs/source/articles/c15.md",
        "D:/codes/funboost_docs/source/articles/c20.md",
        # "D:/codes/boost_spider",
        r"D:\codes\funboost\.agents",
        
        r'D:\codes\boost_spider\boost_scrapy',
        r'D:\codes\boost_spider\boost_spider',
        r'D:\codes\boost_spider\demo_crawler',
        r'D:\codes\boost_spider\README.md',
      
    ],
    collection_name="funboost",
    file_extensions=[".py", ".md", ".html"],
    excluded_paths=[
        r"D:\codes\boost_spider\tests",
        "D:/codes/boost_spider/dist",
    ],
    max_workers = 1,
    delete_first=True,
    verbose=True,
    sleep_interval=0.1,
)  

set_collection_profile(
    "funboost",
    display_name="funboost 源码与文档知识库",
    description="包含 funboost 项目源码和文档，适合查询函数调度、消息队列、broker、BoosterParams、发布消费、重试等实现细节。",
    aliases=["funboost", "分布式函数调度", "Python 队列", "BrokerEnum", "BoosterParams","funspider","boost_spider"],
    tags=["Python", "源码", "消息队列"],
)
