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
        headers: dict[str, str] | None = None,
    ) -> None:
        """Connect (or reconnect) to an MCP server."""
        if name in self._clients:
            await self._clients[name].disconnect()

        client = MCPClient(
            name=name, command=command, url=url, env=env, headers=headers
        )
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

    def _sanitize_schema(self, schema: Any) -> Any:
        """Recursively ensure JSON schema compatibility with strict providers (like Gemini)."""
        if not isinstance(schema, dict):
            return schema

        # Copy to avoid mutating original MCP schema reference which could affect future calls
        schema = dict(schema)

        # Gemini backend compilation hangs on complex union types (anyOf/allOf/oneOf).
        # We simplify them by just picking the first valid type and merging it in.
        for key in ["anyOf", "allOf", "oneOf"]:
            if key in schema and isinstance(schema[key], list) and len(schema[key]) > 0:
                first_option = self._sanitize_schema(schema[key][0])
                if isinstance(first_option, dict):
                    for k, v in first_option.items():
                        if k not in schema:
                            schema[k] = v
                del schema[key]

        if "type" in schema and isinstance(schema["type"], list):
            # Gemini only supports a single type string, pick the first non-null one
            types = [t for t in schema["type"] if t != "null"]
            schema["type"] = types[0] if types else "string"

        t = schema.get("type")

        if t == "array":
            if "items" not in schema:
                schema["items"] = {"type": "string"}
            else:
                schema["items"] = self._sanitize_schema(schema["items"])
        elif t == "object":
            if "properties" in schema:
                props = {}
                for k, v in schema["properties"].items():
                    props[k] = self._sanitize_schema(v)
                schema["properties"] = props

        return schema

    def get_all_tools(self) -> list[dict]:
        """Return OpenAI-compatible tool schemas from all connected MCP servers."""
        schemas: list[dict] = []
        for client in self._clients.values():
            if not client.connected:
                continue
            for tool in client.tools:
                # MCP tools already have a similar structure; convert to OpenAI format.
                raw_params = tool.get(
                    "inputSchema", {"type": "object", "properties": {}}
                )
                params = self._sanitize_schema(raw_params)
                schemas.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.get("name", ""),
                            "description": tool.get("description", ""),
                            "parameters": params,
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
