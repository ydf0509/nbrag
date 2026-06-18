

import my_load_config
from nbrag import batch_ingest, set_collection_profile


batch_ingest(
    paths=[
       r'D:\codes\docs\src',
       r"D:\ProgramData\miniconda3\envs\py312\Lib\site-packages\langchain_anthropic",
       r"D:\ProgramData\miniconda3\envs\py312\Lib\site-packages\langchain_classic",
       r"D:\ProgramData\miniconda3\envs\py312\Lib\site-packages\langchain_community",
       r"D:\ProgramData\miniconda3\envs\py312\Lib\site-packages\langchain_core",
       r"D:\ProgramData\miniconda3\envs\py312\Lib\site-packages\langchain_deepseek",
       r"D:\ProgramData\miniconda3\envs\py312\Lib\site-packages\langchain_google_genai",
       r"D:\ProgramData\miniconda3\envs\py312\Lib\site-packages\langchain_openai",
       r"D:\ProgramData\miniconda3\envs\py312\Lib\site-packages\langchain_protocol",
       r"D:\ProgramData\miniconda3\envs\py312\Lib\site-packages\langchain_text_splitters",
       r"D:\ProgramData\miniconda3\envs\py312\Lib\site-packages\langdetect",
       r"D:\ProgramData\miniconda3\envs\py312\Lib\site-packages\langgraph",
       r"D:\ProgramData\miniconda3\envs\py312\Lib\site-packages\langgraph_sdk",
       r"D:\ProgramData\miniconda3\envs\py312\Lib\site-packages\langsmith",
       r"D:\ProgramData\miniconda3\envs\py312\Lib\site-packages\langchain",
       r"D:\ProgramData\miniconda3\envs\py312\Lib\site-packages\deepagents",
    ],
    collection_name="langchain_ai_codes_and_docs",
    file_extensions=[".py", ".mdx",".html",".md"],
    max_workers = 1,
    delete_first=True,
    verbose=True,
    chunk_size=1500,
    chunk_overlap=200,
    sleep_interval=0.1, 
)

set_collection_profile(
    "langchain_ai_codes_and_docs",
    display_name="LangChain 源码与文档知识库",
    description="包含 LangChain / LangGraph / langchain-ai 相关源码与文档，适合查询 agent、runnable、工具调用、记忆、图工作流和 API 用法。",
    aliases=["LangChain", "LangGraph", "langchain-ai", "AI agent", "Runnable", "create_react_agent", "create_deep_agent"],
    tags=["Python", "AI", "源码", "文档"],
)
