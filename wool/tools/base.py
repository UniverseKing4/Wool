"""Abstract base class and data structures for tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolParameter:
    """Describes one parameter of a tool."""

    name: str
    type: str  # "string" | "integer" | "boolean" | "array" | "object"
    description: str
    required: bool = True
    enum: list[str] | None = None
    default: Any = None


@dataclass
class ToolResult:
    """Outcome of a tool execution."""

    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Tool(ABC):
    """Every built-in tool must subclass this."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def parameters(self) -> list[ToolParameter]: ...

    def to_openai_schema(self) -> dict:
        """Convert to the OpenAI *function-calling* tool schema."""
        properties: dict[str, dict] = {}
        required: list[str] = []
        for p in self.parameters:
            prop: dict[str, Any] = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            if p.default is not None:
                prop["default"] = p.default
            properties[p.name] = prop
            if p.required:
                required.append(p.name)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult: ...
