"""web_fetch — fetch and extract clean content from URLs."""

from __future__ import annotations

import html
import re
from typing import Any

import httpx

from wool.tools.base import Tool, ToolParameter, ToolResult

MAX_RESPONSE_BYTES = 100_000
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\n{3,}")
_SCRIPT_RE = re.compile(
    r"<(script|style|noscript)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE
)


class WebFetch(Tool):
    """Fetch a URL and extract its content."""

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "Fetch content from a URL and return it as text, raw HTML, or simplified markdown."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="url", type="string", description="URL to fetch."),
            ToolParameter(
                name="extract_mode",
                type="string",
                description="Content extraction mode.",
                enum=["text", "html", "markdown"],
                required=False,
                default="text",
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="Request timeout in seconds (default 15).",
                required=False,
                default=15,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        url: str = kwargs.get("url", "")
        mode: str = kwargs.get("extract_mode", "text")
        timeout: int = int(kwargs.get("timeout", 15))

        if not url:
            return ToolResult(success=False, output="", error="URL is required.")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        raw = ""
        truncated = False
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers={"User-Agent": "Wool/0.1 (AI Agent)"},
            ) as client:
                async with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    async for chunk in resp.aiter_text():
                        raw += chunk
                        if len(raw) > MAX_RESPONSE_BYTES:
                            raw = raw[:MAX_RESPONSE_BYTES]
                            truncated = True
                            break
        except httpx.HTTPStatusError as exc:
            return ToolResult(
                success=False,
                output="",
                error=f"HTTP {exc.response.status_code}",
            )
        except httpx.HTTPError as exc:
            return ToolResult(success=False, output="", error=f"Fetch error: {exc}")

        header = f"URL: {url}\n\n"



        if mode == "html":
            content = raw
        elif mode == "text":
            content = self._html_to_text(raw)
        else:  # markdown
            content = self._html_to_text(raw)  # simplified

        if truncated:
            content += "\n\n... (truncated at 100 KB)"

        return ToolResult(
            success=True,
            output=header + content,
            metadata={"url": url},
        )

    @staticmethod
    def _html_to_text(html_str: str) -> str:
        """Lightweight HTML → plain text."""
        text = _SCRIPT_RE.sub("", html_str)
        text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        text = text.replace("</p>", "\n\n").replace("</div>", "\n")
        text = text.replace("</li>", "\n").replace("<li>", "  • ")
        text = (
            text.replace("</h1>", "\n\n")
            .replace("</h2>", "\n\n")
            .replace("</h3>", "\n\n")
        )
        text = _TAG_RE.sub("", text)
        text = html.unescape(text)
        text = _WS_RE.sub("\n\n", text).strip()
        return text
