"""Abstract base classes and data structures for AI providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, AsyncIterator


@dataclass
class Model:
    """A model exposed by a provider."""

    id: str
    name: str
    provider: str


@dataclass
class ChatMessage:
    """A single message in a chat conversation."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None
    usage: dict | None = None

    def to_dict(self) -> dict:
        """Serialise for the OpenAI-compatible API."""
        d: dict = {"role": self.role}
        if self.content is not None:
            d["content"] = self.content
        if self.tool_calls:
            d["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        if self.tool_call_id is not None:
            d["tool_call_id"] = self.tool_call_id
        if self.name is not None:
            d["name"] = self.name
        if self.usage is not None:
            d["usage"] = self.usage
        return d

    @classmethod
    def from_dict(cls, data: dict) -> ChatMessage:
        tcs = None
        if "tool_calls" in data:
            tcs = [ToolCall.from_dict(tc) for tc in data["tool_calls"]]
        return cls(
            role=data["role"],
            content=data.get("content"),
            tool_calls=tcs,
            tool_call_id=data.get("tool_call_id"),
            name=data.get("name"),
            usage=data.get("usage")
        )


@dataclass
class ToolCall:
    """A tool invocation requested by the model."""

    id: str
    name: str
    arguments: str  # raw JSON string

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": self.arguments},
        }

    @classmethod
    def from_dict(cls, data: dict) -> ToolCall:
        func = data.get("function", {})
        return cls(
            id=data["id"],
            name=func.get("name", ""),
            arguments=func.get("arguments", "")
        )


@dataclass
class StreamEvent:
    """A single event emitted during a streaming chat completion."""

    type: str  # "text" | "reasoning" | "tool_call" | "done" | "error" | "usage"
    content: str = ""
    tool_call: ToolCall | None = None
    finish_reason: str | None = None
    usage: dict[str, int] | None = None


class Provider(ABC):
    """Abstract AI provider."""

    def __init__(self, name: str, base_url: str, api_key: str) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @abstractmethod
    async def list_models(self) -> list[Model]:
        """Fetch available models from the provider."""

    @abstractmethod
    def chat_completion_stream(
        self,
        messages: list[ChatMessage],
        model: str,
        tools: list[dict] | None = None,
        temperature: float = 0.0,
    ) -> AsyncIterator[StreamEvent]:
        """Stream a chat completion, yielding ``StreamEvent`` objects."""

    @abstractmethod
    async def close(self) -> None:
        """Release underlying HTTP resources."""
