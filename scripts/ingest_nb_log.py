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
        "D:/codes/nb_log/nb_log",
        "D:/codes/nb_log_readdocs/source/articles",
     
      
    ],
    collection_name="nb_log",
    file_extensions=[".py", ".md", ],
    excluded_paths=[
       
    ],
    max_workers = 1,
    delete_first=True,
    verbose=True,
    sleep_interval=0.1,
)  

set_collection_profile(
    "nb_log",
    display_name="nb_log 源码与文档知识库",
    description="nb_log 是一个基于logging封装的日志三方包，五彩日志，print自动增强，多种filehandler多进程安全切割,能自动重定向输出",
    aliases=["nb_log", 'logging','loguru'],
    tags=["Python", "源码","教程", "日志",'logging','print','logging handler'],
)
