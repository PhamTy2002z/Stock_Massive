"""Every byte a connector sends leaves through here, to a public address only.

A connector URL is typed by a user, so it is the textbook SSRF: ``localhost``,
a ``10.x`` service, the cloud metadata address, or a public name whose DNS
answer is private. The check is ``is_global`` on every address the name resolves
to, the same rule ``agent/tools/web.py`` applies to pages.

Checking is not enough on its own: a name that resolves public at check time and
private at connect time (DNS rebinding) walks straight past it. So the check and
the connection share one resolution. :class:`PinnedBackend` resolves a host the
first time a client connects to it, refuses a non-public answer, and from then
on connects that client to the same address without asking DNS again. TLS still
verifies the certificate against the hostname, because httpcore takes SNI from
the URL and not from the socket.

Redirects are never followed: a 3xx is an answer, and the MCP client treats it
as a failed request. A redirect to ``127.0.0.1`` therefore goes nowhere.

The one way around the rule is :func:`allow_private_hosts_for_tests`, which has
no environment switch at all and refuses under the ``production`` profile —
integration tests run a fake MCP server on loopback, and nothing else may.
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import socket
import ssl
from collections.abc import Callable, Iterator, Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import certifi
import httpcore2
import httpx2

from src.core.config import Settings, get_settings

Resolver = Callable[..., list[tuple[Any, ...]]]

_ALLOW_PRIVATE = False


class ConnectorURLRefused(ValueError):
    """The URL is not one a connector may reach."""


@contextlib.contextmanager
def allow_private_hosts_for_tests(settings: Settings | None = None) -> Iterator[None]:
    """Let loopback and plain http through, for a fake server in a test.

    Refused under ``deployment_profile == "production"`` — the default profile,
    so a deployment that never named one cannot reach this either.
    """
    global _ALLOW_PRIVATE
    profile = (settings or get_settings()).deployment_profile
    if profile == "production":
        raise RuntimeError("private connector hosts are never allowed in production")
    previous, _ALLOW_PRIVATE = _ALLOW_PRIVATE, True
    try:
        yield
    finally:
        _ALLOW_PRIVATE = previous


def private_hosts_allowed() -> bool:
    return _ALLOW_PRIVATE


def resolve_public(host: str, resolver: Resolver = socket.getaddrinfo) -> str:
    """One address for ``host``, every one of whose answers is public."""
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            rows = resolver(host, None, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ConnectorURLRefused(f"the host {host} does not resolve") from exc
        addresses = [ipaddress.ip_address(row[4][0].split("%", 1)[0]) for row in rows]
        if not addresses:
            raise ConnectorURLRefused(f"the host {host} resolved to no address")
    if not _ALLOW_PRIVATE:
        for address in addresses:
            if not address.is_global:
                raise ConnectorURLRefused(
                    f"the host {host} resolves to a non-public address ({address})"
                )
    return str(addresses[0])


def validate_connector_url(url: str, *, resolver: Resolver = socket.getaddrinfo) -> str:
    """A normalised https URL whose host is public, or :class:`ConnectorURLRefused`."""
    parsed = urlsplit((url or "").strip())
    allowed_schemes = {"https", "http"} if _ALLOW_PRIVATE else {"https"}
    if parsed.scheme.lower() not in allowed_schemes:
        raise ConnectorURLRefused("a connector URL must use https")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ConnectorURLRefused("a connector URL needs a host and no credentials in it")
    host = parsed.hostname.rstrip(".").lower()
    resolve_public(host, resolver)
    netloc = f"[{host}]" if ":" in host else host
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    return urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "/", parsed.query, ""))


class PinnedBackend(httpcore2.AsyncNetworkBackend):
    """Resolve each host once per client, refuse private answers, then pin."""

    def __init__(self, resolver: Resolver = socket.getaddrinfo) -> None:
        self._inner = httpcore2.AnyIOBackend()
        self._resolver = resolver
        self._pins: dict[str, str] = {}

    @property
    def pins(self) -> Mapping[str, str]:
        return dict(self._pins)

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> httpcore2.AsyncNetworkStream:
        address = self._pins.get(host)
        if address is None:
            address = await asyncio.to_thread(resolve_public, host, self._resolver)
            self._pins[host] = address
        return await self._inner.connect_tcp(
            address,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(self, *args: Any, **kwargs: Any) -> httpcore2.AsyncNetworkStream:
        raise ConnectorURLRefused("a connector never reaches a unix socket")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


class PinnedTransport(httpx2.AsyncHTTPTransport):
    """httpx2's transport with its connection pool built on :class:`PinnedBackend`."""

    def __init__(self, backend: PinnedBackend) -> None:
        super().__init__(trust_env=False)
        self.backend = backend
        # Rebuilt rather than patched: the pool is the one thing the public
        # constructor does not let a caller give a network backend to.
        # ``test_connectors_netguard`` asserts the pinned backend is the one
        # that connects, so an httpx2 upgrade that renames this fails loudly.
        self._pool = httpcore2.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(cafile=certifi.where()),
            max_connections=10,
            keepalive_expiry=5.0,
            network_backend=backend,
        )


def pinned_client(
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = 20.0,
    resolver: Resolver = socket.getaddrinfo,
) -> httpx2.AsyncClient:
    """An httpx2 client that can only reach public addresses, pinned per host."""
    return httpx2.AsyncClient(
        transport=PinnedTransport(PinnedBackend(resolver)),
        headers=dict(headers or {}),
        timeout=httpx2.Timeout(timeout, read=timeout),
        follow_redirects=False,
        trust_env=False,
    )


__all__ = [
    "ConnectorURLRefused",
    "PinnedBackend",
    "PinnedTransport",
    "allow_private_hosts_for_tests",
    "pinned_client",
    "private_hosts_allowed",
    "resolve_public",
    "validate_connector_url",
]
