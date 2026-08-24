"""Bounded reconnecting DNSE JSON WebSocket transport."""

from __future__ import annotations

import asyncio
import json
import re
import ssl
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable, Protocol

from .auth import WebSocketSigner
from .metrics import AdapterMetrics
from .validation import RESOLUTIONS, validated_symbol


_SYMBOL_CHANNEL = re.compile(
    r"^(security_definition|tick|tick_extra|top_price|expected_price|foreign)\."
    r"[A-Z0-9_*\-]{1,32}\.json$"
)
_INDEX_CHANNEL = re.compile(r"^(market_index|estimated_market_index)\.[A-Z0-9_-]{1,32}\.json$")
_SESSION_CHANNEL = re.compile(r"^session\.[A-Z0-9_*\-]{1,32}\.[A-Z0-9_*\-]{1,32}\.json$")


class WebSocketTransport(Protocol):
    async def send(self, message: str) -> None: ...
    async def recv(self) -> str | bytes: ...
    async def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class Subscription:
    channel: str
    symbols: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        ohlc_parts = self.channel.split(".")
        is_ohlc = (
            len(ohlc_parts) == 3
            and ohlc_parts[0] in {"ohlc", "ohlc_closed"}
            and ohlc_parts[1] in RESOLUTIONS
            and ohlc_parts[2] == "json"
        )
        is_symbol = _SYMBOL_CHANNEL.fullmatch(self.channel) is not None
        is_index = _INDEX_CHANNEL.fullmatch(self.channel) is not None
        is_session = _SESSION_CHANNEL.fullmatch(self.channel) is not None
        if not any((is_ohlc, is_symbol, is_index, is_session)):
            raise ValueError("only documented DNSE market-data JSON channels are admitted")
        normalized_symbols = tuple(validated_symbol(symbol) for symbol in self.symbols)
        object.__setattr__(self, "symbols", normalized_symbols)
        if len(set(normalized_symbols)) != len(normalized_symbols):
            raise ValueError("subscription symbols must be unique")
        if (is_ohlc or is_symbol) and not normalized_symbols:
            raise ValueError("symbol market-data channels require at least one symbol")
        if (is_index or is_session) and normalized_symbols:
            raise ValueError("index and session channels do not accept symbols")

    @property
    def identity(self) -> tuple[str, tuple[str, ...]]:
        return self.channel, self.symbols


