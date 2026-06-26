"""In-chat slash commands for Wool.

Every command prints its output directly and returns ``False`` (continue
the REPL) or ``True`` (exit the REPL).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Coroutine

from wool.config import ProviderConfig
from wool.providers import OpenAICompatProvider
from wool.utils.ansi import (
    bold,
    cyan,
    dim,
    green,
    magenta,
    red,
    white,
    info,
    error as ansi_error,
    success,
    warning,
)

if TYPE_CHECKING:
    from wool.agent import WoolAgent


class SlashCommandHandler:
    """Registry and dispatcher for ``/``-prefixed REPL commands."""

    def __init__(self, agent: WoolAgent) -> None:
        self.agent = agent

    # ── public API ────────────────────────────────────────────────────────

    @staticmethod
    def is_command(text: str) -> bool:
        return text.lstrip().startswith("/")

    async def handle(self, raw: str) -> bool:
        """Dispatch *raw* input.  Returns ``True`` to exit the REPL."""
        parts = raw.strip().split(None, 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        dispatch: dict[str, Callable[..., Coroutine[Any, Any, bool]]] = {
            "/help": self._help,
            "/provider": self._provider,
            "/model": self._model,
            "/models": self._models,
            "/session": self._session,
            "/sessions": self._session,
            "/new": self._new,
            "/rename": self._rename,
            "/fork": self._fork,
            "/tools": self._tools,
            "/mcp": self._mcp,
            "/mcps": self._mcp,
            "/usage": self._usage,
            "/context": self._context,
            "/goal": self._goal,
            "/clear": self._clear,
            "/status": self._status,
            "/rewind": self._rewind,
            "/copy": self._copy,
            "/exit": self._exit,
            "/quit": self._exit,
            "/compact": self._compact,
        }

        handler = dispatch.get(cmd)
        if handler is None:
            ansi_error(f"Unknown command: {cmd}  (try /help)")
            return False
        return await handler(args)

    # ── /help ─────────────────────────────────────────────────────────────

    async def _help(self, _args: str) -> bool:
        print()
        print(f"  {bold(cyan('Wool Commands'))}")
        print()
        cmds = [
            ("/help", "Show this help message"),
            ("/provider list|add|remove|switch", "Manage AI providers"),
            ("/model [list|switch <id>]", "View or change the active model"),
            ("/models", "List available models for the active provider"),
            ("/session(s)", "Open interactive session menu"),
            ("/new [name]", "Create and switch to a new session"),
            ("/rename <new_name>", "Rename the current session"),
            ("/fork [name]", "Fork current conversation to a new session"),
            ("/rewind", "Interactively rewind history to a specific message"),
            ("/tools", "List available tools"),
            ("/mcp list|connect|disconnect", "Manage MCP servers"),
            ("/goal <task>", "Set a goal and work autonomously until complete"),
            ("/usage", "View token usage for the current session"),
            ("/context", "View detailed token breakdown of current context"),
            ("/clear", "Clear conversation history"),
            ("/compact", "Compact history (keep system + last 4 turns)"),
            ("/status", "Show current session status"),
            ("/copy", "Copy the last AI response to clipboard"),
            ("/exit, /quit", "Exit Wool"),
        ]
        for name, desc in cmds:
            print(f"  {green(name):>42s}  {dim(desc)}")
        print()
        return False

    # ── /provider ─────────────────────────────────────────────────────────

    async def _provider(self, args: str) -> bool:
        parts = args.strip().split()
        sub = parts[0] if parts else "list"

        if sub == "list":
            providers = self.agent.config.providers
            if not providers:
                warning(
                    "No providers configured.  Use /provider add <name> <base_url> <api_key>"
                )
            else:
                print()
                for name, pc in providers.items():
                    active = " ◀" if name == self.agent.config.active_provider else ""
                    print(f"  {green(name)}{cyan(active)}  {dim(pc.base_url)}")
                print()

        elif sub == "add":
            if len(parts) < 4:
                ansi_error("Usage: /provider add <name> <base_url> <api_key>")
                return False
            name, base_url, api_key = parts[1], parts[2], parts[3]
            pc = ProviderConfig(name=name, base_url=base_url, api_key=api_key)
            self.agent.config.add_provider(pc)
            # Register the provider in the runtime registry too.
            provider = OpenAICompatProvider(
                name=name, base_url=base_url, api_key=api_key
            )
            self.agent.provider_registry.register(provider)
            if self.agent.active_provider is None:
                self.agent.active_provider = provider
            success(f"Provider '{name}' added.")

        elif sub == "remove":
            if len(parts) < 2:
                ansi_error("Usage: /provider remove <name>")
                return False
            name = parts[1]
            self.agent.config.remove_provider(name)
            self.agent.provider_registry.remove(name)
            if self.agent.active_provider and self.agent.active_provider.name == name:
                # Pick the next available provider.
                names = self.agent.provider_registry.list_providers()
                self.agent.active_provider = (
                    self.agent.provider_registry.get(names[0]) if names else None
                )
                if self.agent.active_provider:
                    self.agent.config.active_provider = self.agent.active_provider.name
                    prov_cfg = self.agent.config.providers.get(
                        self.agent.active_provider.name
                    )
                    self.agent.active_model = (
                        prov_cfg.default_model if prov_cfg else None
                    )
                else:
                    self.agent.config.active_provider = None
                    self.agent.active_model = None
            success(f"Provider '{name}' removed.")

        elif sub == "switch":
            if len(parts) < 2:
                ansi_error("Usage: /provider switch <name>")
                return False
            name = parts[1]
            p = self.agent.provider_registry.get(name)
            if not p:
                ansi_error(f"Provider '{name}' not found.")
                return False
            self.agent.active_provider = p
            self.agent.config.active_provider = name

            p_config = self.agent.config.providers.get(name)
            if p_config and p_config.default_model:
                self.agent.active_model = p_config.default_model
                self.agent.config.active_model = p_config.default_model

            self.agent.config.save()
            success(f"Switched to provider '{name}'.")
        else:
            # Treat as direct provider switch
            p = self.agent.provider_registry.get(sub)
            if not p:
                ansi_error(
                    f"Provider '{sub}' not found. Try: list, add, remove, switch"
                )
                return False
            self.agent.active_provider = p
            self.agent.config.active_provider = sub

            p_config = self.agent.config.providers.get(sub)
            if p_config and p_config.default_model:
                self.agent.active_model = p_config.default_model
                self.agent.config.active_model = p_config.default_model

            self.agent.config.save()
            success(f"Switched to provider '{sub}'.")

        return False

    # ── /model ────────────────────────────────────────────────────────────

    async def _models(self, args: str) -> bool:
        return await self._model("list")

    async def _model(self, args: str) -> bool:
        parts = args.strip().split()
        sub = parts[0] if parts else "show"

        if sub == "show" or not args.strip():
            model = self.agent.active_model or "auto"
            provider_name = (
                self.agent.active_provider.name
                if self.agent.active_provider
                else "none"
            )
            print(
                f"\n  {dim('Model:')} {cyan(model)}  {dim('on')} {green(provider_name)}\n"
            )

        elif sub == "list":
            if not self.agent.active_provider:
                ansi_error("No active provider.")
                return False
            info("Fetching models...")
            try:
                models = await self.agent.active_provider.list_models()
                print()
                for m in models[:50]:
                    print(f"  {cyan(m.id)}")
                if len(models) > 50:
                    print(f"  {dim(f'... and {len(models) - 50} more')}")
                print()
            except Exception as exc:
                ansi_error(f"Failed to fetch models: {exc}")

        elif sub == "switch":
            if len(parts) < 2:
                ansi_error("Usage: /model switch <model_id>")
                return False
            model_id = parts[1]
            self.agent.active_model = model_id
            self.agent.config.active_model = model_id
            if (
                self.agent.active_provider
                and self.agent.active_provider.name in self.agent.config.providers
            ):
                self.agent.config.providers[
                    self.agent.active_provider.name
                ].default_model = model_id
            self.agent.config.save()
            success(f"Model set to '{model_id}'.")

        else:
            # Treat as direct model switch.
            self.agent.active_model = sub
            self.agent.config.active_model = sub
            if (
                self.agent.active_provider
                and self.agent.active_provider.name in self.agent.config.providers
            ):
                self.agent.config.providers[
                    self.agent.active_provider.name
                ].default_model = sub
            self.agent.config.save()
            success(f"Model set to '{sub}'.")

        return False

    # ── /tools ────────────────────────────────────────────────────────────

    async def _tools(self, _args: str) -> bool:
        tools = self.agent.tool_registry.list_tools()
        mcp_tools = self.agent.mcp_manager.get_all_tools()
        print()
        print(f"  {bold('Built-in tools')} ({len(tools)}):")
        for t in tools:
            print(f"    {green(t.name):>30s}  {dim(t.description[:60])}")
        if mcp_tools:
            print(f"\n  {bold('MCP tools')} ({len(mcp_tools)}):")
            for mcp_t in mcp_tools:
                fn = mcp_t.get("function", {})
                print(
                    f"    {magenta(fn.get('name', '?')):>30s}  {dim(fn.get('description', '')[:60])}"
                )
        print()
        return False

    # ── /mcp ──────────────────────────────────────────────────────────────

    async def _mcp(self, args: str) -> bool:
        import shlex

        parts = shlex.split(args.strip()) if args.strip() else []
        sub = parts[0] if parts else "list"

        if sub == "list":
            servers = self.agent.mcp_manager.list_servers()
            if not servers:
                info("No MCP servers connected.")
            else:
                print()
                for s in servers:
                    status = green("●") if s["connected"] else red("○")
                    tool_count = s["tools"]
                    print(f"  {status} {cyan(s['name'])}  {dim(f'{tool_count} tools')}")
                print()

        elif sub == "connect":
            if len(parts) < 3:
                ansi_error("Usage: /mcp connect <name> <command...>")
                ansi_error('   OR: /mcp connect <name> http <url> [-H "Header: Value"]')
                ansi_error("  e.g. /mcp connect myserver npx -y @my/mcp-server")
                ansi_error(
                    '  e.g. /mcp connect web http https://mcp.exa.ai/mcp -H "Authorization: Bearer 123"'
                )
                return False
            name = parts[1]

            command = None
            url = None
            headers = None
            if parts[2] == "http" and len(parts) > 3:
                url = parts[3]
                headers = {}
                i = 4
                while i < len(parts):
                    if parts[i] in ("-H", "--header") and i + 1 < len(parts):
                        header_str = parts[i + 1]
                        if ":" in header_str:
                            k, v = header_str.split(":", 1)
                            headers[k.strip()] = v.strip()
                        i += 2
                    else:
                        ansi_error(f"Unknown argument: {parts[i]}")
                        return False
            else:
                command = parts[2:]

            if not command and not url:
                ansi_error("Provide the command or http url to launch the MCP server.")
                return False

            info(f"Connecting to MCP server '{name}'...")
            try:
                await self.agent.mcp_manager.connect(
                    name, command=command, url=url, headers=headers
                )
                if command:
                    self.agent.config.mcp_servers[name] = {"command": command}
                else:
                    cfg = {"type": "http", "url": url}
                    if headers:
                        cfg["headers"] = headers
                    self.agent.config.mcp_servers[name] = cfg
                self.agent.config.save()
                tools = self.agent.mcp_manager._clients[name].tools
                success(f"Connected to '{name}' — {len(tools)} tools available.")
            except Exception as exc:
                ansi_error(f"Failed to connect: {exc}")

        elif sub == "disconnect":
            if len(parts) < 2:
                ansi_error("Usage: /mcp disconnect <name>")
                return False
            name = parts[1]
            await self.agent.mcp_manager.disconnect(name)
            self.agent.config.mcp_servers.pop(name, None)
            self.agent.config.save()
            success(f"Disconnected from '{name}'.")

        else:
            ansi_error("Unknown sub-command.  Try: list, connect, disconnect")

        return False

    # ── /session ──────────────────────────────────────────────────────────

    async def _session(self, args: str) -> bool:
        from wool.config import CONFIG_DIR

        parts = args.strip().split()
        sub = parts[0] if parts else "list"
        sess_dir = CONFIG_DIR / "sessions"

        if sub == "list":
            sess_dir.mkdir(parents=True, exist_ok=True)
            from wool.utils.menu import run_session_menu

            last_idx = -1
            while True:
                files = {f.stem for f in sess_dir.glob("*.json")}
                files.add(self.agent.config.active_session)
                session_list = sorted(files)

                result = run_session_menu(
                    session_list, self.agent.config.active_session, initial_idx=last_idx
                )
                if not result:
                    return False

                action, selected_name, menu_idx = result
                if action == "delete":
                    name = selected_name

                    if name == "default":
                        is_active = name == self.agent.config.active_session
                        path = self.agent.get_session_path(name)
                        already_cleared = False

                        if is_active:
                            already_cleared = len(self.agent.messages) == 0
                        else:
                            if path.exists():
                                try:
                                    import json

                                    data = json.loads(path.read_text(encoding="utf-8"))
                                    already_cleared = len(data.get("messages", [])) == 0
                                except Exception:
                                    already_cleared = True
                            else:
                                already_cleared = True

                        if already_cleared:
                            info("Session 'default' is already completely cleared.")
                        else:
                            if is_active:
                                self.agent.clear_history()
                            else:
                                if path.exists():
                                    path.write_text(
                                        '{"messages": [], "total_usage": {}}\n',
                                        encoding="utf-8",
                                    )
                            success("Session 'default' history cleared.")

                        last_idx = menu_idx
                        continue

                    path = self.agent.get_session_path(name)
                    if path.exists():
                        path.unlink()
                        success(f"Session '{name}' deleted.")
                    else:
                        ansi_error(f"Session '{name}' not found.")
                        last_idx = menu_idx
                        continue

                    if name == self.agent.config.active_session:
                        if name != "default":
                            self.agent.config.active_session = "default"
                            self.agent.config.save()
                            self.agent.load_session()
                            success("Switched to session 'default'.")
                        else:
                            self.agent.clear_history()

                    # Update index to stay in place. Since the element is deleted,
                    # the next item shifts into menu_idx. If we deleted the last item,
                    # menu_idx is now out of bounds, so we cap it.
                    last_idx = min(menu_idx, len(session_list) - 2)
                    last_idx = max(0, last_idx)

                else:
                    self.agent.save_session()
                    self.agent.config.active_session = selected_name
                    self.agent.config.save()
                    self.agent.load_session()
                    self.agent.save_session()
                    success(f"Switched to session '{selected_name}'.")
                    return False

        elif sub == "new":
            if len(parts) < 2:
                import time

                name = f"session_{int(time.time())}"
            else:
                name = parts[1]

            if name == self.agent.config.active_session:
                info(f"Already in session '{name}'.")
                return False

            self.agent.save_session()
            self.agent.config.active_session = name
            self.agent.config.save()
            self.agent.load_session()
            self.agent.save_session()
            success(f"Switched to session '{name}'.")

        else:
            ansi_error("Unknown sub-command. Try: new")

        return False

    async def _new(self, args: str) -> bool:
        return await self._session(f"new {args}")

    async def _rename(self, args: str) -> bool:
        parts = args.strip().split()
        if not parts:
            ansi_error("Usage: /rename <new_name>")
            return False
        new_name = parts[0]
        old_path = self.agent.get_session_path()
        self.agent.config.active_session = new_name
        self.agent.config.save()
        new_path = self.agent.get_session_path()
        if old_path.exists():
            old_path.rename(new_path)
        self.agent.save_session()
        success(f"Session renamed to '{new_name}'.")
        return False

    async def _fork(self, args: str) -> bool:
        parts = args.strip().split()
        if not parts:
            import time

            new_name = f"{self.agent.config.active_session}_fork_{int(time.time())}"
        else:
            new_name = parts[0]

        if new_name == self.agent.config.active_session:
            ansi_error("Cannot fork to the same session name.")
            return False

        import copy

        msgs_copy = copy.deepcopy(self.agent.messages)

        # Switch session
        self.agent.save_session()
        self.agent.config.active_session = new_name
        self.agent.config.save()
        self.agent.load_session()  # Clears current messages

        # Restore copied messages
        self.agent.messages = msgs_copy
        self.agent.save_session()
        success(f"Forked conversation to new session '{new_name}'.")
        return False

    # ── /goal ─────────────────────────────────────────────────────────────

    async def _goal(self, args: str) -> bool:
        if not args.strip():
            ansi_error("Usage: /goal <task description>")
            return False

        prompt = f"""[GOAL MODE ACTIVATED]
