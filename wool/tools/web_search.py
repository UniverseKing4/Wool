"""web_search — search the web using DuckDuckGo HTML fallback."""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import quote_plus

import httpx

from wool.tools.base import Tool, ToolParameter, ToolResult


class WebSearch(Tool):
    """Search the live web for current information."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web and return results with titles, URLs, and snippets."

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="query", type="string", description="Search query."),
            ToolParameter(
                name="num_results", type="integer",
                description="Number of results to return (default 5).",
                required=False, default=5,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        query: str = kwargs.get("query", "")
        num: int = int(kwargs.get("num_results", 5))

        if not query:
            return ToolResult(success=False, output="", error="Query is required.")

        try:
            results = await self._ddg_search(query, num)
        except Exception as exc:
            return ToolResult(
                success=False, output="",
                error=f"Search failed: {exc}",
            )

        if not results:
            return ToolResult(success=True, output="No results found.")

        parts: list[str] = [f"Search results for: {query}\n"]
        for i, r in enumerate(results, 1):
            parts.append(f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}\n")
        return ToolResult(success=True, output="\n".join(parts))

    async def _ddg_search(self, query: str, num: int) -> list[dict[str, str]]:
        """Scrape DuckDuckGo HTML for results."""
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            },
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        body = resp.text
        results: list[dict[str, str]] = []

        # Parse result blocks.
        for block in re.finditer(
            r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
            r'class="result__snippet"[^>]*>(.*?)</(?:td|div|span)>',
            body, re.DOTALL,
        ):
            if len(results) >= num:
                break
            raw_url = block.group(1)
            title = re.sub(r"<[^>]+>", "", block.group(2)).strip()
            snippet = re.sub(r"<[^>]+>", "", block.group(3)).strip()
            title = html.unescape(title)
            snippet = html.unescape(snippet)

            # DDG wraps actual URLs in a redirect; try to extract.
            m = re.search(r"uddg=([^&]+)", raw_url)
            actual_url = html.unescape(m.group(1)) if m else raw_url
            from urllib.parse import unquote
            actual_url = unquote(actual_url)

            results.append({"title": title, "url": actual_url, "snippet": snippet})

        return results
