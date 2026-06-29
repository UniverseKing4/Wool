"""multi_tool — execute multiple tools concurrently."""

from __future__ import annotations

from typing import Any

from wool.tools.base import Tool, ToolParameter, ToolResult


class MultiToolUse(Tool):
    """Wrapper to execute multiple tools concurrently."""

    @property
    def name(self) -> str:
        return "multi_tool_use"

    @property
    def description(self) -> str:
        return "Use this to execute MULTIPLE tools concurrently in a single step to bypass limitations."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="tool_calls",
                type="array",
                description="Array of tool calls. Each object must have 'name' and 'arguments' properties.",
                required=True,
                items_type="object",
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        # This tool is intercepted by the agent loop and expanded.
        # It should never actually be executed directly.
        return ToolResult(
            success=False,
            output="Error: multi_tool_use failed to parse 'tool_calls' array. Make sure you provide a valid JSON array of objects, where each object has a 'name' and 'arguments' field.",
        )
