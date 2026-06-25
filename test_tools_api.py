import asyncio
from wool.config import WoolConfig
from wool.providers.openai_compat import OpenAICompatProvider
from wool.providers.base import ChatMessage
from wool.agent import WoolAgent

async def main():
    config = WoolConfig.load()
    agent = WoolAgent(config)
    p_config = config.providers.get("antigravity")
    
    provider = OpenAICompatProvider(
        name="antigravity",
        base_url=p_config.base_url,
        api_key=p_config.api_key
    )
    
    all_schemas = agent.tool_registry.get_schemas()
    
    msg = ChatMessage(role="user", content="hey")
    print("Testing antigravity with tools...")
    async for event in provider.chat_completion_stream(
        messages=[msg],
        model="gemini-3.1-pro-low",
        tools=all_schemas,
        temperature=0.0
    ):
        print(event)
        
    await provider.close()
    print("Done!")

asyncio.run(main())
