import asyncio
from wool.config import WoolConfig
from wool.agent import WoolAgent

async def test():
    config = WoolConfig.load()
    agent = WoolAgent(config)
    prompt = "spawn 1 subagent to sleep 2 seconds and echo hello, then write a random python script."
    async for t, c in agent.process_input(prompt):
        if t == "text":
            print(f"TEXT: {c}")
        elif t == "reasoning":
            print(f"REASONING: {c}")
        elif t == "tool_start":
            print(f"TOOL START: {c}")
        elif t == "tool":
            print(f"TOOL: {c}")
        elif t == "error":
            print(f"ERROR: {c}")

asyncio.run(test())
