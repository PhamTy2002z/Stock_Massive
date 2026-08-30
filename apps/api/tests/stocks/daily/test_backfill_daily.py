"""The job: what it skips, what it retries, and what one bad symbol costs.

The scope is stubbed to invented tickers. A run over the real declared list with
a stubbed provider would write invented prices for real companies into the
spine, which is a worse outcome than a thinner test — so the scope selection is
proved read-only, on its own, and the run is proved on symbols nothing else
reads.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, func, select, update

from src.core.config import get_settings
from src.core.database import Base, get_sync_db, sync_engine, sync_session_factory
from src.stocks import backfill_daily
from src.stocks.models import BarDaily, ListingRoster
from src.stocks.providers import vnstock_daily
from src.stocks.trading_day import STALE_AFTER_DAYS, SpineFreshness

from .test_vnstock_daily import synthetic


@contextmanager
def rollback_session():
    """A session for the read-only scope cases, never committed."""
    session = sync_session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


FIRST = "ZZJOB1"
SECOND = "ZZJOB2"
TODAY = date(2026, 6, 16)
NOW = datetime(2026, 6, 16, 9, 30, tzinfo=timezone.utc)


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture(autouse=True)
def no_leftover_bars():
    yield
    with get_sync_db() as session:
        session.execute(delete(BarDaily).where(BarDaily.symbol.in_([FIRST, SECOND])))


@pytest.fixture
def two_symbols(monkeypatch):
    monkeypatch.setattr(
        backfill_daily,
        "scope_symbols",
        lambda session, scope: (
            (FIRST, vnstock_daily.SERIES_EQUITY),
            (SECOND, vnstock_daily.SERIES_EQUITY),
        ),
    )


def days_back(count: int, *, end: date = TODAY) -> list[date]:
    """``count`` weekday sessions ending on or before ``end``, oldest first.

    Weekdays because ingest refuses a weekend row outright: the Trading Day
    calendar is derived from this table, so a Saturday would move the window
    every symbol in the market is measured against.
    """
    days: list[date] = []
    cursor = end
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return list(reversed(days))


def a_page(symbol, *, end, sessions):
    return synthetic(days_back(20, end=end))


def rows_for(symbol: str) -> int:
    with get_sync_db() as session:
        return session.execute(
            select(func.count(BarDaily.trading_day)).where(BarDaily.symbol == symbol)
        ).scalar_one()


def asked_before_the_newest_session(symbol: str, when: date) -> None:
    """Age a symbol's ``observed_at`` so the store reads as asked-about earlier."""
    with get_sync_db() as session:
        session.execute(
            update(BarDaily)
            .where(BarDaily.symbol == symbol)
            .values(
                observed_at=datetime(
                    when.year, when.month, when.day, tzinfo=timezone.utc
                )
            )
        )
        session.commit()


class TestScope:
    def test_the_declared_scope_is_the_declared_universe(self, monkeypatch):
        monkeypatch.setenv("UNIVERSE_SYMBOLS", "VCB,FPT")
        get_settings.cache_clear()
        try:
            with rollback_session() as session:
                targets = backfill_daily.scope_symbols(session, "declared")
        finally:
            get_settings.cache_clear()

        assert targets == (
            ("VCB", vnstock_daily.SERIES_EQUITY),
            ("FPT", vnstock_daily.SERIES_EQUITY),
        )

    def test_the_index_scope_is_one_symbol_in_its_own_series(self):
        with rollback_session() as session:
            targets = backfill_daily.scope_symbols(session, "index")

        assert targets == (("VNINDEX", vnstock_daily.SERIES_INDEX),)

    def test_the_market_scope_is_the_registers_listed_shares(self):
        """The whole market, whatever the declared list says, minus who left."""
        with rollback_session() as session:
            session.add_all(
                [
                    ListingRoster(
                        symbol=FIRST,
                        exchange="HOSE",
                        is_listed=True,
                        source="vnstock",
                        observed_at=datetime(2026, 8, 27, tzinfo=timezone.utc),
                    ),
                    ListingRoster(
                        symbol=SECOND,
                        exchange="HNX",
                        is_listed=False,
                        source="vnstock",
                        observed_at=datetime(2026, 8, 27, tzinfo=timezone.utc),
                    ),
                ]
            )
            session.flush()

            market = backfill_daily.scope_symbols(session, "market")

        assert (FIRST, vnstock_daily.SERIES_EQUITY) in market
        assert SECOND not in {symbol for symbol, _series in market}

    def test_a_scope_that_is_not_a_scope_is_refused(self):
        with rollback_session() as session:
            with pytest.raises(ValueError, match="not a scope"):
                backfill_daily.scope_symbols(session, "everything")

    def test_the_defaults_match_the_depth_each_scope_needs(self):
        assert backfill_daily.DEFAULT_SESSIONS["declared"] == 2000
        assert backfill_daily.DEFAULT_SESSIONS["index"] == 2000
        assert backfill_daily.DEFAULT_SESSIONS["market"] == 400


