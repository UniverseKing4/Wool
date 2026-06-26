import asyncio
import httpx


async def main():
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://mcp.exa.ai/mcp",
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
        )
        print("Status", resp.status_code)
        try:
            async for line in resp.aiter_lines():
                print("Line:", line)
        except Exception as e:
            print("Error:", repr(e))


asyncio.run(main())
