"""fs_write — create and edit files on the Linux filesystem."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import aiofiles

from wool.tools.base import Tool, ToolParameter, ToolResult

# Paths that must never be written to.
_FORBIDDEN_PREFIXES = ("/proc", "/sys", "/dev", "/boot/efi")


class FileSystemWrite(Tool):
    """Create, replace, insert, or append file content."""

    @property
    def name(self) -> str:
        return "fs_write"

    @property
    def description(self) -> str:
        return (
            "Write to the Linux filesystem: create a new file, replace a string, "
            "insert at a line, or append content."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(name="path", type="string", description="Absolute file path."),
            ToolParameter(
                name="mode", type="string",
                description="Write mode.",
                enum=["create", "str_replace", "insert", "append"],
            ),
            ToolParameter(
                name="content", type="string",
                description="Content for create / insert / append.",
                required=False,
            ),
            ToolParameter(
                name="old_str", type="string",
                description="Exact string to find (str_replace mode).",
                required=False,
            ),
            ToolParameter(
                name="new_str", type="string",
                description="Replacement string (str_replace mode).",
                required=False,
            ),
            ToolParameter(
                name="line", type="integer",
                description="Line number for insert mode (1-indexed).",
                required=False,
            ),
            ToolParameter(
                name="create_dirs", type="boolean",
                description="Auto-create parent directories (default true).",
                required=False, default=True,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        path_str: str = kwargs.get("path", "")
        mode: str = kwargs.get("mode", "create")
        if not path_str:
            return ToolResult(success=False, output="", error="Path is required.")

        p = Path(path_str).resolve()

        # Safety: block forbidden paths.
        for prefix in _FORBIDDEN_PREFIXES:
            if str(p).startswith(prefix):
                return ToolResult(
                    success=False, output="",
                    error=f"Writing to {prefix} is forbidden.",
                )

        if mode == "create":
            return await self._create(p, kwargs)
        if mode == "str_replace":
            return await self._str_replace(p, kwargs)
        if mode == "insert":
            return await self._insert(p, kwargs)
        if mode == "append":
            return await self._append(p, kwargs)
        return ToolResult(success=False, output="", error=f"Unknown mode: {mode}")

    # ── create ────────────────────────────────────────────────────────────

    async def _create(self, p: Path, kw: dict) -> ToolResult:
        import asyncio
        content = kw.get("content", "")
        create_dirs = kw.get("create_dirs", True)
        if content is None:
            content = ""

        if create_dirs:
            await asyncio.to_thread(p.parent.mkdir, parents=True, exist_ok=True)
        else:
            exists = await asyncio.to_thread(p.parent.exists)
            if not exists:
                return ToolResult(success=False, output="", error=f"Parent dir missing: {p.parent}")

        try:
            async with aiofiles.open(p, "w", encoding="utf-8") as f:
                await f.write(content)
            return ToolResult(success=True, output=f"Created {p} ({len(content)} chars)")
        except OSError as exc:
            return ToolResult(success=False, output="", error=str(exc))

    # ── str_replace ───────────────────────────────────────────────────────

    async def _str_replace(self, p: Path, kw: dict) -> ToolResult:
        old_str: str | None = kw.get("old_str")
        new_str: str | None = kw.get("new_str")
        if old_str is None:
            return ToolResult(success=False, output="", error="old_str is required.")
        if new_str is None:
            new_str = ""

        import asyncio
        exists = await asyncio.to_thread(p.exists)
        if not exists:
            return ToolResult(success=False, output="", error=f"Not found: {p}")

        await self._backup(p)

        try:
            async with aiofiles.open(p, "r", encoding="utf-8", errors="replace") as f:
                text = await f.read()
        except OSError as exc:
            return ToolResult(success=False, output="", error=str(exc))

        count = text.count(old_str)
        if count == 0:
            return ToolResult(success=False, output="", error="old_str not found in file.")
        if count > 1:
            return ToolResult(
                success=False, output="",
                error=f"old_str matches {count} locations — must be unique.",
            )

        text = text.replace(old_str, new_str, 1)
        try:
            async with aiofiles.open(p, "w", encoding="utf-8") as f:
                await f.write(text)
            return ToolResult(success=True, output=f"Replaced in {p}")
        except OSError as exc:
            return ToolResult(success=False, output="", error=str(exc))

    # ── insert ────────────────────────────────────────────────────────────

    async def _insert(self, p: Path, kw: dict) -> ToolResult:
        content = kw.get("content", "")
        line_no = int(kw.get("line", 1))
        import asyncio
        exists = await asyncio.to_thread(p.exists)
        if not exists:
            return ToolResult(success=False, output="", error=f"Not found: {p}")

        await self._backup(p)

        try:
            async with aiofiles.open(p, "r", encoding="utf-8", errors="replace") as f:
                lines = await f.readlines()
        except OSError as exc:
            return ToolResult(success=False, output="", error=str(exc))

        idx = max(0, min(line_no - 1, len(lines)))
        insert_lines = content if content.endswith("\n") else content + "\n"
        lines.insert(idx, insert_lines)

        try:
            async with aiofiles.open(p, "w", encoding="utf-8") as f:
                await f.writelines(lines)
            return ToolResult(success=True, output=f"Inserted at line {line_no} in {p}")
        except OSError as exc:
            return ToolResult(success=False, output="", error=str(exc))

    # ── append ────────────────────────────────────────────────────────────

    async def _append(self, p: Path, kw: dict) -> ToolResult:
        content = kw.get("content", "")
        import asyncio
        exists = await asyncio.to_thread(p.exists)
        if not exists:
            return ToolResult(success=False, output="", error=f"Not found: {p}")
        try:
            async with aiofiles.open(p, "a", encoding="utf-8") as f:
                await f.write(content)
            return ToolResult(success=True, output=f"Appended {len(content)} chars to {p}")
        except OSError as exc:
            return ToolResult(success=False, output="", error=str(exc))

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    async def _backup(p: Path) -> None:
        """Create a .wool.bak backup before destructive edits."""
        import asyncio
        bak = p.with_suffix(p.suffix + ".wool.bak")
        try:
            await asyncio.to_thread(shutil.copy2, p, bak)
        except OSError:
            pass  # best-effort