class TestRun:
    def test_every_symbol_in_the_scope_is_written(self, two_symbols):
        report = backfill_daily.run(
            scope="market", sessions=20, fetch=a_page, today=TODAY
        )

        assert report.attempted == 2
        assert report.rows_written == 40
        assert rows_for(FIRST) == 20
        assert rows_for(SECOND) == 20

    def test_a_second_run_writes_nothing_and_skips_what_is_deep_enough(
        self, two_symbols
    ):
        """Resume comes from the store, and there is no ledger to disagree.

        The skip needs both halves: enough sessions, and a newest session as new
        as the spine's own.
        """
        backfill_daily.run(scope="market", sessions=20, fetch=a_page, today=TODAY)
        report = backfill_daily.run(
            scope="market", sessions=20, fetch=a_page, today=TODAY
        )

        assert report.skipped == 2
        assert report.rows_written == 0
        assert rows_for(FIRST) == 20

    def test_a_symbol_short_of_the_depth_is_fetched_again(self, two_symbols):
        backfill_daily.run(scope="market", sessions=20, fetch=a_page, today=TODAY)
        report = backfill_daily.run(
            scope="market",
            sessions=30,
            fetch=lambda symbol, *, end, sessions: synthetic(days_back(30, end=end)),
            today=TODAY,
        )

        assert report.skipped == 0
        assert rows_for(FIRST) == 30

    def test_a_symbol_asked_about_before_the_newest_session_is_fetched_again(
        self, two_symbols
    ):
        """Depth alone would freeze a symbol at the day it was first filled."""
        backfill_daily.run(
            scope="market",
            sessions=20,
            fetch=lambda symbol, *, end, sessions: synthetic(
                days_back(20, end=TODAY - timedelta(days=10))
                if symbol == FIRST
                else days_back(20, end=TODAY)
            ),
            today=TODAY,
        )
        asked_before_the_newest_session(FIRST, TODAY - timedelta(days=10))

        report = backfill_daily.run(
            scope="market", sessions=20, fetch=a_page, today=TODAY
        )
        by_symbol = {entry.symbol: entry for entry in report.symbols}

        assert by_symbol[FIRST].skipped is False
        assert by_symbol[SECOND].skipped is True

    def test_a_share_that_did_not_trade_today_is_not_asked_about_twice(
        self, two_symbols
    ):
        """A thin board's silence is an answer, and it was already paid for.

        FIRST last matched ten days ago and SECOND traded today, so the spine's
        newest session is today and FIRST's newest is not. Judged by sessions
        alone FIRST could never be current, and every run would call the provider
        again for a share that simply is not trading — 677 of 1,522 listed shares
        were in that position on 2026-08-27.
        """
        report = backfill_daily.run(
            scope="market",
            sessions=20,
            fetch=lambda symbol, *, end, sessions: synthetic(
                days_back(20, end=TODAY - timedelta(days=10))
                if symbol == FIRST
                else days_back(20, end=TODAY)
            ),
            today=TODAY,
        )
        assert report.skipped == 0

        again = backfill_daily.run(
            scope="market", sessions=20, fetch=a_page, today=TODAY
        )

        assert again.skipped == 2
        assert again.rows_written == 0

    def test_one_failing_symbol_does_not_end_the_run(self, two_symbols):
        """1,523 calls against a provider with no SLA cannot stop at the first.

        Nothing is lost by continuing: the failed symbol is simply not deep
        enough next time, and re-running the command retries exactly it.
        """

        def fetch(symbol, *, end, sessions):
            if symbol == FIRST:
                raise vnstock_daily.DailyIngestError("the provider hung up")
            return synthetic(days_back(20, end=end))

        report = backfill_daily.run(
            scope="market", sessions=20, fetch=fetch, today=TODAY
        )

        assert report.failures == (FIRST,)
        assert rows_for(FIRST) == 0
        assert rows_for(SECOND) == 20

    def test_a_failing_symbol_does_not_roll_back_the_symbols_before_it(
        self, two_symbols
    ):
        """Each symbol has its own transaction, so an abort costs one symbol."""

        def fetch(symbol, *, end, sessions):
            if symbol == SECOND:
                raise vnstock_daily.DailyIngestError("the provider hung up")
            return synthetic(days_back(20, end=end))

        backfill_daily.run(scope="market", sessions=20, fetch=fetch, today=TODAY)

        assert rows_for(FIRST) == 20
        assert rows_for(SECOND) == 0

    def test_an_empty_scope_is_a_warning_rather_than_a_crash(self, monkeypatch):
        monkeypatch.setattr(backfill_daily, "scope_symbols", lambda session, scope: ())

        report = backfill_daily.run(scope="market", fetch=a_page, today=TODAY)

        assert report.symbols == []
        assert report.rows_written == 0

    def test_a_scope_the_cli_does_not_offer_is_refused(self):
        with pytest.raises(ValueError, match="not a scope"):
            backfill_daily.run(scope="everything")


