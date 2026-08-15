"""Classic technical vocabulary over a prepared window of bars."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .bars import BarFrame
from .fields import FieldReading
from .issues import SignalIssue

RSI_PERIOD = 14
RSI_MIN_SESSIONS = RSI_PERIOD + 1
MACD_FAST_PERIOD = 12
MACD_SLOW_PERIOD = 26
MACD_MIN_SESSIONS = MACD_SLOW_PERIOD
BOLLINGER_PERIOD = 20
BOLLINGER_MIN_SESSIONS = BOLLINGER_PERIOD
BOLLINGER_STANDARD_DEVIATIONS = 2.0
KELLY_EDGE_SENSITIVITY = 0.50


@dataclass(frozen=True)
class FractionalKellySizing:
    """Long-only capital fractions from inputs supplied by the caller.

    The full-Kelly number is deliberately named only as a ceiling. The two
    usable answers stop at half Kelly, and the sensitivity range repeats the
    half-Kelly arithmetic after moving the dominant input — the mean edge — by
    plus or minus fifty percent.
    """

    edge_input: float
    variance_input: float
    quarter_kelly: float
    half_kelly: float
    full_kelly_ceiling: float
    input_sensitivity_range: tuple[float, float]


def rsi_reading(frame: BarFrame) -> FieldReading:
    closes = [bar.close for bar in frame.bars if bar.close is not None]
    if len(closes) < RSI_MIN_SESSIONS:
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


def macd_reading(frame: BarFrame) -> FieldReading:
    closes = [bar.close for bar in frame.bars if bar.close is not None]
    if len(closes) < MACD_MIN_SESSIONS:
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


def bollinger_percent_b_reading(frame: BarFrame) -> FieldReading:
    closes = [bar.close for bar in frame.bars if bar.close is not None]
    if len(closes) < BOLLINGER_MIN_SESSIONS:
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


def fractional_kelly_sizing(*, edge: float, variance: float) -> FractionalKellySizing:
    """Size from caller-owned estimates; this function has no market-data input."""
    if not math.isfinite(edge) or edge < 0.0:
        raise ValueError("edge must be a finite non-negative caller estimate")
    if not math.isfinite(variance) or variance <= 0.0:
        raise ValueError("variance must be a finite positive caller estimate")
    full_kelly_ceiling = edge / variance
    quarter_kelly = 0.25 * full_kelly_ceiling
    half_kelly = 0.50 * full_kelly_ceiling
    sensitivity = (
        0.50 * (edge * (1.0 - KELLY_EDGE_SENSITIVITY) / variance),
        0.50 * (edge * (1.0 + KELLY_EDGE_SENSITIVITY) / variance),
    )
    return FractionalKellySizing(
        edge_input=edge,
        variance_input=variance,
        quarter_kelly=quarter_kelly,
        half_kelly=half_kelly,
        full_kelly_ceiling=full_kelly_ceiling,
        input_sensitivity_range=sensitivity,
    )
