import asyncio
from wool.config import WoolConfig
from wool.agent import WoolAgent

async def main():
    config = WoolConfig.load()
    agent = WoolAgent(config)
    
    from wool.commands.slash import SlashCommandHandler
    cmd = SlashCommandHandler(agent)
    
    # We will mock stdin.read
    import sys
    
    class MockStdin:
        def __init__(self, chars):
            self.chars = list(chars)
            
        def fileno(self):
            return 0
            
        def read(self, n=1):
            if not self.chars:
                return ''
            res = "".join(self.chars[:n])
            self.chars = self.chars[n:]
            return res

    # Escape
    sys.stdin = MockStdin(['\x1b'])
    
    await cmd.handle("/session")
    print("Exited successfully!")
    
asyncio.run(main())
