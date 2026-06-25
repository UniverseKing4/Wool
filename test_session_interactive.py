import asyncio
from wool.config import WoolConfig
from wool.agent import WoolAgent

async def main():
    config = WoolConfig.load()
    agent = WoolAgent(config)
    
    from wool.commands.slash import SlashCommandHandler
    cmd = SlashCommandHandler(agent)
    
    # We will mock input using a string, wait, input is blocking so we'll patch it.
    import builtins
    original_input = builtins.input
    
    def mock_input(prompt):
        print(prompt, end="")
        return "2"
        
    builtins.input = mock_input
    
    await cmd.handle("/session")
    
    def mock_input_delete(prompt):
        print(prompt, end="")
        return "d 3"
        
    builtins.input = mock_input_delete
    await cmd.handle("/session list")
    
asyncio.run(main())
