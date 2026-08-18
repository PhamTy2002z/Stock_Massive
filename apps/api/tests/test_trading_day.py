"""Which days the store actually holds a session for."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.stocks.models import ProviderSnapshot
from src.stocks.providers import Capability, ProviderSource
from src.stocks.providers.normalize import VN_TZ
from src.stocks.trading_day import (
    latest_trading_day,
    market_generation,
    trading_days_before,
    trading_days_between,
)


def open_session() -> Session:
    engine = create_engine("sqlite://")
    ProviderSnapshot.__table__.create(engine)
    return Session(engine)


def session_stamp(day: date) -> datetime:
    """A market session is dated at midnight in Vietnam on the day it traded."""
    return datetime.combine(day, datetime.min.time(), tzinfo=VN_TZ)


def record_session(
    session: Session,
    day: date,
    symbol: str = "VCB",
    capability: Capability = Capability.MARKET,
    observed_at: datetime | None = None,
) -> None:
    effective_at = session_stamp(day)
    session.add(
        ProviderSnapshot(
            capability=capability.value,
            symbol=symbol,
            source=ProviderSource.FIINQUANT.value,
            effective_at=effective_at,
            observed_at=observed_at or effective_at,
            schema_version=1,
            payload={},
        )
    )
    session.flush()


def test_an_empty_store_has_no_trading_day():
    """A fresh environment has to say so rather than substitute today."""
    assert latest_trading_day(open_session()) is None


def test_a_session_stamped_at_vietnam_midnight_reads_as_that_day():
    session = open_session()
    record_session(session, date(2026, 8, 13))

    assert latest_trading_day(session) == date(2026, 8, 13)


def test_the_newest_session_wins_across_symbols():
    """Trading Day is market-wide: one symbol lagging does not hold it back."""
    session = open_session()
    record_session(session, date(2026, 8, 11), symbol="VCB")
    record_session(session, date(2026, 8, 13), symbol="FPT")

    assert latest_trading_day(session) == date(2026, 8, 13)


def test_only_market_snapshots_date_a_trading_day():
    """A fundamental filing is not a session, however recent it is."""
    session = open_session()
    record_session(session, date(2026, 8, 11), capability=Capability.MARKET)
    record_session(
        session,
        date(2026, 8, 20),
        capability=Capability.FUNDAMENTAL,
        symbol="FPT",
    )

    assert latest_trading_day(session) == date(2026, 8, 11)


def test_preceding_days_skip_the_weekend_without_padding():
    """The gap between Friday and Monday is not two more Trading Days."""
    session = open_session()
    for day in (date(2026, 8, 6), date(2026, 8, 7), date(2026, 8, 10)):
        record_session(session, day)

    assert trading_days_before(session, date(2026, 8, 11), 3) == (
        date(2026, 8, 10),
        date(2026, 8, 7),
        date(2026, 8, 6),
    )


def test_preceding_days_return_fewer_rather_than_reaching_past_the_store():
    """Twenty asked for and seventeen held is seventeen, never a padded twenty.

    A baseline quietly built from fewer sessions is a baseline that means
    something different from the one beside it, so the caller has to see the
    shortfall.
    """
    session = open_session()
    for day in (date(2026, 8, 10), date(2026, 8, 11)):
        record_session(session, day)

    assert trading_days_before(session, date(2026, 8, 12), 20) == (
        date(2026, 8, 11),
        date(2026, 8, 10),
    )


def test_preceding_days_exclude_the_day_asked_about():
    session = open_session()
    for day in (date(2026, 8, 10), date(2026, 8, 11)):
        record_session(session, day)

    assert trading_days_before(session, date(2026, 8, 11), 5) == (date(2026, 8, 10),)


def test_one_session_counts_once_however_many_symbols_traded():
    session = open_session()
    for symbol in ("VCB", "FPT", "VNM"):
        record_session(session, date(2026, 8, 10), symbol=symbol)
    record_session(session, date(2026, 8, 11), symbol="VCB")

    assert trading_days_before(session, date(2026, 8, 12), 5) == (
        date(2026, 8, 11),
        date(2026, 8, 10),
    )


def test_a_window_the_exchange_was_shut_for_holds_no_sessions():
    """An empty answer is real, and is not the same as an empty store."""
    session = open_session()
    record_session(session, date(2026, 8, 10))

    assert trading_days_between(session, date(2026, 8, 15), date(2026, 8, 16)) == ()


def test_a_window_is_closed_at_both_ends():
    session = open_session()
    for day in (date(2026, 8, 10), date(2026, 8, 11), date(2026, 8, 12)):
        record_session(session, day)

    assert trading_days_between(session, date(2026, 8, 10), date(2026, 8, 12)) == (
        date(2026, 8, 10),
        date(2026, 8, 11),
        date(2026, 8, 12),
    )


def test_market_generation_advances_on_a_market_write():
    session = open_session()
    earlier = datetime(2026, 8, 13, 9, 15, tzinfo=timezone.utc)
    record_session(session, date(2026, 8, 12), observed_at=earlier)
    before = market_generation(session)

    record_session(
        session,
        date(2026, 8, 13),
        observed_at=earlier + timedelta(hours=7),
    )

    assert before is not None
    assert market_generation(session) > before


def test_market_generation_ignores_a_fundamental_write():
    """A census filing must not invalidate a market signal's cached answer."""
    session = open_session()
    observed = datetime(2026, 8, 13, 9, 15, tzinfo=timezone.utc)
    record_session(session, date(2026, 8, 12), observed_at=observed)
    before = market_generation(session)

    record_session(
        session,
        date(2026, 8, 13),
        capability=Capability.FUNDAMENTAL,
        observed_at=observed + timedelta(hours=7),
    )

    assert market_generation(session) == before


def test_market_generation_of_an_empty_store_is_none():
    assert market_generation(open_session()) is None
