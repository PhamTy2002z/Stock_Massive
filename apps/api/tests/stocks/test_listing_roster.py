"""The register writer: the board mapping, the delisting, and the ICB join.

Nothing here commits. ``ListingRosterStore.write`` makes a statement about the
whole table by design — a symbol missing from a refresh is a symbol that left —
so a committed test refresh would delist the stored market. Every case runs in a
transaction that is rolled back, and asserts through the same session.

The provider is an injected callable, and the frames are the ones captured on
2026-08-27: ``HSX`` where the table says ``HOSE``, ``DELISTED`` where a board
should be, a share with no classification, and instrument types that are not
companies at all.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from src.core.database import sync_session_factory
from src.stocks.listing_roster import (
    ListingRosterStore,
    refresh_roster,
)
from src.stocks.models import ListingRoster
from src.stocks.providers.contracts import Exchange

from .daily import fixtures

STAMP = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)

#: Symbols invented for these cases. Real tickers would make an assertion depend
#: on what the stored register happens to hold today.
GONE = "ZZGONE"


@pytest.fixture
def session():
    """A session that is never committed, so the stored register survives."""
    session = sync_session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def seed(
    session, symbol: str, *, exchange: str = "HOSE", is_listed: bool = True
) -> None:
    session.merge(
        ListingRoster(
            symbol=symbol,
            exchange=exchange,
            is_listed=is_listed,
            company_name=f"{symbol} Corp",
            source="vnstock",
            observed_at=STAMP,
        )
    )
    session.flush()


def do_refresh(session):
    return refresh_roster(
        session,
        fetch_listings=fixtures.listings,
        fetch_industries=fixtures.industries,
        observed_at=STAMP,
    )


def row(session, symbol: str) -> ListingRoster:
    return session.execute(
        select(ListingRoster).where(ListingRoster.symbol == symbol)
    ).scalar_one()


class TestBoards:
    def test_the_providers_hsx_is_stored_as_hose(self, session):
        """The provider writes HSX and this table has always written HOSE.

        Not cosmetic: eligibility is decided by the board name, so a second
        spelling would drop real companies out of anything that filters on it.
        """
        seed(session, "YEG", exchange="HNX")
        do_refresh(session)

        assert row(session, "YEG").exchange == Exchange.HOSE.value

    def test_each_board_the_response_names_is_kept(self, session):
        do_refresh(session)

        assert row(session, "YEG").exchange == "HOSE"
        assert row(session, "X20").exchange == "HNX"
        assert row(session, "YTC").exchange == "UPCOM"

    def test_only_shares_are_written(self, session):
        """Covered warrants and ETFs are instruments, not listed companies."""
        refresh = do_refresh(session)
        written = session.execute(
            select(ListingRoster.symbol).where(
                ListingRoster.symbol.in_(["CVIC2601", "E1VFVN30"])
            )
        ).scalars()

        assert refresh.listed == 4
        assert tuple(written) == ()


class TestDelisting:
    def test_a_share_the_provider_puts_on_no_board_keeps_its_row(self, session):
        """A company that left has to be seen to have left.

        Deleted, it would simply stop matching every query and each reader would
        go on treating its last stored numbers as current.
        """
        seed(session, "XDC", exchange="HOSE")
        refresh = do_refresh(session)

        stored = row(session, "XDC")
        assert stored.is_listed is False
        assert stored.exchange == "HOSE"
        assert stored.company_name is not None
        assert "XDC" in refresh.newly_delisted

    def test_a_symbol_the_response_never_names_is_delisted_too(self, session):
        seed(session, GONE)
        refresh = do_refresh(session)

        assert row(session, GONE).is_listed is False
        assert GONE in refresh.newly_delisted

    def test_a_symbol_named_only_as_another_instrument_is_left_alone(self, session):
        """This refresh describes shares, so it says nothing about a warrant.

        Marking it delisted would be a claim the response never made.
        """
        seed(session, "E1VFVN30")
        refresh = do_refresh(session)

        assert row(session, "E1VFVN30").is_listed is True
        assert "E1VFVN30" not in refresh.newly_delisted

    def test_a_share_that_came_back_is_reported_as_newly_listed(self, session):
        seed(session, "YEG", exchange="HOSE", is_listed=False)
        refresh = do_refresh(session)

        assert row(session, "YEG").is_listed is True
        assert "YEG" in refresh.newly_listed

    def test_an_empty_refresh_is_refused(self, session):
        with pytest.raises(ValueError, match="delist the whole market"):
            ListingRosterStore(session).write([], shares=[], mentioned=[])


class TestClassification:
    def test_the_level_two_industry_name_is_joined_onto_the_code(self, session):
        do_refresh(session)

        stored = row(session, "YEG")
        assert stored.icb_code == "5500"
        assert stored.icb_name == "Truyền thông"

    def test_a_share_with_no_classification_is_a_normal_row(self, session):
        refresh = do_refresh(session)

        stored = row(session, "XPH")
        assert stored.is_listed is True
        assert stored.icb_code is None
        assert stored.icb_name is None
        assert refresh.unclassified == 1

    def test_a_failed_industry_read_keeps_the_register(self, session):
        """The classification call is best-effort by contract.

        Losing the names must cost the names, not the whole refresh: the boards
        are what every downstream reader needs first.
        """

        def broken():
            raise RuntimeError("the provider hung up")

        refresh = refresh_roster(
            session,
            fetch_listings=fixtures.listings,
            fetch_industries=broken,
            observed_at=STAMP,
        )

        stored = row(session, "YEG")
        assert refresh.listed == 4
        assert stored.icb_code == "5500"
        assert stored.icb_name is None

    def test_a_stored_classification_survives_a_refresh_that_carries_none(
        self, session
    ):
        do_refresh(session)
        refresh_roster(
            session,
            fetch_listings=lambda: fixtures.listings().assign(icb_code2=None),
            fetch_industries=fixtures.industries,
            observed_at=STAMP,
        )

        stored = row(session, "YEG")
        assert stored.icb_code == "5500"
        assert stored.icb_name == "Truyền thông"

    def test_a_response_missing_a_column_is_refused(self, session):
        with pytest.raises(RuntimeError, match="exchange"):
            refresh_roster(
                session,
                fetch_listings=lambda: fixtures.listings().drop(columns=["exchange"]),
                fetch_industries=fixtures.industries,
                observed_at=STAMP,
            )


class TestReads:
    def test_listed_symbols_answers_alphabetically(self, session):
        do_refresh(session)
        listed = ListingRosterStore(session).listed_symbols()

        assert {"X20", "XPH", "YEG", "YTC"} <= set(listed)
        assert "XDC" not in listed
        assert list(listed) == sorted(listed)

    def test_listed_symbols_can_be_narrowed_to_one_board(self, session):
        do_refresh(session)
        listed = ListingRosterStore(session).listed_symbols([Exchange.HNX])

        assert "X20" in listed
        assert "YEG" not in listed

    def test_identity_of_reads_back_what_the_refresh_wrote(self, session):
        do_refresh(session)
        identity = ListingRosterStore(session).identity_of("ytc")

        assert identity is not None
        assert identity.symbol == "YTC"
        assert identity.exchange is Exchange.UPCOM
        assert identity.icb_name == "Y tế"
        assert identity.is_listed is True
