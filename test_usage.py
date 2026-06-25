import asyncio
from wool.agent import WoolAgent
from wool.config import WoolConfig

async def test():
    config = WoolConfig()
    agent = WoolAgent(config)
    print("Initial Usage:", agent.total_usage)
    agent.total_usage["prompt_tokens"] += 123
    agent.total_usage["completion_tokens"] += 456
    agent.total_usage["total_tokens"] = agent.total_usage["prompt_tokens"] + agent.total_usage["completion_tokens"]
    
    from wool.commands import SlashCommandHandler
    cmd = SlashCommandHandler(agent)
    await cmd.handle("/usage")
    
asyncio.run(test())
