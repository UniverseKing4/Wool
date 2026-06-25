import asyncio
import time
import json
from wool.config import WoolConfig
from wool.agent import WoolAgent
from wool.providers.base import ToolCall

async def mock_process_input():
    config = WoolConfig.load()
    agent = WoolAgent(config)
    
    pending_tool_calls = [
        ToolCall(id="tc1", name="use_subagent", arguments=json.dumps({"task": "Task 1"})),
        ToolCall(id="tc2", name="use_subagent", arguments=json.dumps({"task": "Task 2"}))
    ]
    
    async def execute_tool(tc):
        await asyncio.sleep(2 if tc.id == "tc1" else 1)
        return tc, {}, f"Result of {tc.id}"
        
    tasks = {tc.id: asyncio.create_task(execute_tool(tc)) for tc in pending_tool_calls}

    for tc in pending_tool_calls:
        yield "tool", f"┌─ {tc.name}\n"
        yield "tool", f"│ Args: {tc.arguments}\n"
        yield "tool", f"└─ [Running background task...]\n\n"

    for completed_task in asyncio.as_completed(tasks.values()):
        tc, args, result_text = await completed_task
        yield "tool", f"┌─ {tc.name} Result:\n"
        yield "tool", f"│ {result_text}\n"
        yield "tool", f"└─\n\n"

async def main():
    start_time = time.time()
    async for t, c in mock_process_input():
        print(f"[{time.time() - start_time:.1f}s] {c}", end="")
        
asyncio.run(main())
