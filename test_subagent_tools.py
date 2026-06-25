import asyncio
from wool.config import WoolConfig
from wool.agent import WoolAgent

async def main():
    config = WoolConfig.load()
    agent = WoolAgent(config)
    
    tool = agent.tool_registry.get("use_subagent")
    
    print("Starting subagent execution...")
    result = await tool.execute(
        task="Use execute_bash to run `ls -la` and summarize the files. Do not ask me to do it.",
        context="",
        tools=["default_api:execute_bash"]
    )
    
    print("Subagent Result:")
    print(result.output)
    
asyncio.run(main())
