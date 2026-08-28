"""Which days the daily spine actually holds a closed session for."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.stocks.models import BarDaily
from src.stocks.providers.normalize import VN_TZ
from src.stocks.trading_day import (
    CALENDAR_SERIES,
    latest_trading_day,
    spine_freshness,
    trading_days_before,
    trading_days_between,
)

EQUITY = "equity"


def open_session() -> Session:
    engine = create_engine("sqlite://")
    BarDaily.__table__.create(engine)
    return Session(engine)


def after_the_close(day: date) -> datetime:
    """When a run that waited for the close would have read this session."""
    return datetime.combine(day, time(16, 30), tzinfo=VN_TZ)


def record_session(
    session: Session,
    day: date,
    *,
    symbol: str = "VNINDEX",
    series: str = CALENDAR_SERIES,
    observed_at: datetime | None = None,
    close: float = 1_800.0,
) -> None:
    price = Decimal(str(close))
    stamp = observed_at or after_the_close(day)
    session.add(
        BarDaily(
            symbol=symbol,
            trading_day=day,
            series=series,
            open=price,
            high=price,
            low=price,
            close=price,
            volume=1_000_000,
            price_basis="adjusted_at_source",
            source="vnstock",
            observed_at=_as_stored(stamp),
        )
    )
    session.flush()


def _as_stored(value: datetime) -> datetime:
    """The instant as Postgres would hold it, so SQLite round-trips the same one.

    ``observed_at`` is ``timestamptz``: Postgres normalises to UTC on write and
    hands the instant back. SQLite has no such type — SQLAlchemy writes whatever
    wall-clock the value carries and drops the offset — so a fixture handing it
    a Vietnam-local time would come back seven hours earlier than the instant it
    meant, and every settled test in this file would be measuring the fixture
    rather than the code.
    """
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def test_an_empty_spine_has_no_trading_day():
    """A fresh environment has to say so rather than substitute today."""
    assert latest_trading_day(open_session()) is None


def test_the_newest_closed_session_is_the_trading_day():
    session = open_session()
    record_session(session, date(2026, 8, 13))

    assert latest_trading_day(session) == date(2026, 8, 13)


def test_a_session_still_being_filled_in_is_not_a_trading_day():
    """The row was read before the close, so it is a partial bar, not a session.

    ``vnstock_daily`` writes the current session during trading hours with
    whatever the provider has of it. Nothing in the numbers says so; only
    ``observed_at`` does.
    """
    session = open_session()
    record_session(session, date(2026, 8, 12))
    record_session(
        session,
        date(2026, 8, 13),
        observed_at=datetime.combine(date(2026, 8, 13), time(11, 0), tzinfo=VN_TZ),
    )

    assert latest_trading_day(session) == date(2026, 8, 12)


def test_the_verdict_does_not_move_when_the_wall_clock_crosses_the_close():
    """Two calls inside one Turn cannot measure two different windows.

    The settled test reads ``observed_at`` against the session's own close, and
    never ``datetime.now()``: a Turn asking at 14:59:50 and again at 15:00:10
    would otherwise get two different newest sessions.
    """
    session = open_session()
    record_session(session, date(2026, 8, 12))
    record_session(
        session,
        date(2026, 8, 13),
        observed_at=datetime.combine(date(2026, 8, 13), time(14, 59), tzinfo=VN_TZ),
    )

    assert latest_trading_day(session) == date(2026, 8, 12)
    assert latest_trading_day(session) == date(2026, 8, 12)


def test_a_row_read_exactly_at_the_close_counts_as_closed():
    session = open_session()
    record_session(
        session,
        date(2026, 8, 13),
        observed_at=datetime.combine(date(2026, 8, 13), time(15, 0), tzinfo=VN_TZ),
    )

    assert latest_trading_day(session) == date(2026, 8, 13)


def test_an_observed_at_without_a_zone_is_read_as_utc():
    """Which is how the store has always read that column."""
    session = open_session()
    record_session(
        session,
        date(2026, 8, 13),
        # 09:30 UTC is 16:30 in Vietnam: after the close.
        observed_at=datetime(2026, 8, 13, 9, 30),
    )

    assert latest_trading_day(session) == date(2026, 8, 13)


def test_the_equity_series_does_not_define_the_calendar():
    """A union over 1,522 shares would call a day a session for any one of them.

    The calendar is the index series alone, so an equity row landing on a day
    the index has none of moves nothing.
    """
    session = open_session()
    record_session(session, date(2026, 8, 13))
    record_session(session, date(2026, 8, 14), symbol="STB", series=EQUITY, close=74.5)

    assert latest_trading_day(session) == date(2026, 8, 13)
    assert trading_days_before(session, date(2026, 8, 20), 5) == (date(2026, 8, 13),)


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


def test_preceding_days_return_fewer_rather_than_reaching_past_the_spine():
    """Twenty asked for and two held is two, never a padded twenty.

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


def test_a_window_the_exchange_was_shut_for_holds_no_sessions():
    """An empty answer is real, and is not the same as an empty spine."""
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


class TestFreshness:
    """Nothing feeds the spine from inside the app, so somebody has to be told."""

    def test_an_empty_spine_is_empty_and_not_stale(self):
        reading = spine_freshness(open_session(), today=date(2026, 8, 20))

        assert reading.is_empty
        assert not reading.is_stale
        assert reading.age_days is None
        assert "no session at all" in reading.describe()

    def test_a_spine_fed_today_is_neither(self):
        session = open_session()
        record_session(session, date(2026, 8, 13))

        reading = spine_freshness(session, today=date(2026, 8, 13))

        assert not reading.is_empty
        assert not reading.is_stale
        assert reading.age_days == 0

    def test_a_spine_nobody_has_fed_says_how_many_days_ago(self):
        session = open_session()
        record_session(session, date(2026, 8, 13))

        reading = spine_freshness(session, today=date(2026, 8, 24))

        assert reading.is_stale
        assert reading.age_days == 11
        assert "2026-08-13" in reading.describe()

    def test_the_last_read_is_reported_even_when_it_was_a_partial_session(self):
        """Because "a run happened and wrote nothing closed" is its own state."""
        session = open_session()
        record_session(session, date(2026, 8, 12))
        partial = datetime.combine(date(2026, 8, 13), time(11, 0), tzinfo=VN_TZ)
        record_session(session, date(2026, 8, 13), observed_at=partial)

        reading = spine_freshness(session, today=date(2026, 8, 13))

        assert reading.latest_session == date(2026, 8, 12)
        assert reading.last_observed_at is not None
        assert _as_utc(reading.last_observed_at) == partial.astimezone(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """SQLite hands a timestamp back without its zone; the store reads it as UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def test_the_probe_does_not_walk_back_forever_through_partial_sessions():
    """A spine left partial for a week is stale, and that is a different answer.

    ``latest_trading_day`` looks back a handful of days for one that settled; it
    does not scan fifteen years hunting for the last good one, because a spine
    that far behind is an operational fact ``spine_freshness`` reports rather
    than a window to serve.
    """
    session = open_session()
    day = date(2026, 8, 3)
    for offset in range(10):
        session_day = day + timedelta(days=offset)
        if session_day.weekday() >= 5:
            continue
        record_session(
            session,
            session_day,
            observed_at=datetime.combine(session_day, time(11, 0), tzinfo=VN_TZ),
        )

    assert latest_trading_day(session) is None
