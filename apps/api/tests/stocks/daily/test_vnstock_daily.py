"""Daily ingest: the units, the upsert, and the pages behind the provider's cap.

The provider is a callable here, never the network. The frames it answers with
are the ones captured on 2026-08-27, because their units and their loose window
are what this code exists to survive.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest
from sqlalchemy import delete, func, select

from src.core.database import Base, get_sync_db, sync_engine
from src.stocks.models import BarDaily
from src.stocks.providers import vnstock_daily

from . import fixtures

SYMBOL = "DLYST"
INDEX_SYMBOL = "DLYIX"
TODAY = date(2026, 6, 16)


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture(autouse=True)
def no_leftover_bars():
    yield
    with get_sync_db() as session:
        session.execute(
            delete(BarDaily).where(BarDaily.symbol.in_([SYMBOL, INDEX_SYMBOL]))
        )


def synthetic(
    days: list[date], *, close: float = 10.0, volume: int = 1_000
) -> pd.DataFrame:
    """A frame of chosen sessions, in the provider's units and column order."""
    return pd.DataFrame.from_records(
        [
            {
                "time": pd.Timestamp(day),
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": volume,
            }
            for day in days
        ],
        columns=list(vnstock_daily.REQUIRED_COLUMNS),
    )


def sessions_back(count: int, *, end: date) -> list[date]:
    """``count`` consecutive calendar days ending at ``end``, oldest first."""
    return [end - timedelta(days=offset) for offset in range(count - 1, -1, -1)]


def _stored(session, symbol: str = SYMBOL) -> tuple[int, int]:
    return session.execute(
        select(func.count(BarDaily.trading_day), func.sum(BarDaily.volume)).where(
            BarDaily.symbol == symbol
        )
    ).one()


class TestNormalize:
    def test_a_captured_equity_response_is_stored_in_dong(self):
        with get_sync_db() as session:
            outcome = vnstock_daily.ensure_daily_bars(
                session,
                SYMBOL,
                sessions=13,
                fetch=lambda symbol, **_: fixtures.stb_daily(),
                today=TODAY,
            )
            row = session.execute(
                select(BarDaily).where(
                    BarDaily.symbol == SYMBOL,
                    BarDaily.trading_day == date(2026, 6, 15),
                )
            ).scalar_one()

            assert outcome.rows_written == 13
            assert outcome.sessions_stored == 13
            # The window is a hint: the response carried a session on each side
            # of the one asked for, and both are real sessions.
            assert outcome.first_session == date(2026, 5, 29)
            assert outcome.last_session == date(2026, 6, 16)
            assert float(row.close) == 71_800.0
            assert float(row.open) == 71_100.0
            assert row.volume == 4_486_600
            assert row.series == vnstock_daily.SERIES_EQUITY

    def test_an_index_response_keeps_its_points(self):
        with get_sync_db() as session:
            vnstock_daily.ensure_daily_bars(
                session,
                INDEX_SYMBOL,
                sessions=10,
                series=vnstock_daily.SERIES_INDEX,
                fetch=lambda symbol, **_: fixtures.vnindex_daily(),
                today=TODAY,
            )
            row = session.execute(
                select(BarDaily).where(
                    BarDaily.symbol == INDEX_SYMBOL,
                    BarDaily.trading_day == date(2026, 6, 11),
                )
            ).scalar_one()

            assert float(row.close) == 1798.61
            assert row.series == vnstock_daily.SERIES_INDEX

    def test_the_price_basis_is_written_on_every_row(self):
        """A stored window can be asked what its numbers mean.

        The value is a column and not an assumption made elsewhere, because a
        window whose basis is only implied is how two incomparable price series
        ended up in one table before.
        """
        with get_sync_db() as session:
            vnstock_daily.ensure_daily_bars(
                session,
                SYMBOL,
                sessions=13,
                fetch=lambda symbol, **_: fixtures.stb_daily(),
                today=TODAY,
            )
            bases = set(
                session.execute(
                    select(BarDaily.price_basis).where(BarDaily.symbol == SYMBOL)
                ).scalars()
            )

        assert bases == {"adjusted_at_source"}

    def test_a_response_missing_a_column_writes_nothing(self):
        frame = fixtures.stb_daily().drop(columns=["volume"])

        with get_sync_db() as session:
            with pytest.raises(vnstock_daily.DailyIngestError, match="volume"):
                vnstock_daily.ensure_daily_bars(
                    session,
                    SYMBOL,
                    sessions=13,
                    fetch=lambda symbol, **_: frame,
                    today=TODAY,
                )
            session.rollback()
            rows, _ = _stored(session)

        assert rows == 0

    def test_a_session_with_no_price_is_left_out_rather_than_zeroed(self):
        """A halted session is missing data, not a measured collapse."""
        frame = fixtures.stb_daily()
        frame.loc[frame["time"] == pd.Timestamp("2026-06-04"), ["open", "close"]] = None

        with get_sync_db() as session:
            outcome = vnstock_daily.ensure_daily_bars(
                session,
                SYMBOL,
                sessions=12,
                fetch=lambda symbol, **_: frame,
                today=TODAY,
            )
            days = set(
                session.execute(
                    select(BarDaily.trading_day).where(BarDaily.symbol == SYMBOL)
                ).scalars()
            )

        assert outcome.rows_written == 12
        assert date(2026, 6, 4) not in days

    def test_a_series_the_table_does_not_hold_is_refused(self):
        with get_sync_db() as session:
            with pytest.raises(vnstock_daily.DailyIngestError, match="series"):
                vnstock_daily.ensure_daily_bars(
                    session,
                    SYMBOL,
                    sessions=1,
                    series="futures",
                    fetch=lambda symbol, **_: fixtures.stb_daily(),
                    today=TODAY,
                )


