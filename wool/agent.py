"""Core agent — the brain of Wool.

Implements the full agentic loop:
    user message → LLM call → tool execution → LLM call → … → response
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from wool.config import WoolConfig, CONFIG_DIR
from wool.mcp import MCPManager
from wool.providers import (
    ChatMessage,
    OpenAICompatProvider,
    Provider,
    ProviderRegistry,
    StreamEvent,
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
from wool.utils.ansi import bold, cyan, dim, green, red, yellow

SYSTEM_PROMPT = """\
You are Wool, a powerful AI coding assistant running in a Linux terminal.
You have access to tools for file operations, code intelligence, bash execution, web access, and more.

Guidelines:
- Be direct, concise, and helpful.
- Write clean, production-quality code.
- When using tools, briefly explain what you are doing.
- After receiving tool results, summarise findings clearly.
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
        self.total_usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

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
                name=pc.name, base_url=pc.base_url, api_key=pc.api_key,
            )
            self.provider_registry.register(provider)

        if self.config.active_provider:
            self.active_provider = self.provider_registry.get(
                self.config.active_provider,
            )
        elif self.config.providers:
            first_name = next(iter(self.config.providers))
            self.active_provider = self.provider_registry.get(first_name)
            
        if self.active_provider:
            pc = self.config.providers.get(self.active_provider.name)
            if pc and pc.default_model:
                self.active_model = pc.default_model

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
            yield "text", (
                "\n" + red("No provider configured.") + "\n"
                + dim("  Use: /provider add <name> <base_url> <api_key>") + "\n"
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

            try:
                async for event in self.active_provider.chat_completion_stream(
                    messages=self.messages,
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
                        for k, v in event.usage.items():
                            if isinstance(v, int):
                                self.total_usage[k] = self.total_usage.get(k, 0) + v
                    elif event.type == "error":
                        yield "text", "\n" + red(f"Error: {event.content}") + "\n"
                        return
            except Exception as exc:
                yield "text", "\n" + red(f"Provider error: {exc}") + "\n"
                return

            # Record the assistant turn.
            final_content = accumulated_text
            if accumulated_reasoning:
                final_content = f"<think>\n{accumulated_reasoning}\n</think>\n{final_content}"
                
            self.messages.append(ChatMessage(
                role="assistant",
                content=final_content or None,
                tool_calls=pending_tool_calls or None,
            ))
            self.save_session()

            # If there are no tool calls, we're done.
            if not pending_tool_calls:
                return

            # Execute each tool call concurrently and feed results back as they finish.
            import asyncio
            
            async def execute_tool(tc):
                try:
                    args: dict[str, Any] = json.loads(tc.arguments) if tc.arguments else {}
                except json.JSONDecodeError:
                    args = {}

                tool = self.tool_registry.get(tc.name)
                if tool:
                    try:
                        result = await tool.execute(**args)
                        result_text = result.output if result.success else f"Error: {result.error or result.output}"
                    except Exception as exc:
                        result_text = f"Tool execution error: {exc}"
                else:
                    # Fall through to MCP.
                    try:
                        mcp_result = await self.mcp_manager.call_tool(tc.name, args)
                        result_text = json.dumps(mcp_result) if isinstance(mcp_result, dict) else str(mcp_result)
                    except Exception as exc:
                        result_text = f"Tool not found: {exc}"
                        
                return tc, args, result_text

            tasks = {tc.id: asyncio.create_task(execute_tool(tc)) for tc in pending_tool_calls}

            # 1. Print all tool headers and arguments IMMEDIATELY
            for tc in pending_tool_calls:
                yield "tool_start", tc.name
                yield "tool", f"  {dim('┌─')} {cyan(tc.name)} {dim('──────────────────────────────────────────')}\r\n"

                try:
                    args: dict[str, Any] = json.loads(tc.arguments) if tc.arguments else {}
                except json.JSONDecodeError:
                    args = {}

                if args:
                    args_fmt = json.dumps(args, indent=2)
                    yield "tool", f"  {dim('│')} {bold('Arguments:')}\r\n"
                    for line in args_fmt.splitlines():
                        yield "tool", f"  {dim('│')} {line}\r\n"
                        
                yield "tool", f"  {dim('└─')} {dim('[Running background task...]')}\r\n\r\n"

            # 2. Wait for them as they complete and print results in separate boxes!
            for completed_task in asyncio.as_completed(tasks.values()):
                tc, args, result_text = await completed_task

                # Cap result length to avoid excessive memory usage.
                if len(result_text) > 30_000:
                    result_text = result_text[:30_000] + "\n… (truncated)"

                # Show immersive full output with ANSI borders for the result
                output_lines = result_text.splitlines()
                num_lines = len(output_lines)
                
                yield "tool", f"  {dim('┌─')} {cyan(tc.name)} {bold(f'Result ({num_lines} lines):')} {dim('─────────────')}\r\n"
                for line in output_lines:
                    yield "tool", f"  {dim('│')} {dim(line)}\r\n"
                yield "tool", f"  {dim('└──────────────────────────────────────────────────')}\r\n\r\n"

                self.messages.append(ChatMessage(
                    role="tool",
                    content=result_text,
                    tool_call_id=tc.id,
                    name=tc.name,
                ))
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
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.messages = [ChatMessage.from_dict(m) for m in data.get("messages", [])]
        except Exception:
            self.messages = []

    def save_session(self) -> None:
        path = self.get_session_path()
        data = {"messages": [m.to_dict() for m in self.messages]}
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def clear_history(self) -> None:
        self.messages.clear()
        self.total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.save_session()

    async def shutdown(self) -> None:
        self.save_session()
        await self.provider_registry.close_all()
        await self.mcp_manager.disconnect_all()