class TestCli:
    def test_the_scope_is_required_and_checked(self):
        with pytest.raises(SystemExit):
            backfill_daily._parse_args([])
        with pytest.raises(SystemExit):
            backfill_daily._parse_args(["--scope", "everything"])

    def test_sessions_defaults_to_the_scopes_own_depth(self):
        args = backfill_daily._parse_args(["--scope", "market"])

        assert args.scope == "market"
        assert args.sessions is None

    def test_a_run_with_failures_exits_non_zero(self, monkeypatch):
        monkeypatch.setattr(
            backfill_daily,
            "run",
            lambda **kwargs: backfill_daily.BackfillReport(
                scope="index",
                sessions=1,
                symbols=[
                    backfill_daily.SymbolReport(
                        symbol="VNINDEX", series="index", error="the provider hung up"
                    )
                ],
            ),
        )

        assert backfill_daily.main(["--scope", "index"]) == 1

    def test_a_clean_run_over_a_current_spine_exits_zero(self, monkeypatch):
        monkeypatch.setattr(
            backfill_daily,
            "run",
            lambda **kwargs: backfill_daily.BackfillReport(scope="index", sessions=1),
        )
        _freshness(monkeypatch, age_days=0)

        assert backfill_daily.main(["--scope", "index"]) == 0

    def test_a_clean_run_that_left_the_spine_behind_exits_non_zero(self, monkeypatch):
        """Nothing failed and the market still stopped moving.

        This is the state R2 exists for: the job is the only thing feeding the
        Trading Day calendar, so a run that wrote nothing and said "fine" would
        let the newest session freeze while every answer still carries a date.
        """
        monkeypatch.setattr(
            backfill_daily,
            "run",
            lambda **kwargs: backfill_daily.BackfillReport(scope="index", sessions=1),
        )
        _freshness(monkeypatch, age_days=STALE_AFTER_DAYS + 1)

        assert backfill_daily.main(["--scope", "index"]) == 1

    def test_a_clean_run_over_an_empty_spine_exits_non_zero(self, monkeypatch):
        monkeypatch.setattr(
            backfill_daily,
            "run",
            lambda **kwargs: backfill_daily.BackfillReport(scope="index", sessions=1),
        )
        _freshness(monkeypatch, age_days=None)

        assert backfill_daily.main(["--scope", "index"]) == 1


def _freshness(monkeypatch, *, age_days: int | None) -> None:
    """State what the spine looks like, instead of depending on the test database."""
    latest = None if age_days is None else TODAY - timedelta(days=age_days)
    monkeypatch.setattr(
        backfill_daily,
        "spine_freshness",
        lambda session, **_: SpineFreshness(
            latest_session=latest,
            last_observed_at=None if latest is None else NOW,
            age_days=age_days,
        ),
    )


class TestTheSkipReferenceComesFromTheCalendar:
    """The spine has to be able to move past its own newest session.

    Both in-store references are this job's own output, so either one makes the
    spine a fixed point: every symbol that reached the newest stored session is
    "current" with that session, and a spine that missed a day can never be told
    to go and get it. Measured in production on 2026-08-30 — every one of 1,523
    symbols was frozen at 2026-08-27 and every run skipped every symbol.
    """

    def test_a_weekend_asks_for_the_friday_before_it(self):
        friday = date(2026, 8, 28)

        assert backfill_daily.latest_expected_session(date(2026, 8, 29)) == friday
        assert backfill_daily.latest_expected_session(date(2026, 8, 30)) == friday
        assert backfill_daily.latest_expected_session(friday) == friday

    def test_a_spine_behind_the_calendar_is_fetched_again(self, two_symbols):
        """The regression: judged against itself, this run skipped everything."""
        stale_end = TODAY - timedelta(days=3)
        backfill_daily.run(
            scope="market",
            sessions=20,
            fetch=lambda symbol, *, end, sessions: synthetic(
                days_back(20, end=stale_end)
            ),
            today=stale_end,
        )
        asked_before_the_newest_session(FIRST, stale_end)
        asked_before_the_newest_session(SECOND, stale_end)

        report = backfill_daily.run(
            scope="market", sessions=20, fetch=a_page, today=TODAY
        )

        assert report.skipped == 0
        assert report.attempted == 2
