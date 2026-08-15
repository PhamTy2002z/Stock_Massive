"""Classic indicators as descriptive market vocabulary."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.stocks.models import CorporateAction, ListingRoster, ProviderSnapshot
from src.stocks.providers import Exchange
from src.stocks.signals.bars import Bar, BarFrame
from src.stocks.signals.fields import Claim, FieldKind, Sign, Unit
from src.stocks.signals.indicators import (
    INDICATOR_WARMUP_SESSIONS,
    bollinger_percent_b_reading,
    macd_reading,
    rsi_reading,
)
from src.stocks.signals.issues import SignalIssue
from src.stocks.signals.price_band import LimitLock
from src.stocks.signals.registry import (
    BOLLINGER_PERCENT_B,
    MACD,
    RSI,
)
from src.stocks.signals.serving import serve_field

from .test_price_band import list_on, write_session


def frame_of(closes: list[float]) -> BarFrame:
    first = date(2025, 1, 2)
    bars = tuple(
        Bar(
            session_date=first + timedelta(days=index),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1_000_000,
            total_value_vnd=None,
            adjustment_factor=Decimal(1),
            limit_lock=LimitLock.NONE,
        )
        for index, close in enumerate(closes)
    )
    return BarFrame(symbol="AAA", bars=bars)


def open_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (
        ProviderSnapshot.__table__,
        ListingRoster.__table__,
        CorporateAction.__table__,
    ):
        table.create(engine)
    return Session(engine)


def store_indicator_history(session: Session, sessions: int = 105) -> list[date]:
    list_on(session, "AAA", Exchange.HOSE)
    days: list[date] = []
    cursor = date(2025, 1, 2)
    while len(days) < sessions:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    close = 20_000.0
    for index, day in enumerate(days):
        next_close = close * (1.006 if index % 3 else 0.996)
        write_session(
            session,
            "AAA",
            day,
            open_price=close,
            high=max(close, next_close) * 1.005,
            low=min(close, next_close) * 0.995,
            close=next_close,
        )
        close = next_close
    return days


def test_the_indicator_pack_is_registered_as_vocabulary_not_as_signals():
    fields = (RSI, MACD, BOLLINGER_PERCENT_B)

    assert [field.name for field in fields] == [
        "indicator_pack.rsi_14",
        "indicator_pack.macd_12_26_vnd",
        "indicator_pack.bollinger_percent_b_20",
    ]
    assert [field.unit for field in fields] == [
        Unit.INDEX_0_100,
        Unit.VND,
        Unit.RATIO,
    ]
    assert [field.sign for field in fields] == [
        Sign.NON_NEGATIVE,
        Sign.SIGNED,
        Sign.SIGNED,
    ]
    assert all(field.kind is FieldKind.VOCABULARY for field in fields)
    assert all(field.claim is Claim.DESCRIPTIVE for field in fields)
    assert all(field.threshold is None for field in fields)
    assert all(field.null_fpr is None for field in fields)
    assert all("no out-of-sample edge is claimed" in field.interpretation for field in fields)


def test_recursive_indicators_load_a_warmup_before_their_named_period():
    assert RSI.min_sessions == INDICATOR_WARMUP_SESSIONS
    assert MACD.min_sessions == INDICATOR_WARMUP_SESSIONS
    assert INDICATOR_WARMUP_SESSIONS > 26


def test_rsi_uses_wilders_fourteen_session_definition():
    # Wilder's published worksheet example; the independently worked result is
    # 70.464 after the first fourteen price changes.
    closes = [
        44.34,
        44.09,
        44.15,
        43.61,
        44.33,
        44.83,
        45.10,
        45.42,
        45.84,
        46.08,
        45.89,
        46.03,
        45.61,
        46.28,
        46.28,
    ]

    reading = rsi_reading(frame_of(closes))

    assert reading.value == pytest.approx(70.464135, rel=1e-6)
    assert reading.extras == {"period": 14, "sessions": 15}


def test_macd_is_the_twelve_session_ema_less_the_twenty_six_session_ema():
    # Twenty-five closes at 100 seed both EMAs there. A final close at 112
    # moves the fast EMA by 24/13 and the slow one by 6/13, leaving 18/13.
    reading = macd_reading(frame_of([100.0] * 25 + [112.0]))

    assert reading.value == pytest.approx(18.0 / 13.0)
    assert reading.extras == {
        "fast_period": 12,
        "slow_period": 26,
        "sessions": 26,
    }


def test_bollinger_percent_b_is_the_fraction_from_lower_to_upper_band():
    # For closes 1..20 the population variance is 33.25. With two standard
    # deviations on either side, the last close sits at this worked fraction.
    reading = bollinger_percent_b_reading(
        frame_of([float(value) for value in range(1, 21)])
    )

    assert reading.value == pytest.approx(0.9118772355)
    assert reading.extras == {
        "period": 20,
        "standard_deviations": 2.0,
        "sessions": 20,
    }


def test_bollinger_percent_b_is_masked_when_the_band_has_no_width():
    reading = bollinger_percent_b_reading(frame_of([20_000.0] * 20))

    assert reading.value is None
    assert reading.refusal is SignalIssue.ZERO_RANGE_SESSION


@pytest.mark.parametrize("field", [RSI, MACD, BOLLINGER_PERCENT_B])
def test_each_indicator_is_served_with_the_health_of_its_prepared_window(field):
    with open_session() as session:
        days = store_indicator_history(session)
        answer = serve_field(session, "AAA", field, end=days[-1])

    assert answer.value is not None
    assert answer.refusal is None
    assert answer.health.sessions_used == field.min_sessions
    assert answer.health.refusal is None
