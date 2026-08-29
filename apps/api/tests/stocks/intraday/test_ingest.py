"""Ingest: the padding filter, the upsert, and the delta the second call makes.

The provider is a callable here, never the network. The frames it returns are
built to the shape observed on 2026-08-26 — a full 96-bucket grid with ``NaN``
prices outside session hours — because that shape is the thing the code under
test exists to survive.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd
import pytest
from sqlalchemy import delete, func, select

from src.core.database import Base, get_sync_db, sync_engine
from src.stocks.intraday import ingest, session_window
from src.stocks.models import BarIntraday15m
from src.stocks.providers.normalize import VN_TZ

SYMBOL = "INGST"

#: The full grid the provider answers on: 96 quarter hours from midnight.
GRID = tuple(
    (datetime.min + timedelta(minutes=15 * step)).time() for step in range(96)
)


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture(autouse=True)
def no_leftover_bars():
    yield
    with get_sync_db() as session:
        session.execute(delete(BarIntraday15m).where(BarIntraday15m.symbol == SYMBOL))


def provider_frame(days: list[date], *, volume: int = 100_000) -> pd.DataFrame:
    """A day of the real grid: session buckets filled, everything else NaN."""
    records = []
    for day in days:
        for moment in GRID:
            stamp = datetime.combine(day, moment)
            if session_window.phase_of(moment) is None:
                records.append(
                    {
                        "time": stamp,
                        "open": float("nan"),
                        "high": float("nan"),
                        "low": float("nan"),
                        "close": float("nan"),
                        "volume": 0,
                    }
                )
            else:
                records.append(
                    {
                        "time": stamp,
                        "open": 74.5,
                        "high": 74.9,
                        "low": 74.2,
                        "close": 74.6,
                        "volume": volume,
                    }
                )
    return pd.DataFrame.from_records(records)


def a_week(end: date) -> list[date]:
    return [end - timedelta(days=offset) for offset in range(4, -1, -1)]


def test_only_session_buckets_are_written_and_the_padding_is_counted():
    days = a_week(date(2026, 8, 21))

    with get_sync_db() as session:
        outcome = ingest.ensure_bars(
            session,
            SYMBOL,
            sessions=5,
            fetch=lambda symbol, start, end: provider_frame(days),
            today=date(2026, 8, 21),
        )
        session.commit()

        stored = session.execute(
            select(func.count()).select_from(BarIntraday15m).where(
                BarIntraday15m.symbol == SYMBOL
            )
        ).scalar_one()
        phases = set(
            session.execute(
                select(BarIntraday15m.phase).where(BarIntraday15m.symbol == SYMBOL)
            ).scalars()
        )

    assert outcome.rows_written == 5 * len(session_window.SESSION_BUCKETS)
    assert outcome.padding_dropped == 5 * (96 - len(session_window.SESSION_BUCKETS))
    assert stored == outcome.rows_written
    assert phases == {"ato", "am", "pm", "atc"}
    assert outcome.sessions_stored == 5
    assert outcome.last_session == date(2026, 8, 21)


def test_running_the_same_ingest_twice_does_not_double_the_volume():
    days = a_week(date(2026, 8, 21))
    fetch = lambda symbol, start, end: provider_frame(days)

    with get_sync_db() as session:
        ingest.ensure_bars(
            session, SYMBOL, sessions=5, fetch=fetch, today=date(2026, 8, 21)
        )
        session.commit()
        first = _totals(session)

        ingest.ensure_bars(
            session, SYMBOL, sessions=5, fetch=fetch, today=date(2026, 8, 21)
        )
        session.commit()
        second = _totals(session)

    assert first == second


def test_a_revised_last_bucket_is_corrected_rather_than_duplicated():
    days = [date(2026, 8, 21)]

    with get_sync_db() as session:
        ingest.ensure_bars(
            session,
            SYMBOL,
            sessions=1,
            fetch=lambda *_: provider_frame(days, volume=100_000),
            today=date(2026, 8, 21),
        )
        session.commit()

        ingest.ensure_bars(
            session,
            SYMBOL,
            sessions=1,
            fetch=lambda *_: provider_frame(days, volume=250_000),
            today=date(2026, 8, 21),
        )
        session.commit()

        rows, total = _totals(session)

    assert rows == len(session_window.SESSION_BUCKETS)
    assert total == 250_000 * len(session_window.SESSION_BUCKETS)


def test_a_quarter_hour_the_provider_repeats_does_not_abort_the_transaction():
    """The provider sending one bucket twice must cost the fetch, not the answer.

    ``ON CONFLICT DO UPDATE`` refuses a statement whose own values hold a key
    twice, and Postgres raises ``CardinalityViolation`` — which aborts the whole
    transaction rather than the statement. A Study runs its ingest and writes its
    artifact in one session, so an unresolved duplicate here would take the
    answer down with the fetch, and the row recording the failure with it.

    The later value wins, for the same reason the write is an upsert at all: the
    provider revises a session's last bucket.
    """
    day = date(2026, 8, 21)
    frame = provider_frame([day], volume=100_000)
    # The closing auction, sent a second time with a different number — which is
    # the bucket the provider has actually been seen to revise.
    closing = frame[frame["volume"] > 0].tail(1)
    repeated = pd.concat([frame, closing.assign(volume=777_000)])

    with get_sync_db() as session:
        ingest.ensure_bars(
            session, SYMBOL, sessions=1, fetch=lambda *_: repeated, today=day
        )
        session.commit()
        rows, _total = _totals(session)
        # The session is still usable, which is the whole point: a write after
        # the ingest is what a Study does next.
        assert session.execute(select(func.count(BarIntraday15m.symbol))).scalar() >= 1

    assert rows == len(session_window.SESSION_BUCKETS)

    with get_sync_db() as session:
        last = session.execute(
            select(BarIntraday15m.volume)
            .where(BarIntraday15m.symbol == SYMBOL)
            .order_by(BarIntraday15m.bucket_start.desc())
            .limit(1)
        ).scalar_one()
    assert last == 777_000


def test_a_cold_symbol_is_asked_for_the_provider_ceiling():
    asked: list[tuple[date, date]] = []

    def fetch(symbol, start, end):
        asked.append((start, end))
        return provider_frame([date(2026, 8, 21)])

    with get_sync_db() as session:
        ingest.ensure_bars(
            session, SYMBOL, sessions=30, fetch=fetch, today=date(2026, 8, 21)
        )
        session.commit()

    start, end = asked[0]
    assert start == date(2026, 8, 21) - timedelta(days=ingest.COLD_START_DAYS)
    assert end == date(2026, 8, 21)


def test_a_warm_symbol_is_asked_only_from_its_last_stored_session():
    days = a_week(date(2026, 8, 21))
    asked: list[date] = []

    def fetch(symbol, start, end):
        asked.append(start)
        return provider_frame(days)

    with get_sync_db() as session:
        ingest.ensure_bars(
            session, SYMBOL, sessions=5, fetch=fetch, today=date(2026, 8, 21)
        )
        session.commit()
        ingest.ensure_bars(
            session, SYMBOL, sessions=5, fetch=fetch, today=date(2026, 8, 21)
        )
        session.commit()

    assert asked[0] == date(2026, 8, 21) - timedelta(days=ingest.COLD_START_DAYS)
    # The last stored session, not the day after it: the provider revises it.
    assert asked[1] == date(2026, 8, 21)


def test_a_store_shorter_than_the_question_is_refilled_from_the_ceiling():
    """Two stored sessions cannot answer a thirty-session question.

    Asking from the store's own edge would leave it permanently short, so a
    store thinner than the window is treated as cold.
    """
    asked: list[date] = []

    def fetch(symbol, start, end):
        asked.append(start)
        return provider_frame([date(2026, 8, 20), date(2026, 8, 21)])

    with get_sync_db() as session:
        ingest.ensure_bars(
            session, SYMBOL, sessions=2, fetch=fetch, today=date(2026, 8, 21)
        )
        session.commit()
        ingest.ensure_bars(
            session, SYMBOL, sessions=30, fetch=fetch, today=date(2026, 8, 21)
        )
        session.commit()

    assert asked[1] == date(2026, 8, 21) - timedelta(days=ingest.COLD_START_DAYS)


def test_prices_are_scaled_from_thousands_to_dong():
    with get_sync_db() as session:
        ingest.ensure_bars(
            session,
            SYMBOL,
            sessions=1,
            fetch=lambda *_: provider_frame([date(2026, 8, 21)]),
            today=date(2026, 8, 21),
        )
        session.commit()
        row = session.execute(
            select(BarIntraday15m).where(BarIntraday15m.symbol == SYMBOL).limit(1)
        ).scalar_one()

    assert float(row.close) == 74_600.0
    assert float(row.open) == 74_500.0


def test_a_response_missing_a_column_writes_nothing():
    frame = provider_frame([date(2026, 8, 21)]).drop(columns=["volume"])

    with get_sync_db() as session:
        with pytest.raises(ingest.IntradayIngestError, match="volume"):
            ingest.ensure_bars(
                session,
                SYMBOL,
                sessions=1,
                fetch=lambda *_: frame,
                today=date(2026, 8, 21),
            )
        session.rollback()
        rows, _ = _totals(session)

    assert rows == 0


def test_a_session_bucket_with_no_trade_is_left_out_rather_than_zeroed():
    """An untraded quarter hour is missing data, not a measured zero."""
    frame = provider_frame([date(2026, 8, 21)])
    quiet = frame["time"] == datetime.combine(date(2026, 8, 21), time(10, 30))
    frame.loc[quiet, ["open", "high", "low", "close"]] = float("nan")
    frame.loc[quiet, "volume"] = 0

    with get_sync_db() as session:
        ingest.ensure_bars(
            session,
            SYMBOL,
            sessions=1,
            fetch=lambda *_: frame,
            today=date(2026, 8, 21),
        )
        session.commit()
        labels = set(
            session.execute(
                select(BarIntraday15m.bucket_start).where(
                    BarIntraday15m.symbol == SYMBOL
                )
            ).scalars()
        )

    assert len(labels) == len(session_window.SESSION_BUCKETS) - 1


def test_the_quarter_hour_the_market_is_still_inside_is_not_written():
    """A bucket seven minutes old is seven minutes of trade under a full label.

    The provider answers about the day in progress and reports the current
    quarter hour as though it were finished. Written, it becomes a fifteen-minute
    row carrying a fraction of a quarter hour — and an artifact freezes it there,
    because an artifact is rendered again rather than recomputed.
    """
    day = date(2026, 8, 21)
    # Inside the 10:30 bucket, seven minutes into it.
    now = datetime(2026, 8, 21, 10, 37, tzinfo=VN_TZ)

    with get_sync_db() as session:
        outcome = ingest.ensure_bars(
            session,
            SYMBOL,
            sessions=1,
            fetch=lambda *_: provider_frame([day]),
            today=day,
            now=now,
        )
        session.commit()
        written = _bucket_times(session)

    # 10:15 ended at 10:30 and its minute of slack is up; 10:30 is the one the
    # clock is inside, and everything after it has not started.
    assert time(10, 15) in written
    assert time(10, 30) not in written
    assert max(written) == time(10, 15)
    assert outcome.buckets_underway == len(session_window.SESSION_BUCKETS) - len(
        written
    )
    assert outcome.rows_written == len(written)


def test_a_bucket_is_written_once_its_grace_has_elapsed_and_not_a_second_before():
    """The cut-off is the bucket's own end plus the slack, to the second."""
    day = date(2026, 8, 21)
    settled = (
        datetime(2026, 8, 21, 10, 30, tzinfo=VN_TZ)
        + timedelta(minutes=session_window.BUCKET_MINUTES)
        + ingest.SETTLE_GRACE
    )
    fetch = lambda *_: provider_frame([day])

    with get_sync_db() as session:
        ingest.ensure_bars(
            session,
            SYMBOL,
            sessions=1,
            fetch=fetch,
            today=day,
            now=settled - timedelta(seconds=1),
        )
        session.commit()
        assert time(10, 30) not in _bucket_times(session)

        # The same fetch a second later: the warm path re-reads the session it
        # belongs to, so the bucket arrives on its own without a backfill.
        ingest.ensure_bars(
            session, SYMBOL, sessions=1, fetch=fetch, today=day, now=settled
        )
        session.commit()
        assert time(10, 30) in _bucket_times(session)


def test_a_session_the_clock_has_left_behind_is_written_whole():
    """Yesterday is never held back: every one of its buckets is finished."""
    day = date(2026, 8, 20)

    with get_sync_db() as session:
        outcome = ingest.ensure_bars(
            session,
            SYMBOL,
            sessions=1,
            fetch=lambda *_: provider_frame([day]),
            today=date(2026, 8, 21),
            now=datetime(2026, 8, 21, 9, 5, tzinfo=VN_TZ),
        )
        session.commit()

    assert outcome.buckets_underway == 0
    assert outcome.rows_written == len(session_window.SESSION_BUCKETS)


def _bucket_times(session) -> set[time]:
    """The clock times of every stored bucket for this symbol."""
    return {
        stamp.astimezone(VN_TZ).time()
        for stamp in session.execute(
            select(BarIntraday15m.bucket_start).where(BarIntraday15m.symbol == SYMBOL)
        ).scalars()
    }


def _totals(session) -> tuple[int, int]:
    row = session.execute(
        select(func.count(), func.coalesce(func.sum(BarIntraday15m.volume), 0)).where(
            BarIntraday15m.symbol == SYMBOL
        )
    ).one()
    return int(row[0]), int(row[1])
