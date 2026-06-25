import asyncio
import json
from wool.config import WoolConfig
from wool.providers.openai_compat import OpenAICompatProvider
from wool.providers.base import ChatMessage, ToolCall

async def test():
    config = WoolConfig.load()
    provider = OpenAICompatProvider(
        name="test",
        base_url=config.providers[config.active_provider].base_url,
        api_key=config.providers[config.active_provider].api_key
    )
    
    messages = [
        ChatMessage(role="user", content="spawn 3 subagents at ONCE for different tasks first, then write a random pythin script as waiting for the agents to finish"),
        ChatMessage(role="assistant", content="<think>Spawning subagents</think>", tool_calls=[
            ToolCall(id="tc1", name="use_subagent", arguments=json.dumps({"task": "echo 1", "tools": ["execute_bash"]}))
        ]),
        ChatMessage(role="tool", content="Subagent Execution Complete.\nFinal Output:\n1", tool_call_id="tc1", name="use_subagent"),
        ChatMessage(role="user", content="Tool execution complete. Please continue with the rest of the task, or provide a final summary of the tool execution.")
    ]
    
    from wool.agent import WoolAgent
    agent = WoolAgent(config)
    schemas = agent.tool_registry.get_schemas()
    
    async for event in provider.chat_completion_stream(
        messages=messages,
        model=config.active_model,
        tools=schemas,
        temperature=0.0
    ):
        print("EVENT:", event)

asyncio.run(test())
