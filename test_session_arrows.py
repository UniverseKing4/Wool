import asyncio
from wool.config import WoolConfig
from wool.agent import WoolAgent
import sys
import os

async def main():
    config = WoolConfig.load()
    agent = WoolAgent(config)
    
    from wool.commands.slash import SlashCommandHandler
    cmd = SlashCommandHandler(agent)
    
    # We will mock stdin using a real pipe so os.read and select works
    r_fd, w_fd = os.pipe()
    
    # Write the arrow sequence "\x1b[B" and "\n"
    os.write(w_fd, b'\x1b[B\n')
    
    # Swap sys.stdin to the pipe read end
    old_stdin_fd = sys.stdin.fileno()
    os.dup2(r_fd, old_stdin_fd)
    
    await cmd.handle("/session")
    print("Exited successfully!")
    
    os.close(r_fd)
    os.close(w_fd)
    
asyncio.run(main())