class TestIdempotence:
    def test_running_the_same_ingest_twice_writes_the_same_rows(self):
        fetch = lambda symbol, **_: fixtures.stb_daily()  # noqa: E731

        with get_sync_db() as session:
            vnstock_daily.ensure_daily_bars(
                session, SYMBOL, sessions=13, fetch=fetch, today=TODAY
            )
            session.commit()
            first = _stored(session)

            vnstock_daily.ensure_daily_bars(
                session, SYMBOL, sessions=13, fetch=fetch, today=TODAY
            )
            session.commit()
            second = _stored(session)

        assert first == second

    def test_a_restated_session_is_corrected_rather_than_duplicated(self):
        day = [date(2026, 6, 15)]

        with get_sync_db() as session:
            vnstock_daily.ensure_daily_bars(
                session,
                SYMBOL,
                sessions=1,
                fetch=lambda symbol, **_: synthetic(day, close=71.8, volume=1_000),
                today=TODAY,
            )
            session.commit()
            vnstock_daily.ensure_daily_bars(
                session,
                SYMBOL,
                sessions=1,
                fetch=lambda symbol, **_: synthetic(day, close=70.0, volume=2_000),
                today=TODAY,
            )
            session.commit()
            rows, volume = _stored(session)
            close = session.execute(
                select(BarDaily.close).where(BarDaily.symbol == SYMBOL)
            ).scalar_one()

        assert rows == 1
        assert volume == 2_000
        assert float(close) == 70_000.0

    def test_a_session_the_provider_repeats_does_not_abort_the_transaction(self):
        """A duplicated key must cost the fetch, not everything in the session.

        ``ON CONFLICT DO UPDATE`` refuses a statement whose own values hold a key
        twice, and Postgres raises ``CardinalityViolation`` — which aborts the
        whole transaction rather than the statement. In a job writing symbol
        after symbol, an unresolved duplicate would take every other symbol's
        write down with it. The later value wins, because a re-stated session is
        the provider correcting an adjustment factor.
        """
        frame = fixtures.stb_daily()
        repeated = pd.concat([frame, frame.tail(1).assign(close=99.9)])

        with get_sync_db() as session:
            outcome = vnstock_daily.ensure_daily_bars(
                session,
                SYMBOL,
                sessions=13,
                fetch=lambda symbol, **_: repeated,
                today=TODAY,
            )
            # The session is still usable, which is the point: a job writes the
            # next symbol through it.
            assert session.execute(select(func.count(BarDaily.symbol))).scalar() >= 1
            session.commit()
            rows, _ = _stored(session)
            last = session.execute(
                select(BarDaily.close)
                .where(BarDaily.symbol == SYMBOL)
                .order_by(BarDaily.trading_day.desc())
                .limit(1)
            ).scalar_one()

        assert outcome.rows_written == 13
        assert rows == 13
        assert float(last) == 99_900.0


