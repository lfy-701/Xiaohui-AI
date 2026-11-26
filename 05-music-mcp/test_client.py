"""用 MCP 官方客户端验证音乐服务：握手、列工具、调用。"""
import asyncio
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

sys.stdout.reconfigure(encoding="utf-8")
URL = "http://127.0.0.1:8102/mcp"


async def main():
    async with streamablehttp_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print("握手成功:", init.serverInfo.name, init.serverInfo.version)

            tools = await session.list_tools()
            print(f"\n工具 {len(tools.tools)} 个：")
            for t in tools.tools:
                ro = getattr(t.annotations, "readOnlyHint", None) if t.annotations else None
                print(f"  - {t.name:<22} 只读={ro}  {t.description.splitlines()[0][:40]}")

            print("\n调用 search_music('周杰伦 晴天')")
            r = await session.call_tool("search_music", {"query": "周杰伦 晴天", "limit": 3})
            text = r.content[0].text if r.content else ""
            print(text[:600])

            print("\n调用 recommend_music('放松')")
            r2 = await session.call_tool("recommend_music", {"mood": "放松", "limit": 2})
            print((r2.content[0].text if r2.content else "")[:400])


asyncio.run(main())
