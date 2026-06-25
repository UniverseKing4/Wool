"""MCP client — JSON-RPC 2.0 over stdio transport.

Connects to an MCP server launched as a subprocess (stdio transport)
or via SSE (HTTP transport).  Implements the MCP lifecycle:

    connect → initialize → tools/list → tools/call → disconnect
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any


class MCPClient:
    """Communicates with a single MCP server."""

    def __init__(
        self,
        name: str,
        command: list[str] | None = None,
        url: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self.command = command
        self.url = url
        self.env = env
        self._process: asyncio.subprocess.Process | None = None
        self._tools: list[dict] = []
        self._connected: bool = False
        self._req_id = 0
        self._pending: dict[int, asyncio.Future[dict]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._buf = b""

    # ── lifecycle ─────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Launch the MCP server process and perform the handshake."""
        if self._connected:
            return

        if self.command:
            await self._connect_stdio()
        elif self.url:
            # SSE transport is architecturally supported but not yet implemented.
            raise NotImplementedError("SSE transport not yet implemented.")
        else:
            raise ValueError("Either command or url must be provided.")

    async def _connect_stdio(self) -> None:
        assert self.command is not None
        import os

        env = {**os.environ, **(self.env or {})}
        self._process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        # Start background reader.
        self._reader_task = asyncio.create_task(self._read_loop())

        # JSON-RPC initialize handshake.
        result = await self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "wool", "version": "0.1.0"},
        })
        # Send initialized notification (no response expected).
        await self._notify("notifications/initialized", {})
        self._connected = True

    async def disconnect(self) -> None:
        """Shut down the MCP server."""
        self._connected = False
        
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(RuntimeError("MCP disconnected"))
        self._pending.clear()
        
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        if self._process:
            try:
                self._process.stdin.close()  # type: ignore[union-attr]
            except Exception:
                pass
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except (asyncio.TimeoutError, ProcessLookupError):
                self._process.kill()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=1)
                except Exception:
                    pass
            self._process = None
        self._tools.clear()

    # ── tool operations ───────────────────────────────────────────────────

    async def list_tools(self) -> list[dict]:
        """Fetch available tools from the server."""
        if not self._connected:
            raise RuntimeError(f"MCP server '{self.name}' is not connected.")
        result = await self._request("tools/list", {})
        raw_tools = result.get("tools", [])
        self._tools = raw_tools
        return raw_tools

    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        """Invoke a tool on the server."""
        if not self._connected:
            raise RuntimeError(f"MCP server '{self.name}' is not connected.")
        result = await self._request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        return result

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def tools(self) -> list[dict]:
        return list(self._tools)

    # ── JSON-RPC transport (stdio) ────────────────────────────────────────

    async def _request(self, method: str, params: dict) -> dict:
        """Send a JSON-RPC request and wait for the matching response."""
        self._req_id += 1
        rid = self._req_id
        msg = {"jsonrpc": "2.0", "id": rid, "method": method, "params": params}
        future: asyncio.Future[dict] = asyncio.get_event_loop().create_future()
        self._pending[rid] = future
        await self._send(msg)
        try:
            return await asyncio.wait_for(future, timeout=30)
        except asyncio.TimeoutError:
            self._pending.pop(rid, None)
            raise RuntimeError(f"MCP request '{method}' timed out.")

    async def _notify(self, method: str, params: dict) -> None:
        """Send a JSON-RPC notification (no id, no response)."""
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        await self._send(msg)

    async def _send(self, msg: dict) -> None:
        """Write a JSON-RPC message with Content-Length framing."""
        if not self._process or not self._process.stdin:
            raise RuntimeError("MCP process not running.")
        body = json.dumps(msg).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
        self._process.stdin.write(header + body)
        await self._process.stdin.drain()

    async def _read_loop(self) -> None:
        """Read JSON-RPC responses from stdout, resolving pending futures."""
        assert self._process and self._process.stdout
        try:
            non_header_lines = 0
            while True:
                # Read headers until blank line.
                content_length = 0
                while True:
                    line = await self._process.stdout.readline()
                    if not line:
                        return  # EOF
                    line_s = line.decode("utf-8", errors="replace").strip()
                    if not line_s:
                        break  # end of headers
                    if line_s.lower().startswith("content-length:"):
                        content_length = int(line_s.split(":", 1)[1].strip())
                        non_header_lines = 0
                    else:
                        non_header_lines += 1
                        if non_header_lines > 100:
                            return  # Safety break for malformed stdio
                            
                if content_length <= 0:
                    continue
                body = await self._process.stdout.readexactly(content_length)
                try:
                    msg = json.loads(body)
                except json.JSONDecodeError:
                    continue

                # Resolve pending request.
                rid = msg.get("id")
                if rid is not None and rid in self._pending:
                    future = self._pending.pop(rid)
                    if "error" in msg:
                        future.set_exception(
                            RuntimeError(f"MCP error: {msg['error']}")
                        )
                    else:
                        future.set_result(msg.get("result", {}))
        except asyncio.CancelledError:
            pass
        except Exception:
            pass  # reader dies silently; disconnect will clean up
        finally:
            self._connected = False
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(RuntimeError("MCP disconnected"))
            self._pending.clear()
