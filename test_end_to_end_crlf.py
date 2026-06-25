import asyncio
from wool.cli import _consume, _spinner
from wool.agent import WoolAgent
from wool.config import WoolConfig
import sys
import tty
import termios

async def main():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    try:
        from wool.cli import _prompt
        from wool.utils.streaming import StreamPrinter
        
        async def mock_iter():
            yield "tool", "\r\n  ┌─ execute_bash \r\n  │ Arguments:\r\n  │ \r\n  └─ \r\n\r\n"
            yield "text", "Here is the HTML!\r\n"
            yield "text", "```\r\nhtml\r\n```\r\n"
        
        class MockAgent:
            def process_input(self, text):
                class Iter:
                    def __aiter__(self): return self
                    async def __anext__(self):
                        for c in mock_iter(): return c
                        raise StopAsyncIteration
                return Iter()
                
        # To test we need to mock agent globally or just pass it
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

