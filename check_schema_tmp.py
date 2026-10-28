import asyncio, json
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

async def main():
    async with streamablehttp_client("http://127.0.0.1:9101/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            for t in tools.tools:
                if t.name == "nbrag_read_more_original_text":
                    print(json.dumps(t.inputSchema, indent=2, ensure_ascii=False))
                    return
            print("tool not found")

asyncio.run(main())
