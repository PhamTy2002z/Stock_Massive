"""Whether the prices around an ex-date corroborate the action declared on it.

The one function here that had no test at all is ``_session_low``, and it was
broken in two independent ways because of it: it ordered by
``ProviderSnapshot.written_at``, a column the model does not have, and it built
the day's bounds in UTC while a session is stamped at midnight in Vietnam. The
first raised; the second would have quietly read the wrong seven hours once the
raise was fixed — and a ``None`` from here turns every confirmable corporate
action into ``no_corroborating_gap``, which is a wrong answer that looks like a
cautious one.

So the assertions below are about the reading reaching a number at all, on a
session the spine holds, as much as about the verdict it produces.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.stocks.models import BarDaily, CorporateAction, ListingRoster
from src.stocks.providers import Exchange
from src.stocks.signals.corporate_actions import (
    Confirmation,
    ConfirmationReason,
    _session_low,
    confirm_ex_date,
)

from .test_price_band import list_on, write_session

OBSERVED_AT = datetime(2026, 8, 13, 11, 0, tzinfo=timezone.utc)


def open_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (
        BarDaily.__table__,
        ListingRoster.__table__,
        CorporateAction.__table__,
    ):
        table.create(engine)
    return Session(engine)


def a_stock_dividend(symbol: str, ex_date: date, ratio: str) -> CorporateAction:
    return CorporateAction(
        symbol=symbol,
        source="vnstock",
        event_code="ISS",
        title="Stock dividend",
        kind="stock_dividend",
        ex_date=ex_date,
        exercise_ratio=Decimal(ratio),
        changes_share_count=True,
        confirmation="unconfirmed",
        observed_at=OBSERVED_AT,
    )


class TestTheSessionLowThisReadsTheGapFrom:
    def test_it_answers_with_the_low_of_the_session_the_spine_holds(self):
        with open_session() as session:
            write_session(
                session,
                "MBB",
                date(2025, 8, 14),
                open_price=27_000,
                high=27_600,
                low=26_400,
                close=27_100,
            )

            assert _session_low(session, "MBB", date(2025, 8, 14)) == Decimal("26400")

    def test_a_lowercase_symbol_reaches_the_same_row(self):
        with open_session() as session:
            write_session(session, "MBB", date(2025, 8, 14), close=27_100, low=26_400)

            assert _session_low(session, "mbb", date(2025, 8, 14)) == Decimal("26400")

    def test_a_session_the_spine_does_not_hold_answers_with_nothing(self):
        with open_session() as session:
            write_session(session, "MBB", date(2025, 8, 13), close=25_800)

            assert _session_low(session, "MBB", date(2025, 8, 14)) is None

    def test_the_index_series_is_not_a_symbol_this_reads(self):
        """Writing an equity session also marks the calendar; the two must not
        be confused for one another by a query that forgot the series."""
        with open_session() as session:
            write_session(session, "MBB", date(2025, 8, 14), close=27_100, low=26_400)

            assert _session_low(session, "VNINDEX", date(2025, 8, 14)) is None


class TestWhetherAnExDateIsCorroborated:
    def test_a_session_that_gapped_below_its_floor_confirms_the_action(self):
        """MBB's real shape: a −20% session against a ±7% band, on an ex-date."""
        ex_date = date(2025, 8, 14)
        with open_session() as session:
            list_on(session, "MBB", Exchange.HOSE)
            write_session(session, "MBB", date(2025, 8, 13), close=25_800)
            write_session(
                session,
                "MBB",
                ex_date,
                open_price=20_600,
                high=20_800,
                low=20_500,
                close=20_550,
            )

            verdict = confirm_ex_date(
                session, "MBB", ex_date, [a_stock_dividend("MBB", ex_date, "0.25")]
            )

        assert verdict.confirmation is Confirmation.CONFIRMED
        assert verdict.reason is None

    def test_an_ordinary_session_contradicts_terms_that_say_it_should_have_gapped(self):
        ex_date = date(2025, 8, 14)
        with open_session() as session:
            list_on(session, "MBB", Exchange.HOSE)
            write_session(session, "MBB", date(2025, 8, 13), close=25_800)
            write_session(
                session,
                "MBB",
                ex_date,
                open_price=25_800,
                high=25_900,
                low=25_700,
                close=25_800,
            )

            verdict = confirm_ex_date(
                session, "MBB", ex_date, [a_stock_dividend("MBB", ex_date, "0.25")]
            )

        assert verdict.confirmation is Confirmation.UNCONFIRMED
        assert verdict.reason is not ConfirmationReason.SESSION_UNDECIDED

    def test_a_session_the_spine_cannot_measure_is_undecided_rather_than_denied(self):
        """No anchor, so there is no band and therefore no question to answer."""
        ex_date = date(2025, 8, 14)
        with open_session() as session:
            list_on(session, "MBB", Exchange.HOSE)
            write_session(session, "MBB", ex_date, close=20_550)

            verdict = confirm_ex_date(
                session, "MBB", ex_date, [a_stock_dividend("MBB", ex_date, "0.25")]
            )

        assert verdict.confirmation is Confirmation.UNCONFIRMED
        assert verdict.reason is ConfirmationReason.SESSION_UNDECIDED
