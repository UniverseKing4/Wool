"""execute_bash — run shell commands with Linux process-group management."""

from __future__ import annotations

import asyncio
import os
import re
import shlex
import signal
from typing import Any

from wool.tools.base import Tool, ToolParameter, ToolResult, RESTRICTED_DIR
import wool.tools.base as base

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
        if base.IS_RESTRICTED and ".." in command:
            return ToolResult(
                success=False,
                output="",
                error="Blocked: path traversal (..) is strictly forbidden.",
            )
            
        for pat in _DANGEROUS_PATTERNS:
            if pat.search(command):
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Blocked: command matched dangerous pattern ({pat.pattern}).",
                )

        try:
            if base.IS_RESTRICTED:
                # Check if unshare is supported (Termux/Android often lacks it)
                unshare_supported = False
                try:
                    import subprocess
                    ret = subprocess.run(["unshare", "-m", "-r", "true"], capture_output=True)
                    if ret.returncode == 0:
                        unshare_supported = True
                except Exception:
                    pass

                if unshare_supported:
                    script = f'''
RESTRICTED={shlex.quote(str(RESTRICTED_DIR))}
PARENT=$(dirname "$RESTRICTED")

# Overmount visible siblings to prevent path traversal
for item in "$PARENT"/*; do
    if [ "$item" = "$PARENT/*" ]; then continue; fi
    if [ "$item" != "$RESTRICTED" ] && [ -d "$item" ]; then
        mount -t tmpfs tmpfs "$item" 2>/dev/null || true
    elif [ "$item" != "$RESTRICTED" ] && [ -f "$item" ]; then
        mount --bind /dev/null "$item" 2>/dev/null || true
    fi
done

# For directories safely outside /home, apply strict parent overmount
if [[ "$PARENT" != /home* ]] && [[ "$PARENT" != /root* ]]; then
    mount --bind "$RESTRICTED" /mnt
    mount -t tmpfs tmpfs "$PARENT" 2>/dev/null || true
    mkdir -p "$RESTRICTED"
    mount --bind /mnt "$RESTRICTED" 2>/dev/null || true
    umount /mnt 2>/dev/null || true
fi

cd "$RESTRICTED"
exec bash -c {shlex.quote(command)}
'''
                    proc = await asyncio.create_subprocess_exec(
                        "unshare", "-m", "-r", "bash", "-c", script,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        start_new_session=True,  # own process group for clean kill
                    )
                else:
                    # Graceful degradation for Termux/environments without unshare
                    proc = await asyncio.create_subprocess_exec(
                        "bash",
                        "-c",
                        f"cd {shlex.quote(str(RESTRICTED_DIR))} && exec bash -c {shlex.quote(command)}",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        start_new_session=True,
                    )
            else:
                proc = await asyncio.create_subprocess_exec(
                    "bash",
                    "-c",
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    start_new_session=True,  # own process group for clean kill
                )

            stream_callback = kwargs.get("__stream_callback")
            
            stdout_chunks: list[str] = []
            stderr_chunks: list[str] = []

            async def read_stream(stream: asyncio.StreamReader, chunks_list: list[str]) -> None:
                while True:
                    chunk = await stream.read(1024)
                    if not chunk:
                        break
                    text = chunk.decode(errors="replace")
                    chunks_list.append(text)
                    if stream_callback:
                        await stream_callback(text)

            assert proc.stdout is not None
            assert proc.stderr is not None

            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        read_stream(proc.stdout, stdout_chunks),
                        read_stream(proc.stderr, stderr_chunks)
                    ),
                    timeout=timeout
                )
                stdout = "".join(stdout_chunks)
                stderr = "".join(stderr_chunks)
                await proc.wait()
            except asyncio.TimeoutError:
                stdout = "".join(stdout_chunks)
                stderr = "".join(stderr_chunks)
                # Terminate the process group to kill all descendants
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass
                await proc.wait()
                return ToolResult(
                    success=False,
                    output=stdout,
                    error=f"Command timed out after {timeout} seconds. Stderr: {stderr}",
                    metadata={"exit_code": -9},
                )
            except asyncio.CancelledError:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                except ProcessLookupError:
                    pass
                raise

            combined = stdout
            if stderr:
                combined += ("\n--- stderr ---\n" + stderr) if stdout else stderr

            if len(combined) > MAX_OUTPUT:
                combined = (
                    combined[:MAX_OUTPUT] + f"\n... (truncated at {MAX_OUTPUT} chars)"
                )

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
            return ToolResult(
                success=False, output="", error=f"Permission denied: {exc}"
            )
        except OSError as exc:
            return ToolResult(success=False, output="", error=f"OS error: {exc}")
