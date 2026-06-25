"""CLI REPL — the user-facing interface for Wool.

Pure line-by-line stdin/stdout.  No TUI, no curses.  Just a clean REPL
with ANSI colours.
"""

from __future__ import annotations

import asyncio
import sys
import termios
import tty

from wool import __version__
from wool.agent import WoolAgent
from wool.commands import SlashCommandHandler
from wool.config import WoolConfig
from wool.utils.ansi import (
    bold,
    cyan,
    dim,
    green,
    white,
    yellow,
    gray,
)
from wool.utils.streaming import StreamPrinter


# ── banner ────────────────────────────────────────────────────────────────────


def _print_banner(agent: WoolAgent) -> None:
    provider = agent.active_provider.name if agent.active_provider else "none"
    model = agent.active_model or "auto"
    n_tools = len(agent.tool_registry.list_tools())
    n_mcp = len(agent.mcp_manager.list_servers())

    print()
    print(f"  {bold(cyan('🐑 Wool'))} {dim('v' + __version__)}")
    print(f"  {dim('Ultra-lightweight CLI AI Agent')}")
    print()
    print(
        f"  {dim('Provider:')} {green(provider)}  "
        f"{dim('│')}  {dim('Model:')} {cyan(model)}"
    )
    print(
        f"  {dim('Tools:')} {white(str(n_tools))} {dim('built-in')}  "
        f"{dim('│')}  {dim('MCP:')} {white(str(n_mcp))} {dim('servers')}"
    )
    print(f"  {dim('Type')} {yellow('/help')} {dim('for commands')}")
    print()


# ── prompt ────────────────────────────────────────────────────────────────────


def _prompt(turn: int) -> str:
    return f"  {dim(str(turn))} {bold(cyan('wool'))} {dim('›')} "


# ── REPL ──────────────────────────────────────────────────────────────────────


async def run_repl() -> None:
    """Main read-eval-print loop."""
    config = WoolConfig.load()
    agent = WoolAgent(config)
    commands = SlashCommandHandler(agent)

    _print_banner(agent)

    turn = 1

    while True:
        # ── read ──
        try:
            user_input = input(_prompt(turn))
        except EOFError:
            print()
            break

        text = user_input.strip()
        if not text:
            continue

        # ── slash commands ──
        if commands.is_command(text):
            should_exit = await commands.handle(text)
            if should_exit:
                break
            continue

        # ── eval / print ──
        print()
        printer = StreamPrinter()
        
        loop = asyncio.get_running_loop()
        cancel_event = asyncio.Event()
        
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        
        def on_input() -> None:
            ch = sys.stdin.read(1)
            if ch == '\x1b' or ch == '\x03':  # Escape or Ctrl+C
                cancel_event.set()

        is_thinking = asyncio.Event()
        is_thinking.set()

        async def _spinner() -> None:
            frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            i = 0
            spinner_active = False
            try:
                while not cancel_event.is_set():
                    if is_thinking.is_set():
                        sys.stdout.write(f"\r  {cyan(frames[i % len(frames)])} {dim('thinking...')}")
                        sys.stdout.flush()
                        spinner_active = True
                        i += 1
                        await asyncio.sleep(0.08)
                    else:
                        if spinner_active:
                            sys.stdout.write("\r\033[K")
                            sys.stdout.flush()
                            spinner_active = False
                        
                        wait_think = asyncio.create_task(is_thinking.wait())
                        wait_cancel = asyncio.create_task(cancel_event.wait())
                        await asyncio.wait([wait_think, wait_cancel], return_when=asyncio.FIRST_COMPLETED)
            except asyncio.CancelledError:
                pass
            finally:
                if spinner_active:
                    sys.stdout.write("\r\033[K")
                    sys.stdout.flush()

        async def _consume() -> None:
            nonlocal printer
            has_reasoned = False
            transitioned = False
            iterator = agent.process_input(text).__aiter__()
            try:
                while True:
                    next_task = asyncio.create_task(iterator.__anext__())
                    cancel_wait = asyncio.create_task(cancel_event.wait())
                    
                    done, _ = await asyncio.wait(
                        [next_task, cancel_wait], 
                        timeout=0.2, 
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    if cancel_event.is_set():
                        break

                    if next_task not in done:
                        is_thinking.set()
                        await asyncio.wait(
                            [next_task, asyncio.create_task(cancel_event.wait())], 
                            return_when=asyncio.FIRST_COMPLETED
                        )
                        if cancel_event.is_set():
                            break

                    try:
                        chunk_tuple = next_task.result()
                    except StopAsyncIteration:
                        break
                        
                    if is_thinking.is_set():
                        is_thinking.clear()
                        await asyncio.sleep(0.01)  # tiny delay to ensure clear
                        
                    chunk_type, chunk = chunk_tuple

                    if chunk_type == "text":
                        if has_reasoned and not transitioned:
                            sys.stdout.write("\n\n")
                            sys.stdout.flush()
                            transitioned = True
                        printer.print_chunk(chunk)
                    elif chunk_type == "reasoning":
                        has_reasoned = True
                        sys.stdout.write(dim(gray(chunk)))
                        sys.stdout.flush()
                    elif chunk_type == "tool":
                        if has_reasoned and not transitioned:
                            sys.stdout.write("\n\n")
                            sys.stdout.flush()
                            transitioned = True
                        printer.finish()
                        sys.stdout.write(chunk)
                        sys.stdout.flush()
            except asyncio.CancelledError:
                pass

        try:
            tty.setcbreak(fd)
            loop.add_reader(fd, on_input)
            
            spinner_task = asyncio.create_task(_spinner())
            task = asyncio.create_task(_consume())
            cancel_task = asyncio.create_task(cancel_event.wait())
            
            await asyncio.wait(
                [task, cancel_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            cancel_event.set()
            if is_thinking.is_set():
                is_thinking.clear()
            await spinner_task
            
            if cancel_event.is_set():
                if not task.done():
                    task.cancel()
                    await task
                printer.finish()
                print(f"\n{dim('  (cancelled via Escape)')}")
                continue
            else:
                await task  # raise any exceptions
                
        except KeyboardInterrupt:
            if not task.done():
                task.cancel()
                await task
            printer.finish()
            print(f"\n{dim('  (interrupted)')}")
            continue
        finally:
            loop.remove_reader(fd)
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        printer.finish()
        print()  # spacer after response
        turn += 1

    # ── shutdown ──
    print(f"\n  {dim('← Shutting down…')}")
    await agent.shutdown()
    print(f"  {dim('← Goodbye. 🐑')}\n")
