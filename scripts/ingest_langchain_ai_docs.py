

import my_load_config
from nbrag.core import batch_ingest


batch_ingest(
    paths=[
       r'D:\codes\docs\src',

    ],
    collection_name="langchain_ai_docs",
    file_extensions=[".py", ".mdx",".html",".md"],
    max_workers = 1,
    delete_first=True,
    verbose=True,
    chunk_size=1000,
    chunk_overlap=200,
    sleep_interval=0.1, 
)