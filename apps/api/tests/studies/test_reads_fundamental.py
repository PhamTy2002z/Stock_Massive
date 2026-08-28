"""The quarterly reader: eight quarters, once each, and a null that stays a null.

Three of the four cases here are about a quarter appearing twice — a restatement,
a second schema version, a re-observation — because the store is append-only and
the way this read goes wrong is by drawing one quarter as two.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from src.core.database import Base, get_sync_db, sync_engine
from src.stocks.models import ProviderSnapshot
from src.stocks.providers.normalize import VN_TZ
from src.studies import reads_fundamental

from . import condition_fixture as fixture

SYMBOL = fixture.SYMBOL


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture
def store():
    with get_sync_db() as session:
        yield session
        fixture.clear_quarters(session, symbol=SYMBOL)


def test_the_newest_quarters_come_back_oldest_first(store):
    periods = fixture.load_quarters(store)
    store.flush()

    quarters = reads_fundamental.quarters_for(store, SYMBOL)

    assert [quarter.period_end for quarter in quarters] == periods
    assert [quarter.net_profit_vnd for quarter in quarters] == list(
        fixture.QUARTER_PROFITS_VND
    )


def test_only_the_asked_for_number_of_quarters_comes_back(store):
    fixture.load_quarters(store)
    store.flush()

    assert len(reads_fundamental.quarters_for(store, SYMBOL, 4)) == 4
    assert reads_fundamental.quarters_for(store, SYMBOL, 0) == ()
    # The four newest, not the four the index happened to reach first.
    assert reads_fundamental.quarters_for(store, SYMBOL, 4)[-1].period_end == date(
        2026, 6, 30
    )


def test_a_restated_quarter_is_one_quarter_and_the_newest_reading_of_it(store):
    fixture.load_quarters(store)
    period = date(2026, 6, 30)
    store.add(
        ProviderSnapshot(
            capability="fundamental",
            symbol=SYMBOL,
            source=fixture.SOURCE,
            effective_at=datetime(2026, 6, 30, tzinfo=VN_TZ),
            # A later reading of the same quarter, which is how a restatement
            # arrives in an append-only store.
            observed_at=fixture.AS_OF + timedelta(days=30),
            schema_version=2,
            payload=fixture.quarter_payload(SYMBOL, period, 2_000e9),
        )
    )
    store.flush()

    quarters = reads_fundamental.quarters_for(store, SYMBOL)

    assert len(quarters) == len(fixture.QUARTER_PROFITS_VND)
    assert quarters[-1].period_end == period
    assert quarters[-1].net_profit_vnd == 2_000e9


def test_the_parent_line_is_preferred_and_the_fallback_is_recorded(store):
    fixture.load_quarters(store, profits=(1_000e9, 1_100e9))
    # The newest quarter, restated with no parent line — ordinary for this
    # provider, and the case where the two lines stop being interchangeable.
    store.add(
        ProviderSnapshot(
            capability="fundamental",
            symbol=SYMBOL,
            source=fixture.SOURCE,
            effective_at=datetime(2026, 6, 30, tzinfo=VN_TZ),
            observed_at=fixture.AS_OF + timedelta(days=1),
            schema_version=2,
            payload=fixture.quarter_payload(
                SYMBOL, date(2026, 6, 30), 900e9, parent=False
            ),
        )
    )
    store.flush()

    quarters = reads_fundamental.quarters_for(store, SYMBOL)

    assert quarters[0].net_profit_line == "parent"
    assert quarters[1].net_profit_line == "consolidated"
    assert quarters[1].net_profit_vnd == 900e9


def test_a_quarter_with_neither_profit_line_reads_as_absent_and_not_as_zero(store):
    store.add(
        ProviderSnapshot(
            capability="fundamental",
            symbol=SYMBOL,
            source=fixture.SOURCE,
            effective_at=datetime(2026, 6, 30, tzinfo=VN_TZ),
            observed_at=fixture.AS_OF,
            schema_version=1,
            payload=fixture.quarter_payload(SYMBOL, date(2026, 6, 30), None),
        )
    )
    store.flush()

    quarter = reads_fundamental.quarters_for(store, SYMBOL)[0]

    assert quarter.net_profit_vnd is None
    assert quarter.net_profit_line is None


def test_a_symbol_nothing_has_filed_for_reads_as_nothing(store):
    assert reads_fundamental.quarters_for(store, "NOSUCHSYM") == ()