Your overarching goal is: {args.strip()}

You must work autonomously to completely fulfill this goal. 
If you need to execute tools, do so. 
At the end of every response, you MUST evaluate if the goal is completely finished.
If the goal is NOT finished, you MUST output the exact string `<CONTINUE>` at the very end of your response. This will trigger the system to automatically let you take another turn.
If the goal IS finished, output `<FINISHED>` and explain what you accomplished.
"""
        import readline

        try:

            def pre_input_hook():
                readline.insert_text(prompt)
                readline.redisplay()
                readline.set_pre_input_hook(None)

            readline.set_pre_input_hook(pre_input_hook)
        except ImportError:
            pass

        success(f"Goal mode primed! Press Enter to start: '{args.strip()}'")
        return False

    # ── /usage ────────────────────────────────────────────────────────────

    async def _usage(self, _args: str) -> bool:
        prompt = self.agent.total_usage.get("prompt_tokens", 0)
        completion = self.agent.total_usage.get("completion_tokens", 0)
        total = self.agent.total_usage.get("total_tokens", prompt + completion)

        current_ctx = 0
        for msg in reversed(self.agent.messages):
            if msg.role == "assistant" and getattr(msg, "usage", None):
                usage = msg.usage
                if usage:
                    current_ctx = usage.get("prompt_tokens", 0) + usage.get(
                        "completion_tokens", 0
                    )
                break

        print()
        print(f"  {bold(cyan('Session Token Usage (Dynamic)'))}")
        print(f"  {dim('Cumulative Prompt:')}     {prompt:,}")
        print(f"  {dim('Cumulative Completion:')} {completion:,}")
        print(f"  {dim('Cumulative Total:')}      {bold(f'{total:,}')}")
        print()
        if current_ctx > 0:
            print(f"  {dim('Current Context Size:')}  {current_ctx:,} {dim('tokens')}")
            print()
        return False

    # ── /context ──────────────────────────────────────────────────────────

    async def _context(self, _args: str) -> bool:
        def est_tokens(text: str | None) -> int:
            if not text:
                return 0
            return max(1, len(text) // 4)

        import json

        user_msgs = 0
        agent_resp = 0
        tool_calls = 0

        for msg in self.agent.messages:
            if msg.role == "user":
                user_msgs += est_tokens(msg.content)
            elif msg.role == "assistant":
                # For context weight, we use character count estimation instead of
                # generated tokens, because generated tokens reflect output effort,
                # whereas input tokens reflect string length.
                agent_resp += est_tokens(msg.content)
                if getattr(msg, "tool_calls", None):
                    try:
                        tc_list = msg.tool_calls
                        if tc_list:
                            tool_calls += est_tokens(
                                json.dumps([tc.to_dict() for tc in tc_list])
                            )
                    except Exception:
                        pass
            elif msg.role == "tool":
                tool_calls += est_tokens(msg.content)

        from wool.agent import SYSTEM_PROMPT

        sys_prompt = est_tokens(SYSTEM_PROMPT)

        try:
            builtin_schemas = []
            subagent_schemas = []
            for t in self.agent.tool_registry.list_tools():
                schema = t.to_openai_schema()
                if t.name == "use_subagent":
                    subagent_schemas.append(schema)
                else:
                    builtin_schemas.append(schema)
            builtin_tools = est_tokens(json.dumps(builtin_schemas))
            subagents = est_tokens(json.dumps(subagent_schemas))
        except Exception:
            builtin_tools = 0
            subagents = 0

        try:
            mcp_tools = est_tokens(json.dumps(self.agent.mcp_manager.get_all_tools()))
        except Exception:
            mcp_tools = 0

        total = (
            user_msgs
            + agent_resp
            + tool_calls
            + sys_prompt
            + builtin_tools
            + subagents
            + mcp_tools
        )

        print()
        print(f"  {bold(cyan('Context Breakdown (Estimated Tokens)'))}")
        print(f"  {dim('Total:')}             {bold(f'{total:,}')} {dim('tokens')}")
        print(f"  {green('◉')} {dim('User messages:')}   {user_msgs:,} {dim('tokens')}")
        print(
            f"  {green('◉')} {dim('Agent responses:')} {agent_resp:,} {dim('tokens')}"
        )
        print(
            f"  {green('◉')} {dim('Tool calls:')}      {tool_calls:,} {dim('tokens')}"
        )
        print(f"  {dim('□')}")
        print(f"  {cyan('⛁')} {dim('System prompt:')}   {sys_prompt:,} {dim('tokens')}")
        print(
            f"  {cyan('⛁')} {dim('Built-in tools:')}  {builtin_tools:,} {dim('tokens')}"
        )
        print(f"  {cyan('⛁')} {dim('Subagents:')}       {subagents:,} {dim('tokens')}")
        print(f"  {cyan('⛁')} {dim('MCP tools:')}       {mcp_tools:,} {dim('tokens')}")
        print()
        return False

    # ── /clear ────────────────────────────────────────────────────────────

    async def _clear(self, _args: str) -> bool:
        self.agent.clear_history()
        success("Conversation history cleared.")
        return False

    # ── /compact ──────────────────────────────────────────────────────────

    async def _compact(self, _args: str) -> bool:
        msgs = self.agent.messages
        system = [m for m in msgs if m.role == "system"]
        others = [m for m in msgs if m.role != "system"]

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

        # Find real user message indices
        user_msg_indices = [i for i, m in enumerate(others) if is_real_user(m)]
        if not user_msg_indices:
            info("No user messages to compact.")
            return False

        start_idx = user_msg_indices[-1]
        last_user_msg = others[start_idx]

        # Find the final assistant response text
        last_assistant_msg = None
        for m in reversed(others[start_idx:]):
            if m.role == "assistant" and m.content:
                last_assistant_msg = m
                break

        from wool.providers.base import ChatMessage

        recent = [last_user_msg]
        if last_assistant_msg:
            # Strip tool calls to make it a pure text response
            clean_ast = ChatMessage(
                role="assistant", content=last_assistant_msg.content
            )
            recent.append(clean_ast)

        # Everything else (older messages, tool calls, tool results) goes into the summary
        older_messages = [
            m for m in others if m is not last_user_msg and m is not last_assistant_msg
        ]

        if not older_messages:
            info("History is already perfectly compact.")
            return False

        info("Summarizing older messages...")
        import json

        summary_prompt = "Please summarize the following conversation concisely:\n\n"
        for m in older_messages:
            summary_prompt += (
                json.dumps(m.to_dict(), indent=2, ensure_ascii=False) + "\n\n"
            )

        from wool.providers.base import ChatMessage

        temp_msgs = system + [ChatMessage(role="user", content=summary_prompt)]

        if not self.agent.active_provider:
            ansi_error("No active provider.")
            return False

        model = self.agent.active_model or "auto"
        try:
            summary_text = ""
            async for ev in self.agent.active_provider.chat_completion_stream(
                temp_msgs, model
            ):
                if ev.type == "text":
                    summary_text += ev.content

            summary_msg = ChatMessage(
                role="system",
                content=f"Summary of previous conversation:\n{summary_text.strip()}",
            )

            from wool.utils.markdown import render_markdown

            print(
                f"\n{bold(magenta('Compact Summary:'))}\n{render_markdown(summary_text.strip())}\n"
            )

            self.agent.messages = system + [summary_msg] + recent
            success(f"Compacted to {len(recent)} messages and 1 summary.")
        except Exception as e:
            ansi_error(f"Failed to summarize: {e}")

        return False

    # ── /status ───────────────────────────────────────────────────────────

    async def _status(self, _args: str) -> bool:
        a = self.agent
        provider = a.active_provider.name if a.active_provider else "none"
        model = a.active_model or "auto"
        tools_n = len(a.tool_registry.list_tools())
        mcp_n = len(a.mcp_manager.list_servers())
        msgs = sum(1 for m in a.messages if m.role != "system")

        print()
        print(f"  {bold(cyan('Wool Status'))}")
        print(f"  {dim('Provider:')}  {green(provider)}")
        print(f"  {dim('Model:')}     {cyan(model)}")
        print(f"  {dim('Tools:')}     {white(str(tools_n))} {dim('built-in')}")
        print(f"  {dim('MCP:')}       {white(str(mcp_n))} {dim('servers')}")
        print(f"  {dim('History:')}   {white(str(msgs))} {dim('messages')}")
        print()
        return False

    # ── /rewind ───────────────────────────────────────────────────────────

    async def _rewind(self, _args: str) -> bool:
        from wool.utils.menu import run_rewind_menu

        # Build list of user messages
        user_msgs = []
        for i, m in enumerate(self.agent.messages):
            if m.role == "user" and m.content:
                if "Tool execution complete. Please continue" in m.content:
                    continue
                if (
                    "The background subagents have finished. Here are their final results:"
                    in m.content
                ):
                    continue
                # Replace newlines with spaces and truncate for display
                snippet = " ".join(m.content.split())
                if len(snippet) > 60:
                    snippet = snippet[:57] + "..."
                user_msgs.append((i, snippet))

        if not user_msgs:
            warning("No user messages found in this session.")
            return False

        target_idx = run_rewind_menu(user_msgs)
        if target_idx is None:
            return False

        selected_user_msg = self.agent.messages[target_idx].content

        # Drop the selected message and everything after it
        self.agent.messages = self.agent.messages[:target_idx]
        self.agent.save_session()

        if selected_user_msg:
            try:
                import readline

                def pre_input_hook():
                    readline.insert_text(selected_user_msg)
                    readline.redisplay()
                    readline.set_pre_input_hook(None)

                readline.set_pre_input_hook(pre_input_hook)
            except ImportError:
                # Fallback if readline is not available (e.g. Windows)
                pass

        success("Conversation history rewound successfully.")
        return False

    # ── /copy ─────────────────────────────────────────────────────────────

    async def _copy(self, _args: str) -> bool:
        # Find the last message with role == "assistant"
        last_msg = None
        for msg in reversed(self.agent.messages):
            if msg.role == "assistant" and msg.content:
                last_msg = msg.content
                break

        if not last_msg:
            warning("No AI response found to copy.")
            return False

        import sys
        import base64

        # 1. Try OSC 52 (works over SSH/Codespaces)
        try:
            b64 = base64.b64encode(last_msg.encode("utf-8")).decode("utf-8")
            # Send OSC 52 copy command to the terminal
            sys.stdout.write(f"\033]52;c;{b64}\a")
            sys.stdout.flush()
        except Exception:
            pass

        # 2. Try Pyperclip as fallback for local desktop users
        try:
            import pyperclip

            pyperclip.copy(last_msg)
        except Exception:
            # We don't print the pyperclip error anymore because OSC 52 likely succeeded
            # if they are in a terminal that supports it, or if they are headless they don't care.
            pass

        success("Copied the last AI response to clipboard.")
        return False

    # ── /exit ─────────────────────────────────────────────────────────────

    async def _exit(self, _args: str) -> bool:
        return True
