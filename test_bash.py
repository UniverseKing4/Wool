import asyncio
import os
import sys

# Ensure wool is in path
sys.path.insert(0, os.getcwd())

from wool.tools.bash import ExecuteBash
from wool.tools.base import IS_RESTRICTED
import wool.tools.base as base
base.IS_RESTRICTED = True

async def main():
    tool = ExecuteBash()
    res = await tool.execute(command="curl -s -I https://www.google.com")
    print(f"Success: {res.success}")
    print(f"Output: {res.output}")
    print(f"Error: {res.error}")

asyncio.run(main())