class DnseWebSocketClient:
    def __init__(
        self,
        signer: WebSocketSigner,
        *,
        url: str = "wss://ws-openapi.dnse.com.vn/v1/stream?encoding=json",
        connector: Callable[..., Awaitable[WebSocketTransport]] | None = None,
        metrics: AdapterMetrics | None = None,
        queue_size: int = 2_000,
        rotation_seconds: float = 8 * 60 * 60,
        clock: Callable[[], float] = time.monotonic,
        on_reconnect: Callable[[tuple[Subscription, ...]], Awaitable[None]] | None = None,
    ) -> None:
        if not url.startswith("wss://") or "encoding=json" not in url:
            raise ValueError("DNSE WebSocket requires verified WSS JSON transport")
        if queue_size < 1 or not 1 <= rotation_seconds <= 8 * 60 * 60:
            raise ValueError("invalid WebSocket queue or rotation bound")
        self._signer = signer
        self._url = url
        self._connector = connector or _connect
        self.metrics = metrics or AdapterMetrics()
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=queue_size)
        self._rotation_seconds = rotation_seconds
        self._clock = clock
        self._on_reconnect = on_reconnect
        self._transport: WebSocketTransport | None = None
        self._connected_at = 0.0
        self._subscriptions: dict[tuple[str, tuple[str, ...]], Subscription] = {}
        self._closed = False
        self._pump: asyncio.Task[None] | None = None

    def set_reconnect_handler(
        self,
        handler: Callable[[tuple[Subscription, ...]], Awaitable[None]] | None,
    ) -> None:
        """Attach the ingestion recovery hook without exposing transport internals."""
        self._on_reconnect = handler

    async def connect(self) -> None:
        self._closed = False
        transport = await asyncio.wait_for(
            self._connector(
                self._url,
                open_timeout=10,
                close_timeout=5,
                ping_interval=None,
                max_queue=256,
            ),
            timeout=12,
        )
        self._transport = transport
        welcome = await self._receive_json(timeout=10)
        if welcome.get("action") not in {"welcome", "connected"} and not (
            welcome.get("session_id") or welcome.get("sid")
        ):
            await transport.close()
            self._transport = None
            raise RuntimeError("unexpected DNSE WebSocket welcome")
        await transport.send(json.dumps(self._signer.message(), separators=(",", ":")))
        auth = await self._receive_json(timeout=10)
        if auth.get("action") != "auth_success":
            await transport.close()
            self._transport = None
            raise RuntimeError("DNSE WebSocket authentication failed")
        self._connected_at = self._clock()

    async def subscribe(self, subscription: Subscription) -> None:
        self._subscriptions[subscription.identity] = subscription
        await self._send_subscription("subscribe", subscription)

    async def unsubscribe(self, subscription: Subscription) -> None:
        await self._send_subscription("unsubscribe", subscription)
        self._subscriptions.pop(subscription.identity, None)

    async def stream(self) -> AsyncIterator[dict[str, Any]]:
        if self._transport is None:
            await self.connect()
        if self._pump is None or self._pump.done():
            self._pump = asyncio.create_task(self._pump_messages())
        try:
            while not self._closed:
                item = await self._queue.get()
                self.metrics.gauge("queue_depth", self._queue.qsize())
                yield item
        finally:
            await self.close()

    async def close(self) -> None:
        self._closed = True
        current = asyncio.current_task()
        if self._pump and self._pump is not current and not self._pump.done():
            self._pump.cancel()
            try:
                await self._pump
            except asyncio.CancelledError:
                pass
        self._pump = None
        if self._transport is not None:
            await self._transport.close()
            self._transport = None

    async def _pump_messages(self) -> None:
        backoff = 0.25
        while not self._closed:
            try:
                if self._transport is None or self._clock() - self._connected_at >= self._rotation_seconds:
                    await self._reconnect()
                message = await self._receive_json(timeout=240)
                action = message.get("action")
                if action == "ping":
                    transport = self._transport
                    if transport is None:
                        raise RuntimeError("DNSE WebSocket disconnected during ping")
                    await transport.send('{"action":"pong"}')
                    continue
                if action in {"pong", "subscribed", "unsubscribed"}:
                    continue
                self._enqueue(message)
                backoff = 0.25
            except asyncio.CancelledError:
                raise
            except Exception:
                self.metrics.increment("disconnects")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 10)
                if self._transport is not None:
                    await self._transport.close()
                    self._transport = None

    async def _reconnect(self) -> None:
        previous = tuple(self._subscriptions.values())
        if self._transport is not None:
            await self._transport.close()
            self._transport = None
        await self.connect()
        for subscription in previous:
            await self._send_subscription("subscribe", subscription)
        if previous:
            self.metrics.increment("reconnects")
            if self._on_reconnect is not None:
                await self._on_reconnect(previous)

    def _enqueue(self, message: dict[str, Any]) -> None:
        if self._queue.full():
            self._queue.get_nowait()
            self.metrics.increment("queue_pressure")
            self.metrics.increment("gaps")
        self._queue.put_nowait(message)
        self.metrics.gauge("queue_depth", self._queue.qsize())

    async def _send_subscription(self, action: str, subscription: Subscription) -> None:
        if self._transport is None:
            raise RuntimeError("DNSE WebSocket is not connected")
        payload = {
            "action": action,
            "channels": [
                {"name": subscription.channel, "symbols": list(subscription.symbols)}
            ],
        }
        await self._transport.send(json.dumps(payload, separators=(",", ":")))

    async def _receive_json(self, *, timeout: float) -> dict[str, Any]:
        if self._transport is None:
            raise RuntimeError("DNSE WebSocket is not connected")
        raw = await asyncio.wait_for(self._transport.recv(), timeout=timeout)
        if isinstance(raw, bytes):
            raise ValueError("MessagePack/binary payloads are not admitted")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("DNSE WebSocket message must be a JSON object")
        return data


async def _connect(url: str, **kwargs: Any) -> WebSocketTransport:
    import certifi
    import websockets

    kwargs.setdefault("ssl", ssl.create_default_context(cafile=certifi.where()))
    return await websockets.connect(url, **kwargs)
