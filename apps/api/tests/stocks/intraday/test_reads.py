"""The read: closed sessions only, whole sessions, newest N of them."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import pytest
from sqlalchemy import delete

from src.core.database import Base, get_sync_db, sync_engine
from src.stocks.intraday import ingest, reads, session_window
from src.stocks.models import BarIntraday15m
from src.stocks.providers.normalize import VN_TZ

SYMBOL = "READS"
TODAY = date(2026, 8, 26)
GRID = tuple(
    (datetime.min + timedelta(minutes=15 * step)).time() for step in range(96)
)


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture(autouse=True)
def stored_sessions():
    days = [TODAY - timedelta(days=offset) for offset in range(4, -1, -1)]
    records = []
    for day in days:
        for moment in GRID:
            in_session = session_window.phase_of(moment) is not None
            records.append(
                {
                    "time": datetime.combine(day, moment),
                    "open": 74.5 if in_session else float("nan"),
                    "high": 74.9 if in_session else float("nan"),
                    "low": 74.2 if in_session else float("nan"),
                    "close": 74.6 if in_session else float("nan"),
                    "volume": 100_000 if in_session else 0,
                }
            )
    frame = pd.DataFrame.from_records(records)

    with get_sync_db() as session:
        ingest.ensure_bars(
            session,
            SYMBOL,
            sessions=len(days),
            fetch=lambda *_: frame,
            today=TODAY,
        )
        session.commit()

    yield days

    with get_sync_db() as session:
        session.execute(delete(BarIntraday15m).where(BarIntraday15m.symbol == SYMBOL))


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(TODAY.year, TODAY.month, TODAY.day, hour, minute, tzinfo=VN_TZ)


def test_today_is_not_a_closed_session_before_the_auction_settles(stored_sessions):
    with get_sync_db() as session:
        assert reads.latest_closed_session(
            session, SYMBOL, now=at(11, 0)
        ) == stored_sessions[-2]


def test_today_becomes_a_closed_session_once_the_auction_has_settled(stored_sessions):
    with get_sync_db() as session:
        assert reads.latest_closed_session(
            session, SYMBOL, now=at(15, 0)
        ) == stored_sessions[-1]


def test_the_window_is_the_newest_closed_sessions_whole(stored_sessions):
    with get_sync_db() as session:
        bars = reads.bars_for(session, SYMBOL, 2, now=at(11, 0))

    days = sorted({bar.trading_day for bar in bars})
    assert days == stored_sessions[-3:-1]
    assert len(bars) == 2 * len(session_window.SESSION_BUCKETS)
    assert bars == tuple(sorted(bars, key=lambda bar: bar.bucket_start))


def test_asking_for_more_sessions_than_the_store_holds_returns_what_there_is(
    stored_sessions,
):
    with get_sync_db() as session:
        bars = reads.bars_for(session, SYMBOL, 60, now=at(11, 0))
        available = reads.sessions_available(session, SYMBOL, now=at(11, 0))

    assert available == len(stored_sessions) - 1
    assert len({bar.trading_day for bar in bars}) == available


def test_a_bar_labels_itself_in_vietnamese_local_time(stored_sessions):
    with get_sync_db() as session:
        bars = reads.bars_for(session, SYMBOL, 1, now=at(11, 0))

    assert bars[0].bucket_label == "09:00"
    assert bars[-1].bucket_label == "14:45"
    assert {bar.bucket_label for bar in bars} == set(
        session_window.SESSION_BUCKET_LABELS
    )


def test_traded_value_is_volume_at_the_close_in_dong(stored_sessions):
    with get_sync_db() as session:
        bars = reads.bars_for(session, SYMBOL, 1, now=at(11, 0))

    assert float(bars[0].traded_value) == 74_600.0 * 100_000


def test_an_unknown_symbol_reads_as_an_empty_window():
    with get_sync_db() as session:
        assert reads.bars_for(session, "NOSUCH", 30) == ()
        assert reads.latest_closed_session(session, "NOSUCH") is None
        assert reads.sessions_available(session, "NOSUCH") == 0
