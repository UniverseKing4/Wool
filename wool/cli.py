"""CLI REPL — the user-facing interface for Wool.

Pure line-by-line stdin/stdout.  No TUI, no curses.  Just a clean REPL
with ANSI colours.
"""

from __future__ import annotations

import asyncio
import sys
import termios
import tty
import readline
import signal
import time

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
    if not sys.stdout.isatty():
        return f"  {turn} wool › "

    # Readline requires \001 and \002 around non-printable ANSI escape sequences
    # to calculate the visible width of the prompt correctly. If omitted, typing
    # long strings will wrap incorrectly and overwrite the prompt.
    S = "\001"
    E = "\002"
    return (
        f"  {S}\033[2m{E}{turn}{S}\033[0m{E} "
        f"{S}\033[1m\033[36m{E}wool{S}\033[0m{E} "
        f"{S}\033[2m{E}›{S}\033[0m{E} "
    )


# ── REPL ──────────────────────────────────────────────────────────────────────


async def run_repl() -> None:
    """Main read-eval-print loop."""
    config = WoolConfig.load()
    agent = WoolAgent(config)
    commands = SlashCommandHandler(agent)

    if config.mcp_servers:
        from wool.utils.ansi import red, info, success

        print()
        info("Restoring MCP connections...")
        for name, mcp_cfg in config.mcp_servers.items():
            if "command" in mcp_cfg:
                try:
                    await agent.mcp_manager.connect(name, command=mcp_cfg["command"])
                except Exception as e:
                    print(f"  {red('✗')} Failed to auto-connect MCP '{name}': {e}")
        success(f"Restored {len(agent.mcp_manager.list_servers())} MCP servers.\n")

    _print_banner(agent)

    typeahead_buffer: list[str] = []

    def _pre_input_hook() -> None:
        if typeahead_buffer:
            text = "".join(typeahead_buffer)
            readline.insert_text(text)
            readline.redisplay()
            typeahead_buffer.clear()

    readline.set_pre_input_hook(_pre_input_hook)
    readline.parse_and_bind("set disable-completion on")

    auto_next_text = None

    while True:

        def is_real_user(m):
            if m.role != "user":
                return False
            if not m.content:
                return True
            if "Tool execution complete. Please continue" in m.content:
                return False
            if (
                "The background subagents have finished. Here are their final results:"
                in m.content
            ):
                return False
            return True

        turn = sum(1 for m in agent.messages if is_real_user(m)) + 1

        # ── read ──
        if auto_next_text:
            text = auto_next_text
            auto_next_text = None
            print(f"{_prompt(turn)}{text}")
        else:
            old_handler = signal.signal(signal.SIGINT, signal.default_int_handler)
            try:
                user_input = input(_prompt(turn))
            except KeyboardInterrupt:
                print()
                typeahead_buffer.clear()
                if readline.get_line_buffer():
                    continue
                break
            except EOFError:
                print()
                break
            finally:
                signal.signal(signal.SIGINT, old_handler)

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
            if ch == "\x03":  # Ctrl+C
                cancel_event.set()
                typeahead_buffer.clear()
            elif ch == "\x1b":  # Escape or start of escape sequence
                import select

                r, _, _ = select.select([sys.stdin.fileno()], [], [], 0.05)
                if r:
                    # It's an escape sequence (e.g. arrow keys), read and discard it
                    sys.stdin.read(2)
                else:
                    # It's a plain Escape key press
                    cancel_event.set()
                    typeahead_buffer.clear()
            elif ch in ("\x7f", "\b"):  # Backspace
                if typeahead_buffer:
                    typeahead_buffer.pop()
            elif ch.isprintable() or ch == " ":
                typeahead_buffer.append(ch)

        is_thinking = asyncio.Event()
        is_thinking.set()

        async def _spinner() -> None:
            frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            i = 0
            spinner_active = False
            try:
                while not cancel_event.is_set():
                    if is_thinking.is_set():
                        sys.stdout.write(
                            f"\r  {cyan(frames[i % len(frames)])} {dim('thinking...')}"
                        )
                        sys.stdout.flush()
                        spinner_active = True
                        i += 1
                        try:
                            await asyncio.wait_for(cancel_event.wait(), 0.08)
                        except asyncio.TimeoutError:
                            pass
                    else:
                        wait_think = asyncio.create_task(is_thinking.wait())
                        wait_cancel = asyncio.create_task(cancel_event.wait())
                        await asyncio.wait(
                            [wait_think, wait_cancel],
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        if not wait_think.done():
                            wait_think.cancel()
                        if not wait_cancel.done():
                            wait_cancel.cancel()
            except asyncio.CancelledError:
                pass
            finally:
                if spinner_active and is_thinking.is_set():
                    sys.stdout.write("\r" + " " * 30 + "\r")
                    sys.stdout.flush()

        tools_used = 0

        async def _consume() -> None:
            nonlocal printer, tools_used
            reasoning_printer = StreamPrinter(base_style="\033[2m\033[90m")
            has_reasoned = False
            transitioned = False
            last_chunk_type = None
            start_time = time.time()
            iterator = agent.process_input(text).__aiter__()
            next_task: asyncio.Task[tuple[str, str]] | None = None
            try:
                while True:
                    next_task = asyncio.create_task(iterator.__anext__())  # type: ignore
                    cancel_wait = asyncio.create_task(cancel_event.wait())

                    done, _ = await asyncio.wait(
                        [next_task, cancel_wait],
                        timeout=0.2,
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    if cancel_event.is_set():
                        break

                    if next_task not in done:
                        # Only show spinner if we haven't started, or if we just finished a tool.
                        # This prevents the spinner from corrupting the current line if the network lags mid-sentence.
                        if last_chunk_type in (None, "tool"):
                            is_thinking.set()

                        inner_cancel_wait = asyncio.create_task(cancel_event.wait())
                        await asyncio.wait(
                            [next_task, inner_cancel_wait],
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        if not inner_cancel_wait.done():
                            inner_cancel_wait.cancel()

                        if cancel_event.is_set():
                            break

                    if not cancel_wait.done():
                        cancel_wait.cancel()

                    try:
                        chunk_tuple = next_task.result()
                    except StopAsyncIteration:
                        if is_thinking.is_set():
                            is_thinking.clear()
                            sys.stdout.write("\r" + " " * 30 + "\r")
                            sys.stdout.flush()
                        break

                    if is_thinking.is_set():
                        is_thinking.clear()
                        sys.stdout.write("\r" + " " * 30 + "\r")
                        sys.stdout.flush()

                    chunk_type, chunk = chunk_tuple

                    if chunk_type == "text":
                        if has_reasoned and not transitioned:
                            reasoning_printer.finish()
                            sys.stdout.write("\r\n")
                            sys.stdout.flush()
                            transitioned = True
                        printer.print_chunk(chunk)
                    elif chunk_type == "reasoning":
                        has_reasoned = True
                        reasoning_printer.print_chunk(chunk)
                    elif chunk_type == "tool_start":
                        tools_used += 1
                    elif chunk_type == "tool":
                        if has_reasoned and not transitioned:
                            reasoning_printer.finish()
                            sys.stdout.write("\r\n")
                            sys.stdout.flush()
                            transitioned = True
                        printer.finish()
                        sys.stdout.write(chunk)
                        sys.stdout.flush()

                        has_reasoned = False
                        transitioned = False

                    last_chunk_type = chunk_type
            except asyncio.CancelledError:
                pass
            finally:
                if next_task and not next_task.done():
                    next_task.cancel()
                    try:
                        await next_task
                    except Exception:
                        pass
                try:
                    if hasattr(iterator, "aclose"):
                        await iterator.aclose()
                except Exception:
                    pass
                if has_reasoned and not transitioned:
                    reasoning_printer.finish()
                    sys.stdout.write("\r\n")
                    sys.stdout.flush()
                printer.finish()

                latency = time.time() - start_time
                if tools_used > 0:
                    tool_str = (
                        f"Executed {tools_used} tool{'s' if tools_used != 1 else ''}"
                    )
                    sys.stdout.write(
                        f"\r\n  {dim(f'({tool_str} • {latency:.1f}s)')}\r\n"
                    )
                else:
                    sys.stdout.write(f"\r\n  {dim(f'({latency:.1f}s)')}\r\n")
                sys.stdout.flush()

        try:
            tty.setcbreak(fd)
            loop.add_reader(fd, on_input)

            spinner_task = asyncio.create_task(_spinner())
            task = asyncio.create_task(_consume())
            cancel_task = asyncio.create_task(cancel_event.wait())

            await asyncio.wait([task, cancel_task], return_when=asyncio.FIRST_COMPLETED)

            user_cancelled = cancel_event.is_set()

            cancel_event.set()
            if is_thinking.is_set():
                is_thinking.clear()
            await spinner_task

            if user_cancelled:
                auto_next_text = None
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                printer.finish()
                print(f"\r\n{dim('  (cancelled via Escape)')}")
                continue
            else:
                if (
                    agent.messages
                    and agent.messages[-1].role == "assistant"
                    and agent.messages[-1].content
                ):
                    if "<CONTINUE>" in agent.messages[-1].content:
                        auto_next_text = "<CONTINUE>"
                try:
                    await task  # raise any exceptions
                except asyncio.CancelledError:
                    pass

        except KeyboardInterrupt:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            printer.finish()
            print(f"\r\n{dim('  (interrupted)')}")
            continue
        finally:
            loop.remove_reader(fd)
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            agent.save_session()

        print()  # spacer after response

    # ── shutdown ──
    print(f"\n  {dim('← Shutting down…')}")
    await agent.shutdown()
    print(f"  {dim('← Goodbye. 🐑')}\n")
