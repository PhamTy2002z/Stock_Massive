"""Where a symbol's liquidity actually sits inside the session.

The question: *thanh khoản của mã này tập trung vào khung giờ nào trong N phiên
gần nhất?* Three numbers per bucket, and each one is there because the other two
can be read wrongly on their own:

**Average amount** is what the question sounds like it wants, and alone it is
mostly a picture of which sessions were busy. One session five times the size of
the others moves every bucket average it touches.

**Liquidity share** — the bucket's amount over that session's own total, averaged
across sessions — is the fix. A share is comparable between a quiet Tuesday and a
frantic Friday, which is what "tập trung vào khung giờ nào" is asking about.

**Spike frequency** — how often the bucket is among the session's top two —
separates a habit from an accident. Two extraordinary closes in thirty sessions
can hand ``14:45`` the highest average share while a reader who trades at 14:45
on an ordinary day finds nothing there. A share of 18% that happens 21 times out
of 30 is a different claim from a share of 18% that happens twice, and the two are
indistinguishable without this.

That is also why the heatmap is the hero picture rather than the bar chart: the
bar chart shows the average, and the heatmap shows whether the average is a habit.

## Missing buckets are holes, not zeroes

Real sessions are missing buckets — a HOSE symbol never has ``09:00`` at all, and
a quiet quarter hour is simply absent from the provider's answer. Those cells are
``None``, and the widget colours them as "no data". Writing 0 would be a
different and false claim: that the bucket existed and nobody traded in it. For
the same reason a session's shares are normalised over the buckets it actually
has, so they still sum to 1.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import time
from decimal import Decimal
from statistics import median
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.stocks.intraday import reads, session_window
from src.stocks.signals.issues import SignalIssue

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

NAME = "intraday_liquidity_profile"
VERSION = 1

#: Below this the picture is of a fortnight rather than of a habit, and the
#: refusal says so. A fixed floor rather than a share of the request: the
#: question is about repetition, and repetition needs a count.
MIN_SESSIONS = 10

SESSIONS_FLOOR = 10
SESSIONS_CEILING = 60

#: How many buckets of a session count as its peak for spike frequency. Two
#: rather than one because the closing auction takes the top slot on most
#: sessions of most symbols, and a definition that only ever names the winner
#: would answer "the close" for everything. Changing this changes what the number
#: means, so it ships as a new ``version`` rather than as an edit.
SPIKE_TOP_N = 2

Metric = Literal["volume", "value"]

_UNITS: Mapping[Metric, str] = {"volume": "shares", "value": "VND"}
_AMOUNT_LABELS: Mapping[Metric, str] = {
    "volume": "Khối lượng",
    "value": "Giá trị (VND)",
}
_PHASE_LABELS: Mapping[str, str] = {
    "ato": "Mở cửa (ATO)",
    "am": "Buổi sáng",
    "pm": "Buổi chiều",
    "atc": "Đóng cửa (ATC)",
}


class LiquidityParams(BaseModel):
    """What the model fills in.

    ``sessions`` clamps rather than refuses. A model that asks for a year of
    sessions has asked a sensible question with an unusable number, and one round
    trip spent on "60 is the maximum" buys nothing a clamp plus an honest
    ``sessionsUsed`` does not already say.
    """

    symbol: str = Field(description="Mã chứng khoán trong Universe, vd STB")
    sessions: int = Field(
        default=30,
        description=(
            f"Số phiên gần nhất đã đóng, {SESSIONS_FLOOR}–{SESSIONS_CEILING}; "
            "ngoài khoảng sẽ được kẹp về biên"
        ),
    )
    metric: Metric = Field(
        default="volume",
        description="volume = số cổ phiếu, value = giá trị tiền theo giá đóng bucket",
    )

    @field_validator("symbol")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("sessions")
    @classmethod
    def _clamp(cls, value: int) -> int:
        return max(SESSIONS_FLOOR, min(SESSIONS_CEILING, value))


def compute(context: StudyContext) -> StudyResult:
    params = context.params
    assert isinstance(params, LiquidityParams)

    if params.symbol not in context.universe:
        raise StudyRefused(
            SignalIssue.MISSING_TARGET_SESSION,
            f"{params.symbol} is not in the declared Universe",
        )

    bars = reads.bars_for(
        context.session, params.symbol, params.sessions, now=context.as_of
    )
    by_session = _group_by_session(bars, params.metric)
    if len(by_session) < MIN_SESSIONS:
        raise StudyRefused(
            SignalIssue.INSUFFICIENT_SESSIONS,
            f"{len(by_session)} closed sessions stored, {MIN_SESSIONS} needed",
        )

    buckets = _bucket_statistics(by_session)
    ranked = sorted(buckets, key=lambda item: item.avg_share, reverse=True)
    peak = ranked[0]
    sessions_used = len(by_session)

    headline = {
        "symbol": params.symbol,
        "sessionsUsed": sessions_used,
        "metric": params.metric,
        "peakWindow": peak.label,
        "peakAvgAmount": _round(peak.avg_amount),
        "peakShare": round(peak.avg_share, 4),
        "peakOccurrence": f"{peak.spike_sessions}/{sessions_used}",
        "top3": [
            {
                "window": item.label,
                "share": round(item.avg_share, 4),
                "avgAmount": _round(item.avg_amount),
                "occurrence": f"{item.spike_sessions}/{sessions_used}",
            }
            for item in ranked[:3]
        ],
        "phaseSummary": _phase_summary(buckets),
    }

    return StudyResult(
        headline=headline,
        frames={
            "tiles": _tiles_frame(peak, sessions_used, params.metric),
            "profile": _profile_frame(buckets, params.metric),
            "heatmap": _heatmap_frame(by_session),
            "ranking": _ranking_frame(ranked, params.metric),
        },
        provenance=Provenance(
            source="vnstock",
            as_of=context.as_of,
            sessions_used=sessions_used,
            health="normal" if sessions_used >= params.sessions else "degraded",
            reason=(
                None
                if sessions_used >= params.sessions
                else f"store holds {sessions_used} of {params.sessions} sessions"
            ),
        ),
    )


class _Bucket:
    """One column of the picture, across every session in the window."""

    __slots__ = ("label", "avg_amount", "median_amount", "avg_share", "spike_sessions")

    def __init__(
        self,
        label: str,
        avg_amount: float,
        median_amount: float,
        avg_share: float,
        spike_sessions: int,
    ) -> None:
        self.label = label
        self.avg_amount = avg_amount
        self.median_amount = median_amount
        self.avg_share = avg_share
        self.spike_sessions = spike_sessions


def _group_by_session(
    bars: Sequence[reads.Bar15m], metric: Metric
) -> dict[object, dict[str, float]]:
    """Amount per bucket label, per session, oldest session first."""
    grouped: dict[object, dict[str, float]] = {}
    for bar in bars:
        amount = float(bar.volume if metric == "volume" else bar.traded_value)
        grouped.setdefault(bar.trading_day, {})[bar.bucket_label] = amount
    return grouped


def _bucket_statistics(
    by_session: Mapping[object, Mapping[str, float]]
) -> list[_Bucket]:
    """Statistics for every bucket the window actually contains.

    A bucket present in **no** session is left out entirely: for a HOSE symbol
    ``09:00`` is not a quiet quarter hour, it is a quarter hour the exchange does
    not have, and a row of zeroes for it would be a finding about nothing. The
    heatmap keeps the full grid so the columns line up; this list does not.

    A bucket present in **some** sessions is a different thing, and every average
    here is taken over the whole window rather than over the sessions the bucket
    appeared in. That distinction is the correctness of the whole picture:
    dividing by appearances says a bucket that traded once in thirty sessions had
    a share of eighteen percent, and the four phases then sum to more than one.
    Absent means nothing traded in that quarter hour that day, which is a zero.
    """
    sessions = len(by_session)
    amounts: dict[str, list[float]] = {}
    shares: dict[str, list[float]] = {}
    spikes: dict[str, int] = {}

    for buckets in by_session.values():
        total = sum(buckets.values())
        for label in _spiking(buckets):
            spikes[label] = spikes.get(label, 0) + 1
        for label, amount in buckets.items():
            amounts.setdefault(label, []).append(amount)
            shares.setdefault(label, []).append(amount / total if total else 0.0)

    return [
        _Bucket(
            label=label,
            avg_amount=sum(amounts[label]) / sessions,
            # Padded to the window before the median is taken, for the same
            # reason the averages divide by it: the sessions this bucket is
            # missing from are sessions it was worth nothing in.
            median_amount=float(
                median(amounts[label] + [0.0] * (sessions - len(amounts[label])))
            ),
            avg_share=sum(shares[label]) / sessions,
            spike_sessions=spikes.get(label, 0),
        )
        for label in session_window.SESSION_BUCKET_LABELS
        if label in amounts
    ]


def _spiking(buckets: Mapping[str, float]) -> frozenset[str]:
    """Which buckets are *unambiguously* among this session's largest.

    Strictly greater than the largest amount that is not in the top
    :data:`SPIKE_TOP_N`, which is the only tie-break that means anything. Taking
    the first two of a sorted list breaks ties by whatever order the buckets
    arrived in, which is the clock — so on a session where every bucket traded
    the same amount, ``09:15`` and ``09:30`` collected a spike apiece and the
    frequency became a fact about sorting rather than about liquidity.

    A session with no more buckets than the cut awards nothing: where everything
    is in the top two, being in the top two distinguishes nothing.
    """
    if len(buckets) <= SPIKE_TOP_N:
        return frozenset()
    ordered = sorted(buckets.values(), reverse=True)
    cut = ordered[SPIKE_TOP_N]
    return frozenset(label for label, amount in buckets.items() if amount > cut)


def _phase_summary(buckets: Sequence[_Bucket]) -> dict[str, float]:
    """Share by part of the session, summed rather than averaged.

    A phase's share is the share of the whole session that lands in it, so the
    four add to 1. Averaging the buckets inside a phase would make the four-bucket
    afternoon look comparable to the one-bucket close, which is the comparison a
    reader is least likely to want.
    """
    totals = {phase: 0.0 for phase in _PHASE_LABELS}
    for bucket in buckets:
        hour, minute = bucket.label.split(":")
        phase = session_window.phase_of(time(int(hour), int(minute)))
        if phase is not None:
            totals[phase] += bucket.avg_share
    return {phase: round(value, 4) for phase, value in totals.items()}


def _tiles_frame(peak: _Bucket, sessions_used: int, metric: Metric) -> Frame:
    return Frame(
        kind="table",
        columns=("label", "value", "unit"),
        rows=(
            ("Khung giờ đỉnh", peak.label, None),
            ("Tỷ trọng thanh khoản", round(peak.avg_share * 100, 2), "%"),
            (_AMOUNT_LABELS[metric] + " trung bình", _round(peak.avg_amount), _UNITS[metric]),
            ("Số phiên lặp lại", f"{peak.spike_sessions}/{sessions_used}", "phiên"),
        ),
        unit=None,
        labels={"label": "Chỉ số", "value": "Giá trị", "unit": "Đơn vị"},
    )


def _profile_frame(buckets: Sequence[_Bucket], metric: Metric) -> Frame:
    return Frame(
        kind="series",
        columns=("bucket", "avg_amount", "median_amount", "share", "spike_frequency"),
        rows=tuple(
            (
                bucket.label,
                _round(bucket.avg_amount),
                _round(bucket.median_amount),
                round(bucket.avg_share, 4),
                bucket.spike_sessions,
            )
            for bucket in buckets
        ),
        unit=_UNITS[metric],
        labels={
            "bucket": "Khung giờ",
            "avg_amount": f"{_AMOUNT_LABELS[metric]} trung bình",
            "median_amount": f"{_AMOUNT_LABELS[metric]} trung vị",
            "share": "Tỷ trọng trong phiên",
            "spike_frequency": f"Số phiên nằm trong top {SPIKE_TOP_N}",
        },
    )


def _heatmap_frame(by_session: Mapping[object, Mapping[str, float]]) -> Frame:
    """Sessions down, the full bucket grid across, share in the cells.

    The grid is the full one even where a column is empty for this symbol, so
    every session in every heatmap is measured against the same axis. A cell the
    session has no bucket for is ``None``.
    """
    labels = session_window.SESSION_BUCKET_LABELS
    rows = []
    for day in sorted(by_session):
        buckets = by_session[day]
        total = sum(buckets.values())
        rows.append(
            (str(day),)
            + tuple(
                round(buckets[label] / total, 4)
                if label in buckets and total
                else None
                for label in labels
            )
        )

    return Frame(
        kind="matrix",
        columns=("session",) + labels,
        rows=tuple(rows),
        unit="share",
        labels={"session": "Phiên", **{label: label for label in labels}},
    )


def _ranking_frame(ranked: Sequence[_Bucket], metric: Metric) -> Frame:
    return Frame(
        kind="table",
        columns=("rank", "bucket", "share", "avg_amount", "spike_frequency"),
        rows=tuple(
            (
                position,
                bucket.label,
                round(bucket.avg_share, 4),
                _round(bucket.avg_amount),
                bucket.spike_sessions,
            )
            for position, bucket in enumerate(ranked, start=1)
        ),
        unit=_UNITS[metric],
        labels={
            "rank": "Hạng",
            "bucket": "Khung giờ",
            "share": "Tỷ trọng trong phiên",
            "avg_amount": f"{_AMOUNT_LABELS[metric]} trung bình",
            "spike_frequency": f"Số phiên nằm trong top {SPIKE_TOP_N}",
        },
    )


def view(result: StudyResult) -> SignalDeskSpec:
    """Four blocks: the numbers, the average, the habit, the ranking.

    The heatmap sits above the ranking deliberately. The ranking is the answer a
    reader came for and the heatmap is the reason to believe it, and a reader who
    scrolls past the reason still sees the answer.
    """
    symbol = result.headline["symbol"]
    return SignalDeskSpec(
        title=f"Thanh khoản trong phiên — {symbol}",
        blocks=(
            SignalDeskBlock(
                widget="stat_tiles",
                widget_version=1,
                frame="tiles",
                options={"label": "label", "value": "value", "unit": "unit"},
            ),
            SignalDeskBlock(
                widget="bar_series",
                widget_version=1,
                frame="profile",
                options={
                    "x": "bucket",
                    "y": "share",
                    "secondary": "avg_amount",
                    "yFormat": "percent",
                },
            ),
            SignalDeskBlock(
                widget="session_heatmap",
                widget_version=1,
                frame="heatmap",
                options={"rowKey": "session", "valueFormat": "percent"},
            ),
            SignalDeskBlock(
                widget="ranked_bars",
                widget_version=1,
                frame="ranking",
                options={"label": "bucket", "value": "share", "valueFormat": "percent"},
            ),
        ),
    )


def _round(value: float) -> float:
    """Numbers a reader will see, at a width a reader can read."""
    return float(Decimal(str(value)).quantize(Decimal("1")))


DEFINITION = register(
    StudyDefinition(
        name=NAME,
        version=VERSION,
        question=(
            "Thanh khoản của một mã tập trung vào khung giờ nào trong N phiên "
            "gần nhất, và mức đó lặp lại bao nhiêu phiên?"
        ),
        display_name="Thanh khoản trong phiên",
        params_model=LiquidityParams,
        requires=("intraday_bar_15m",),
        frames=("tiles", "profile", "heatmap", "ranking"),
        widgets=(
            ("stat_tiles", 1),
            ("bar_series", 1),
            ("session_heatmap", 1),
            ("ranked_bars", 1),
        ),
        compute=compute,
        view=view,
    )
)


__all__ = ["DEFINITION", "LiquidityParams", "MIN_SESSIONS", "NAME", "VERSION"]
