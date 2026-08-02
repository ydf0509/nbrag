import my_load_config
from nbrag.contrib.ingest_github_proj import ingest_github_proj
from nbrag import set_collection_profile


ingest_github_proj(
    "https://github.com/anomalyco/opencode",
    collection_name="opencode",
    relative_paths=["packages", "sdks", "script", "specs", ],
    branch="dev",
    delete_first=True,
    verbose=True,
)


set_collection_profile(
    "opencode",
    display_name="OpenCode",
    description="OpenCode 是开源 AI 编程 Agent，包含 build/plan 双 Agent 模式、桌面应用、MCP 集成，以及 packages、sdks、script 等模块",
    aliases=["opencode", "opencode ai", "ai coding agent", "build agent", "plan agent"],
    tags=["OpenCode", "AI", "Agent", "Coding", "TypeScript", "MCP", "CLI"],
)