class TestPaging:
    def test_depth_beyond_one_call_pages_backward_from_the_earliest_row(self):
        """Two thousand rows is one call; deeper is a call ending a day earlier.

        The cap fills backward from ``end``, so the only cursor that reaches
        further is the earliest session already received, minus a day.
        """
        first_page = sessions_back(40, end=TODAY)
        second_page = sessions_back(40, end=first_page[0] - timedelta(days=1))
        asked: list[date] = []

        def fetch(symbol, *, end, sessions):
            asked.append(end)
            return synthetic(first_page if len(asked) == 1 else second_page)

        with get_sync_db() as session:
            outcome = vnstock_daily.ensure_daily_bars(
                session, SYMBOL, sessions=75, fetch=fetch, today=TODAY
            )

        assert asked[0] == TODAY
        assert asked[1] == first_page[0] - timedelta(days=1)
        assert outcome.calls == 2
        assert outcome.sessions_stored == 80
        assert outcome.first_session == second_page[0]

    def test_paging_stops_once_the_requested_depth_is_stored(self):
        asked: list[date] = []

        def fetch(symbol, *, end, sessions):
            asked.append(end)
            return synthetic(sessions_back(40, end=end))

        with get_sync_db() as session:
            outcome = vnstock_daily.ensure_daily_bars(
                session, SYMBOL, sessions=30, fetch=fetch, today=TODAY
            )

        assert outcome.calls == 1
        assert asked == [TODAY]

    def test_paging_stops_when_a_page_comes_back_empty(self):
        calls: list[date] = []

        def fetch(symbol, *, end, sessions):
            calls.append(end)
            if len(calls) == 1:
                return synthetic(sessions_back(20, end=end))
            return synthetic([])

        with get_sync_db() as session:
            outcome = vnstock_daily.ensure_daily_bars(
                session, SYMBOL, sessions=2000, fetch=fetch, today=TODAY
            )

        assert outcome.calls == 2
        assert outcome.sessions_stored == 20

    def test_a_page_before_the_first_session_keeps_what_arrived(self):
        """Depth past a young listing is the history ending, not a failed symbol.

        The first page is where an outage is reported; a later one that answers
        nothing must not roll back the sessions already written.
        """
        page = sessions_back(20, end=TODAY)
        calls: list[date] = []

        def fetch(symbol, *, end, sessions):
            calls.append(end)
            if len(calls) == 1:
                return synthetic(page)
            raise vnstock_daily.DailyIngestError("answered nothing")

        with get_sync_db() as session:
            outcome = vnstock_daily.ensure_daily_bars(
                session, SYMBOL, sessions=2000, fetch=fetch, today=TODAY
            )
            session.commit()
            rows, _ = _stored(session)

        assert len(calls) == 2
        assert outcome.calls == 1
        assert rows == 20

    def test_the_first_page_failing_is_reported_rather_than_swallowed(self):
        def fetch(symbol, *, end, sessions):
            raise vnstock_daily.DailyIngestError("answered nothing")

        with get_sync_db() as session:
            with pytest.raises(vnstock_daily.DailyIngestError):
                vnstock_daily.ensure_daily_bars(
                    session, SYMBOL, sessions=400, fetch=fetch, today=TODAY
                )

    def test_a_provider_repeating_the_same_block_does_not_page_forever(self):
        """The window is a hint, so a page can fail to move backward at all."""
        block = sessions_back(20, end=TODAY)
        calls: list[date] = []

        def fetch(symbol, *, end, sessions):
            calls.append(end)
            return synthetic(block)

        with get_sync_db() as session:
            outcome = vnstock_daily.ensure_daily_bars(
                session, SYMBOL, sessions=2000, fetch=fetch, today=TODAY
            )

        assert outcome.calls == 2
        assert len(calls) < vnstock_daily.MAX_PAGES
        assert outcome.sessions_stored == 20


class TestRequestWindow:
    def test_the_window_asked_for_is_wider_than_the_sessions_wanted(self, monkeypatch):
        """A session is not a calendar day, and asking short returns short.

        The provider's row cap — not the window — bounds the answer, so the
        window is padded past 400 trading sessions rather than trimmed to them.
        """
        asked: dict[str, str] = {}

        class FakeQuote:
            def __init__(self, **_):
                pass

            def history(self, **kwargs):
                asked.update(kwargs)
                return fixtures.stb_daily()

        monkeypatch.setattr(vnstock_daily, "Quote", FakeQuote)
        monkeypatch.setattr(
            vnstock_daily,
            "safe_vnstock_call",
            lambda func, *args, **kwargs: func(*args, **kwargs),
        )

        frame = vnstock_daily.fetch_daily("STB", end=TODAY, sessions=400)

        assert asked["end"] == TODAY.isoformat()
        assert asked["interval"] == "1D"
        start = date.fromisoformat(asked["start"])
        assert (TODAY - start).days > 400
        assert not frame.empty

    def test_a_window_the_provider_answers_nothing_for_raises(self, monkeypatch):
        """The wrapper flattens every failure to None, including "no data here".

        Raising is right at this level: the caller knows whether earlier pages
        arrived, and only it can tell an outage from the end of a history.
        """

        class SilentQuote:
            def __init__(self, **_):
                pass

            def history(self, **_):  # pragma: no cover - never reached
                return None

        def opens_a_client_but_answers_nothing(func, *args, **kwargs):
            """The client is built through the wrapper too; only the call is silent."""
            return SilentQuote() if func is SilentQuote else None

        monkeypatch.setattr(vnstock_daily, "Quote", SilentQuote)
        monkeypatch.setattr(
            vnstock_daily, "safe_vnstock_call", opens_a_client_but_answers_nothing
        )

        with pytest.raises(vnstock_daily.DailyIngestError, match="answered nothing"):
            vnstock_daily.fetch_daily("STB", end=TODAY, sessions=10)

    def test_a_client_the_provider_will_not_open_raises(self, monkeypatch):
        """A constructor that exits the process must not walk past the job.

        vnstock calls ``sys.exit()`` when it has had enough, from the constructor
        as well as from the call, and ``SystemExit`` is a ``BaseException`` that
        every ``except Exception`` between here and the job would miss.
        """
        monkeypatch.setattr(
            vnstock_daily, "safe_vnstock_call", lambda *args, **kwargs: None
        )

        with pytest.raises(vnstock_daily.DailyIngestError, match="would not open"):
            vnstock_daily.fetch_daily("STB", end=TODAY, sessions=10)
