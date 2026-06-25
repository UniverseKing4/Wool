import asyncio
from wool.config import WoolConfig
from wool.agent import WoolAgent
import httpx
import json

async def main():
    config = WoolConfig.load()
    agent = WoolAgent(config)
    p_config = config.providers.get("antigravity")
    
    all_schemas = agent.tool_registry.get_schemas()
    
    body = {
        "model": "gemini-3.1-pro-low",
        "messages": [{"role": "user", "content": "hey"}],
        "tools": all_schemas,
        "tool_choice": "auto",
        "temperature": 0.0,
        "stream": True
    }
    
    url = f"{p_config.base_url}/chat/completions"
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers={"Authorization": f"Bearer {p_config.api_key}"}, json=body)
        print("Status:", resp.status_code)
        print("Headers:", resp.headers)
        print("Body:", resp.text)

asyncio.run(main())
