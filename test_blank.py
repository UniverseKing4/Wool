import asyncio
from wool.config import WoolConfig
from wool.agent import WoolAgent

async def test():
    config = WoolConfig.load()
    agent = WoolAgent(config)
    prompt = "spawn 3 subagents at ONCE for different tasks first, then write a random pythin script as waiting for the agents to finish"
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
