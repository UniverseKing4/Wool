"""MCP client — JSON-RPC 2.0 over stdio transport.

Connects to an MCP server launched as a subprocess (stdio transport)
or via SSE (HTTP transport).  Implements the MCP lifecycle:

    connect → initialize → tools/list → tools/call → disconnect
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx



class MCPClient:
    """Communicates with a single MCP server."""

    def __init__(
        self,
        name: str,
        command: list[str] | None = None,
        url: str | None = None,
        env: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self.command = command
        self.url = url
        self.env = env
        self.headers = headers
        self._process: asyncio.subprocess.Process | None = None
        self._http_client: httpx.AsyncClient | None = None
        self._post_url: str | None = None
        self._endpoint_future: asyncio.Future[bool] | None = None
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
            await self._connect_sse()
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
        await self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "wool", "version": "1.0.0"},
            },
        )
        # Send initialized notification (no response expected).
        await self._notify("notifications/initialized", {})
        self._connected = True

    async def _connect_sse(self) -> None:
        assert self.url is not None
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=15.0, read=None, write=15.0, pool=15.0)
        )
        headers = dict(self.headers) if self.headers else {}
        headers["Accept"] = "application/json, text/event-stream"

        self._req_id += 1
        rid = self._req_id
        msg = {
            "jsonrpc": "2.0",
            "id": rid,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "wool", "version": "1.0.0"},
            },
        }

        # Test Serverless MCP
        try:
            response = await self._http_client.post(self.url, json=msg, headers=headers)
            if response.status_code == 200:
                self._is_serverless = True
                self._post_url = self.url
                self._serverless_session_id = response.headers.get("mcp-session-id")

                # Register future to capture response
                future: asyncio.Future[dict] = asyncio.get_event_loop().create_future()
                self._pending[rid] = future
                await self._parse_serverless_response(response)

                # Check if it was resolved
                if future.done() and not future.cancelled():
                    await self._notify("notifications/initialized", {})
                    self._connected = True
                    return
        except Exception:
            pass

        # Fallback to standard SSE
        self._is_serverless = False
        self._pending.pop(rid, None)
        self._endpoint_future = asyncio.get_event_loop().create_future()
        self._reader_task = asyncio.create_task(self._sse_read_loop())

        try:
            await asyncio.wait_for(self._endpoint_future, timeout=15)
        except asyncio.TimeoutError:
            raise RuntimeError("Timed out waiting for MCP SSE endpoint event.")

        # JSON-RPC initialize handshake.
        await self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "wool", "version": "1.0.0"},
            },
        )
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

        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

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
        result = await self._request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments,
            },
        )
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
        """Write a newline-delimited JSON-RPC message."""
        if self.command:
            if not self._process or not self._process.stdin:
                raise RuntimeError("MCP process not running.")
            body = json.dumps(msg).encode("utf-8") + b"\n"
            self._process.stdin.write(body)
            await self._process.stdin.drain()
        elif self.url:
            if not self._http_client or not self._post_url:
                raise RuntimeError(
                    "MCP SSE not fully connected (missing POST endpoint)."
                )
            headers = dict(self.headers) if self.headers else {}
            headers["Content-Type"] = "application/json"
            headers["Accept"] = "application/json, text/event-stream"
            if getattr(self, "_is_serverless", False) and getattr(
                self, "_serverless_session_id", None
            ):
                headers["Mcp-Session-Id"] = self._serverless_session_id

            response = await self._http_client.post(
                self._post_url, json=msg, headers=headers
            )
            response.raise_for_status()

            if getattr(self, "_is_serverless", False):
                await self._parse_serverless_response(response)

    async def _read_loop(self) -> None:
        """Read newline-delimited JSON-RPC responses from stdout, resolving pending futures."""
        assert self._process and self._process.stdout
        try:
            while True:
                line = await self._process.stdout.readline()
                if not line:
                    return  # EOF

                line_s = line.decode("utf-8", errors="replace").strip()
                if not line_s:
                    continue

                try:
                    msg = json.loads(line_s)
                except json.JSONDecodeError:
                    continue

                # Resolve pending request.
                rid = msg.get("id")
                if rid is not None and rid in self._pending:
                    future = self._pending.pop(rid)
                    if "error" in msg:
                        future.set_exception(RuntimeError(f"MCP error: {msg['error']}"))
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

    async def _sse_read_loop(self) -> None:
        """Read SSE events and handle JSON-RPC responses."""
        headers = dict(self.headers) if self.headers else {}
        headers["Accept"] = "text/event-stream"
        assert self._http_client is not None
        assert self.url is not None
        try:
            async with self._http_client.stream(
                "GET", self.url, headers=headers
            ) as response:
                response.raise_for_status()
                event_name = "message"
                event_data: list[str] = []
                async for line in response.aiter_lines():
                    if not line:
                        data = "\n".join(event_data)
                        if event_name == "endpoint":
                            post_url = data.strip()
                            if not post_url.startswith("http"):
                                import urllib.parse

                                post_url = urllib.parse.urljoin(self.url, post_url)
                            self._post_url = post_url
                            if (
                                self._endpoint_future
                                and not self._endpoint_future.done()
                            ):
                                self._endpoint_future.set_result(True)
                        elif event_name == "message":
                            try:
                                msg = json.loads(data)
                                rid = msg.get("id")
                                if rid is not None and rid in self._pending:
                                    future = self._pending.pop(rid)
                                    if "error" in msg:
                                        future.set_exception(
                                            RuntimeError(f"MCP error: {msg['error']}")
                                        )
                                    else:
                                        future.set_result(msg.get("result", {}))
                            except Exception:
                                pass
                        event_name = "message"
                        event_data.clear()
                        continue

                    if line.startswith("event:"):
                        event_name = line[6:].strip()
                    elif line.startswith("data:"):
                        # SSE data lines can have a single leading space which should be stripped
                        data_val = line[5:]
                        if data_val.startswith(" "):
                            data_val = data_val[1:]
                        event_data.append(data_val)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if self._endpoint_future and not self._endpoint_future.done():
                self._endpoint_future.set_exception(e)
        finally:
            self._connected = False
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(RuntimeError("MCP disconnected"))
            self._pending.clear()

    async def _parse_serverless_response(self, response: httpx.Response) -> None:
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            text = await response.aread()
            try:
                msg = json.loads(text.decode("utf-8"))
                rid = msg.get("id")
                if rid is not None and rid in self._pending:
                    future = self._pending.pop(rid)
                    if "error" in msg:
                        future.set_exception(RuntimeError(f"MCP error: {msg['error']}"))
                    else:
                        future.set_result(msg.get("result", {}))
            except Exception:
                pass
            return

        event_name = "message"
        event_data: list[str] = []
        async for line in response.aiter_lines():
            if not line:
                data = "\n".join(event_data)
                if event_name == "message" and data.strip():
                    try:
                        msg = json.loads(data)
                        rid = msg.get("id")
                        if rid is not None and rid in self._pending:
                            future = self._pending.pop(rid)
                            if "error" in msg:
                                future.set_exception(
                                    RuntimeError(f"MCP error: {msg['error']}")
                                )
                            else:
                                future.set_result(msg.get("result", {}))
                    except Exception:
                        pass
                event_name = "message"
                event_data.clear()
                continue

            if line.startswith("event:"):
                event_name = line[6:].strip()
            elif line.startswith("data:"):
                data_val = line[5:]
                if data_val.startswith(" "):
                    data_val = data_val[1:]
                event_data.append(data_val)

        # In case the response doesn't end with a blank line
        if event_data:
            data = "\n".join(event_data)
            if event_name == "message" and data.strip():
                try:
                    msg = json.loads(data)
                    rid = msg.get("id")
                    if rid is not None and rid in self._pending:
                        future = self._pending.pop(rid)
                        if "error" in msg:
                            future.set_exception(
                                RuntimeError(f"MCP error: {msg['error']}")
                            )
                        else:
                            future.set_result(msg.get("result", {}))
                except Exception:
                    pass
