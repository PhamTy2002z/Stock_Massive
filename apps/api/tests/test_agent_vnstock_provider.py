"""The shared door to vnstock: a limiter below the package's quota, and a quota
breach that refuses one call instead of exiting the process."""

from __future__ import annotations

import pytest

from src.agent.tools import vnstock_provider
from src.agent.tools.vnstock_provider import MarketDataError, RequestGate


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_the_gate_admits_up_to_its_limit_then_waits_for_room():
    clock = Clock()
    gate = RequestGate(limit=3, window=60.0, clock=clock, sleep=clock.sleep)

    for _ in range(3):
        gate.acquire()
    clock.now = 58.0
    gate.acquire(max_wait=5.0)  # the first stamp expires at 60

    assert clock.now == pytest.approx(60.0)


def test_the_gate_refuses_when_room_is_further_away_than_it_may_wait():
    clock = Clock()
    gate = RequestGate(limit=2, window=60.0, clock=clock, sleep=clock.sleep)
    gate.acquire(weight=2)

    with pytest.raises(MarketDataError) as refused:
        gate.acquire(max_wait=4.0)

    assert refused.value.code == vnstock_provider.RATE_LIMITED
    assert "60s" in str(refused.value)


def test_a_quota_exit_inside_the_package_is_one_refused_call(monkeypatch):
    monkeypatch.setattr(vnstock_provider, "GATE", RequestGate(limit=100))

    def exits() -> None:
        raise SystemExit("Rate limit exceeded. Process terminated.")

    with pytest.raises(MarketDataError) as refused:
        vnstock_provider.call(exits, symbol="STB")

    assert refused.value.code == vnstock_provider.RATE_LIMITED


def test_the_packages_own_quota_exception_is_classified_by_name():
    class RateLimitExceeded(Exception):
        pass

    assert vnstock_provider.classify(RateLimitExceeded("x"), "STB").code == vnstock_provider.RATE_LIMITED


def test_a_background_fill_leaves_room_for_the_reads_a_model_asks_for():
    clock = Clock()
    gate = RequestGate(limit=6, window=60.0, clock=clock, sleep=clock.sleep)
    for _ in range(4):
        gate.acquire(max_wait=0.0, keep_free=2)

    with pytest.raises(MarketDataError):
        gate.acquire(max_wait=0.0, keep_free=2)  # the fill stops two short
    gate.acquire(max_wait=0.0)
    gate.acquire(max_wait=0.0)  # and the model's own reads still get in


def test_concurrent_misses_for_one_key_make_one_provider_call(monkeypatch):
    import threading
    import time
    from datetime import datetime, timezone

    monkeypatch.setattr(vnstock_provider, "READS", vnstock_provider.TtlCache())
    calls = []
    started = threading.Event()

    def load():
        calls.append(1)
        started.set()
        time.sleep(0.1)
        return {"close": [1.0]}

    now = datetime.now(timezone.utc)
    results = []

    def read():
        results.append(vnstock_provider.cached(("bars", "VNM"), 60.0, load, now=now))

    threads = [threading.Thread(target=read) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)

    assert len(calls) == 1
    assert [value for value, _ in results] == [{"close": [1.0]}] * 8
    # Every waiter left, so nothing is held for the key afterwards.
    assert vnstock_provider._flights == {}


def test_a_failed_load_lets_the_next_caller_load_again(monkeypatch):
    from datetime import datetime, timezone

    monkeypatch.setattr(vnstock_provider, "READS", vnstock_provider.TtlCache())
    now = datetime.now(timezone.utc)

    def refused():
        raise MarketDataError(vnstock_provider.RATE_LIMITED, "spent")

    with pytest.raises(MarketDataError):
        vnstock_provider.cached("k", 60.0, refused, now=now)
    value, _ = vnstock_provider.cached("k", 60.0, lambda: 7, now=now)

    assert value == 7
    assert vnstock_provider._flights == {}


def test_a_waiter_behind_a_hung_leader_gives_up_without_loading(monkeypatch):
    import threading
    from datetime import datetime, timezone

    monkeypatch.setattr(vnstock_provider, "READS", vnstock_provider.TtlCache())
    monkeypatch.setattr(vnstock_provider, "FLIGHT_WAIT_SECONDS", 0.2)
    now = datetime.now(timezone.utc)
    calls: list[str] = []
    entered, release = threading.Event(), threading.Event()

    def hang():
        calls.append("leader")
        entered.set()
        release.wait(5)
        return 1

    leader = threading.Thread(target=lambda: vnstock_provider.cached("k", 60.0, hang, now=now))
    leader.start()
    assert entered.wait(2)
    try:
        with pytest.raises(MarketDataError) as refused:
            vnstock_provider.cached("k", 60.0, lambda: calls.append("waiter") or 2, now=now)
    finally:
        release.set()
        leader.join(5)

    assert refused.value.code == vnstock_provider.PROVIDER_UNAVAILABLE
    # The waiter never made a second provider call beside the hung one.
    assert calls == ["leader"]
    assert vnstock_provider._flights == {}


def test_only_the_first_import_swaps_sys_stdout(monkeypatch):
    import sys
    import threading

    monkeypatch.setattr(vnstock_provider, "_vnstock_module", None)
    swaps = []
    sentinel = object()

    def import_module(name):
        swaps.append(sys.stdout)
        print("sponsorship banner")
        return sentinel

    monkeypatch.setattr(vnstock_provider.importlib, "import_module", import_module)
    before = sys.stdout
    threads = [
        threading.Thread(target=vnstock_provider.import_vnstock) for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)

    assert len(swaps) == 1 and swaps[0] is not before  # captured, once
    assert sys.stdout is before
    assert vnstock_provider.import_vnstock() is sentinel
    assert len(swaps) == 1
