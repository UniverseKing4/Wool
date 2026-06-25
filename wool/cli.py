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

        first_chunk_received = asyncio.Event()

        async def _spinner() -> None:
            frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            i = 0
            try:
                while not first_chunk_received.is_set() and not cancel_event.is_set():
                    sys.stdout.write(f"\r  {cyan(frames[i % len(frames)])} {dim('thinking...')}")
                    sys.stdout.flush()
                    try:
                        await asyncio.wait_for(first_chunk_received.wait(), 0.08)
                    except asyncio.TimeoutError:
                        i += 1
            except asyncio.CancelledError:
                pass
            finally:
                sys.stdout.write("\r\033[K")
                sys.stdout.flush()

        async def _consume() -> None:
            nonlocal printer
            try:
                async for chunk_type, chunk in agent.process_input(text):
                    if not first_chunk_received.is_set():
                        first_chunk_received.set()
                        
                    if chunk_type == "text":
                        printer.print_chunk(chunk)
                    elif chunk_type == "tool":
                        printer.finish()
                        sys.stdout.write(chunk)
                        sys.stdout.flush()
                        
                    if cancel_event.is_set():
                        break
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
            
            if not first_chunk_received.is_set():
                first_chunk_received.set()
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
