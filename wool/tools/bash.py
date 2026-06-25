"""execute_bash — run shell commands with Linux process-group management."""

from __future__ import annotations

import asyncio
import os
import re
import signal
from typing import Any

from wool.tools.base import Tool, ToolParameter, ToolResult

# Commands that should never be run.
_DANGEROUS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\brm\s+(-\w*\s+)*-\w*r\w*\s+/\s*$"),  # rm -rf /
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bdd\b.*\bof\s*=\s*/dev/"),
    re.compile(r":\(\)\s*\{\s*:\|:\s*&\s*\}\s*;"),  # fork bomb
    re.compile(r"\bshutdown\b"),
    re.compile(r"\breboot\b"),
    re.compile(r"\binit\s+0\b"),
]

MAX_OUTPUT = 50_000


class ExecuteBash(Tool):
    """Securely execute bash commands on Linux."""

    @property
    def name(self) -> str:
        return "execute_bash"

    @property
    def description(self) -> str:
        return (
            "Execute a bash command on the host Linux system. "
            "Returns stdout, stderr, and exit code."
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="command",
                type="string",
                description="The bash command to execute.",
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="Maximum seconds to wait (default 30).",
                required=False,
                default=30,
            ),
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        command: str = kwargs.get("command", "")
        timeout: int = int(kwargs.get("timeout", 30))

        if not command.strip():
            return ToolResult(success=False, output="", error="Empty command.")

        # Safety check
        for pat in _DANGEROUS_PATTERNS:
            if pat.search(command):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Blocked: command matched dangerous pattern ({pat.pattern}).",
                )

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,  # own process group for clean kill
            )

            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                # Kill the whole process group.
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass
                await proc.wait()
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Command timed out after {timeout}s and was killed.",
                    metadata={"exit_code": -9},
                )

            stdout = stdout_b.decode(errors="replace")
            stderr = stderr_b.decode(errors="replace")
            combined = stdout
            if stderr:
                combined += ("\n--- stderr ---\n" + stderr) if stdout else stderr

            if len(combined) > MAX_OUTPUT:
                combined = combined[:MAX_OUTPUT] + f"\n... (truncated at {MAX_OUTPUT} chars)"

            exit_code = proc.returncode or 0
            return ToolResult(
                success=exit_code == 0,
                output=combined,
                error=None if exit_code == 0 else f"Exit code {exit_code}",
                metadata={"exit_code": exit_code},
            )

        except FileNotFoundError:
            return ToolResult(success=False, output="", error="Shell not found.")
        except PermissionError as exc:
            return ToolResult(success=False, output="", error=f"Permission denied: {exc}")
        except OSError as exc:
            return ToolResult(success=False, output="", error=f"OS error: {exc}")
