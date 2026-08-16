"""One reconnectable MCP server connection over stdio or Streamable HTTP."""

from __future__ import annotations

import asyncio
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

import httpx2
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client


@dataclass(frozen=True)
class DiscoveredTool:
    name: str
    description: str
    input_schema: dict[str, Any]


class MCPConnection:
    """Keep one negotiated client alive and reconnect it with bounded backoff."""

    def __init__(self, name: str, config: dict[str, Any]) -> None:
        self.name = name
        self.config = config
        self._stack: AsyncExitStack | None = None
        self._client: Client | None = None
        self.tools: tuple[DiscoveredTool, ...] = ()
        self.server_version = "unknown"
        self.protocol_version = "unknown"
        self.last_error: str | None = None
        self._failures = 0
        self._retry_at = 0.0
        self._lock = asyncio.Lock()

    @property
    def healthy(self) -> bool:
        return self._client is not None

    async def connect(self) -> tuple[DiscoveredTool, ...]:
        async with self._lock:
            if self._client is not None:
                return self.tools
            if time.monotonic() < self._retry_at:
                raise RuntimeError(f"MCP server {self.name!r} is in reconnect backoff")
            stack = AsyncExitStack()
            try:
                transport = await self._transport(stack)
                client = Client(transport, read_timeout_seconds=20.0)
                await stack.enter_async_context(client)
                listed = await client.list_tools()
                self.tools = tuple(
                    DiscoveredTool(
                        name=tool.name,
                        description=tool.description or f"Tool from MCP server {self.name}.",
                        input_schema=dict(tool.input_schema),
                    )
                    for tool in listed.tools
                )
                info = client.server_info
                self.server_version = (
                    str(getattr(info, "version", "") or "unknown")
                    if info is not None
                    else "unknown"
                )
                self.protocol_version = str(client.protocol_version or "unknown")
                self._stack = stack.pop_all()
                self._client = client
                self._failures = 0
                self._retry_at = 0.0
                self.last_error = None
                return self.tools
            except Exception as exc:
                await stack.aclose()
                self._failed(exc)
                raise

    async def call(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        if self._client is None:
            await self.connect()
        assert self._client is not None
        try:
            return await self._client.call_tool(
                tool_name, arguments, read_timeout_seconds=20.0
            )
        except Exception as exc:
            await self.close()
            self._failed(exc)
            raise

    async def close(self) -> None:
        async with self._lock:
            stack, self._stack = self._stack, None
            self._client = None
            if stack is not None:
                await stack.aclose()

    async def _transport(self, stack: AsyncExitStack):
        transport = str(self.config.get("transport") or "").lower()
        if transport == "stdio":
            command = str(self.config.get("command") or "").strip()
            if not command:
                raise ValueError(f"MCP server {self.name!r} has no stdio command")
            params = StdioServerParameters(
                command=command,
                args=[str(arg) for arg in self.config.get("args", [])],
                env={
                    str(key): str(value)
                    for key, value in dict(self.config.get("env") or {}).items()
                }
                or None,
                cwd=self.config.get("cwd"),
            )
            return stdio_client(params)
        if transport == "streamable_http":
            url = str(self.config.get("url") or "").strip()
            if not url:
                raise ValueError(f"MCP server {self.name!r} has no HTTP URL")
            headers = {
                str(key): str(value)
                for key, value in dict(self.config.get("headers") or {}).items()
            }
            http = await stack.enter_async_context(
                httpx2.AsyncClient(headers=headers, follow_redirects=True)
            )
            return streamable_http_client(url, http_client=http)
        raise ValueError(
            f"MCP server {self.name!r} transport must be stdio or streamable_http"
        )

    def _failed(self, exc: Exception) -> None:
        self._failures += 1
        self.last_error = str(exc)[:500]
        self._retry_at = time.monotonic() + min(60.0, 2 ** min(self._failures, 5))


__all__ = ["DiscoveredTool", "MCPConnection"]
