import asyncio
from wool.config import WoolConfig
from wool.agent import WoolAgent

async def main():
    config = WoolConfig.load()
    agent = WoolAgent(config)
    
    from wool.commands.slash import SlashCommandHandler
    cmd = SlashCommandHandler(agent)
    
    await cmd.handle("/rename shorty")
    
asyncio.run(main())
