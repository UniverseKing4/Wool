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
                import subprocess
                import shutil
                is_android = "com.termux" in os.environ.get("PREFIX", "") or os.path.exists("/system/build.prop")
                
                if shutil.which("unshare") and not is_android:
                    # 1. Standard Linux Sandbox via unshare
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
                        start_new_session=True,
                    )
                else:
                    # 2. Perfect Android/Termux (or missing unshare) Sandbox via PROOT
                    # Auto-install proot if missing
                    try:
                        subprocess.run(["proot", "--version"], capture_output=True, check=True)
                    except (FileNotFoundError, subprocess.CalledProcessError):
                        # Install proot
                        if os.path.exists("/data/data/com.termux/files/usr/bin/pkg"):
                            subprocess.run(["pkg", "install", "-y", "proot"], capture_output=True)
                        elif os.path.exists("/usr/bin/apt-get"):
                            subprocess.run(["apt-get", "update"], capture_output=True)
                            subprocess.run(["apt-get", "install", "-y", "proot"], capture_output=True)
                    
                    # Proot jail script (Unified for standard Linux, native Termux, and PRoot Debian)
                    prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
                    script = f'''
RESTRICTED={shlex.quote(str(RESTRICTED_DIR))}
JAIL=$(mktemp -d)
BINDS=""
for d in /bin /usr /lib /lib64 /etc /dev /proc /system /apex /vendor /linkerconfig /bionic "{prefix}"; do
    if [ -d "$d" ]; then
        BINDS="$BINDS -b $d:$d"
    fi
done
exec proot -r "$JAIL" $BINDS -b "$RESTRICTED":/workspace -w /workspace bash -c {shlex.quote(command)}
'''
                    proc = await asyncio.create_subprocess_exec(
                        "bash", "-c", script,
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
                buffer = ""
                total_len = 0
                while True:
                    chunk = await stream.read(1024)
                    if not chunk:
                        if buffer and total_len < MAX_OUTPUT:
                            buffer = re.sub(r"(?im)^.*linkerconfig/ld\.config\.txt.*$\n?", "", buffer)
                            if buffer:
                                chunks_list.append(buffer)
                                if stream_callback:
                                    await stream_callback(buffer)
                        break
                    
                    text = chunk.decode(errors="replace")
                    buffer += text
                    
                    if "\n" in buffer:
                        lines = buffer.split("\n")
                        complete_lines = lines[:-1]
                        buffer = lines[-1]
                        
                        output_text = "\n".join(complete_lines) + "\n"
                        output_text = re.sub(r"(?im)^.*linkerconfig/ld\.config\.txt.*$\n?", "", output_text)
                        
                        if output_text and total_len < MAX_OUTPUT:
                            chunks_list.append(output_text)
                            total_len += len(output_text)
                            if stream_callback:
                                await stream_callback(output_text)

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
                
                # Filter out harmless Android linker warnings in Termux proot sandbox
                stderr = re.sub(r"(?im)^.*linkerconfig/ld\.config\.txt.*$\n?", "", stderr).strip()
                
                await proc.wait()
            except asyncio.TimeoutError:
                stdout = "".join(stdout_chunks)
                stderr = "".join(stderr_chunks)
                stderr = re.sub(r"(?im)^.*linkerconfig/ld\.config\.txt.*$\n?", "", stderr).strip()
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
                try:
                    await asyncio.wait_for(proc.wait(), timeout=1)
                except Exception:
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

        except FileNotFoundError as e:
            return ToolResult(success=False, output="", error=f"Shell not found: {e}")
        except PermissionError as exc:
            return ToolResult(
                success=False, output="", error=f"Permission denied: {exc}"
            )
        except OSError as exc:
            return ToolResult(success=False, output="", error=f"OS error: {exc}")
