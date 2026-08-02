import my_load_config
from nbrag.contrib.ingest_github_proj import ingest_github_proj
from nbrag import set_collection_profile

ingest_github_proj(
    "https://github.com/run-llama/llama_index",
    collection_name="llama_index",
    relative_paths=[
        "llama-index-core",
        "docs",
        "llama-index-instrumentation",
        "llama-index-utils",
    ],
    delete_first=True,
    verbose=True,
)

set_collection_profile(
    "llama_index",
    display_name="LlamaIndex",
    description="LlamaIndex 是开源的数据框架（Data Framework），用于构建 LLM 应用和 Agentic 系统。提供数据连接器（130+ 格式）、文档解析（LlamaParse）、索引构建、高级检索/查询接口、Workflows 编排、Agent 构建等核心能力，支持 300+ 集成（LLM、Embedding、Vector Store 等）",
    aliases=["llama_index", "llama index", "llamaindex", "llama-index-core", "llamaparse", "LlamaIndex", "LlamaParse", "LlamaAgents"],
    tags=["LlamaIndex", "Python", "RAG", "Data Framework", "LLM", "Agent", "Document Parsing", "Vector Store", "Retrieval"],
)