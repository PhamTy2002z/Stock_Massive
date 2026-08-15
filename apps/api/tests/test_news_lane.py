"""The news exception stays an exception.

Every test here is about a bound: how often the provider may be reached, who
may reach it, how old an answer may be before it stops being served, and what
happens when the Collector owns the account. Without those, ``search_news``
would be a second collector wearing a tool's name.
"""

from __future__ import annotations

import pytest

from src.core.news_lane import (
    FRESH_SECONDS,
    STALE_LIMIT_SECONDS,
    NewsLane,
    NewsUnavailable,
)
from src.core.quota import CollectorLeaseHeld, QuotaLane, active_lane
from tests.fake_redis import FakeRedis


class Clock:
    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def build(redis: FakeRedis | None = None):
    clock = Clock()
    fake = redis if redis is not None else FakeRedis(clock=clock)
    return NewsLane(redis_factory=lambda: fake, clock=clock), fake, clock


class Fetcher:
    """A live read that records how often it actually happened."""

    def __init__(self, payload=None, error: Exception | None = None) -> None:
        self.payload = payload if payload is not None else [{"title": "a headline"}]
        self.error = error
        self.calls = 0
        self.lanes: list[QuotaLane] = []

    def __call__(self):
        self.calls += 1
        self.lanes.append(active_lane())
        if self.error is not None:
            raise self.error
        return self.payload


class TestTheFreshWindow:
    def test_a_first_read_reaches_the_provider(self):
        lane, _, _ = build()
        fetch = Fetcher()

        result = lane.read("VCB", fetch)

        assert fetch.calls == 1
        assert result.payload == [{"title": "a headline"}]
        assert result.stale is False

    def test_a_second_read_inside_six_hours_reaches_nobody(self):
        lane, _, clock = build()
        fetch = Fetcher()

        lane.read("VCB", fetch)
        clock.advance(FRESH_SECONDS - 60)
        result = lane.read("VCB", fetch)

        assert fetch.calls == 1
        assert result.stale is False

    def test_a_read_past_the_fresh_window_refreshes(self):
        lane, _, clock = build()
        fetch = Fetcher()

        lane.read("VCB", fetch)
        clock.advance(FRESH_SECONDS + 60)
        result = lane.read("VCB", fetch)

        assert fetch.calls == 2
        assert result.age_seconds == 0.0

    def test_the_cache_is_per_symbol(self):
        lane, _, _ = build()
        fetch = Fetcher()

        lane.read("VCB", fetch)
        lane.read("FPT", fetch)

        assert fetch.calls == 2


class TestTheLane:
    def test_the_live_read_happens_on_the_news_lane(self):
        """So it passes the same account bucket as everything else."""
        lane, _, _ = build()
        fetch = Fetcher()

        lane.read("VCB", fetch)

        assert fetch.lanes == [QuotaLane.NEWS]

    def test_the_lane_is_given_back_afterwards(self):
        lane, _, _ = build()

        lane.read("VCB", Fetcher())

        assert active_lane() is QuotaLane.LEGACY


class TestSingleFlight:
    def test_a_reader_arriving_mid_refresh_makes_no_second_call(self):
        """Ten readers asking about one symbol make one upstream call."""
        lane, fake, clock = build()
        lane.read("VCB", Fetcher())
        clock.advance(FRESH_SECONDS + 60)

        # What another reader holding the refresh claim looks like from here.
        fake.set("stock_massive:news:VCB:refreshing", "the-other-reader", ex=60)
        second = Fetcher()
        result = lane.read("VCB", second)

        assert second.calls == 0
        assert result.stale is True

    def test_the_claim_is_released_after_a_successful_read(self):
        lane, fake, _ = build()

        lane.read("VCB", Fetcher())

        assert fake.get("stock_massive:news:VCB:refreshing") is None

    def test_the_claim_is_released_after_a_failed_read(self):
        lane, fake, clock = build()
        lane.read("VCB", Fetcher())
        clock.advance(FRESH_SECONDS + 60)

        lane.read("VCB", Fetcher(error=RuntimeError("provider down")))

        assert fake.get("stock_massive:news:VCB:refreshing") is None


class TestStaleService:
    def test_the_collector_lease_sends_a_reader_to_the_stale_copy(self):
        lane, _, clock = build()
        lane.read("VCB", Fetcher())
        clock.advance(FRESH_SECONDS + 60)

        result = lane.read(
            "VCB", Fetcher(error=CollectorLeaseHeld("the Collector is running"))
        )

        assert result.stale is True
        assert result.age_seconds == pytest.approx(FRESH_SECONDS + 60)

    def test_a_provider_failure_sends_a_reader_to_the_stale_copy(self):
        lane, _, clock = build()
        lane.read("VCB", Fetcher())
        clock.advance(FRESH_SECONDS + 60)

        result = lane.read("VCB", Fetcher(error=RuntimeError("provider down")))

        assert result.stale is True

    def test_nothing_older_than_a_day_is_served(self):
        lane, _, clock = build()
        lane.read("VCB", Fetcher())
        clock.advance(STALE_LIMIT_SECONDS + 60)

        with pytest.raises(NewsUnavailable):
            lane.read("VCB", Fetcher(error=RuntimeError("provider down")))

    def test_a_symbol_with_nothing_stored_refuses_rather_than_invents(self):
        lane, _, _ = build()

        with pytest.raises(NewsUnavailable):
            lane.read("VCB", Fetcher(error=RuntimeError("provider down")))

    def test_a_stale_read_says_how_old_it_is(self):
        lane, _, clock = build()
        lane.read("VCB", Fetcher())
        clock.advance(FRESH_SECONDS * 2)

        result = lane.read("VCB", Fetcher(error=RuntimeError("provider down")))

        assert result.age_seconds == pytest.approx(FRESH_SECONDS * 2)
        assert result.stale is True


class TestFailClosed:
    def test_without_redis_there_is_no_lane_and_no_call(self):
        fetch = Fetcher()
        lane = NewsLane(redis_factory=lambda: None)

        with pytest.raises(NewsUnavailable):
            lane.read("VCB", fetch)

        assert fetch.calls == 0

    def test_a_broken_cache_does_not_become_an_unbounded_live_call(self):
        class BrokenRedis:
            def get(self, key):
                raise ConnectionError("redis is gone")

            def set(self, *args, **kwargs):
                raise ConnectionError("redis is gone")

        fetch = Fetcher()
        lane = NewsLane(redis_factory=lambda: BrokenRedis())

        with pytest.raises(NewsUnavailable):
            lane.read("VCB", fetch)

        assert fetch.calls == 0


class TestStorage:
    def test_a_read_expires_at_the_stale_limit_not_the_fresh_window(self):
        """Otherwise there is nothing left to fall back on during an outage —
        which is the one case this lane exists for."""
        lane, fake, clock = build()

        lane.read("VCB", Fetcher())
        clock.advance(FRESH_SECONDS + 60)

        assert fake.get("stock_massive:news:VCB") is not None

    def test_an_unreadable_cached_record_is_discarded_rather_than_served(self):
        lane, fake, _ = build()
        fake.set("stock_massive:news:VCB", "not json at all")
        fetch = Fetcher()

        result = lane.read("VCB", fetch)

        assert fetch.calls == 1
        assert result.stale is False
