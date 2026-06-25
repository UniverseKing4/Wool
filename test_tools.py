import asyncio
from wool.config import WoolConfig
from wool.agent import WoolAgent
import json

async def main():
    config = WoolConfig.load()
    agent = WoolAgent(config)
    schemas = agent.tool_registry.get_schemas()
    for s in schemas:
        if s["function"]["name"] == "mcp_call":
            print(json.dumps(s, indent=2))

asyncio.run(main())
