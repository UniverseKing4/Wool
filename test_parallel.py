import asyncio
from wool.config import WoolConfig
from wool.agent import WoolAgent
from wool.providers.base import ToolCall
import json
import time

async def main():
    config = WoolConfig.load()
    agent = WoolAgent(config)
    
    # We mock pending_tool_calls to have two sleep commands
    pending_tool_calls = [
        ToolCall(id="tc1", name="execute_bash", arguments=json.dumps({"command": "sleep 2 && echo 'Done 1'"})),
        ToolCall(id="tc2", name="execute_bash", arguments=json.dumps({"command": "sleep 1 && echo 'Done 2'"})),
        ToolCall(id="tc3", name="execute_bash", arguments=json.dumps({"command": "echo 'Done 3'"}))
    ]
    
    agent.messages = [] # Empty for test
    
    # Normally this is set by the provider, we simulate it
    agent.messages.append(type("mock", (), {"role": "assistant", "content": None, "tool_calls": pending_tool_calls})())
    
    print("Starting process_input loop...")
    start_time = time.time()
    
    # Just iterate through the tool execution part
    # Actually wait, process_input expects user_input and then calls provider. 
    # We can't easily mock process_input completely because it calls the provider.
    pass

# We will just write a small test function to simulate the loop logic we just added
async def test_logic():
    config = WoolConfig.load()
    agent = WoolAgent(config)
    
    pending_tool_calls = [
        ToolCall(id="tc1", name="execute_bash", arguments=json.dumps({"command": "sleep 3 && echo 'Task 1'"})),
        ToolCall(id="tc2", name="execute_bash", arguments=json.dumps({"command": "sleep 1 && echo 'Task 2'"})),
        ToolCall(id="tc3", name="execute_bash", arguments=json.dumps({"command": "echo 'Task 3'"}))
    ]
    
    async def execute_tool(tc):
        try:
            args = json.loads(tc.arguments) if tc.arguments else {}
        except json.JSONDecodeError:
            args = {}
        tool = agent.tool_registry.get(tc.name)
        result = await tool.execute(**args)
        return tc, args, result.output
        
    start_time = time.time()
    tasks = [asyncio.create_task(execute_tool(tc)) for tc in pending_tool_calls]
    for completed_task in asyncio.as_completed(tasks):
        tc, args, result_text = await completed_task
        print(f"Finished {tc.id} in {time.time() - start_time:.2f}s: {result_text.strip()}")

asyncio.run(test_logic())
