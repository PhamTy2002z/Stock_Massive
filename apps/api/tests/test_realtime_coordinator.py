"""REST and WebSocket delivery converge on the same ingestion boundary."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from src.stocks.realtime import DnseIngestionCoordinator, FeedHealthState
from src.stocks.realtime.dnse import (
    DnseEventParser,
    ReconciliationBatch,
    RestResult,
    Subscription,
)


class CapturingSpine:
    def __init__(self):
        self.events = []
        self.health = []

    async def submit(self, event):
        self.events.append(event)
        return True

    async def set_feed_health(self, status, *, reason=None):
        self.health.append((status, reason))


class FakeRest:
    async def security_definition(self, symbol, _board=None):
        return RestResult(
            request_id=f"secdef-{symbol}",
            data={
                "T": "sd",
                "symbol": symbol,
                "marketId": "STO",
                "boardId": "G1",
                "time": "2026-08-24T02:00:00Z",
                "securityGroupId": "ST",
                "securityStatus": "listed",
                "isin": "VN000000FPT1",
                "basicPrice": "71.4",
                "ceilingPrice": "76.3",
                "floorPrice": "66.5",
            },
        )

    async def close_price(self, _symbol, _board=None):
        return RestResult(request_id="close", data={"close": "71.4"})


class FakeReconciler:
    def __init__(self, event):
        self.event = event

    async def reconcile(self, **_kwargs):
        return ReconciliationBatch((self.event,), (), 0, 1)


class FakeWebSocket:
    def __init__(self, payload):
        self.payload = payload
        self.connected = False
        self.closed = False
        self.subscriptions = []
        self.reconnect_handler = None

    def set_reconnect_handler(self, handler):
        self.reconnect_handler = handler

    async def connect(self):
        self.connected = True

    async def subscribe(self, subscription):
        self.subscriptions.append(subscription)

    async def stream(self):
        yield self.payload

    async def close(self):
        self.closed = True


def trade_payload(trade_id="live"):
    return {
        "T": "te",
        "marketId": "STO",
        "boardId": "G1",
        "symbol": "FPT",
        "tradingSessionId": 2,
        "time": "2026-08-24T02:00:00Z",
        "matchPrice": "71.4",
        "matchQtty": 10,
        "side": 1,
        "tradeId": trade_id,
    }


def coordinator(spine, websocket, reconciler):
    parser = DnseEventParser(clock=lambda: datetime(2026, 8, 24, 2, 0, 1, tzinfo=UTC))
    return DnseIngestionCoordinator(
        spine, parser, websocket, FakeRest(), reconciler
    )


@pytest.mark.asyncio
async def test_rest_bootstrap_and_reconnect_use_the_same_submit_path():
    spine = CapturingSpine()
    parser = DnseEventParser(clock=lambda: datetime(2026, 8, 24, 2, 0, 1, tzinfo=UTC))
    recovered = parser.parse(trade_payload("recovered"), request_id="gap").event
    assert recovered is not None
    service = coordinator(spine, FakeWebSocket(trade_payload()), FakeReconciler(recovered))

    assert await service.bootstrap_instruments(("FPT",)) == ()
    assert await service.reconcile(
        symbol="FPT", family="trades", trading_day=date(2026, 8, 24)
    ) == ()

    assert [event.metadata.event_family.value for event in spine.events] == [
        "security_definition",
        "trade",
    ]
    assert spine.health[-1] == (FeedHealthState.CONNECTED, None)


@pytest.mark.asyncio
async def test_websocket_closed_bar_or_tick_delivery_cannot_bypass_spine():
    spine = CapturingSpine()
    websocket = FakeWebSocket(trade_payload())
    parser = DnseEventParser(clock=lambda: datetime(2026, 8, 24, 2, 0, 1, tzinfo=UTC))
    recovered = parser.parse(trade_payload("recovered"), request_id="gap").event
    service = coordinator(spine, websocket, FakeReconciler(recovered))

    await service.run_live(())

    assert websocket.connected is True
    assert websocket.closed is True
    assert len(spine.events) == 1
    assert spine.events[0].provider_trade_id == "live"
    assert (FeedHealthState.CONNECTED, None) in spine.health


@pytest.mark.asyncio
async def test_websocket_reconnect_runs_rest_reconciliation_before_healthy():
    spine = CapturingSpine()
    websocket = FakeWebSocket(trade_payload())
    parser = DnseEventParser(clock=lambda: datetime(2026, 8, 24, 2, 0, 1, tzinfo=UTC))
    recovered = parser.parse(trade_payload("gap"), request_id="gap").event
    service = coordinator(spine, websocket, FakeReconciler(recovered))
    assert service and websocket.reconnect_handler is not None

    await websocket.reconnect_handler(
        (Subscription("tick.G1.json", ("FPT",)),)
    )

    assert [event.provider_trade_id for event in spine.events] == ["gap"]
    assert spine.health[0] == (
        FeedHealthState.RECONNECTING,
        "rest_reconciliation",
    )
    assert spine.health[-1] == (FeedHealthState.CONNECTED, None)
