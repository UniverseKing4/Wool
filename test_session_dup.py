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
    
    # Let's use a PTY to see exactly what is output
    import pty
    import termios
    import tty
    import time
    
    m, s = pty.openpty()
    
    # We will run the menu in a background task
    import threading
    
    def run_menu():
        old_stdin = sys.stdin.fileno()
        old_stdout = sys.stdout.fileno()
        os.dup2(s, 0)
        os.dup2(s, 1)
        asyncio.run(cmd.handle("/session"))
        os.dup2(old_stdin, 0)
        os.dup2(old_stdout, 1)
        
    t = threading.Thread(target=run_menu)
    t.start()
    
    time.sleep(0.2)
    os.write(m, b'\x1b[B')  # DOWN
    time.sleep(0.2)
    os.write(m, b'\x1b[A')  # UP
    time.sleep(0.2)
    os.write(m, b'q')       # QUIT
    
    t.join()
    
    output = os.read(m, 4096).decode()
    print("OUTPUT WAS:")
    print(repr(output))
    
asyncio.run(main())
