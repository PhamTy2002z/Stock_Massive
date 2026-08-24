"""Opt-in configuration and lifecycle ownership for the realtime feed."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from src.core.config import Settings
from src.stocks.realtime.runtime import RealtimeRuntime


def test_realtime_configuration_is_opt_in_and_requires_secrets_and_redis():
    assert Settings().realtime_ingestion_enabled is False
    with pytest.raises(ValidationError, match="DNSE_API_KEY"):
        Settings(realtime_ingestion_enabled=True, cache_redis_url="redis://cache")
    with pytest.raises(ValidationError, match="Redis"):
        Settings(
            realtime_ingestion_enabled=True,
            dnse_api_key="key",
            dnse_api_secret="secret",
            cache_redis_url="",
            upstash_redis_url="",
            upstash_redis_token="",
            upstash_redis_rest_url="",
            upstash_redis_rest_token="",
        )

    configured = Settings(
        realtime_ingestion_enabled=True,
        dnse_api_key="key",
        dnse_api_secret="secret",
        cache_redis_url="redis://cache",
        dnse_board_ids="G1,G4,G1",
    )
    assert configured.realtime_boards == ("G1", "G4")
    assert "secret" not in repr(configured.dnse_api_secret)
    with pytest.raises(ValidationError, match="invalid board"):
        Settings(
            realtime_ingestion_enabled=True,
            dnse_api_key="key",
            dnse_api_secret="secret",
            cache_redis_url="redis://cache",
            dnse_board_ids="G1,bad board",
        )


class FakeSpine:
    def __init__(self):
        self.started = False
        self.stopped_with = None

    async def start(self):
        self.started = True

    async def stop(self, *, timeout):
        self.stopped_with = timeout


class FakeCoordinator:
    def __init__(self):
        self.bootstrapped = None
        self.subscriptions = None
        self.running = asyncio.Event()

    async def bootstrap_instruments(self, symbols):
        self.bootstrapped = symbols
        return ()

    async def run_live(self, subscriptions):
        self.subscriptions = subscriptions
        self.running.set()
        await asyncio.Future()


class FakeRest:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_runtime_starts_one_feed_and_owns_clean_shutdown():
    coordinator = FakeCoordinator()
    spine = FakeSpine()
    rest = FakeRest()
    runtime = RealtimeRuntime(
        coordinator,
        spine,
        rest,
        symbols=("FPT", "HPG"),
        boards=("G1", "G4"),
        shutdown_timeout=7,
    )

    await runtime.start()
    await coordinator.running.wait()
    subscriptions = coordinator.subscriptions
    assert spine.started is True
    assert coordinator.bootstrapped == ("FPT", "HPG")
    assert subscriptions is not None
    assert len({subscription.identity for subscription in subscriptions}) == len(
        subscriptions
    )
    assert not any(
        subscription.channel.startswith("top_price")
        for subscription in subscriptions
    )

    await runtime.stop()
    assert spine.stopped_with == 7
    assert rest.closed is True


@pytest.mark.asyncio
async def test_runtime_closes_rest_even_when_spine_shutdown_fails():
    class FailingSpine(FakeSpine):
        async def stop(self, *, timeout):
            raise RuntimeError(f"failed after {timeout}")

    coordinator = FakeCoordinator()
    spine = FailingSpine()
    rest = FakeRest()
    runtime = RealtimeRuntime(
        coordinator,
        spine,
        rest,
        symbols=(),
        boards=("G1",),
        shutdown_timeout=3,
    )
    await runtime.start()
    await coordinator.running.wait()

    with pytest.raises(RuntimeError, match="failed after 3"):
        await runtime.stop()
    assert rest.closed is True
