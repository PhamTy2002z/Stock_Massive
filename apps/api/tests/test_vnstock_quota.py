"""One arbiter, one allowance.

The thing under test is not "does a sleep happen" but "can two callers between
them outpace the account". That is why the concurrency test is here rather than
a spacing assertion on a single caller: a single caller was already correctly
paced by the module this replaces, and the account was still being outpaced.
"""

from __future__ import annotations

import threading

import pytest

from src.core.quota import (
    ACCOUNT_KEY,
    ACCOUNT_SPACING_WITH_KEY,
    ACCOUNT_SPACING_WITHOUT_KEY,
    COLLECTOR_LEASE_KEY,
    LEGACY_MAX_WAIT_SECONDS,
    NEWS_KEY,
    NEWS_SPACING_WITH_KEY,
    NEWS_SPACING_WITHOUT_KEY,
    NEWS_WAITING_KEY,
    CollectorLeaseHeld,
    QuotaLane,
    QuotaUnavailable,
    QuotaWaitTooLong,
    VnstockQuotaArbiter,
    active_lane,
    quota_arbiter,
    quota_lane,
    set_quota_arbiter,
)
from tests.fake_redis import FakeRedis, PositionalFakeRedis


class Clock:
    """A frozen clock that records what was slept instead of sleeping it.

    Frozen rather than advancing, and that is the interesting half: the
    reservation is what has to hold under concurrent callers, so time must not
    move underneath one caller because another one waited. What each caller was
    told to wait is exactly what the bucket handed it.
    """

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start
        self.slept: list[float] = []
        self._lock = threading.Lock()

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        with self._lock:
            self.slept.append(seconds)


def build(api_key: str = "", redis: FakeRedis | None = None, **kwargs):
    clock = Clock()
    fake = redis if redis is not None else FakeRedis(clock=clock)
    arbiter = VnstockQuotaArbiter(
        redis_factory=lambda: fake,
        api_key=api_key,
        clock=clock,
        sleep=clock.sleep,
        **kwargs,
    )
    return arbiter, fake, clock


