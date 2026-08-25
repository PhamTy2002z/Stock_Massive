"""Bounded durable reads use the same total order as realtime replay."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.database import Base
from src.stocks.models import RealtimeEvent
from src.stocks.realtime import EventFamily, MarketDataSource, RealtimeEventStore

from .test_realtime_ingestion import BASE_TIME, trade


@pytest.fixture
def store():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[RealtimeEvent.__table__])
    yield RealtimeEventStore(sessionmaker(bind=engine, expire_on_commit=False))
    engine.dispose()


@pytest.mark.asyncio
async def test_query_is_bounded_paginated_and_stably_ordered(store):
    for event in (trade(3), trade(1), trade(2)):
        assert await store.append(event)

    first = await store.query(
        EventFamily.TRADE,
        "fpt",
        start=BASE_TIME,
        end=BASE_TIME + timedelta(seconds=1),
        limit=2,
    )
    second = await store.query(
        EventFamily.TRADE,
        "FPT",
        start=BASE_TIME,
        end=BASE_TIME + timedelta(seconds=1),
        after=first.next_cursor,
        limit=2,
    )

    assert first.events == (trade(1), trade(2))
    assert first.next_cursor is not None
    assert second.events == (trade(3),)
    assert second.next_cursor is None


@pytest.mark.asyncio
async def test_query_can_keep_provider_and_derived_sources_separate(store):
    assert await store.append(trade(1))

    page = await store.query(
        EventFamily.TRADE,
        "FPT",
        start=BASE_TIME,
        end=BASE_TIME + timedelta(seconds=1),
        source=MarketDataSource.INTERNAL,
    )

    assert page.events == ()


@pytest.mark.asyncio
async def test_query_refuses_unbounded_or_invalid_windows(store):
    with pytest.raises(ValueError, match="limit"):
        await store.query(
            EventFamily.TRADE,
            "FPT",
            start=BASE_TIME,
            end=BASE_TIME + timedelta(seconds=1),
            limit=1_001,
        )
    with pytest.raises(ValueError, match="window"):
        await store.query(
            EventFamily.TRADE,
            "FPT",
            start=BASE_TIME,
            end=BASE_TIME,
        )
