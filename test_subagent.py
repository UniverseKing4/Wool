import asyncio
from wool.config import WoolConfig
from wool.agent import WoolAgent
from wool.providers.base import ChatMessage

async def main():
    config = WoolConfig.load()
    agent = WoolAgent(config)
    
    # We will invoke the subagent tool directly
    tool = agent.tool_registry.get("use_subagent")
    
    print("Starting subagent execution...")
    result = await tool.execute(
        task="Say 'Hello from subagent!' and nothing else.",
        context="",
        tools=[]
    )
    
    print("Subagent Result:")
    print(result.output)
    
asyncio.run(main())
