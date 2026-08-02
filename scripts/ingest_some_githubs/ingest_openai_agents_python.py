import my_load_config
from nbrag.contrib.ingest_github_proj import ingest_github_proj
from nbrag import set_collection_profile

ingest_github_proj(
    "https://github.com/openai/openai-agents-python",
    collection_name="openai-agents-python",
    relative_paths=["src",
    'docs/zh',
    'examples',
    
    ],
    delete_first = True,
    verbose=True,
)

set_collection_profile(
    "openai-agents-python",
    display_name="OpenAI Agents SDK",
    description="OpenAI 官方 Agents SDK，轻量级多 Agent 工作流框架，支持 Agent、Sandbox Agent、Handoff、Guardrail、工具调用、MCP、Human-in-the-loop、Session、Tracing、Realtime Agent 等核心能力，provider-agnostic 支持 100+ LLM",
    aliases=["openai agents", "agents sdk", "agent", "runner", "handoff", "guardrail", "sandbox agent", "realtime agent"],
    tags=["OpenAI", "Agent", "Python", "SDK", "多Agent", "MCP", "工作流"],
)