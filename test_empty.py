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
    # Test ping
    res = await tool.execute(command="ping -c 1 8.8.8.8")
    print(f"Ping output: {res.output!r}")
    print(f"Ping error: {res.error}")

    # Test curl
    res2 = await tool.execute(command="curl -s -I https://www.google.com && curl -s -I https://example.com")
    print(f"Curl output: {res2.output!r}")
    print(f"Curl error: {res2.error}")

asyncio.run(main())
