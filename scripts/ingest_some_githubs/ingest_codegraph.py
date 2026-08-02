import my_load_config
from nbrag.contrib.ingest_github_proj import ingest_github_proj
from nbrag import set_collection_profile


ingest_github_proj(
    "https://github.com/colbymchenry/codegraph",
    collection_name="codegraph",
    relative_paths=["src", "codegraph-kernel", "telemetry-worker", "docs", "site", "scripts", "__tests__"],
    delete_first=True,
    verbose=True,
)


set_collection_profile(
    "codegraph",
    display_name="CodeGraph",
    description="CodeGraph 是一个语义化代码智能工具，基于 Rust 内核构建完整的代码图（code graph），为 Claude Code、Cursor、Codex 等 Agent 提供精确的跨文件上下文、调用链分析和变更影响范围，支持 30+ 种编程语言",
    aliases=["codegraph", "code graph", "semantic code intelligence", "code intelligence", "agent context"],
    tags=["CodeGraph", "Rust", "TypeScript", "Agent", "MCP", "代码图", "上下文", "代码分析"],
)
