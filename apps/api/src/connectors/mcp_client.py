"""Talk to one remote MCP server: list its tools, call one.

A fresh session per operation (initialize, then the request): nothing is held
open between Turns, so there is no per-user connection to leak, and a server
that restarted between two calls is simply a new session.

# ponytail: one session per call costs an initialize round trip each time; pool
# sessions per (user, connector) with a short TTL if connector latency matters.

The SDK reports a refused request as one generic error and loses the status, so
the pinned client records the last HTTP status it saw; that is what tells a 401
(park the connector, ask the user to sign in again) from a server that is down
(retry later). Errors are three types because the caller's move differs.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx2
import mcp_types as types
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from . import netguard

#: Enough for any real server, few enough that a hostile one cannot page us
#: through an endless list.
MAX_LISTED_TOOLS = 500
MAX_LIST_PAGES = 10


class ConnectorError(Exception):
    """A connector operation failed; ``code`` is the stable reason."""

    code = "connector_failed"


class ConnectorAuthError(ConnectorError):
    """The server refused our credentials (401/403). Permanent until re-auth."""

    code = "auth_failed"


class ConnectorUnavailable(ConnectorError):
    """The server could not be reached or answered with a server error."""

    code = "unavailable"


class ConnectorProtocolError(ConnectorError):
    """The server answered, but not with something MCP can use."""

    code = "protocol_error"


@dataclass(frozen=True)
class Target:
    """Where one connector lives and what to send it."""

    url: str
    headers: Mapping[str, str] = field(default_factory=dict)
    timeout: float = 20.0


@dataclass
class _Seen:
    status: int | None = None


def _innermost(error: BaseException) -> BaseException:
    while isinstance(error, BaseExceptionGroup) and error.exceptions:
        error = error.exceptions[0]
    return error


def _classify(error: BaseException, seen: _Seen) -> ConnectorError:
    inner = _innermost(error)
    if isinstance(inner, ConnectorError):
        return inner
    if seen.status in (401, 403):
        return ConnectorAuthError(f"the server answered {seen.status}")
    if isinstance(inner, netguard.ConnectorURLRefused):
        return ConnectorUnavailable(str(inner))
    if seen.status is not None and 300 <= seen.status < 400:
        return ConnectorProtocolError(f"the server redirected ({seen.status}); redirects are not followed")
    if seen.status is not None and seen.status >= 500:
        return ConnectorUnavailable(f"the server answered {seen.status}")
    if isinstance(inner, (httpx2.TransportError, TimeoutError, OSError)):
        return ConnectorUnavailable(f"the server could not be reached ({type(inner).__name__})")
    if seen.status is not None and seen.status >= 400:
        return ConnectorProtocolError(f"the server answered {seen.status}")
    return ConnectorProtocolError(f"the server's answer was not usable ({type(inner).__name__})")


@contextlib.asynccontextmanager
async def _session(target: Target) -> AsyncIterator[ClientSession]:
    seen = _Seen()

    async def remember(response: httpx2.Response) -> None:
        seen.status = response.status_code

    client = netguard.pinned_client(headers=target.headers, timeout=target.timeout)
    client.event_hooks["response"] = [remember]
    try:
        url = await asyncio.to_thread(netguard.validate_connector_url, target.url)
        async with client:
            async with streamable_http_client(url, http_client=client) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=target.timeout) as session:
                    await session.initialize()
                    yield session
    except ConnectorError:
        raise
    except Exception as exc:  # noqa: BLE001 - every failure becomes a typed one
        # A cancellation is not caught here: it is a BaseException, and a Turn
        # that was stopped must stop rather than report a broken connector.
        raise _classify(exc, seen) from exc


async def list_tools(target: Target) -> list[types.Tool]:
    tools: list[types.Tool] = []
    async with _session(target) as session:
        cursor: str | None = None
        for _ in range(MAX_LIST_PAGES):
            page = await session.list_tools(
                params=types.PaginatedRequestParams(cursor=cursor) if cursor else None
            )
            tools.extend(page.tools)
            cursor = page.next_cursor
            if not cursor or len(tools) >= MAX_LISTED_TOOLS:
                break
    return tools[:MAX_LISTED_TOOLS]


async def call_tool(target: Target, name: str, arguments: Mapping[str, Any]) -> types.CallToolResult:
    async with _session(target) as session:
        result = await session.call_tool(name, dict(arguments), read_timeout_seconds=target.timeout)
    if not isinstance(result, types.CallToolResult):
        raise ConnectorProtocolError("the server asked for input this client cannot give")
    return result


def result_text(result: types.CallToolResult) -> tuple[str, Sequence[str]]:
    """The text a tool returned, and a note for every block that was not text."""
    pieces: list[str] = []
    skipped: list[str] = []
    for block in result.content:
        if isinstance(block, types.TextContent):
            pieces.append(block.text)
        else:
            skipped.append(getattr(block, "type", type(block).__name__))
    if not pieces and result.structured_content is not None:
        pieces.append(json.dumps(result.structured_content, ensure_ascii=False, default=str))
    return "\n".join(pieces), skipped


__all__ = [
    "ConnectorAuthError",
    "ConnectorError",
    "ConnectorProtocolError",
    "ConnectorUnavailable",
    "MAX_LISTED_TOOLS",
    "Target",
    "call_tool",
    "list_tools",
    "result_text",
]
