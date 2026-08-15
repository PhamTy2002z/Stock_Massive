"""Every live vnstock call spends an account slot, and nothing else does.

This is the seam the arbiter had to sit on: services import `Quote`, `Trading`,
`Listing` and the rest straight from `src.core.vnstock_client`, so an allowance
enforced only inside the provider adapters would leave every legacy route
spending the same account with nothing counting it.
"""

from __future__ import annotations


import pytest

import src.core.vnstock_client as vnstock_client
from src.core.quota import CollectorLeaseHeld, QuotaLane, QuotaUnavailable


class SpyArbiter:
    """Records what was admitted, and can refuse like the real one."""

    def __init__(self, refuse: Exception | None = None) -> None:
        self.acquired: list[QuotaLane] = []
        self._refuse = refuse

    def acquire(self, lane=None, max_wait=None):
        if self._refuse is not None:
            raise self._refuse
        self.acquired.append(lane)
        return 0.0


class FakeQuote:
    """Stands in for a vnstock entry point, counting the calls that land."""

    def __init__(self) -> None:
        self.calls = 0

    def history(self, **kwargs):
        self.calls += 1
        return "a frame"


@pytest.fixture
def spy(monkeypatch):
    arbiter = SpyArbiter()
    monkeypatch.setattr(vnstock_client, "quota_arbiter", lambda: arbiter)
    return arbiter


def guarded(target, label="Quote"):
    return vnstock_client._GuardedProxy(target, label)


class TestEveryReadIsAdmitted:
    def test_one_call_spends_one_slot(self, spy):
        quote = guarded(FakeQuote())

        quote.history(start="2026-01-01")

        assert spy.acquired == [QuotaLane.LEGACY]

    def test_an_undeclared_caller_spends_on_the_legacy_lane(self, spy):
        """The safe answer for a caller that never said which lane it is."""
        guarded(FakeQuote()).history()

        assert spy.acquired == [QuotaLane.LEGACY]

    def test_the_declared_lane_is_the_one_charged(self, spy):
        from src.core.quota import quota_lane

        with quota_lane(QuotaLane.COLLECTOR):
            guarded(FakeQuote()).history()

        assert spy.acquired == [QuotaLane.COLLECTOR]

    def test_three_calls_spend_three_slots(self, spy):
        quote = guarded(FakeQuote())

        for _ in range(3):
            quote.history()

        assert len(spy.acquired) == 3


class TestRefusalStopsTheCall:
    def test_a_call_refused_by_the_arbiter_never_reaches_the_provider(
        self, monkeypatch
    ):
        target = FakeQuote()
        monkeypatch.setattr(
            vnstock_client,
            "quota_arbiter",
            lambda: SpyArbiter(refuse=CollectorLeaseHeld("the Collector is running")),
        )

        with pytest.raises(CollectorLeaseHeld):
            guarded(target).history()

        assert target.calls == 0

    def test_no_redis_means_no_call(self, monkeypatch):
        target = FakeQuote()
        monkeypatch.setattr(
            vnstock_client,
            "quota_arbiter",
            lambda: SpyArbiter(refuse=QuotaUnavailable("no arbiter")),
        )

        with pytest.raises(QuotaUnavailable):
            guarded(target).history()

        assert target.calls == 0


class TestWhatIsNotCharged:
    def test_walking_the_object_graph_costs_nothing(self, spy):
        """`Vnstock().stock(...)` hands back a holder, not a response.

        Charging it would make the allowance smaller than the account's, and
        by an amount that depends on how a caller happens to spell its access.
        """
        class Root:
            def stock(self, **kwargs):
                return type(
                    "StockComponents", (FakeQuote,), {"__module__": "vnstock.fake"}
                )()

        guarded(Root(), "Vnstock").stock(symbol="HPG")

        assert spy.acquired == []

    def test_a_read_through_that_holder_is_charged(self, spy):
        class Root:
            def stock(self, **kwargs):
                component = type(
                    "StockComponents", (FakeQuote,), {"__module__": "vnstock.fake"}
                )()
                return component

        stock = guarded(Root(), "Vnstock").stock(symbol="HPG")
        stock.history()

        assert spy.acquired == [QuotaLane.LEGACY]

    def test_constructing_an_entry_point_costs_nothing(self, spy):
        class Entry:
            def __init__(self, source: str = "VCI") -> None:
                self.source = source

            def price_board(self, **kwargs):
                return "a board"

        factory = vnstock_client._guarded_class(Entry, "Trading")
        board = factory(source="VCI")

        assert spy.acquired == []

        board.price_board(symbols_list=["HPG"])

        assert spy.acquired == [QuotaLane.LEGACY]


class TestTheOldGuardIsGone:
    def test_no_process_local_semaphore_decides_the_allowance(self):
        """A semaphore bounds how many calls run at once, not how fast they go.

        Four in flight against a 20-a-minute account is not a rate limit, and
        it was one of three guards that each believed it was the quota.
        """
        assert not hasattr(vnstock_client, "_call_slots")
        assert not hasattr(vnstock_client, "_MAX_CONCURRENT_CALLS")
