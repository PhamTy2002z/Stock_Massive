"""What is true about a symbol right now, on four axes, with no verdict.

The question a reader asks is *có thể mua STB giá hiện tại không?* and this Study
deliberately does not answer it. What it answers is the question underneath:
**where does the price sit, what has the business earned, and which stated
conditions currently hold?** The reader concludes; the engine measures. That
split is the whole design, and three consequences of it are load-bearing.

**Every condition's wording is fixed in this file.** A checklist whose labels
were written by the model is a checklist the model can re-word to fit the
conclusion it already reached. So the labels are constants, the statuses are
arithmetic, and the model's whole freedom is which of them to narrate.

**Nothing here is a verdict, and the headline has no word for one.** There is no
score, no rating, no PREFERRED, no WAIT. ``conditions`` counts what held and what
did not, and a count is not a recommendation however it is read.

**Momentum is computed here rather than read from a Signal Field.** The three
figures a review of this kind wants — twelve-month return, drawdown from the
52-week high, RSI — all exist as registered Signal Fields, and every one of them
derives from ``provider_snapshots`` rows whose only source is FiinQuant, a
provider this deployment is not licensed to redistribute from. Drawing them
would put those numbers on a Signal Desk, which is precisely the provenance hole this
phase was written to close. All three are pure functions of a close series, and
``bar_daily`` holds an adjusted vnstock series — the correct input for all three,
since adjustment is exactly what one wants when measuring what holding the share
returned.

## The windows, and why each is fixed

``horizon_sessions`` is what the price line draws. Everything measured has its
own window, fixed in code, so the same symbol answers the same numbers whatever
horizon was asked for:

* the 52-week band is the last :data:`RANGE_SESSIONS` sessions, which is also
  what the twelve-month return is measured across;
* the concentration zone is the last :data:`ZONE_SESSIONS` sessions;
* RSI is taken over the last :data:`RSI_WINDOW_SESSIONS`, far enough past the
  Wilder average's convergence that the seed no longer shows, and fixed so the
  figure is not a function of the parameter the model happened to pass.

A window shorter than the 52-week band is refused rather than relabelled: every
condition here names "52 tuần" in text a reader will hold this system to.

## What the zone claims, and what it does not

"Vùng giá đóng cửa tập trung" is a twenty-bin histogram of the closes of the last
sixty sessions, and the zone is the adjacent pair of bins holding the most of
them. That is all it is. It is not support, not resistance, and not a level
anything is expected to bounce off — the algorithm is too simple to earn those
words, so the label does not use them and neither may the prose.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from src.stocks.signals.issues import SignalIssue

from . import reads_daily, reads_fundamental
from .contracts import (
    SignalDeskBlock,
    SignalDeskSpec,
    Frame,
    Provenance,
    StudyContext,
    StudyDefinition,
    StudyRefused,
    StudyResult,
)
from .registry import register

NAME = "entry_condition_review"
VERSION = 1

#: Sessions this system counts as 52 weeks. The market trades about 250 sessions
#: a year, and a session count rather than 364 calendar days because the band and
#: the twelve-month return are then measured over exactly the same bars — a
#: calendar cutoff makes them two windows that differ by whichever holidays fell
#: in the year.
RANGE_SESSIONS = 250

#: Below this the study refuses. The band, the return and every condition that
#: names "52 tuần" would otherwise be a claim about ten months labelled as a
#: year, which is worse than no answer.
MIN_SESSIONS = RANGE_SESSIONS

HORIZON_FLOOR = RANGE_SESSIONS
HORIZON_CEILING = 500

#: The recent window the concentration zone is drawn from, and how finely it is
#: cut. Sixty sessions is about a quarter — long enough to hold a range and short
#: enough that it is still *recent* structure; twenty bins over that range puts
#: three sessions in an average bin, so a pair of bins standing out is a pair a
#: reader can see on the strip.
ZONE_SESSIONS = 60
ZONE_BINS = 20

#: How many adjacent bins the zone spans. Two, so the zone is a band rather than
#: a single price: the histogram's bin edges are an artefact of the window's own
#: high and low, and a one-bin answer would move whenever the sixtieth session
#: rolled off.
ZONE_BAND_BINS = 2

RSI_PERIOD = 14

#: Sessions the RSI is taken over. Wilder's average is recursive with no closed
#: form, so its value depends on where the walk started; a hundred sessions is
#: roughly seven times the period, by which point the seed has decayed out of the
#: figure. Fixed rather than following ``horizon_sessions`` so that two runs of
#: this Study on one symbol cannot disagree about its RSI.
RSI_WINDOW_SESSIONS = 100

#: The two thresholds the conditions test against. Both are stated in the labels
#: a reader sees, because a checklist whose thresholds are implicit is a
#: checklist nobody can disagree with.
NEAR_HIGH_PCT = 5.0
RSI_OVERBOUGHT = 70.0

Status = Literal["met", "not_met", "unknown"]
EarningsTrend = Literal["improving", "deteriorating", "mixed", "unknown"]

#: The condition wording, fixed here and nowhere else. Each one is a statement
#: about a measurement, in the indicative: no imperative verb, no price tied to
#: an action, nothing a reader could read as an instruction.
LABEL_OFF_HIGH = "Giá đóng cửa còn cách đỉnh 52 tuần trên 5%"
LABEL_RSI = "RSI 14 phiên dưới ngưỡng quá mua 70"
LABEL_RETURN_12M = "Lợi nhuận nắm giữ 12 tháng dương"
LABEL_IN_ZONE = "Giá đóng cửa nằm trong vùng giá đóng cửa tập trung 60 phiên"
LABEL_PROFIT_POSITIVE = "Lợi nhuận quý gần nhất dương"
LABEL_PROFIT_IMPROVED = "Lợi nhuận quý gần nhất cao hơn cùng kỳ năm trước"

#: The note under the checklist. Fixed prose, describing what the panel measured
#: and what it does not know — the shape a brokerage disclosure takes, without a
#: single "nên" or "hãy" in it.
CHECKLIST_NOTE = (
    "Bảng điều kiện mô tả trạng thái dữ liệu tại phiên đã đóng gần nhất: mỗi "
    "dòng nêu một mức đo được và ngưỡng nó được so với. Các mức này thay đổi "
    "theo từng phiên, và bảng không xét mục tiêu, kỳ hạn hay khả năng chịu lỗ "
    "của người đọc."
)

_STATUS_LABELS: Mapping[Status, str] = {
    "met": "Đạt",
    "not_met": "Chưa đạt",
    "unknown": "Chưa rõ",
}


class ConditionReviewParams(BaseModel):
    """What the model fills in.

    ``horizon_sessions`` clamps rather than refuses, like every other Study's
    window: a model asking for five years has asked a sensible question with an
    unusable number, and an honest ``sessionsUsed`` says more than a round trip
    spent on the maximum. The floor is the 52-week band itself — the horizon is
    what the line draws, and a line shorter than the band it is drawn against
    would leave the band's edges off the picture.
    """

    symbol: str = Field(description="Mã chứng khoán, vd STB")
    horizon_sessions: int = Field(
        default=RANGE_SESSIONS,
        description=(
            f"Số phiên đã đóng vẽ trên đường giá, {HORIZON_FLOOR}–"
            f"{HORIZON_CEILING}; ngoài khoảng sẽ được kẹp về biên. Dải 52 tuần, "
            "vùng tích luỹ và RSI luôn tính trên cửa sổ riêng của chúng."
        ),
    )

    @field_validator("symbol")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("horizon_sessions")
    @classmethod
    def _clamp(cls, value: int) -> int:
        return max(HORIZON_FLOOR, min(HORIZON_CEILING, value))


@dataclass(frozen=True)
class _Zone:
    """The adjacent bins holding the most closes, and how many that was.

    ``window`` is how many closes the histogram saw, so "22 of 60 sessions" is a
    fraction of what was measured rather than of what was hoped for.
    """

    low: float
    high: float
    sessions: int
    window: int


@dataclass(frozen=True)
class _QuarterReading:
    """One quarter as the earnings axis reads it."""

    period_end: date
    label: str
    net_profit_vnd: float | None
    yoy_pct: float | None
    improved: bool | None


@dataclass(frozen=True)
class _Condition:
    """One row of the checklist: a fixed sentence and a computed status.

    ``value`` and ``unit`` are the measurement behind the status, kept as a
    number rather than a formatted string so the browser formats it the way it
    formats every other number on the panel. ``evidence_ref`` names the frame
    that holds it, which is what makes a row checkable rather than merely
    stated.
    """

    label: str
    status: Status
    value: float | None
    unit: str | None
    evidence_ref: str


def compute(context: StudyContext) -> StudyResult:
    """Measure the four axes and score the fixed conditions against them."""
    params = context.params
    assert isinstance(params, ConditionReviewParams)

    bars = reads_daily.bars_for(
        context.session,
        params.symbol,
        params.horizon_sessions,
        now=context.as_of,
    )
    if len(bars) < MIN_SESSIONS:
        raise StudyRefused(
            SignalIssue.INSUFFICIENT_SESSIONS,
            f"{len(bars)} closed daily sessions stored for {params.symbol}, "
            f"{MIN_SESSIONS} needed for a 52-week review",
        )

    bases = {bar.price_basis for bar in bars}
    if len(bases) > 1:
        # Every row written today is ``adjusted_at_source``, so this is a guard
        # rather than a branch anybody has seen. It is here because the three
        # figures below — the band, the return, the drawdown — are the ones a
        # mixed window breaks silently: a pre-split price beside a post-split one
        # makes a 52-week high nobody traded at.
        raise StudyRefused(
            SignalIssue.MIXED_PRICE_BASIS,
            f"the stored window for {params.symbol} mixes price bases "
            f"({', '.join(sorted(bases))}), which cannot be compared",
        )

    closes = [float(bar.close) for bar in bars]
    year = bars[-RANGE_SESSIONS:]
    last = closes[-1]
    high_52w = max(float(bar.high) for bar in year)
    low_52w = min(float(bar.low) for bar in year)
    percentile = _position_in_range(last, low_52w, high_52w)
    drawdown_pct = (last - high_52w) / high_52w * 100 if high_52w > 0 else 0.0
    first_of_year = float(year[0].close)
    return_12m_pct = (
        (last / first_of_year - 1) * 100 if first_of_year > 0 else None
    )
    rsi_14 = _rsi(closes[-RSI_WINDOW_SESSIONS:])
    zone = _concentration_zone(closes[-ZONE_SESSIONS:])

    quarters = _read_quarters(context.session, params.symbol)
    trend = _earnings_trend(quarters)
    latest = quarters[-1] if quarters else None

    conditions = _conditions(
        drawdown_pct=drawdown_pct,
        rsi_14=rsi_14,
        return_12m_pct=return_12m_pct,
        last=last,
        zone=zone,
        latest=latest,
    )
    tally = _tally(conditions)

    headline = {
        "symbol": params.symbol,
        "asOfSession": bars[-1].trading_day.isoformat(),
        "sessionsUsed": len(bars),
        "pricePosition": {
            "last": _price(last),
            "high52w": _price(high_52w),
            "low52w": _price(low_52w),
            "percentile": _pct(percentile),
            "offHighPct": _pct(drawdown_pct),
            "return12mPct": _pct(return_12m_pct),
            "rsi14": _pct(rsi_14),
            "closeCluster": {
                "low": _price(zone.low),
                "high": _price(zone.high),
                "sessions": f"{zone.sessions}/{zone.window}",
            },
        },
        "earningsTrend": trend,
        "latestQuarter": (
            None
            if latest is None
            else {
                "period": latest.label,
                "netProfitVnd": latest.net_profit_vnd,
                "yoyPct": _pct(latest.yoy_pct),
            }
        ),
        # Counts first, because a count is the whole of what this Study concludes.
        # The items travel with them because the model is asked to narrate which
        # conditions hold, and a model handed three integers would have to invent
        # the sentences — these are the fixed ones.
        "conditions": {
            **tally,
            "items": [
                {"label": item.label, "status": item.status} for item in conditions
            ],
        },
    }

    degraded = _degradations(len(bars), params.horizon_sessions, trend)
    return StudyResult(
        headline=headline,
        frames={
            "tiles": _tiles_frame(last, percentile, return_12m_pct, drawdown_pct, rsi_14),
            "range_band": _range_frame(low_52w, high_52w, last, percentile, zone),
            "price_context": _price_frame(bars),
            "earnings_quarters": _earnings_frame(quarters),
            "conditions": _conditions_frame(conditions),
        },
        provenance=Provenance(
            source="vnstock",
            as_of=context.as_of,
            sessions_used=len(bars),
            health="normal" if not degraded else "degraded",
            reason="; ".join(degraded) or None,
        ),
    )


# -- the four axes ---------------------------------------------------------


def _position_in_range(last: float, low: float, high: float) -> float:
    """Where the last close sits between the 52-week low and high, in percent.

    A zero-width range answers 100: the price is at the high, which is also the
    low, and the alternative — a null — would make every condition downstream
    unknown for a symbol that traded at one price all year.
    """
    span = high - low
    if span <= 0:
        return 100.0
    return (last - low) / span * 100


def _rsi(closes: Sequence[float], period: int = RSI_PERIOD) -> float | None:
    """Wilder's RSI over a close series, or ``None`` when it is undefined.

    The seed is the simple mean of the first ``period`` changes and every step
    after it is Wilder's smoothing — the original definition, and the one every
    platform a reader might compare against implements.

    A window with no down move answers 100. A window with no move at all answers
    ``None`` rather than 50: fifty is the midpoint of a scale of *relative*
    strength, and a series that never moved has no relative strength to report.
    """
    if len(closes) < period + 1:
        return None
    changes = [later - earlier for earlier, later in zip(closes, closes[1:])]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]

    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        average_gain = (average_gain * (period - 1) + gain) / period
        average_loss = (average_loss * (period - 1) + loss) / period

    if average_loss == 0:
        return None if average_gain == 0 else 100.0
    return 100.0 - 100.0 / (1.0 + average_gain / average_loss)


def _concentration_zone(closes: Sequence[float]) -> _Zone:
    """The adjacent pair of histogram bins holding the most closes.

    Ties go to the lower pair. Not a preference for cheap prices — it is the
    only tie-break that does not make the answer a fact about iteration order,
    and a zone that moved between two runs over identical data would be the one
    thing a "recomputed every run" claim cannot survive.

    The top bin includes the window's high, so the highest close lands in a bin
    rather than one past the last edge.
    """
    low, high = min(closes), max(closes)
    if high <= low:
        return _Zone(low=low, high=high, sessions=len(closes), window=len(closes))

    width = (high - low) / ZONE_BINS
    counts = [0] * ZONE_BINS
    for close in closes:
        index = min(int((close - low) / width), ZONE_BINS - 1)
        counts[index] += 1

    pairs = range(ZONE_BINS - ZONE_BAND_BINS + 1)
    best = max(pairs, key=lambda start: (sum(counts[start : start + ZONE_BAND_BINS]), -start))
    inside = sum(counts[best : best + ZONE_BAND_BINS])
    return _Zone(
        low=low + best * width,
        high=low + (best + ZONE_BAND_BINS) * width,
        sessions=inside,
        window=len(closes),
    )


def _read_quarters(session: Session, symbol: str) -> tuple[_QuarterReading, ...]:
    """The stored quarters, each with its year-on-year reading where there is one.

    ``yoy_pct`` needs a positive base: the percentage change from a loss is a
    number a reader cannot use, and printing one is how a swing from -100 to +50
    becomes "up 150%". ``improved`` is the sign of the change, which is defined
    whatever the two signs are, and it is what the trend is classified on.
    """
    quarters = reads_fundamental.quarters_for(session, symbol)
    readings = []
    for index, quarter in enumerate(quarters):
        prior = quarters[index - 4] if index >= 4 else None
        current_profit = quarter.net_profit_vnd
        prior_profit = prior.net_profit_vnd if prior is not None else None
        improved = (
            None
            if current_profit is None or prior_profit is None
            else current_profit > prior_profit
        )
        yoy_pct = (
            (current_profit / prior_profit - 1) * 100
            if current_profit is not None
            and prior_profit is not None
            and prior_profit > 0
            else None
        )
        readings.append(
            _QuarterReading(
                period_end=quarter.period_end,
                label=_quarter_label(quarter.period_end),
                net_profit_vnd=current_profit,
                yoy_pct=yoy_pct,
                improved=improved,
            )
        )
    return tuple(readings)


def _earnings_trend(quarters: Sequence[_QuarterReading]) -> EarningsTrend:
    """Four year-on-year readings, or ``unknown`` — never a partial verdict.

    Fewer than :data:`reads_fundamental.QUARTERS` stored quarters means fewer
    than four comparable pairs, and three quarters of a trend read as a trend
    while being a different claim. Roughly a thousand symbols in this store hold
    exactly one quarter, so this branch is the ordinary case rather than the
    edge, and it answers ``unknown`` while the rest of the study still answers.
    """
    recent = [quarter.improved for quarter in quarters[-4:]]
    if len(recent) < 4 or any(flag is None for flag in recent):
        return "unknown"
    if all(recent):
        return "improving"
    if not any(recent):
        return "deteriorating"
    return "mixed"


# -- the checklist ---------------------------------------------------------


def _conditions(
    *,
    drawdown_pct: float,
    rsi_14: float | None,
    return_12m_pct: float | None,
    last: float,
    zone: _Zone,
    latest: _QuarterReading | None,
) -> tuple[_Condition, ...]:
    """Six statements, in the order a reader meets the axes on the signal_desk.

    Every status is a comparison; none of them is a judgement. A missing input
    is ``unknown`` and never ``not_met`` — those are different claims, and the
    second one would make a company that has not filed look like a company whose
    profit fell.
    """
    latest_profit = latest.net_profit_vnd if latest is not None else None
    return (
        _Condition(
            label=LABEL_OFF_HIGH,
            status=_status(drawdown_pct <= -NEAR_HIGH_PCT),
            value=_pct(drawdown_pct),
            unit="%",
            evidence_ref="range_band",
        ),
        _Condition(
            label=LABEL_IN_ZONE,
            status=_status(zone.low <= last <= zone.high),
            value=_price(last),
            unit="đ",
            evidence_ref="range_band",
        ),
        _Condition(
            label=LABEL_RETURN_12M,
            status=_status(None if return_12m_pct is None else return_12m_pct > 0),
            value=_pct(return_12m_pct),
            unit="%",
            evidence_ref="price_context",
        ),
        _Condition(
            label=LABEL_RSI,
            status=_status(None if rsi_14 is None else rsi_14 < RSI_OVERBOUGHT),
            value=_pct(rsi_14),
            unit=None,
            evidence_ref="tiles",
        ),
        _Condition(
            label=LABEL_PROFIT_POSITIVE,
            status=_status(None if latest_profit is None else latest_profit > 0),
            value=latest_profit,
            unit="VND",
            evidence_ref="earnings_quarters",
        ),
        _Condition(
            label=LABEL_PROFIT_IMPROVED,
            status=_status(latest.improved if latest is not None else None),
            value=_pct(latest.yoy_pct) if latest is not None else None,
            unit="%",
            evidence_ref="earnings_quarters",
        ),
    )


def _status(held: bool | None) -> Status:
    if held is None:
        return "unknown"
    return "met" if held else "not_met"


def _tally(conditions: Sequence[_Condition]) -> dict[str, int]:
    return {
        "met": sum(1 for item in conditions if item.status == "met"),
        "notMet": sum(1 for item in conditions if item.status == "not_met"),
        "unknown": sum(1 for item in conditions if item.status == "unknown"),
    }


def _degradations(
    sessions_used: int, asked_for: int, trend: EarningsTrend
) -> list[str]:
    """Why the panel is thinner than it could be, in the reader's terms.

    The earnings axis counts: a review missing one of its four axes is not a
    healthy review, and a strip that said ``normal`` would leave the reader to
    notice the empty block for themselves.
    """
    reasons = []
    if sessions_used < asked_for:
        reasons.append(f"store holds {sessions_used} of {asked_for} sessions")
    if trend == "unknown":
        reasons.append(
            "the earnings axis is unknown: fewer than "
            f"{reads_fundamental.QUARTERS} comparable quarters stored"
        )
    return reasons


# -- frames ----------------------------------------------------------------


def _tiles_frame(
    last: float,
    percentile: float,
    return_12m_pct: float | None,
    drawdown_pct: float,
    rsi_14: float | None,
) -> Frame:
    return Frame(
        kind="table",
        columns=("label", "value", "unit"),
        rows=(
            ("Giá đóng cửa gần nhất", _price(last), "đ"),
            ("Vị thế trong dải 52 tuần", _pct(percentile), "%"),
            ("Lợi nhuận 12 tháng", _pct(return_12m_pct), "%"),
            ("Cách đỉnh 52 tuần", _pct(drawdown_pct), "%"),
            ("RSI 14 phiên", _pct(rsi_14), None),
        ),
        unit=None,
        labels={"label": "Chỉ số", "value": "Giá trị", "unit": "Đơn vị"},
    )


def _range_frame(
    low: float, high: float, last: float, percentile: float, zone: _Zone
) -> Frame:
    """The band, the marker and the cluster — one row, because it is one picture."""
    return Frame(
        kind="table",
        columns=("low", "high", "current", "percentile", "zone_low", "zone_high"),
        rows=(
            (
                _price(low),
                _price(high),
                _price(last),
                _pct(percentile),
                _price(zone.low),
                _price(zone.high),
            ),
        ),
        unit="VND",
        labels={
            "low": "Đáy 52 tuần",
            "high": "Đỉnh 52 tuần",
            "current": "Giá đóng cửa gần nhất",
            "percentile": "Vị thế trong dải (%)",
            "zone_low": "Đáy vùng giá đóng cửa tập trung",
            "zone_high": "Đỉnh vùng giá đóng cửa tập trung",
        },
    )


def _price_frame(bars: Sequence[reads_daily.DailyBar]) -> Frame:
    return Frame(
        kind="series",
        columns=("session", "close"),
        rows=tuple(
            (bar.trading_day.isoformat(), _price(float(bar.close))) for bar in bars
        ),
        unit="VND",
        labels={"session": "Phiên", "close": "Giá đóng cửa"},
    )


def _earnings_frame(quarters: Sequence[_QuarterReading]) -> Frame:
    """Eight quarters, with the year-on-year reading on the four that have one.

    Empty when nothing is stored, rather than absent: the block still draws, and
    a reader sees an earnings axis with no bars in it — which is the honest
    picture of a company this store has not collected.
    """
    return Frame(
        kind="series",
        columns=("quarter", "net_profit_vnd", "yoy_pct"),
        rows=tuple(
            (quarter.label, quarter.net_profit_vnd, _pct(quarter.yoy_pct))
            for quarter in quarters
        ),
        unit="VND",
        labels={
            "quarter": "Quý",
            "net_profit_vnd": "Lợi nhuận sau thuế",
            "yoy_pct": "So cùng kỳ (%)",
        },
    )


def _conditions_frame(conditions: Sequence[_Condition]) -> Frame:
    return Frame(
        kind="table",
        columns=("label", "status", "status_text", "value", "unit", "evidence"),
        rows=tuple(
            (
                item.label,
                item.status,
                _STATUS_LABELS[item.status],
                item.value,
                item.unit,
                item.evidence_ref,
            )
            for item in conditions
        ),
        unit=None,
        labels={
            "label": "Điều kiện",
            "status": "Mã trạng thái",
            "status_text": "Trạng thái",
            "value": "Mức đo được",
            "unit": "Đơn vị",
            "evidence": "Khối dữ liệu",
        },
    )


def view(result: StudyResult) -> SignalDeskSpec:
    """Five blocks: the numbers, the band, the path, the quarters, the checklist.

    The checklist is last on purpose. It is the block a reader will look at
    first and the one that means least without the four measurements above it,
    and putting it at the top would invite reading six ticks as a verdict.
    """
    symbol = result.headline["symbol"]
    return SignalDeskSpec(
        title=f"Điều kiện hiện tại — {symbol}",
        blocks=(
            SignalDeskBlock(
                widget="stat_tiles",
                widget_version=1,
                frame="tiles",
                options={"label": "label", "value": "value", "unit": "unit"},
            ),
            SignalDeskBlock(
                widget="range_strip",
                widget_version=1,
                frame="range_band",
                options={
                    "low": "low",
                    "high": "high",
                    "current": "current",
                    "percentile": "percentile",
                    "bandLow": "zone_low",
                    "bandHigh": "zone_high",
                    "bandLabel": "Vùng giá đóng cửa tập trung 60 phiên",
                },
            ),
            SignalDeskBlock(
                widget="line_series",
                widget_version=1,
                frame="price_context",
                options={"x": "session", "y": "close"},
            ),
            SignalDeskBlock(
                widget="bar_series",
                widget_version=1,
                frame="earnings_quarters",
                options={"x": "quarter", "y": "net_profit_vnd"},
            ),
            SignalDeskBlock(
                widget="condition_checklist",
                widget_version=1,
                frame="conditions",
                options={
                    "label": "label",
                    "status": "status",
                    "value": "value",
                    "unit": "unit",
                    "evidence": "evidence",
                    "note": CHECKLIST_NOTE,
                },
            ),
        ),
    )


# -- readings a person will see -------------------------------------------


def _quarter_label(period_end: date) -> str:
    return f"Q{(period_end.month - 1) // 3 + 1}/{period_end.year}"


def _price(value: float | None) -> float | None:
    """A price at the width a share is quoted in: whole dong."""
    if value is None:
        return None
    return float(Decimal(str(value)).quantize(Decimal("1")))


def _pct(value: float | None) -> float | None:
    """A rate at two decimals, which is more precision than any of them earns."""
    if value is None:
        return None
    return round(value, 2)


DEFINITION = register(
    StudyDefinition(
        name=NAME,
        version=VERSION,
        question=(
            "Giá một mã đang ở đâu trong dải 52 tuần, lợi nhuận quý đang đi "
            "theo hướng nào, và những điều kiện nào đang đạt hay chưa đạt?"
        ),
        display_name="Điều kiện hiện tại",
        params_model=ConditionReviewParams,
        # Nothing to warm: this Study reads the daily bars the market-wide
        # backfill writes and the quarters the collector already stored, so a
        # question never waits on a provider. A symbol the backfill has not
        # reached refuses, naming the store rather than the company.
        requires=(),
        frames=(
            "tiles",
            "range_band",
            "price_context",
            "earnings_quarters",
            "conditions",
        ),
        widgets=(
            ("stat_tiles", 1),
            ("range_strip", 1),
            ("line_series", 1),
            ("bar_series", 1),
            ("condition_checklist", 1),
        ),
        compute=compute,
        view=view,
    )
)


__all__ = [
    "CHECKLIST_NOTE",
    "DEFINITION",
    "HORIZON_CEILING",
    "HORIZON_FLOOR",
    "MIN_SESSIONS",
    "NAME",
    "RANGE_SESSIONS",
    "RSI_PERIOD",
    "RSI_WINDOW_SESSIONS",
    "VERSION",
    "ZONE_BINS",
    "ZONE_SESSIONS",
    "ConditionReviewParams",
    "compute",
    "view",
]
