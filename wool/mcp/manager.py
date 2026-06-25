"""MCP manager — manages connections to multiple MCP servers."""

from __future__ import annotations

from typing import Any

from wool.mcp.client import MCPClient


class MCPManager:
    """Lifecycle manager for :class:`MCPClient` instances."""

    def __init__(self) -> None:
        self._clients: dict[str, MCPClient] = {}

    async def connect(
        self,
        name: str,
        command: list[str] | None = None,
        url: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        """Connect (or reconnect) to an MCP server."""
        if name in self._clients:
            await self._clients[name].disconnect()

        client = MCPClient(name=name, command=command, url=url, env=env)
        await client.connect()
        # Eagerly fetch tool list so they're available immediately.
        await client.list_tools()
        self._clients[name] = client

    async def disconnect(self, name: str) -> None:
        client = self._clients.pop(name, None)
        if client:
            await client.disconnect()

    async def disconnect_all(self) -> None:
        for client in list(self._clients.values()):
            try:
                await client.disconnect()
            except Exception:
                pass
        self._clients.clear()

    def list_servers(self) -> list[dict[str, Any]]:
        return [
            {
                "name": c.name,
                "connected": c.connected,
                "tools": len(c.tools),
            }
            for c in self._clients.values()
        ]

    def get_all_tools(self) -> list[dict]:
        """Return OpenAI-compatible tool schemas from all connected MCP servers."""
        schemas: list[dict] = []
        for client in self._clients.values():
            if not client.connected:
                continue
            for tool in client.tools:
                # MCP tools already have a similar structure; convert to OpenAI format.
                schemas.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.get("name", ""),
                            "description": tool.get("description", ""),
                            "parameters": tool.get(
                                "inputSchema", {"type": "object", "properties": {}}
                            ),
                        },
                    }
                )
        return schemas

    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        """Route a tool call to the correct MCP server."""
        for client in self._clients.values():
            if not client.connected:
                continue
            for tool in client.tools:
                if tool.get("name") == tool_name:
                    return await client.call_tool(tool_name, arguments)
        raise RuntimeError(f"MCP tool '{tool_name}' not found on any connected server.")
