import asyncio
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import ANSI
import time

async def background_task():
    print("\n[Background] Started sleeping...")
    await asyncio.sleep(2)
    print("\n[Background] Finished sleeping!")

async def main():
    session = PromptSession()
    asyncio.create_task(background_task())
    try:
        user_input = await session.prompt_async(ANSI("\033[36mPrompt>\033[0m "))
        print("Got:", user_input)
    except KeyboardInterrupt:
        print("Exit")

asyncio.run(main())
