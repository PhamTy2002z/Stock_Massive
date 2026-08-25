"""Bounded source-neutral S3 serving contracts over stored evidence only."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.database import Base
from src.stocks.models import RealtimeEvent
from src.stocks.realtime import EventFamily, HotProjectionStore, RealtimeEventStore
from src.stocks.realtime.service import RealtimeReadService

from .test_realtime_aggregation import trade
from .test_realtime_ingestion import FakeRedis


@pytest.fixture
def event_store():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[RealtimeEvent.__table__])
    yield RealtimeEventStore(sessionmaker(bind=engine, expire_on_commit=False))
    engine.dispose()


@pytest.mark.asyncio
async def test_event_api_is_bounded_paginated_and_contains_no_provider_payload(
    event_store,
):
    first, second = trade(1), trade(2, second=20)
    assert await event_store.append(first)
    assert await event_store.append(second)
    service = RealtimeReadService(
        event_store,
        HotProjectionStore(FakeRedis()),
        ("FPT",),
        clock=lambda: datetime(2026, 8, 24, 3, tzinfo=UTC),
    )
    start = first.metadata.provider_time - timedelta(seconds=1)
    end = second.metadata.provider_time + timedelta(seconds=1)

    page_one = await service.events(
        EventFamily.TRADE, "fpt", start=start, end=end, limit=1
    )
    page_two = await service.events(
        EventFamily.TRADE,
        "FPT",
        start=start,
        end=end,
        limit=1,
        cursor=page_one.next_cursor,
    )

    assert tuple(item.evidence_id for item in page_one.items + page_two.items) == (
        first.metadata.evidence_id,
        second.metadata.evidence_id,
    )
    assert page_two.next_cursor is None
    assert page_one.items[0].board == "G1"
    assert page_one.items[0].units["quantity"] == "share"
    assert "raw_payload_hash" not in page_one.items[0].data


@pytest.mark.asyncio
async def test_event_api_refuses_non_universe_oversized_and_cross_query_cursor(
    event_store,
):
    event = trade(1)
    assert await event_store.append(event)
    service = RealtimeReadService(
        event_store,
        HotProjectionStore(FakeRedis()),
        ("FPT",),
    )
    start = event.metadata.provider_time - timedelta(seconds=1)
    end = event.metadata.provider_time + timedelta(seconds=1)

    with pytest.raises(LookupError, match="Universe"):
        await service.events(EventFamily.TRADE, "VCB", start=start, end=end)
    with pytest.raises(ValueError, match="window exceeds"):
        await service.events(
            EventFamily.TRADE,
            "FPT",
            start=start,
            end=start + timedelta(days=1, microseconds=1),
        )
    page = await service.events(
        EventFamily.TRADE, "FPT", start=start, end=end, limit=1
    )
    assert page.next_cursor is None
    with pytest.raises(ValueError, match="invalid realtime cursor"):
        await service.events(
            EventFamily.TRADE,
            "FPT",
            start=start,
            end=end,
            cursor="not-a-cursor",
        )


@pytest.mark.asyncio
async def test_projection_api_reads_board_specific_hot_metrics(event_store):
    redis = FakeRedis()
    projections = HotProjectionStore(redis)
    from src.stocks.realtime.metrics import project_trade_metrics

    metric = project_trade_metrics((trade(1), trade(2)))
    assert await projections.save_metric(metric)
    service = RealtimeReadService(event_store, projections, ("FPT",))

    response = await service.metrics("FPT", "G1")

    assert response.projections["trade_metrics"]["session_volume_shares"] == 200
    assert response.projections["trade_metrics"]["units"]["session_volume_shares"] == "share"
    assert response.projections["trade_metrics"]["freshness_seconds"] >= 0
    assert (await service.metrics("FPT", "G4")).projections == {}


def test_all_s3_routes_are_registered_in_the_application_contract():
    from src.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/realtime/trades/{symbol}" in paths
    assert "/api/v1/realtime/bars/{symbol}" in paths
    assert "/api/v1/realtime/foreign-flow/{symbol}" in paths
    assert "/api/v1/realtime/projections/{symbol}" in paths
    assert "/api/v1/realtime/health" in paths
