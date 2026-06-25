"""In-chat slash commands for Wool.

Every command prints its output directly and returns ``False`` (continue
the REPL) or ``True`` (exit the REPL).
"""

from __future__ import annotations

import shlex
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from wool.config import ProviderConfig
from wool.providers import OpenAICompatProvider
from wool.utils.ansi import (
    bold, cyan, dim, gray, green, magenta, red, yellow, white,
    info, error as ansi_error, success, warning,
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
            "/new": self._new,
            "/rename": self._rename,
            "/tools": self._tools,
            "/mcp": self._mcp,
            "/usage": self._usage,
            "/clear": self._clear,
            "/status": self._status,
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
            ("/session", "Open interactive session menu"),
            ("/new [name]", "Create and switch to a new session"),
            ("/rename <new_name>", "Rename the current session"),
            ("/tools", "List available tools"),
            ("/mcp list|connect|disconnect", "Manage MCP servers"),
            ("/usage", "View token usage for the current session"),
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
                warning("No providers configured.  Use /provider add <name> <base_url> <api_key>")
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
            provider = OpenAICompatProvider(name=name, base_url=base_url, api_key=api_key)
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
                    pc = self.agent.config.providers.get(self.agent.active_provider.name)
                    self.agent.active_model = pc.default_model if pc else None
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
            ansi_error("Unknown sub-command.  Try: list, add, remove, switch")

        return False

    # ── /model ────────────────────────────────────────────────────────────

    async def _models(self, args: str) -> bool:
        return await self._model("list")

    async def _model(self, args: str) -> bool:
        parts = args.strip().split()
        sub = parts[0] if parts else "show"

        if sub == "show" or not args.strip():
            model = self.agent.active_model or "auto"
            provider_name = self.agent.active_provider.name if self.agent.active_provider else "none"
            print(f"\n  {dim('Model:')} {cyan(model)}  {dim('on')} {green(provider_name)}\n")

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
            if self.agent.active_provider and self.agent.active_provider.name in self.agent.config.providers:
                self.agent.config.providers[self.agent.active_provider.name].default_model = model_id
            self.agent.config.save()
            success(f"Model set to '{model_id}'.")

        else:
            # Treat as direct model switch.
            self.agent.active_model = sub
            self.agent.config.active_model = sub
            if self.agent.active_provider and self.agent.active_provider.name in self.agent.config.providers:
                self.agent.config.providers[self.agent.active_provider.name].default_model = sub
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
            for t in mcp_tools:
                fn = t.get("function", {})
                print(f"    {magenta(fn.get('name', '?')):>30s}  {dim(fn.get('description', '')[:60])}")
        print()
        return False

    # ── /mcp ──────────────────────────────────────────────────────────────

    async def _mcp(self, args: str) -> bool:
        parts = args.strip().split()
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
            if len(parts) < 2:
                ansi_error("Usage: /mcp connect <name> <command...>")
                ansi_error("  e.g. /mcp connect myserver npx -y @my/mcp-server")
                return False
            name = parts[1]
            command = parts[2:] if len(parts) > 2 else None
            if not command:
                ansi_error("Provide the command to launch the MCP server.")
                return False
            info(f"Connecting to MCP server '{name}'...")
            try:
                await self.agent.mcp_manager.connect(name, command=command)
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
            
            while True:
                files = {f.stem for f in sess_dir.glob("*.json")}
                files.add(self.agent.config.active_session)
                session_list = sorted(files)
                
                result = run_session_menu(session_list, self.agent.config.active_session)
                if not result:
                    return False
                    
                action, selected_name = result
                if action == "delete":
                    name = selected_name
                    path = self.agent.get_session_path(name)
                    
                    if path.exists():
                        path.unlink()
                        success(f"Session '{name}' deleted.")
                    else:
                        ansi_error(f"Session '{name}' not found.")
                        continue
                        
                    if name == self.agent.config.active_session:
                        if name != "default":
                            self.agent.config.active_session = "default"
                            self.agent.config.save()
                            self.agent.load_session()
                            success("Switched to session 'default'.")
                        else:
                            self.agent.clear_history()
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

    # ── /usage ────────────────────────────────────────────────────────────

    async def _usage(self, _args: str) -> bool:
        usage = self.agent.total_usage
        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        total = usage.get("total_tokens", 0)
        
        print()
        print(f"  {bold(cyan('Session Token Usage'))}")
        print(f"  {dim('Prompt:')}     {prompt:,}")
        print(f"  {dim('Completion:')} {completion:,}")
        print(f"  {dim('Total:')}      {bold(f'{total:,}')}")
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
        if len(msgs) <= 5:
            info("History is already compact.")
            return False
        system = [m for m in msgs if m.role == "system"]
        recent = [m for m in msgs if m.role != "system"][-4:]
        self.agent.messages = system + recent
        success(f"Compacted to {len([m for m in self.agent.messages if m.role != 'system'])} messages.")
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

    # ── /copy ─────────────────────────────────────────────────────────────

    async def _copy(self, _args: str) -> bool:
        import pyperclip
        from pyperclip import PyperclipException
        
        # Find the last message with role == "assistant"
        for msg in reversed(self.agent.messages):
            if msg.role == "assistant" and msg.content:
                try:
                    pyperclip.copy(msg.content)
                    success("Copied the last AI response to clipboard.")
                except PyperclipException as e:
                    ansi_error(f"Clipboard error: {e}")
                return False
                
        warning("No AI response found to copy.")
        return False

    # ── /exit ─────────────────────────────────────────────────────────────

    async def _exit(self, _args: str) -> bool:
        return True
