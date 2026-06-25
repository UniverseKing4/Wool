import asyncio
from wool.config import WoolConfig
from wool.agent import WoolAgent
from wool.providers.base import ChatMessage

async def main():
    config = WoolConfig.load()
    agent = WoolAgent(config)
    agent.messages.append(ChatMessage(role="user", content="hello session test"))
    agent.save_session()
    
    from wool.commands.slash import SlashCommandHandler
    cmd = SlashCommandHandler(agent)
    await cmd.handle("/session list")
    
    await cmd.handle("/session new test2")
    await cmd.handle("/session list")
    
    await cmd.handle("/session delete test2")
    
asyncio.run(main())
