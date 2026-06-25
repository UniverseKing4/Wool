import asyncio
from wool.config import WoolConfig
from wool.agent import WoolAgent
import json

async def main():
    config = WoolConfig.load()
    agent = WoolAgent(config)
    schemas = agent.tool_registry.get_schemas()
    for s in schemas:
        try:
            props = s["function"]["parameters"]["properties"]
            if "tools" in props:
                print(s["function"]["name"])
                print(json.dumps(props["tools"], indent=2))
        except:
            pass

asyncio.run(main())
