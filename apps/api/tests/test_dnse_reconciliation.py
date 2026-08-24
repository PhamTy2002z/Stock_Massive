"""Reconnect backfill recovers measured gaps without double counting live data."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from src.stocks.realtime import DataOutcomeKind
from src.stocks.realtime.dnse import (
    DnseEventParser,
    EventOrderTracker,
    ReconnectReconciler,
    RestPage,
    SnapshotDeduplicator,
)


BASE = {
    "marketId": "STO",
    "boardId": "G1",
    "symbol": "FPT",
    "tradingSessionId": 2,
    "matchPrice": "71.4",
    "matchQtty": 10,
    "side": 1,
}


class Pages:
    def __init__(self, rows):
        self.rows = rows

    async def pages(self, *_args, **_kwargs):
        yield RestPage(tuple(self.rows), None)


@pytest.mark.asyncio
async def test_reconnect_backfill_recovers_only_the_missing_event():
    observed = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)
    parser = DnseEventParser(clock=lambda: observed)
    live_row = {**BASE, "T": "te", "time": "2026-08-24T07:00:00Z", "tradeId": "live"}
    missing_row = {**BASE, "time": "2026-08-24T07:00:01Z", "tradeId": "gap"}
    live = parser.parse(live_row, request_id="live").event
    assert live is not None
    dedupe = SnapshotDeduplicator()
    assert dedupe.classify(live) is None
    reconciler = ReconnectReconciler(Pages([live_row, missing_row]), parser, dedupe)

    batch = await reconciler.reconcile(
        symbol="FPT", family="trades", trading_day=date(2026, 8, 24), board="G1"
    )

    assert batch.pages_read == 1
    assert batch.duplicate_count == 1
    assert [event.provider_trade_id for event in batch.recovered] == ["gap"]
    assert any(outcome.kind is DataOutcomeKind.DUPLICATE for outcome in batch.outcomes)


def test_out_of_order_event_becomes_a_gap_outcome():
    now = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)
    parser = DnseEventParser(clock=lambda: now)
    later = parser.parse(
        {**BASE, "T": "te", "time": "2026-08-24T07:00:02Z"}, request_id="later"
    ).event
    earlier = parser.parse(
        {**BASE, "T": "te", "time": "2026-08-24T07:00:01Z"}, request_id="earlier"
    ).event
    assert later and earlier
    tracker = EventOrderTracker()

    assert tracker.classify(later) is None
    outcome = tracker.classify(earlier)
    assert outcome and outcome.kind is DataOutcomeKind.GAP
