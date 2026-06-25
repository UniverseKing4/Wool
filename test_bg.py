import asyncio
from wool.config import WoolConfig
from wool.agent import WoolAgent

async def test():
    config = WoolConfig.load()
    agent = WoolAgent(config)
    prompt = "spawn 1 subagent to echo hello, then write a short string."
    async for t, c in agent.process_input(prompt):
        if t == "text":
            print(f"TEXT: {c}")
        elif t == "tool_start":
            print(f"TOOL START: {c}")
        elif t == "tool":
            print(f"TOOL: {c}")

    await asyncio.sleep(10) # wait for bg task

asyncio.run(test())
