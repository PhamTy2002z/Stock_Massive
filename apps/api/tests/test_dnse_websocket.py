"""Deterministic WebSocket lifecycle, heartbeat, resubscribe, and cancellation."""

from __future__ import annotations

import asyncio
import json
import ssl

import pytest

from src.stocks.realtime.dnse import (
    DnseCredentials,
    DnseWebSocketClient,
    Subscription,
    WebSocketSigner,
)
from src.stocks.realtime.dnse.websocket import _connect


class FakeSocket:
    def __init__(self, messages: list[dict | bytes]):
        self.messages = asyncio.Queue()
        for message in messages:
            self.messages.put_nowait(message if isinstance(message, bytes) else json.dumps(message))
        self.sent: list[dict] = []
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    async def recv(self):
        return await self.messages.get()

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_auth_ping_rotation_resubscribe_and_clean_cancellation():
    sockets = [
        FakeSocket(
            [
                {"action": "welcome", "session_id": "one"},
                {"action": "auth_success"},
                {"action": "ping"},
            ]
        ),
        FakeSocket(
            [
                {"action": "welcome", "session_id": "two"},
                {"action": "auth_success"},
                {"T": "te", "symbol": "FPT"},
            ]
        ),
    ]
    connect_count = 0
    reconnected = []

    async def connector(*_args, **_kwargs):
        nonlocal connect_count
        socket = sockets[connect_count]
        connect_count += 1
        return socket

    times = iter([0.0, 0.0, 2.0, 2.0, 2.0, 2.0])
    client = DnseWebSocketClient(
        WebSocketSigner(DnseCredentials("key", "secret"), timestamp=lambda: 1.0),
        connector=connector,
        rotation_seconds=1,
        clock=lambda: next(times, 2.0),
        queue_size=1,
        on_reconnect=lambda subscriptions: _capture_reconnect(
            reconnected, subscriptions
        ),
    )
    await client.connect()
    subscription = Subscription("tick_extra.G1.json", ("FPT",))
    await client.subscribe(subscription)

    stream = client.stream()
    message = await asyncio.wait_for(anext(stream), timeout=2)
    await stream.aclose()

    assert message["symbol"] == "FPT"
    assert {item["action"] for item in sockets[0].sent} >= {"auth", "subscribe", "pong"}
    assert any(item["action"] == "subscribe" for item in sockets[1].sent)
    assert all(socket.closed for socket in sockets)
    assert client.metrics.snapshot().counters["reconnects"] == 1
    assert reconnected == [(subscription,)]


@pytest.mark.asyncio
async def test_binary_payload_is_refused_and_bounded_queue_records_pressure():
    socket = FakeSocket(
        [
            {"action": "welcome", "session_id": "one"},
            {"action": "auth_success"},
            {"T": "te", "symbol": "FPT"},
            {"T": "te", "symbol": "HPG"},
        ]
    )

    async def connector(*_args, **_kwargs):
        return socket

    client = DnseWebSocketClient(
        WebSocketSigner(DnseCredentials("key", "secret"), timestamp=lambda: 1.0),
        connector=connector,
        queue_size=1,
    )
    await client.connect()
    client._enqueue({"symbol": "FPT"})
    client._enqueue({"symbol": "HPG"})
    await client.close()

    snapshot = client.metrics.snapshot()
    assert snapshot.counters["queue_pressure"] == 1
    assert snapshot.counters["gaps"] == 1


def test_subscription_identity_does_not_overwrite_symbol_sets():
    first = Subscription("tick.G1.json", ("FPT",))
    second = Subscription("tick.G1.json", ("HPG",))
    assert first.identity != second.identity
    with pytest.raises(ValueError):
        Subscription("tick.G1.msgpack", ("FPT",))
    with pytest.raises(ValueError):
        Subscription("order.STOCK.json", ("FPT",))


@pytest.mark.asyncio
async def test_default_connector_uses_a_verified_ca_context(monkeypatch):
    captured = {}

    async def connect(_url, **kwargs):
        captured.update(kwargs)
        return FakeSocket([])

    monkeypatch.setattr("websockets.connect", connect)
    await _connect("wss://ws-openapi.dnse.com.vn/v1/stream?encoding=json")

    context = captured["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode is ssl.CERT_REQUIRED
    assert context.check_hostname is True


async def _capture_reconnect(target, subscriptions):
    target.append(subscriptions)
