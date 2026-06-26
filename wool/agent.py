"""Core agent — the brain of Wool.

Implements the full agentic loop:
    user message → LLM call → tool execution → LLM call → … → response
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator

from wool.config import CONFIG_DIR, WoolConfig
from wool.mcp import MCPManager
from wool.providers import (
    ChatMessage,
    OpenAICompatProvider,
    Provider,
    ProviderRegistry,
    ToolCall,
)
from wool.tools import ToolRegistry
from wool.tools.bash import ExecuteBash
from wool.tools.code_intel import CodeIntelligence
from wool.tools.fs_read import FileSystemRead
from wool.tools.fs_write import FileSystemWrite
from wool.tools.subagent import SubagentDelegation
from wool.tools.web_fetch import WebFetch
from wool.tools.web_search import WebSearch
from wool.utils.ansi import bold, cyan, dim, red, yellow

SYSTEM_PROMPT = """\
You are Wool, a powerful AI coding assistant running in a Linux terminal.
You have access to tools for file operations, code intelligence, bash execution, web access, and more.

Guidelines:
- Be direct, concise, and helpful.
- Write clean, production-quality code.
- When using tools, briefly explain what you are doing.
- After receiving tool results, you MUST ALWAYS provide a final text response summarising the findings or outcome. Never leave the user hanging without a final response, even if the tool output itself was detailed.
- Respect Linux file permissions and system security.
- You FULLY support parallel tool execution. If you need to perform multiple independent tasks (e.g. searching multiple files, spawning multiple subagents), you MUST invoke all of them concurrently in a single step!
- CRITICAL: You must use the native JSON tool calling format provided by the API. DO NOT use text-based tags like `<call:function{}>` to execute tools. Emit multiple standard JSON tool calls in your response natively.
"""

MAX_TOOL_ITERATIONS = 25


class WoolAgent:
    """Orchestrates conversation, tools, and providers."""

    def __init__(self, config: WoolConfig) -> None:
        self.config = config
        self.provider_registry = ProviderRegistry()
        self.tool_registry = ToolRegistry()
        self.mcp_manager = MCPManager()
        self.messages: list[ChatMessage] = []
        self.active_provider: Provider | None = None
        self.active_model: str | None = config.active_model
        self.total_usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self._active_bg_tasks: list[asyncio.Task[Any]] = []

        self._setup_tools()
        self._setup_providers()
        self.load_session()

    # ── bootstrapping ─────────────────────────────────────────────────────

    def _setup_tools(self) -> None:
        for tool in (
            ExecuteBash(),
            FileSystemRead(),
            FileSystemWrite(),
            CodeIntelligence(),
            WebFetch(),
            WebSearch(),
            SubagentDelegation(),
        ):
            self.tool_registry.register(tool)

    def _setup_providers(self) -> None:
        for name, pc in self.config.providers.items():
            provider = OpenAICompatProvider(
                name=pc.name,
                base_url=pc.base_url,
                api_key=pc.api_key,
            )
            self.provider_registry.register(provider)

        if self.config.active_provider:
            self.active_provider = self.provider_registry.get(
                self.config.active_provider,
            )

        if not self.active_provider and self.config.providers:
            first_name = next(iter(self.config.providers))
            self.active_provider = self.provider_registry.get(first_name)

        if self.active_provider:
            prov_cfg = self.config.providers.get(self.active_provider.name)
            if prov_cfg and prov_cfg.default_model:
                self.active_model = prov_cfg.default_model

    # ── system message ────────────────────────────────────────────────────

    def _ensure_system_message(self) -> None:
        if not self.messages or self.messages[0].role != "system":
            self.messages.insert(0, ChatMessage(role="system", content=SYSTEM_PROMPT))

    # ── main agentic loop ─────────────────────────────────────────────────

    async def process_input(self, user_input: str) -> AsyncIterator[tuple[str, str]]:
        """Process *user_input* through the full agent loop.

        Yields text chunks as they stream from the LLM.  Handles tool
        calls internally, looping back to the LLM until a text-only
        response is produced or the iteration limit is reached.
        """
        self._ensure_system_message()
        self.messages.append(ChatMessage(role="user", content=user_input))
        self.save_session()

        if not self.active_provider:
            self.messages.pop()
            self.save_session()
            yield (
                "text",
                (
                    "\n"
                    + red("No provider configured.")
                    + "\n"
                    + dim("  Use: /provider add <name> <base_url> <api_key>")
                    + "\n"
                ),
            )
            return

        model = self.active_model or "auto"

        # Collect tool schemas (built-in + MCP).
        all_schemas = self.tool_registry.get_schemas()
        all_schemas.extend(self.mcp_manager.get_all_tools())

        for iteration in range(1, MAX_TOOL_ITERATIONS + 1):
            accumulated_text = ""
            accumulated_reasoning = ""
            pending_tool_calls: list[ToolCall] = []
            last_usage = None

            # Ensure messages are squashed to prevent consecutive roles breaking upstream proxies/LLMs
            squashed_messages: list[ChatMessage] = []
            for msg in self.messages:
                if not squashed_messages:
                    squashed_messages.append(ChatMessage.from_dict(msg.to_dict()))
                else:
                    last_msg = squashed_messages[-1]
                    if last_msg.role == msg.role and msg.role in ("user", "assistant"):
                        if isinstance(last_msg.content, str) and isinstance(msg.content, str):
                            last_msg.content += "\n\n" + msg.content
                        elif msg.content:
                            last_msg.content = msg.content
                        if msg.tool_calls:
                            if not last_msg.tool_calls:
                                last_msg.tool_calls = []
                            last_msg.tool_calls.extend(msg.tool_calls)
                    else:
                        squashed_messages.append(ChatMessage.from_dict(msg.to_dict()))

            try:
                async for event in self.active_provider.chat_completion_stream(
                    messages=squashed_messages,
                    model=model,
                    tools=all_schemas or None,
                    temperature=0.0,
                ):
                    if event.type == "text":
                        accumulated_text += event.content
                        yield "text", event.content
                    elif event.type == "reasoning":
                        accumulated_reasoning += event.content
                        yield "reasoning", event.content
                    elif event.type == "tool_call" and event.tool_call:
                        pending_tool_calls.append(event.tool_call)
                    elif event.type == "usage" and event.usage:
                        last_usage = event.usage
                        for k, v in event.usage.items():
                            if isinstance(v, int):
                                self.total_usage[k] = self.total_usage.get(k, 0) + v
                    elif event.type == "error":
                        yield "text", "\n" + red(f"Error: {event.content}") + "\n"
                        return
            except BaseException as exc:
                if iteration == 1 and not accumulated_text and not pending_tool_calls:
                    self.messages.pop()
                    self.save_session()
                elif accumulated_text or pending_tool_calls:
                    fc = accumulated_text
                    if accumulated_reasoning:
                        fc = f"<think>\n{accumulated_reasoning}\n</think>\n{fc}"
                    self.messages.append(
                        ChatMessage(
                            role="assistant",
                            content=fc or None,
                            tool_calls=pending_tool_calls or None,
                            usage=last_usage,
                        )
                    )
                    self.save_session()

                if isinstance(exc, Exception):
                    yield "text", "\n" + red(f"Provider error: {exc}") + "\n"
                    return
                raise

            # Record the assistant turn.
            final_content = accumulated_text
            if accumulated_reasoning:
                final_content = (
                    f"<think>\n{accumulated_reasoning}\n</think>\n{final_content}"
                )

            self.messages.append(
                ChatMessage(
                    role="assistant",
                    content=final_content or None,
                    tool_calls=pending_tool_calls or None,
                    usage=last_usage,
                )
            )
            self.save_session()

            # If there are no tool calls, check for background tasks.
            if not pending_tool_calls:
                if hasattr(self, "_active_bg_tasks") and self._active_bg_tasks:
                    bg_tasks = self._active_bg_tasks
                    self._active_bg_tasks = []

                    yield (
                        "tool",
                        f"\r\n  {dim('┌─')} {cyan('System')} {dim('──────────────────────────────────────────')}\r\n",
                    )
                    yield (
                        "tool",
                        f"  {dim('│')} {dim('Waiting for background subagents to finish...')}\r\n",
                    )
                    yield (
                        "tool",
                        f"  {dim('└──────────────────────────────────────────────────')}\r\n\r\n",
                    )

                    results = await asyncio.gather(*bg_tasks, return_exceptions=True)

                    combined_result = []
                    for i, res in enumerate(results):
                        if isinstance(res, BaseException):
                            combined_result.append(f"Subagent {i + 1} failed: {res}")
                        else:
                            bg_tc, bg_res = res
                            combined_result.append(
                                f"Subagent {bg_tc.id} Result:\n{bg_res}"
                            )

                    final_text = "\n\n".join(combined_result)

                    output_lines = final_text.splitlines()
                    num_lines = len(output_lines)
                    yield (
                        "tool",
                        f"  {dim('┌─')} {cyan('System')} {bold(f'Background Results ({num_lines} lines):')} {dim('─────────────')}\r\n",
                    )
                    for line in output_lines:
                        yield "tool", f"  {dim('│')} {dim(line)}\r\n"
                    yield (
                        "tool",
                        f"  {dim('└──────────────────────────────────────────────────')}\r\n\r\n",
                    )

                    self.messages.append(
                        ChatMessage(
                            role="user",
                            content=f"The background subagents have finished. Here are their final results:\n\n{final_text}\n\nPlease provide a final summary of these results to the user.",
                        )
                    )
                    self.save_session()
                    continue
                else:
                    return

            original_pending_tool_calls = pending_tool_calls

            # Expand use_subagent with multiple tasks to bypass proxy limitations
            expanded_tool_calls = []
            expansion_map: dict[
                str, list[str]
            ] = {}  # original_id -> list of expanded_ids

            for tc in pending_tool_calls:
                if tc.name == "use_subagent":
                    try:
                        args = json.loads(tc.arguments) if tc.arguments else {}
                        tasks_array = args.get("tasks", [])
                        if tasks_array and isinstance(tasks_array, list):
                            expanded_ids = []
                            for i, t in enumerate(tasks_array):
                                new_args = args.copy()
                                new_args.pop("tasks", None)
                                new_args["task"] = t
                                expanded_id = f"{tc.id}_{i}"
                                expanded_ids.append(expanded_id)
                                expanded_tool_calls.append(
                                    ToolCall(
                                        id=expanded_id,
                                        name="use_subagent",
                                        arguments=json.dumps(new_args),
                                    )
                                )
                            expansion_map[tc.id] = expanded_ids
                            continue
                    except Exception:
                        pass
                expanded_tool_calls.append(tc)

            pending_tool_calls = expanded_tool_calls

            # Execute each tool call concurrently and feed results back as they finish.
            async def execute_tool(
                tc: ToolCall,
            ) -> tuple[ToolCall, dict[str, Any], str]:
                try:
                    args: dict[str, Any] = (
                        json.loads(tc.arguments) if tc.arguments else {}
                    )
                except json.JSONDecodeError:
                    args = {}

                tool = self.tool_registry.get(tc.name)
                if tool:
                    try:
                        result = await tool.execute(**args)
                        result_text = (
                            result.output
                            if result.success
                            else f"Error: {result.error or result.output}"
                        )
                    except Exception as exc:
                        result_text = f"Tool execution error: {exc}"
                else:
                    # Fall through to MCP.
                    try:
                        mcp_result = await self.mcp_manager.call_tool(tc.name, args)
                        result_text = (
                            json.dumps(mcp_result)
                            if isinstance(mcp_result, dict)
                            else str(mcp_result)
                        )
                    except Exception as exc:
                        result_text = f"Tool not found: {exc}"

                return tc, args, result_text

            tasks = {}
            for tc in pending_tool_calls:
                if tc.name == "use_subagent":
                    # Run in background but save the task so we can wait for it at the end of the turn
                    async def run_bg_subagent(bg_tc):
                        _, _, bg_res = await execute_tool(bg_tc)
                        return bg_tc, bg_res

                    bg_task = asyncio.create_task(run_bg_subagent(tc))
                    if not hasattr(self, "_active_bg_tasks"):
                        self._active_bg_tasks = []
                    self._active_bg_tasks.append(bg_task)

                    # Return immediate success to the LLM so it can continue streaming the current turn!
                    async def instant_success(tc):
                        return (
                            tc,
                            {},
                            "Subagent successfully spawned and is running in the background. You may continue your work.",
                        )

                    tasks[tc.id] = asyncio.create_task(instant_success(tc))
                else:
                    tasks[tc.id] = asyncio.create_task(execute_tool(tc))

            # 1. Print all tool headers and arguments IMMEDIATELY
            for tc in pending_tool_calls:
                yield "tool_start", tc.name
                yield (
                    "tool",
                    f"  {dim('┌─')} {cyan(tc.name)} {dim('──────────────────────────────────────────')}\r\n",
                )

                try:
                    tc_args: dict[str, Any] = (
                        json.loads(tc.arguments) if tc.arguments else {}
                    )
                except json.JSONDecodeError:
                    tc_args = {}

                if tc_args:
                    args_fmt = json.dumps(tc_args, indent=2)
                    yield "tool", f"  {dim('│')} {bold('Arguments:')}\r\n"
                    for line in args_fmt.splitlines():
                        yield "tool", f"  {dim('│')} {line}\r\n"

                if tc.name == "use_subagent":
                    yield (
                        "tool",
                        f"  {dim('└─')} {dim('[Spawned background task]')}\r\n\r\n",
                    )
                else:
                    yield "tool", f"  {dim('└─')} {dim('[Executing...]')}\r\n\r\n"

            # 2. Wait for them as they complete and print results in separate boxes!
            completed_results: dict[str, str] = {}
            try:
                for completed_task in asyncio.as_completed(tasks.values()):
                    tc, args, result_text = await completed_task

                    # Cap result length to avoid excessive memory usage.
                    if len(result_text) > 30_000:
                        result_text = result_text[:30_000] + "\n… (truncated)"

                    completed_results[tc.id] = result_text

                    # Show immersive full output with ANSI borders for the result
                    output_lines = result_text.splitlines()
                    num_lines = len(output_lines)

                    yield (
                        "tool",
                        f"  {dim('┌─')} {cyan(tc.name)} {bold(f'Result ({num_lines} lines):')} {dim('─────────────')}\r\n",
                    )
                    for line in output_lines:
                        yield "tool", f"  {dim('│')} {dim(line)}\r\n"
                    yield (
                        "tool",
                        f"  {dim('└──────────────────────────────────────────────────')}\r\n\r\n",
                    )
            finally:
                for t in tasks.values():
                    if not t.done():
                        t.cancel()

            # 3. Merge expanded tool results back into original tool call IDs
            for original_tc in original_pending_tool_calls:
                if original_tc.id in expansion_map:
                    expanded_ids = expansion_map[original_tc.id]
                    combined_result = []
                    for i, exp_id in enumerate(expanded_ids):
                        combined_result.append(
                            f"--- Subagent {i + 1} Output ---\n{completed_results.get(exp_id, '')}"
                        )
                    final_result_text = "\n\n".join(combined_result)
                else:
                    final_result_text = completed_results.get(original_tc.id, "")

                self.messages.append(
                    ChatMessage(
                        role="tool",
                        content=final_result_text,
                        tool_call_id=original_tc.id,
                        name=original_tc.name,
                    )
                )

            # Force Gemini to continue the task or summarize, preventing 0-token silent exits
            self.messages.append(
                ChatMessage(
                    role="user",
                    content="Tool execution complete. Please continue with the rest of the task, or provide a final summary.",
                )
            )

            self.save_session()

            # Loop continues — LLM will process the tool results.

        # Safety limit reached.
        yield "text", "\n" + yellow("⚠ Reached maximum tool iterations.") + "\n"

    # ── session management ────────────────────────────────────────────────

    def get_session_path(self, session_name: str | None = None) -> Path:
        name = session_name or self.config.active_session
        sess_dir = CONFIG_DIR / "sessions"
        sess_dir.mkdir(parents=True, exist_ok=True)
        return sess_dir / f"{name}.json"

    def load_session(self) -> None:
        path = self.get_session_path()
        if not path.exists():
            self.messages = []
            self.total_usage = {}
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.messages = [ChatMessage.from_dict(m) for m in data.get("messages", [])]
            self.total_usage = data.get("total_usage", {})
        except Exception:
            self.messages = []
            self.total_usage = {}

    def save_session(self) -> None:
        if not self.messages and not getattr(
            self, "_history_cleared_explicitly", False
        ):
            # Don't wipe out the session on disk if we just started a fresh session
            # and haven't done anything yet.
            return

        path = self.get_session_path()
        data = {
            "messages": [m.to_dict() for m in self.messages],
            "total_usage": self.total_usage,
        }

        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        temp_path.replace(path)

    def clear_history(self) -> None:
        self.messages.clear()
        self.total_usage = {}
        self._history_cleared_explicitly = True
        self.save_session()

    async def shutdown(self) -> None:
        self.save_session()
        if hasattr(self, "_active_bg_tasks"):
            for t in self._active_bg_tasks:
                if not t.done():
                    t.cancel()
            await asyncio.gather(*self._active_bg_tasks, return_exceptions=True)
            self._active_bg_tasks.clear()
        await self.provider_registry.close_all()
        await self.mcp_manager.disconnect_all()
