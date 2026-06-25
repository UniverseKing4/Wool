import asyncio
from wool.config import WoolConfig
from wool.agent import WoolAgent

async def main():
    config = WoolConfig.load()
    agent = WoolAgent(config)
    
    from wool.commands.slash import SlashCommandHandler
    cmd = SlashCommandHandler(agent)
    
    # We will mock stdin using a pipe
    import sys
    import os
    
    # Ensure test_loop session exists
    await cmd.handle("/new loop_test")
    
    r_fd, w_fd = os.pipe()
    
    # Send "d", then "d", then "q"
    os.write(w_fd, b'ddq')
    
    old_stdin_fd = sys.stdin.fileno()
    os.dup2(r_fd, old_stdin_fd)
    
    await cmd.handle("/session")
    print("Exited successfully!")
    
    os.close(r_fd)
    os.close(w_fd)
    
asyncio.run(main())