class TestAccountSpacing:
    def test_the_first_call_of_a_run_waits_for_nothing(self):
        arbiter, _, clock = build()

        assert arbiter.acquire(QuotaLane.COLLECTOR) == 0.0
        assert clock.slept == []

    def test_a_guest_account_is_spaced_by_three_seconds(self):
        arbiter, _, clock = build(api_key="")

        arbiter.acquire(QuotaLane.COLLECTOR)
        waited = arbiter.acquire(QuotaLane.COLLECTOR)

        assert waited == pytest.approx(ACCOUNT_SPACING_WITHOUT_KEY, abs=0.01)

    def test_an_api_key_buys_one_second_spacing(self):
        arbiter, _, clock = build(api_key="a-key")

        arbiter.acquire(QuotaLane.COLLECTOR)
        waited = arbiter.acquire(QuotaLane.COLLECTOR)

        assert waited == pytest.approx(ACCOUNT_SPACING_WITH_KEY, abs=0.01)

    def test_ten_concurrent_callers_cannot_outpace_the_account(self):
        """The failure the three old pacers had, written down as a test.

        Every caller reserves its own slot, so the tenth waits nine spacings —
        not nine callers all waiting one.
        """
        arbiter, _, clock = build(api_key="")
        waits: list[float] = []
        lock = threading.Lock()

        def call() -> None:
            waited = arbiter.acquire(QuotaLane.COLLECTOR)
            with lock:
                waits.append(waited)

        threads = [threading.Thread(target=call) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert sorted(waits) == pytest.approx(
            [index * ACCOUNT_SPACING_WITHOUT_KEY for index in range(10)], abs=0.01
        )

    def test_every_lane_consumes_the_same_account_bucket(self):
        arbiter, fake, _ = build()

        for lane in (QuotaLane.COLLECTOR, QuotaLane.BACKFILL, QuotaLane.LEGACY):
            arbiter.acquire(lane)

        # Three reservations, so the marker sits three spacings out.
        assert fake.get(ACCOUNT_KEY) is not None

    def test_a_slot_further_out_than_the_caller_can_wait_is_refused(self):
        arbiter, _, clock = build()

        arbiter.acquire(QuotaLane.LEGACY)

        with pytest.raises(QuotaWaitTooLong):
            arbiter.acquire(QuotaLane.LEGACY, max_wait=0.5)
        assert clock.slept == []

    def test_a_refused_reservation_does_not_consume_the_slot(self):
        arbiter, _, _ = build()

        arbiter.acquire(QuotaLane.LEGACY)
        with pytest.raises(QuotaWaitTooLong):
            arbiter.acquire(QuotaLane.LEGACY, max_wait=0.5)

        # The next real caller waits one spacing, not two: the refusal took
        # nothing with it.
        assert arbiter.acquire(QuotaLane.LEGACY) == pytest.approx(
            ACCOUNT_SPACING_WITHOUT_KEY, abs=0.01
        )


class TestALegacyRouteWaitsOnlySoLong:
    """A frozen legacy endpoint is a user request on a threadpool thread."""

    def test_a_queue_deeper_than_the_bound_is_refused_rather_than_queued(self):
        arbiter, _, _ = build(api_key="")
        depth = int(LEGACY_MAX_WAIT_SECONDS // ACCOUNT_SPACING_WITHOUT_KEY) + 1

        for _ in range(depth):
            arbiter.acquire(QuotaLane.LEGACY)

        with pytest.raises(QuotaWaitTooLong):
            arbiter.acquire(QuotaLane.LEGACY)

    def test_a_cron_with_nobody_waiting_queues_for_as_long_as_it_takes(self):
        arbiter, _, _ = build(api_key="")

        waits = [arbiter.acquire(QuotaLane.BACKFILL) for _ in range(20)]

        assert waits[-1] > LEGACY_MAX_WAIT_SECONDS

    def test_a_caller_that_names_its_own_bound_keeps_it(self):
        arbiter, _, _ = build(api_key="")

        arbiter.acquire(QuotaLane.LEGACY)

        with pytest.raises(QuotaWaitTooLong):
            arbiter.acquire(QuotaLane.LEGACY, max_wait=0.5)


class TestNewsLane:
    def test_news_pays_its_own_lane_and_the_account_bucket(self):
        arbiter, fake, _ = build()

        arbiter.acquire(QuotaLane.NEWS)

        assert fake.get(NEWS_KEY) is not None
        assert fake.get(ACCOUNT_KEY) is not None

    def test_the_news_lane_is_five_a_minute_without_a_key(self):
        arbiter, _, clock = build(api_key="")

        arbiter.acquire(QuotaLane.NEWS)
        arbiter.acquire(QuotaLane.NEWS)

        # The news slot is waited for first; the account slot the same call then
        # takes has, in real time, already come round while it waited.
        assert clock.slept[0] == pytest.approx(NEWS_SPACING_WITHOUT_KEY, abs=0.01)

    def test_the_news_lane_is_fifteen_a_minute_with_a_key(self):
        arbiter, _, clock = build(api_key="a-key")

        arbiter.acquire(QuotaLane.NEWS)
        arbiter.acquire(QuotaLane.NEWS)

        assert clock.slept[0] == pytest.approx(NEWS_SPACING_WITH_KEY, abs=0.01)

    def test_a_finished_news_call_leaves_no_one_waiting(self):
        arbiter, fake, _ = build()

        arbiter.acquire(QuotaLane.NEWS)

        assert int(fake.get(NEWS_WAITING_KEY) or 0) == 0


class TestRankingBelowNews:
    def test_backfill_stands_aside_while_news_is_waiting(self):
        arbiter, fake, clock = build()
        fake.set(NEWS_WAITING_KEY, 1)

        arbiter.acquire(QuotaLane.BACKFILL)

        assert clock.slept, "Backfill took an account slot ahead of a waiting reader"

    def test_a_legacy_route_stands_aside_too(self):
        arbiter, fake, clock = build()
        fake.set(NEWS_WAITING_KEY, 1)

        arbiter.acquire(QuotaLane.LEGACY)

        assert clock.slept

    def test_standing_aside_is_bounded_by_one_news_slot(self):
        """Below news is not behind news forever; a Backfill that never runs is
        its own outage."""
        arbiter, fake, clock = build()
        fake.set(NEWS_WAITING_KEY, 1)

        arbiter.acquire(QuotaLane.BACKFILL)

        assert sum(clock.slept) <= NEWS_SPACING_WITHOUT_KEY + 0.01

    def test_the_collector_never_stands_aside(self):
        arbiter, fake, clock = build()
        fake.set(NEWS_WAITING_KEY, 1)

        arbiter.acquire(QuotaLane.COLLECTOR)

        assert clock.slept == []

    def test_nobody_stands_aside_for_an_empty_queue(self):
        arbiter, _, clock = build()

        arbiter.acquire(QuotaLane.BACKFILL)

        assert clock.slept == []


class TestCollectorLease:
    def test_the_lease_excludes_every_other_lane(self):
        arbiter, _, _ = build()

        with arbiter.collector_lease():
            for lane in (QuotaLane.NEWS, QuotaLane.BACKFILL, QuotaLane.LEGACY):
                with pytest.raises(CollectorLeaseHeld):
                    arbiter.acquire(lane)

    def test_the_collector_itself_still_gets_through(self):
        arbiter, _, _ = build()

        with arbiter.collector_lease():
            assert arbiter.acquire(QuotaLane.COLLECTOR) == 0.0

    def test_it_is_released_when_the_run_ends(self):
        arbiter, fake, _ = build()

        with arbiter.collector_lease():
            pass

        assert fake.get(COLLECTOR_LEASE_KEY) is None
        assert arbiter.acquire(QuotaLane.LEGACY) == 0.0

    def test_it_is_released_when_the_run_dies(self):
        arbiter, fake, _ = build()

        with pytest.raises(RuntimeError, match="collector blew up"):
            with arbiter.collector_lease():
                raise RuntimeError("collector blew up")

        assert fake.get(COLLECTOR_LEASE_KEY) is None

    def test_a_second_run_cannot_take_a_lease_that_is_held(self):
        arbiter, fake, _ = build()
        other, _, _ = build(redis=fake)

        with arbiter.collector_lease():
            with pytest.raises(CollectorLeaseHeld):
                with other.collector_lease():
                    pass  # pragma: no cover - taking the lease is what raises

    def test_a_release_only_removes_this_run_s_own_lease(self):
        """A lease that expired and was retaken must not be deleted by its
        predecessor's finally block."""
        arbiter, fake, _ = build()

        with arbiter.collector_lease():
            fake.set(COLLECTOR_LEASE_KEY, "someone-else's-token")

        assert fake.get(COLLECTOR_LEASE_KEY) == "someone-else's-token"

    def test_the_lease_is_visible_to_anyone_who_asks(self):
        arbiter, _, _ = build()

        assert arbiter.collector_lease_held() is False
        with arbiter.collector_lease():
            assert arbiter.collector_lease_held() is True


class TestFailClosed:
    def test_no_redis_means_no_provider_call(self):
        arbiter = VnstockQuotaArbiter(redis_factory=lambda: None)

        for lane in QuotaLane:
            with pytest.raises(QuotaUnavailable):
                arbiter.acquire(lane)

    def test_a_redis_that_errors_means_no_provider_call(self):
        class BrokenRedis:
            def get(self, key):
                raise ConnectionError("redis is gone")

            def eval(self, *args, **kwargs):
                raise ConnectionError("redis is gone")

        arbiter = VnstockQuotaArbiter(redis_factory=lambda: BrokenRedis())

        with pytest.raises(QuotaUnavailable):
            arbiter.acquire(QuotaLane.COLLECTOR)

    def test_a_collector_lease_cannot_be_taken_without_redis(self):
        arbiter = VnstockQuotaArbiter(redis_factory=lambda: None)

        with pytest.raises(QuotaUnavailable):
            with arbiter.collector_lease():
                pass  # pragma: no cover - acquiring is what raises

    def test_there_is_no_process_local_fallback_to_fall_back_to(self):
        """The failure mode that made this module necessary must stay absent."""
        import src.stocks.providers.vnstock_provider as adapters

        assert not hasattr(adapters, "RequestPacer")
        assert not hasattr(adapters, "process_pacer")


class TestBothRedisClients:
    def test_the_positional_eval_signature_works_too(self):
        clock = Clock()
        fake = PositionalFakeRedis(clock=clock)
        arbiter = VnstockQuotaArbiter(
            redis_factory=lambda: fake,
            api_key="",
            clock=clock,
            sleep=clock.sleep,
        )

        arbiter.acquire(QuotaLane.COLLECTOR)

        assert arbiter.acquire(QuotaLane.COLLECTOR) == pytest.approx(
            ACCOUNT_SPACING_WITHOUT_KEY, abs=0.01
        )


class TestActiveLane:
    def test_an_undeclared_caller_is_legacy(self):
        assert active_lane() is QuotaLane.LEGACY

    def test_a_declared_lane_reaches_the_arbiter_without_being_passed(self):
        arbiter, fake, _ = build()

        with arbiter.collector_lease():
            with quota_lane(QuotaLane.COLLECTOR):
                assert arbiter.acquire() == 0.0

    def test_the_lane_is_restored_after_the_block(self):
        with quota_lane(QuotaLane.BACKFILL):
            assert active_lane() is QuotaLane.BACKFILL
        assert active_lane() is QuotaLane.LEGACY

    def test_the_lane_is_restored_after_a_failure(self):
        with pytest.raises(RuntimeError):
            with quota_lane(QuotaLane.NEWS):
                raise RuntimeError("boom")
        assert active_lane() is QuotaLane.LEGACY


class TestSharedArbiter:
    def test_every_caller_gets_the_same_one(self):
        set_quota_arbiter(None)
        try:
            assert quota_arbiter() is quota_arbiter()
        finally:
            set_quota_arbiter(None)

    def test_an_installed_arbiter_replaces_it(self):
        arbiter, _, _ = build()
        set_quota_arbiter(arbiter)
        try:
            assert quota_arbiter() is arbiter
        finally:
            set_quota_arbiter(None)
