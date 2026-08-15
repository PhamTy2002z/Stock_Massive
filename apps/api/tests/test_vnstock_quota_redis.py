"""The same guarantees, against a real Redis rather than a mirror of one.

``tests/fake_redis.py`` reimplements the arbiter's Lua in Python, which is what
makes the fast suite possible and also what makes it insufficient: a script that
stopped spacing would keep passing there. These tests run the actual scripts on
an actual server.

Excluded from the default run and enabled by pointing ``QUOTA_TEST_REDIS_URL``
at a server — ``redis://localhost:6379/15`` if you have the compose stack up:

    QUOTA_TEST_REDIS_URL=redis://localhost:6379/15 pytest -m redis_server

Database 15 rather than 0, and every key cleared before and after, because these
tests write to the same key names the running application uses.
"""

from __future__ import annotations

import os
import threading
import time

import pytest

from src.core.quota import (
    ACCOUNT_KEY,
    ACCOUNT_SPACING_WITHOUT_KEY,
    COLLECTOR_LEASE_KEY,
    NEWS_KEY,
    NEWS_WAITING_KEY,
    CollectorLeaseHeld,
    QuotaLane,
    QuotaWaitTooLong,
    VnstockQuotaArbiter,
)

pytestmark = pytest.mark.redis_server

REDIS_URL = os.environ.get("QUOTA_TEST_REDIS_URL", "")
KEYS = (ACCOUNT_KEY, NEWS_KEY, NEWS_WAITING_KEY, COLLECTOR_LEASE_KEY)


@pytest.fixture
def server():
    if not REDIS_URL:
        pytest.skip("QUOTA_TEST_REDIS_URL is not set")

    from redis import Redis

    client = Redis.from_url(REDIS_URL, decode_responses=True)
    client.ping()
    for key in KEYS:
        client.delete(key)
    yield client
    for key in KEYS:
        client.delete(key)


def arbiter(server, api_key: str = "", **kwargs) -> VnstockQuotaArbiter:
    return VnstockQuotaArbiter(redis_factory=lambda: server, api_key=api_key, **kwargs)


class TestTheScriptItself:
    def test_consecutive_callers_are_spaced_by_the_account_interval(self, server):
        slept: list[float] = []
        subject = arbiter(server, sleep=slept.append)

        subject.acquire(QuotaLane.COLLECTOR)
        subject.acquire(QuotaLane.COLLECTOR)

        assert slept == pytest.approx([ACCOUNT_SPACING_WITHOUT_KEY], abs=0.05)

    def test_concurrent_callers_each_get_their_own_slot(self, server):
        waits: list[float] = []
        lock = threading.Lock()
        subject = arbiter(server, sleep=lambda seconds: None)

        def call() -> None:
            waited = subject.acquire(QuotaLane.COLLECTOR)
            with lock:
                waits.append(waited)

        threads = [threading.Thread(target=call) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Every caller got a distinct slot, so no two may call at once.
        assert sorted(round(wait) for wait in waits) == [
            round(index * ACCOUNT_SPACING_WITHOUT_KEY) for index in range(8)
        ]

    def test_a_slot_further_out_than_the_caller_can_wait_is_refused(self, server):
        subject = arbiter(server, sleep=lambda seconds: None)
        subject.acquire(QuotaLane.LEGACY)

        with pytest.raises(QuotaWaitTooLong):
            subject.acquire(QuotaLane.LEGACY, max_wait=0.5)

    def test_a_bucket_that_has_gone_quiet_does_not_charge_for_the_silence(
        self, server
    ):
        """A run an hour later starts fresh rather than owing an hour of slots."""
        subject = arbiter(server, sleep=lambda seconds: None)
        subject.acquire(QuotaLane.COLLECTOR)
        server.set(ACCOUNT_KEY, int((time.time() - 3600) * 1000))

        assert subject.acquire(QuotaLane.COLLECTOR) == 0.0


class TestTheLeaseOnARealServer:
    def test_it_excludes_the_other_lanes_and_is_released(self, server):
        subject = arbiter(server, sleep=lambda seconds: None)

        with subject.collector_lease(ttl_seconds=30):
            with pytest.raises(CollectorLeaseHeld):
                subject.acquire(QuotaLane.NEWS)

        assert server.get(COLLECTOR_LEASE_KEY) is None
        assert subject.acquire(QuotaLane.NEWS) >= 0.0

    def test_a_second_holder_is_refused(self, server):
        first = arbiter(server, sleep=lambda seconds: None)
        second = arbiter(server, sleep=lambda seconds: None)

        with first.collector_lease(ttl_seconds=30):
            with pytest.raises(CollectorLeaseHeld):
                with second.collector_lease(ttl_seconds=30):
                    pass  # pragma: no cover - taking the lease is what raises

    def test_the_release_script_only_removes_its_own_token(self, server):
        subject = arbiter(server, sleep=lambda seconds: None)

        with subject.collector_lease(ttl_seconds=30):
            server.set(COLLECTOR_LEASE_KEY, "a-successor")

        assert server.get(COLLECTOR_LEASE_KEY) == "a-successor"
