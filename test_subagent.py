import asyncio
from wool.tools.subagent import SubagentDelegation

async def test():
    tool = SubagentDelegation()
    tasks = [
        tool.execute(task="echo task 1", tools=["execute_bash"]),
        tool.execute(task="echo task 2", tools=["execute_bash"]),
        tool.execute(task="echo task 3", tools=["execute_bash"])
    ]
    results = await asyncio.gather(*tasks)
    for r in results:
        print(r.output)

asyncio.run(test())
