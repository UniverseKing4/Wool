import asyncio
from wool.agent import WoolAgent
from wool.config import WoolConfig

async def main():
    config = WoolConfig.load()
    agent = WoolAgent(config)
    
    # We will mock the active_provider
    class MockProvider:
        async def chat_completion_stream(self, **kwargs):
            yield type('Event', (), {'type': 'text', 'content': 'Hello, '})()
            yield type('Event', (), {'type': 'text', 'content': 'this '})()
            yield type('Event', (), {'type': 'text', 'content': 'is '})()
            yield type('Event', (), {'type': 'text', 'content': 'a test.'})()

    agent.active_provider = MockProvider()
    
    print("Testing processing input...")
    async for chunk_type, chunk in agent.process_input("hello"):
        print(f"[{chunk_type}] {repr(chunk)}")

asyncio.run(main())
