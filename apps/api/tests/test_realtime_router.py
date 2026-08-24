"""The health API serves durable state without calling the provider."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from src.stocks.realtime.health import HealthSnapshot
from src.stocks.realtime.router import get_realtime_health


@pytest.mark.asyncio
async def test_health_route_returns_durable_feed_and_data_state(monkeypatch):
    snapshots = {
        "feed": HealthSnapshot(
            scope="feed",
            status="degraded",
            reason="queue_pressure",
            observed_at=datetime(2026, 8, 24, tzinfo=UTC),
        ),
        "data": HealthSnapshot(
            scope="data",
            status="gapped",
            reason="reconnect_gap",
            observed_at=datetime(2026, 8, 24, tzinfo=UTC),
        ),
    }

    class Store:
        async def read_health(self, scope):
            return snapshots.get(scope)

    monkeypatch.setattr("src.stocks.realtime.router.RealtimeEventStore", Store)

    response = await get_realtime_health()

    assert response.feed and response.feed.status == "degraded"
    assert response.data and response.data.status == "gapped"


@pytest.mark.asyncio
async def test_health_route_distinguishes_never_recorded_from_healthy(monkeypatch):
    class EmptyStore:
        async def read_health(self, _scope):
            return None

    monkeypatch.setattr("src.stocks.realtime.router.RealtimeEventStore", EmptyStore)

    with pytest.raises(HTTPException) as captured:
        await get_realtime_health()
    assert captured.value.status_code == 404


def test_health_route_is_registered_in_the_application_contract():
    from src.main import app

    assert "/api/v1/realtime/health" in app.openapi()["paths"]
