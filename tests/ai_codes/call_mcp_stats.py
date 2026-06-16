"""通过 HTTP MCP 客户端连接 http://localhost:9101/mcp，调用 nbrag_stats。

用法:
    D:/ProgramData/miniconda3/envs/py312/python.exe tests/ai_codes/call_mcp_stats.py
"""
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


URL = "http://localhost:9101/mcp"


async def main():
    async with streamablehttp_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print(f"服务端暴露的工具 ({len(tools.tools)}):")
            for t in tools.tools:
                print(f"  - {t.name}")
            print()

            result = await session.call_tool("nbrag_stats", {})
            print("nbrag_stats 返回：")
            print("-" * 60)
            for content in result.content:
                if hasattr(content, "text"):
                    print(content.text)
            print("-" * 60)


if __name__ == "__main__":
    asyncio.run(main())
