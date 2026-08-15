"""Classic technical vocabulary over a prepared window of bars."""

from __future__ import annotations

import math

from .bars import BarFrame
from .fields import FieldReading, FieldWindow
from .issues import SignalIssue

RSI_PERIOD = 14
MACD_FAST_PERIOD = 12
MACD_SLOW_PERIOD = 26
# Wilder smoothing and an EMA are recursive: loading only the named period
# would seed them anew on every call. One hundred sessions leaves less than one
# percent of either seed in the answer while remaining inside the warm-up the
# signal store already maintains.
INDICATOR_WARMUP_SESSIONS = 100
RSI_MIN_SESSIONS = INDICATOR_WARMUP_SESSIONS
MACD_MIN_SESSIONS = INDICATOR_WARMUP_SESSIONS
BOLLINGER_PERIOD = 20
BOLLINGER_MIN_SESSIONS = BOLLINGER_PERIOD
BOLLINGER_STANDARD_DEVIATIONS = 2.0


def _closing_prices(frame: BarFrame, min_sessions: int) -> list[float] | None:
    closes = [bar.close for bar in frame.bars if bar.close is not None]
    return closes if len(closes) >= min_sessions else None


def rsi_reading(window: FieldWindow) -> FieldReading:
    closes = _closing_prices(window.frame, RSI_PERIOD + 1)
    if closes is None:
        return FieldReading(value=None, refusal=SignalIssue.INSUFFICIENT_HISTORY)

    changes = [current - previous for previous, current in zip(closes, closes[1:])]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    average_gain = sum(gains[:RSI_PERIOD]) / RSI_PERIOD
    average_loss = sum(losses[:RSI_PERIOD]) / RSI_PERIOD
    for gain, loss in zip(gains[RSI_PERIOD:], losses[RSI_PERIOD:]):
        average_gain = ((RSI_PERIOD - 1) * average_gain + gain) / RSI_PERIOD
        average_loss = ((RSI_PERIOD - 1) * average_loss + loss) / RSI_PERIOD

    if average_gain == 0.0 and average_loss == 0.0:
        value = 50.0
    elif average_loss == 0.0:
        value = 100.0
    else:
        value = 100.0 - 100.0 / (1.0 + average_gain / average_loss)
    return FieldReading(
        value=value,
        extras={"period": RSI_PERIOD, "sessions": len(closes)},
    )


def _ema(values: list[float], period: int) -> float:
    average = sum(values[:period]) / period
    weight = 2.0 / (period + 1.0)
    for value in values[period:]:
        average += weight * (value - average)
    return average


def macd_reading(window: FieldWindow) -> FieldReading:
    closes = _closing_prices(window.frame, MACD_SLOW_PERIOD)
    if closes is None:
        return FieldReading(value=None, refusal=SignalIssue.INSUFFICIENT_HISTORY)
    value = _ema(closes, MACD_FAST_PERIOD) - _ema(closes, MACD_SLOW_PERIOD)
    return FieldReading(
        value=value,
        extras={
            "fast_period": MACD_FAST_PERIOD,
            "slow_period": MACD_SLOW_PERIOD,
            "sessions": len(closes),
        },
    )


def bollinger_percent_b_reading(window: FieldWindow) -> FieldReading:
    closes = _closing_prices(window.frame, BOLLINGER_MIN_SESSIONS)
    if closes is None:
        return FieldReading(value=None, refusal=SignalIssue.INSUFFICIENT_HISTORY)
    window = closes[-BOLLINGER_PERIOD:]
    mean = sum(window) / BOLLINGER_PERIOD
    variance = sum((close - mean) ** 2 for close in window) / BOLLINGER_PERIOD
    standard_deviation = math.sqrt(variance)
    if math.isclose(
        standard_deviation,
        0.0,
        abs_tol=1e-12 * max(abs(mean), 1.0),
    ):
        return FieldReading(value=None, refusal=SignalIssue.ZERO_RANGE_SESSION)

    width = BOLLINGER_STANDARD_DEVIATIONS * standard_deviation
    value = (window[-1] - (mean - width)) / (2.0 * width)
    return FieldReading(
        value=value,
        extras={
            "period": BOLLINGER_PERIOD,
            "standard_deviations": BOLLINGER_STANDARD_DEVIATIONS,
            "sessions": len(window),
        },
    )
