import my_load_config
from nbrag.contrib.ingest_github_proj import ingest_github_proj
from nbrag import set_collection_profile

ingest_github_proj(
        "https://github.com/modelcontextprotocol/servers",
        collection_name="claude-mcp-servers",
        relative_paths=["src", 
        # "lib"
        ],
        # file_extensions=[".py", ".md", ".ts", ".json"],
        delete_first = True,
        verbose=True,
    )


set_collection_profile(
    "claude-mcp-servers",
    display_name="MCP Reference Servers",
    description="Model Context Protocol (MCP) 官方参考实现仓库，包含 Everything、Fetch、Filesystem、Git、Memory、Sequential Thinking、Time 等参考服务器，覆盖 C#、Go、Java、Kotlin、PHP、Python、Ruby、Rust、Swift、TypeScript 十种语言 SDK，以及 PostgreSQL、SQLite、GitHub、Slack、Puppeteer、Brave Search 等已归档服务器示例",
    aliases=["mcp servers", "mcp reference", "mcp sdk", "modelcontextprotocol", "mcp"],
    tags=["MCP", "Python", "TypeScript", "SDK", "参考实现", "Filesystem", "Git", "Memory"],
)