"""Tool registry — central catalogue of available tools."""

from __future__ import annotations

from wool.tools.base import Tool


class ToolRegistry:
    """Holds named :class:`Tool` instances and generates OpenAI schemas."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def get_schemas(self) -> list[dict]:
        return [t.to_openai_schema() for t in self._tools.values()]

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)
