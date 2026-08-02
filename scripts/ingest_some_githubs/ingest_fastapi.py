import my_load_config
from nbrag.contrib.ingest_github_proj import ingest_github_proj
from nbrag import set_collection_profile


ingest_github_proj(
    "https://github.com/fastapi/fastapi",
    collection_name="fastapi",
    relative_paths=["fastapi", "docs/en", "docs_src", "tests"],
    branch="master",
    delete_first=True,
    verbose=True,
)


ingest_github_proj(
    "https://github.com/fastapi/full-stack-fastapi-template",
    collection_name="fastapi",
    relative_paths=["backend", "frontend", "deployment.md", "development.md"],
    branch="master",
    verbose=True,
)


set_collection_profile(
    "fastapi",
    display_name="FastAPI Ecosystem",
    description="FastAPI 框架官方仓库（FastAPI、Starlette、Pydantic 核心实现、文档、示例与测试）与 Full Stack FastAPI Template（React + SQLModel + PostgreSQL + Docker + Traefik + JWT 认证）的合并知识库",
    aliases=["fastapi", "full stack fastapi", "fastapi template", "starlette", "pydantic", "uvicorn"],
    tags=["FastAPI", "Python", '源码','教程',"API", "React", "SQLModel", "PostgreSQL", "Docker", "JWT", "Web"],
)
