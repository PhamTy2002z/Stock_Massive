"""The market half, and the rule it must not weaken.

The declared half is a promise to hold data for a symbol; the market half is
only who is listed. So a symbol that exists in the market half alone still has
no stored Snapshot to compute a Signal Field from, and ``get_field`` has to keep
refusing it with the same refusal it has always given. That is the assertion this
file exists for.

Nothing commits: the roster row a case needs is seeded in a transaction that is
rolled back.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from src.agent.registry import ToolContext
from src.agent.tools.signals import REGISTRY, SignalTools
from src.core.database import sync_session_factory
from src.stocks.models import ListingRoster
from src.stocks.universe import Universe, build_universe

STAMP = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)

#: Listed by the register, declared by nobody. Invented so the case does not
#: depend on which real tickers the stored register happens to hold.
MARKET_ONLY = "ZZLIST"


@pytest.fixture
def session():
    session = sync_session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def listed_market_only(session):
    session.add(
        ListingRoster(
            symbol=MARKET_ONLY,
            exchange="HOSE",
            is_listed=True,
            company_name="Listed But Undeclared",
            source="vnstock",
            observed_at=STAMP,
        )
    )
    session.flush()
    return session


class TestTheThirdSet:
    def test_the_market_half_is_not_read_unless_it_is_asked_for(self, session):
        """Every ``get_field`` builds a Universe, and none of them wants 1,500."""
        universe = build_universe(session)

        assert universe.market == ()

    def test_the_market_half_is_the_registers_listed_symbols(self, listed_market_only):
        universe = build_universe(listed_market_only, with_market=True)

        assert MARKET_ONLY in universe.market

    def test_a_delisted_symbol_is_not_in_the_market_half(self, session):
        session.add(
            ListingRoster(
                symbol="ZZLEFT",
                exchange="HOSE",
                is_listed=False,
                company_name="Gone",
                source="vnstock",
                observed_at=STAMP,
            )
        )
        session.flush()

        universe = build_universe(session, with_market=True)

        assert "ZZLEFT" not in universe.market

    def test_the_market_half_never_reaches_membership(self, listed_market_only):
        universe = build_universe(listed_market_only, with_market=True)

        assert MARKET_ONLY not in universe.symbols
        assert universe.contains(MARKET_ONLY) is False
        assert MARKET_ONLY not in universe

    def test_the_market_half_does_not_count_against_the_cap(self):
        universe = Universe(explicit=("VCB", "FPT")).with_market(
            tuple(f"Z{index:04d}" for index in range(1500))
        )

        assert len(universe) == 2
        assert len(universe.market) == 1500

    def test_seating_a_cohort_keeps_the_market_half(self):
        universe = Universe(explicit=("VCB",)).with_market(("AAA",))

        assert universe.with_cohort(("FPT",)).market == ("AAA",)

    def test_the_market_half_is_deduplicated(self):
        universe = Universe(explicit=("VCB",)).with_market(("AAA", "AAA", "BBB"))

        assert universe.market == ("AAA", "BBB")


class TestDeclaredOnlyStillHolds:
    def test_get_field_refuses_a_symbol_that_is_only_in_the_market_half(
        self, listed_market_only
    ):
        """The refusal is the same one, for the same reason, with the same code.

        A Signal Field is computed from Snapshots the collector took for the
        declared half. Admitting a listed-but-undeclared symbol would answer
        with a broken pipeline where the honest answer is that this system never
        collected the company.
        """
        session = listed_market_only
        assert MARKET_ONLY in build_universe(session, with_market=True).market

        @contextmanager
        def opener():
            yield session

        field_id = sorted(REGISTRY)[0]
        result = SignalTools(session_opener=opener).get_field(
            ToolContext(), {"field_id": field_id, "symbol": MARKET_ONLY}
        )

        assert result["error"] == "cannot_read"
        assert "outside the Universe" in result["detail"]
        assert "fieldId" not in result
