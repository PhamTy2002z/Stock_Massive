"""The daily reader: the right sessions, in the right order, of the right series.

Every case here is a way the read can be wrong while returning rows, which is
the only failure mode worth a test: a window that silently starts one session
late, a series that silently mixes points with dong, an order that silently
inverts every return computed on top of it.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import delete

from src.core.database import Base, get_sync_db, sync_engine
from src.stocks.models import BarDaily
from src.stocks.providers.normalize import VN_TZ
from src.studies import reads_daily

from . import condition_fixture as fixture

SYMBOL = fixture.SYMBOL
INDEX = "TSTZX"


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture
def store():
    """The window in the store, and a session to read it through."""
    with get_sync_db() as session:
        fixture.load_bars(session)

    with get_sync_db() as session:
        yield session

    with get_sync_db() as session:
        fixture.clear_bars(session)
        session.execute(delete(BarDaily).where(BarDaily.symbol == INDEX))


def test_the_window_is_the_newest_sessions_and_walks_forward(store):
    bars = reads_daily.bars_for(store, SYMBOL, 30, now=fixture.AS_OF)

    assert len(bars) == 30
    assert bars[-1].trading_day == fixture.LAST_SESSION
    assert [bar.trading_day for bar in bars] == sorted(
        bar.trading_day for bar in bars
    )
    assert [float(bar.close) for bar in bars] == [
        float(close) for close in fixture.closes()[-30:]
    ]
    assert bars[-1].price_basis == fixture.PRICE_BASIS


def test_a_window_wider_than_the_store_comes_back_short_rather_than_padded(store):
    bars = reads_daily.bars_for(store, SYMBOL, 900, now=fixture.AS_OF)

    # Deciding what a short window means belongs to the Study, so the reader
    # hands back what exists and says nothing about it.
    assert len(bars) == fixture.TOTAL_SESSIONS


def test_the_last_session_is_excluded_until_it_has_settled(store):
    trading = datetime(2026, 8, 21, 11, 0, tzinfo=VN_TZ)

    bars = reads_daily.bars_for(store, SYMBOL, 5, now=trading)

    # The ingest writes today's session while it is still trading, and a
    # 52-week high taken from it would change under the reader.
    assert bars[-1].trading_day == date(2026, 8, 20)
    assert (
        reads_daily.sessions_available(store, SYMBOL, now=trading)
        == fixture.TOTAL_SESSIONS - 1
    )


def test_the_index_series_is_read_by_asking_for_it_and_never_by_the_ticker(store):
    store.add(
        BarDaily(
            symbol=INDEX,
            trading_day=fixture.LAST_SESSION,
            series=reads_daily.SERIES_INDEX,
            open=1_800,
            high=1_820,
            low=1_790,
            close=1_811,
            volume=500_000_000,
            price_basis=fixture.PRICE_BASIS,
            source=fixture.SOURCE,
            observed_at=fixture.AS_OF,
        )
    )
    store.flush()

    points = reads_daily.bars_for(
        store, INDEX, 5, series=reads_daily.SERIES_INDEX, now=fixture.AS_OF
    )

    # One table, two scales. A read that trusted the ticker to imply the scale
    # would put 1.811 points in a window of 71.350đ closes.
    assert [float(bar.close) for bar in points] == [1_811.0]
    assert (
        reads_daily.bars_for(
            store, INDEX, 5, series=reads_daily.SERIES_EQUITY, now=fixture.AS_OF
        )
        == ()
    )


def test_an_empty_or_negative_window_reads_nothing_rather_than_everything(store):
    assert reads_daily.bars_for(store, SYMBOL, 0, now=fixture.AS_OF) == ()
    assert reads_daily.bars_for(store, SYMBOL, -5, now=fixture.AS_OF) == ()


def test_the_symbol_is_read_however_the_caller_spelled_it(store):
    bars = reads_daily.bars_for(store, " tstz ", 3, now=fixture.AS_OF)

    assert len(bars) == 3


def test_the_series_names_are_the_ones_the_writer_stores():
    """The two spellings, held equal to the module that writes them.

    ``reads_daily`` restates them rather than importing that module, which loads
    pandas and vnstock so that only the backfill job pays for them. A copy needs
    a check, and this is it.
    """
    from src.stocks.providers import vnstock_daily

    assert reads_daily.SERIES_EQUITY == vnstock_daily.SERIES_EQUITY
    assert reads_daily.SERIES_INDEX == vnstock_daily.SERIES_INDEX
