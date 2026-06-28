"""code_intelligence — symbol search, project overview, and code maps."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any

from wool.tools.base import Tool, ToolParameter, ToolResult, check_path_allowed

# Patterns for common symbol definitions across languages.
_SYMBOL_PATTERNS: dict[str, str] = {
    "python": r"^\s*(class|def|async\s+def)\s+(\w+)",
    "javascript": r"(?:function|const|let|var|class|export\s+(?:default\s+)?(?:function|class|const))\s+(\w+)",
    "typescript": r"(?:function|const|let|var|class|interface|type|enum|export\s+(?:default\s+)?(?:function|class|const|interface|type|enum))\s+(\w+)",
    "go": r"^(?:func|type|var|const)\s+(\w+)",
    "rust": r"^(?:pub\s+)?(?:fn|struct|enum|trait|type|const|static|mod)\s+(\w+)",
    "java": r"(?:public|private|protected)?\s*(?:static\s+)?(?:class|interface|enum|void|int|String|boolean)\s+(\w+)",
    "c": r"^(?:struct|enum|typedef|void|int|char|float|double|long|unsigned)\s+\*?\s*(\w+)\s*[\({;]",
}

_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "c",
    ".hpp": "c",
}


class CodeIntelligence(Tool):
    """Lightweight code intelligence using native Linux tools."""

    @property
    def name(self) -> str:
        return "code_intelligence"

    @property
    def description(self) -> str:
        return (
            "Code intelligence: search symbols, lookup definitions, "
            "list document symbols, pattern search, codebase overview, "
            "or generate a codebase map."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                type="string",
                description="Action to perform.",
                enum=[
                    "search_symbols",
                    "lookup_symbol",
                    "document_symbols",
                    "pattern_search",
                    "codebase_overview",
                    "codebase_map",
                ],
            ),
            ToolParameter(
                name="query",
                type="string",
                description="Symbol name or search query.",
                required=False,
            ),
            ToolParameter(
                name="path",
                type="string",
                description="File or directory path.",
                required=False,
            ),
            ToolParameter(
                name="pattern",
                type="string",
                description="Regex pattern (pattern_search).",
                required=False,
            ),
            ToolParameter(
                name="language",
                type="string",
                description="Filter by language (e.g. python, go, rust).",
                required=False,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        action: str = kwargs.get("action", "")
        
        path_str: str = kwargs.get("path", ".")
        try:
            check_path_allowed(Path(path_str).resolve())
        except PermissionError as e:
            return ToolResult(success=False, output="", error=str(e))
            
        dispatch = {
            "search_symbols": self._search_symbols,
            "lookup_symbol": self._lookup_symbol,
            "document_symbols": self._document_symbols,
            "pattern_search": self._pattern_search,
            "codebase_overview": self._codebase_overview,
            "codebase_map": self._codebase_map,
        }
        fn = dispatch.get(action)
        if not fn:
            return ToolResult(
                success=False, output="", error=f"Unknown action: {action}"
            )
        return await fn(kwargs)

    # ── search_symbols ────────────────────────────────────────────────────

    async def _search_symbols(self, kw: dict) -> ToolResult:
        query = kw.get("query", "")
        path = kw.get("path", ".")
        if not query:
            return ToolResult(success=False, output="", error="query is required.")
        pattern = rf"(class|def|function|func|struct|enum|trait|type|const|interface|var|let)\s+{re.escape(query)}"
        return await self._grep(pattern, path)

    async def _lookup_symbol(self, kw: dict) -> ToolResult:
        return await self._search_symbols(kw)  # Same grep, context-aware

    # ── document_symbols ──────────────────────────────────────────────────

    async def _document_symbols(self, kw: dict) -> ToolResult:
        path = kw.get("path", "")
        if not path:
            return ToolResult(success=False, output="", error="path is required.")
        p = Path(path).resolve()
        if not p.exists() or not p.is_file():
            return ToolResult(success=False, output="", error=f"Not a file: {p}")

        lang = kw.get("language") or _EXT_TO_LANG.get(p.suffix, "")
        pat_str = _SYMBOL_PATTERNS.get(
            lang, r"^\s*(?:class|def|function|func|struct|type)\s+(\w+)"
        )
        pat = re.compile(pat_str, re.MULTILINE)

        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return ToolResult(success=False, output="", error=str(exc))

        symbols: list[str] = []
        for i, line in enumerate(text.splitlines(), 1):
            m = pat.search(line)
            if m:
                # sym = m.group(m.lastindex or 0)
                symbols.append(f"  {i:>5} │ {line.strip()}")

        if not symbols:
            return ToolResult(success=True, output=f"No symbols found in {p.name}")
        header = f"Symbols in {p.name} ({len(symbols)}):\n"
        return ToolResult(success=True, output=header + "\n".join(symbols))

    # ── pattern_search ────────────────────────────────────────────────────

    async def _pattern_search(self, kw: dict) -> ToolResult:
        pattern = kw.get("pattern", "")
        path = kw.get("path", ".")
        if not pattern:
            return ToolResult(success=False, output="", error="pattern is required.")
        return await self._grep(pattern, path)

    # ── codebase_overview ─────────────────────────────────────────────────

    async def _codebase_overview(self, kw: dict) -> ToolResult:
        path = kw.get("path", ".")
        root = Path(path).resolve()
        if not root.is_dir():
            return ToolResult(
                success=False, output="", error=f"Not a directory: {root}"
            )

        ext_counts: dict[str, int] = {}
        total_files = 0
        total_lines = 0
        skip = {
            ".git",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            ".tox",
            "dist",
            "build",
        }

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for fn in filenames:
                fp = Path(dirpath) / fn
                ext = fp.suffix or "(no ext)"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
                total_files += 1
                try:
                    if fp.stat().st_size < 2 * 1024 * 1024:  # skip huge files
                        with open(fp, "rb") as f:
                            total_lines += sum(1 for _ in f)
                except OSError:
                    pass

        lines_parts = [
            f"  {ext:>12}: {c:>6} files"
            for ext, c in sorted(ext_counts.items(), key=lambda x: -x[1])[:20]
        ]
        overview = (
            f"Codebase: {root}\n"
            f"Total files: {total_files}\n"
            f"Total lines: {total_lines:,}\n\n"
            f"By extension:\n" + "\n".join(lines_parts)
        )
        return ToolResult(success=True, output=overview)

    # ── codebase_map ──────────────────────────────────────────────────────

    async def _codebase_map(self, kw: dict) -> ToolResult:
        path = kw.get("path", ".")
        root = Path(path).resolve()
        if not root.is_dir():
            return ToolResult(
                success=False, output="", error=f"Not a directory: {root}"
            )

        skip = {
            ".git",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            ".tox",
            "dist",
            "build",
        }
        lines: list[str] = [f"{root.name}/"]
        self._tree(root, lines, "", skip, depth=0, max_depth=4)
        if len(lines) > 500:
            lines = lines[:500]
            lines.append("... (truncated)")
        return ToolResult(success=True, output="\n".join(lines))

    def _tree(
        self,
        d: Path,
        out: list[str],
        prefix: str,
        skip: set[str],
        depth: int,
        max_depth: int,
    ) -> None:
        if depth >= max_depth:
            return
        try:
            children = sorted(
                d.iterdir(), key=lambda c: (not c.is_dir(), c.name.lower())
            )
        except PermissionError:
            return
        children = [c for c in children if c.name not in skip]
        for i, child in enumerate(children):
            is_last = i == len(children) - 1
            connector = "└── " if is_last else "├── "
            out.append(
                f"{prefix}{connector}{child.name}{'/' if child.is_dir() else ''}"
            )
            if child.is_dir():
                extension = "    " if is_last else "│   "
                self._tree(child, out, prefix + extension, skip, depth + 1, max_depth)

    # ── shared grep helper ────────────────────────────────────────────────

    async def _grep(self, pattern: str, path: str) -> ToolResult:
        cmd = [
            "grep",
            "-rnI",
            "--color=never",
            "-E",
            "--",
            pattern,
            str(Path(path).resolve()),
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            text = stdout.decode(errors="replace")
            if len(text) > 50_000:
                text = text[:50_000] + "\n... (truncated)"
            return ToolResult(success=True, output=text or "No matches found.")
        except asyncio.TimeoutError:
            return ToolResult(success=False, output="", error="Search timed out.")
        except FileNotFoundError:
            return ToolResult(success=False, output="", error="grep not found.")
