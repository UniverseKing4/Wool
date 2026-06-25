import asyncio
from wool.config import WoolConfig
from wool.providers.openai_compat import OpenAICompatProvider
from wool.providers.base import ChatMessage

async def main():
    config = WoolConfig.load()
    p_config = config.providers.get("antigravity")
    
    print("Testing antigravity direct...")
    provider = OpenAICompatProvider(
        name="antigravity",
        base_url=p_config.base_url,
        api_key=p_config.api_key
    )
    
    msg = ChatMessage(role="user", content="hey")
    async for event in provider.chat_completion_stream(
        messages=[msg],
        model="gemini-3.1-pro-low",
        temperature=0.0
    ):
        print(event)
        
    await provider.close()
    print("Done!")

asyncio.run(main())
