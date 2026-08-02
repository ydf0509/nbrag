import my_load_config
from nbrag.contrib.ingest_github_proj import ingest_github_proj
from nbrag import set_collection_profile


ingest_github_proj(
    "https://github.com/crewAIInc/crewAI",
    collection_name="crewai",
    relative_paths=["lib", "docs/v1.15.9/en", "scripts"],
    delete_first=True,
    verbose=True,
)


set_collection_profile(
    "crewai",
    display_name="CrewAI",
    description="CrewAI 是开源的 Python 多 Agent 编排框架，提供 Crews（基于角色的自治 Agent 协作）和 Flows（事件驱动的精确工作流控制）两大核心抽象，支持任务依赖、结构化输出、记忆、Guardrail 等能力",
    aliases=["crewai", "crew ai", "crews", "flows", "multi-agent", "agent orchestration"],
    tags=["CrewAI", "Python", "Agent", "多Agent", "工作流", "编排", "LLM"],
)
