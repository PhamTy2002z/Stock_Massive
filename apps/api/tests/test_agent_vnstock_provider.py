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
