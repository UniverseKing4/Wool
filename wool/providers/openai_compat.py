"""OpenAI-compatible provider — works with any API that exposes the
``/v1/chat/completions`` and ``/v1/models`` endpoints (OpenAI, OpenRouter,
Together, local vLLM/Ollama, etc.).
"""

from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

from wool.providers.base import (
    ChatMessage,
    Model,
    Provider,
    StreamEvent,
    ToolCall,
)


class OpenAICompatProvider(Provider):
    """Concrete provider for any OpenAI-compatible API."""

    def __init__(self, name: str, base_url: str, api_key: str) -> None:
        super().__init__(name, base_url, api_key)
        # Normalise: strip trailing /v1 so we always add it ourselves.
        _b = self.base_url
        if _b.endswith("/v1"):
            _b = _b[:-3]
        elif _b.endswith("/v1/"):
            _b = _b[:-4]
        self._api_base = _b.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=120, write=10, pool=10),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            follow_redirects=True,
        )

    # ── model listing ─────────────────────────────────────────────────────

    async def list_models(self) -> list[Model]:
        url = f"{self._api_base}/v1/models"
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            data = resp.json().get("data", [])
            return [
                Model(id=m["id"], name=m.get("name", m["id"]), provider=self.name)
                for m in data
            ]
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Failed to list models ({exc.response.status_code}): "
                f"{exc.response.text[:300]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"HTTP error listing models: {exc}") from exc

    # ── streaming chat completion ─────────────────────────────────────────

    async def chat_completion_stream(
        self,
        messages: list[ChatMessage],
        model: str,
        tools: list[dict] | None = None,
        temperature: float = 0.0,
    ) -> AsyncIterator[StreamEvent]:
        url = f"{self._api_base}/v1/chat/completions"

        body: dict = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"

        # Accumulators for streamed tool-call deltas.
        tc_index_map: dict[int, dict] = {}  # index → {id, name, arguments}

        try:
            async with self._client.stream("POST", url, json=body) as resp:
                if resp.status_code != 200:
                    raw = await resp.aread()
                    yield StreamEvent(
                        type="error",
                        content=f"HTTP {resp.status_code}: {raw.decode(errors='replace')[:500]}",
                    )
                    return

                async for raw_line in resp.aiter_lines():
                    line = raw_line.strip()
                    if not line or line.startswith(":"):
                        continue  # SSE comment or keep-alive
                    if not line.startswith("data:"):
                        continue
                    payload = line[len("data:"):].strip()
                    if payload == "[DONE]":
                        # Flush any accumulated tool calls.
                        for _idx in sorted(tc_index_map):
                            tc = tc_index_map[_idx]
                            yield StreamEvent(
                                type="tool_call",
                                tool_call=ToolCall(
                                    id=tc.get("id", ""),
                                    name=tc.get("name", ""),
                                    arguments=tc.get("arguments", ""),
                                ),
                            )
                        yield StreamEvent(type="done")
                        return

                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                        
                    if "error" in chunk:
                        err_data = chunk["error"]
                        err_msg = err_data.get("message", str(err_data)) if isinstance(err_data, dict) else str(err_data)
                        yield StreamEvent(type="error", content=f"API Error: {err_msg}")
                        return

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    finish = choices[0].get("finish_reason")

                    # ── reasoning content ──
                    if delta.get("reasoning_content"):
                        yield StreamEvent(type="reasoning", content=delta["reasoning_content"])
                    elif delta.get("reasoning"):
                        yield StreamEvent(type="reasoning", content=delta["reasoning"])

                    # ── text content ──
                    if delta.get("content"):
                        yield StreamEvent(type="text", content=delta["content"])

                    # ── tool-call deltas ──
                    for tc_delta in delta.get("tool_calls", []):
                        idx = tc_delta.get("index", 0)
                        if idx not in tc_index_map:
                            tc_index_map[idx] = {"id": "", "name": "", "arguments": ""}
                        entry = tc_index_map[idx]
                        if tc_delta.get("id"):
                            entry["id"] = tc_delta["id"]
                        fn = tc_delta.get("function", {})
                        if fn.get("name"):
                            entry["name"] = fn["name"]
                        if fn.get("arguments"):
                            entry["arguments"] += fn["arguments"]

                    # ── finish ──
                    if finish and finish != "tool_calls":
                        # Flush any remaining tool calls even without [DONE]
                        for _idx in sorted(tc_index_map):
                            tc = tc_index_map[_idx]
                            yield StreamEvent(
                                type="tool_call",
                                tool_call=ToolCall(
                                    id=tc.get("id", ""),
                                    name=tc.get("name", ""),
                                    arguments=tc.get("arguments", ""),
                                ),
                            )
                        tc_index_map.clear()
                        yield StreamEvent(type="done", finish_reason=finish)
                        return
                    if finish == "tool_calls":
                        for _idx in sorted(tc_index_map):
                            tc = tc_index_map[_idx]
                            yield StreamEvent(
                                type="tool_call",
                                tool_call=ToolCall(
                                    id=tc.get("id", ""),
                                    name=tc.get("name", ""),
                                    arguments=tc.get("arguments", ""),
                                ),
                            )
                        tc_index_map.clear()
                        yield StreamEvent(type="done", finish_reason="tool_calls")
                        return

        except httpx.ReadTimeout:
            yield StreamEvent(type="error", content="Read timeout from provider.")
        except httpx.ConnectError as exc:
            yield StreamEvent(type="error", content=f"Connection error: {exc}")
        except httpx.HTTPError as exc:
            yield StreamEvent(type="error", content=f"HTTP error: {exc}")

    # ── lifecycle ─────────────────────────────────────────────────────────

    async def close(self) -> None:
        await self._client.aclose()
