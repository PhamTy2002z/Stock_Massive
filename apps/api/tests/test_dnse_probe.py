"""The controlled probe reports only evidence it actually observed."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.stocks.realtime.dnse import probe
from src.stocks.realtime.dnse.auth import DnseCredentials


HCM = ZoneInfo("Asia/Ho_Chi_Minh")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (datetime(2026, 8, 24, 9, 0, tzinfo=HCM), True),
        (datetime(2026, 8, 24, 12, 0, tzinfo=HCM), False),
        (datetime(2026, 8, 24, 14, 30, tzinfo=HCM), True),
        (datetime(2026, 8, 23, 10, 0, tzinfo=HCM), False),
    ],
)
def test_market_hours_exclude_lunch_and_weekends(value, expected):
    assert probe._is_market_hours(value) is expected


class FakeWebSocket:
    instances = []

    def __init__(self, _signer):
        self.subscriptions = []
        self.closed = False
        self.instances.append(self)

    async def connect(self):
        return None

    async def subscribe(self, subscription):
        self.subscriptions.append(subscription)

    async def stream(self):
        yield {"T": "te", "symbol": "FPT"}
        yield {"T": "q", "symbol": "FPT"}

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_websocket_probe_reports_handshake_subscriptions_and_bounded_counts(monkeypatch):
    monkeypatch.setattr(probe, "DnseWebSocketClient", FakeWebSocket)

    report = await probe._websocket_probe(
        DnseCredentials("key", "secret"),
        "FPT",
        market_hours=True,
        duration_seconds=1,
    )

    assert report["authentication"] == "ok"
    assert report["subscriptions"] == "ok"
    assert report["subscription_lower_bound"] == 8
    assert report["payloads_observed"] == 2
    assert report["event_family_counts"] == {"q": 1, "te": 1}
    assert FakeWebSocket.instances[-1].closed is True
