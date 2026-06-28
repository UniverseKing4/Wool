"""fs_read — read files, directories, search, and image info."""

from __future__ import annotations

import asyncio
import base64
import mimetypes
import os
from pathlib import Path
from typing import Any

import aiofiles

from wool.tools.base import Tool, ToolParameter, ToolResult, check_path_allowed

MAX_FILE_LINES = 10_000
MAX_DIR_ENTRIES = 1_000


class FileSystemRead(Tool):
    """Read files, list directories, grep-search, or inspect images."""

    @property
    def name(self) -> str:
        return "fs_read"

    @property
    def description(self) -> str:
        return (
            "Read a file's content, list a directory, search for a pattern, "
            "or inspect an image file on the Linux filesystem."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="path", type="string", description="Absolute path to read."
            ),
            ToolParameter(
                name="mode",
                type="string",
                description="Read mode.",
                enum=["file", "directory", "search", "image"],
            ),
            ToolParameter(
                name="start_line",
                type="integer",
                description="First line to read (1-indexed, file mode).",
                required=False,
            ),
            ToolParameter(
                name="end_line",
                type="integer",
                description="Last line to read (inclusive, file mode).",
                required=False,
            ),
            ToolParameter(
                name="pattern",
                type="string",
                description="Grep pattern (search mode).",
                required=False,
            ),
            ToolParameter(
                name="recursive",
                type="boolean",
                description="Recurse into subdirectories (default true).",
                required=False,
                default=True,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        path_str: str = kwargs.get("path", "")
        mode: str = kwargs.get("mode", "file")
        if not path_str:
            return ToolResult(success=False, output="", error="Path is required.")

        p = Path(path_str).resolve()

        try:
            check_path_allowed(p)
        except PermissionError as e:
            return ToolResult(success=False, output="", error=str(e))

        if mode == "file":
            return await self._read_file(p, kwargs)
        if mode == "directory":
            return await asyncio.to_thread(self._list_directory, p)
        if mode == "search":
            return await self._search(p, kwargs)
        if mode == "image":
            return await asyncio.to_thread(self._image_info, p)
        return ToolResult(success=False, output="", error=f"Unknown mode: {mode}")

    # ── file ──────────────────────────────────────────────────────────────

    async def _read_file(self, p: Path, kw: dict) -> ToolResult:
        if not p.exists():
            return ToolResult(success=False, output="", error=f"Not found: {p}")
        if p.is_dir():
            return ToolResult(success=False, output="", error=f"Is a directory: {p}")
        if not os.access(p, os.R_OK):
            return ToolResult(success=False, output="", error=f"Permission denied: {p}")

        start = max(int(kw.get("start_line") or 1), 1)
        end = int(kw.get("end_line") or (start + MAX_FILE_LINES - 1))
        end = max(start, end)

        selected: list[str] = []
        total_lines = 0
        truncated = False

        try:
            async with aiofiles.open(p, "r", encoding="utf-8", errors="replace") as f:
                async for line in f:
                    total_lines += 1
                    if start <= total_lines <= end:
                        if len(selected) >= MAX_FILE_LINES:
                            truncated = True
                            continue
                        selected.append(line)
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc))

        numbered = [
            f"{start + i:>6} │ {line.rstrip()}" for i, line in enumerate(selected)
        ]
        text = "\n".join(numbered)
        if truncated:
            text += f"\n... (truncated at {MAX_FILE_LINES} lines)"
        meta = {
            "total_lines": total_lines,
            "shown": f"{start}-{start + len(selected) - 1}",
        }
        return ToolResult(success=True, output=text, metadata=meta)

    # ── directory ─────────────────────────────────────────────────────────

    def _list_directory(self, p: Path) -> ToolResult:
        if not p.exists():
            return ToolResult(success=False, output="", error=f"Not found: {p}")
        if not p.is_dir():
            return ToolResult(success=False, output="", error=f"Not a directory: {p}")

        entries: list[str] = []
        try:
            children = sorted(
                p.iterdir(), key=lambda c: (not c.is_dir(), c.name.lower())
            )
            for i, child in enumerate(children):
                if i >= MAX_DIR_ENTRIES:
                    entries.append(
                        f"  ... ({len(list(p.iterdir())) - MAX_DIR_ENTRIES} more)"
                    )
                    break
                prefix = "📁" if child.is_dir() else "📄"
                size = ""
                if child.is_file():
                    try:
                        sz = child.stat().st_size
                        size = f"  ({self._human_size(sz)})"
                    except OSError:
                        pass
                link = " → " + str(child.resolve()) if child.is_symlink() else ""
                entries.append(f"  {prefix} {child.name}{size}{link}")
        except PermissionError:
            return ToolResult(success=False, output="", error=f"Permission denied: {p}")

        header = f"Directory: {p}  ({len(entries)} entries)\n"
        return ToolResult(success=True, output=header + "\n".join(entries))

    # ── search ────────────────────────────────────────────────────────────

    async def _search(self, p: Path, kw: dict) -> ToolResult:
        pattern = kw.get("pattern", "")
        if not pattern:
            return ToolResult(
                success=False, output="", error="Pattern is required for search."
            )
        recursive = kw.get("recursive", True)
        flag = "-rn" if recursive else "-n"
        cmd = ["grep", flag, "--color=never", "-I", "--include=*", "--", pattern, str(p)]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            text = stdout.decode(errors="replace")
            if len(text) > 50_000:
                text = text[:50_000] + "\n... (truncated)"
            if not text.strip():
                return ToolResult(success=True, output="No matches found.")
            return ToolResult(success=True, output=text)
        except asyncio.TimeoutError:
            return ToolResult(success=False, output="", error="Search timed out.")
        except FileNotFoundError:
            return ToolResult(
                success=False, output="", error="grep not found on system."
            )

    # ── image ─────────────────────────────────────────────────────────────

    def _image_info(self, p: Path) -> ToolResult:
        if not p.exists():
            return ToolResult(success=False, output="", error=f"Not found: {p}")
        mime, _ = mimetypes.guess_type(str(p))
        if not mime or not mime.startswith("image/"):
            return ToolResult(
                success=False, output="", error=f"Not an image: {p} ({mime})"
            )
        st = p.stat()
        info = (
            f"Image: {p.name}\n"
            f"Type: {mime}\n"
            f"Size: {self._human_size(st.st_size)}\n"
            f"Path: {p}\n"
        )
        if st.st_size < 2 * 1024 * 1024:  # base64 only for < 2 MB
            raw = p.read_bytes()
            b64 = base64.b64encode(raw).decode()
            info += f"Base64 length: {len(b64)}\n"
        return ToolResult(success=True, output=info, metadata={"mime": mime})

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _human_size(n: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.1f} {unit}" if unit != "B" else f"{n} {unit}"
            n /= 1024  # type: ignore[assignment]
        return f"{n:.1f} TB"
