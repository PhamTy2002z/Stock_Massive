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

## What the port changed, and what it could not

The averages, the median, the share and the spike count are the same arithmetic
as before, in the same order, and the regression fixture holds them equal to the
cell. Two things moved. The ``tiles`` frame is gone: it existed to feed a v1
``stat_tiles`` block, and the board's KPI strip is that block's replacement —
every figure it carried is now a reference into ``profile``. And the four
statistics are computed in the sandbox from a tidy frame rather than in this
process, so a template asserts no figure the validator has not read.
"""

from __future__ import annotations

from src.stocks.intraday import session_window
from src.stocks.signals.issues import SignalIssue

from ..contracts import (
    ComputeStep,
    Frame,
    QueryStep,
    StudyContext,
    StudyDefinition,
    StudyRefused,
)
from ..registry import register
from .params import LiquidityParams

NAME = "intraday_liquidity_profile"
VERSION = 2

#: Below this the picture is of a fortnight rather than of a habit, and the
#: refusal says so. A fixed floor rather than a share of the request: the
#: question is about repetition, and repetition needs a count.
MIN_SESSIONS = 10

#: How many buckets of a session count as its peak for spike frequency. Two
#: rather than one because the closing auction takes the top slot on most
#: sessions of most symbols, and a definition that only ever names the winner
#: would answer "the close" for everything. Changing this changes what the number
#: means, so it ships as a new ``version`` rather than as an edit.
SPIKE_TOP_N = 2

_UNITS = {"volume": "shares", "value": "VND"}
_AMOUNT_LABELS = {"volume": "Khối lượng", "value": "Giá trị (VND)"}


# -- the plan --------------------------------------------------------------


def _symbols(context: StudyContext) -> list[str]:
    return [context.params.symbol]


def _bar_arguments(context: StudyContext) -> dict[str, object]:
    # ``close`` as well as ``volume`` because ``value`` is volume at the bucket's
    # closing price — the only one of the four that is a price something
    # certainly traded at.
    return {"window": context.params.sessions, "columns": ["close", "volume"]}


def _in_universe(context: StudyContext) -> None:
    symbol = context.params.symbol
    if symbol not in context.universe:
        raise StudyRefused(
            SignalIssue.MISSING_TARGET_SESSION,
            f"{symbol} is not in the declared Universe",
        )


def _enough_sessions(frame: Frame, context: StudyContext) -> None:
    """The window has to be long enough for "how often" to mean anything."""
    position = frame.columns.index("session")
    sessions = len({row[position] for row in frame.rows})
    if sessions < MIN_SESSIONS:
        raise StudyRefused(
            SignalIssue.INSUFFICIENT_SESSIONS,
            f"{sessions} closed sessions stored, {MIN_SESSIONS} needed",
        )


def _basis(context: StudyContext) -> dict[str, object]:
    return {
        "value_basis": 1 if context.params.metric == "value" else 0,
        # The exchange's own clock, which cannot be read off the data: a bucket
        # no session of this symbol has is exactly the column the heatmap has to
        # keep, so that every session in every heatmap is measured against one
        # axis.
        "bucket_grid": list(session_window.SESSION_BUCKET_LABELS),
        "amount_label": _AMOUNT_LABELS[context.params.metric],
        "unit": _UNITS[context.params.metric],
        "spike_label": f"Số phiên nằm trong top {SPIKE_TOP_N}",
        # The cut itself, not only its name. Written as a literal the arithmetic
        # would go on meaning two after somebody bumped the constant, and the
        # frame would carry a heading that contradicted its own cells.
        "spike_top_n": SPIKE_TOP_N,
    }


#: One tidy row per (session, bucket): the amount, its share of that session, and
#: whether it was unambiguously among the session's largest.
#:
#: Strictly greater than the largest amount outside the top two, which is the
#: only tie-break that means anything. Taking the first two of a sorted list
#: breaks ties by whatever order the buckets arrived in — the clock — so on a
#: session where every bucket traded the same amount, ``09:15`` and ``09:30``
#: would collect a spike apiece and the frequency would be a fact about sorting.
#: A session with no more buckets than the cut awards nothing.
_BUCKETS_CODE = """
amount = f0["close"] * f0["volume"] if value_basis else f0["volume"]
tidy = f0[["session", "bucket"]].copy()
tidy["amount"] = amount.astype("float64")
total = tidy.groupby("session")["amount"].transform("sum")
tidy["share"] = (tidy["amount"] / total).where(total > 0, 0.0)
ranked = tidy.groupby("session")["amount"].rank(method="min", ascending=False)
width = tidy.groupby("session")["amount"].transform("size")
cut = tidy.groupby("session")["amount"].transform(
    lambda column: column.sort_values(ascending=False).iloc[spike_top_n]
    if len(column) > spike_top_n
    else None
)
tidy["spike"] = ((tidy["amount"] > cut) & (width > spike_top_n)).astype("float64")
# A session where nothing traded has no shares to speak of, and a zero would say
# every bucket of it traded nothing *of something*. Left absent so the heatmap
# draws a hole; the profile fills it with the zero it is, below.
tidy["share_drawn"] = tidy["share"].where(total > 0)
result = tidy[["session", "bucket", "amount", "share", "share_drawn", "spike"]]
result.attrs["labels"] = {
    "session": "Phiên",
    "bucket": "Khung giờ",
    "amount": amount_label,
    "share": "Tỷ trọng trong phiên",
    "share_drawn": "Tỷ trọng trong phiên",
    "spike": "Nằm trong nhóm lớn nhất phiên",
}
result.attrs["unit"] = unit
"""

#: Every statistic averaged over the *window*, not over the sessions the bucket
#: appeared in. That distinction is the correctness of the whole picture:
#: dividing by appearances says a bucket that traded once in thirty sessions had
#: a share of eighteen percent, and the phases then sum to more than one. Absent
#: means nothing traded in that quarter hour that day, which is a zero — so the
#: median is taken over the padded window too.
_PROFILE_CODE = """
sessions = f0["session"].nunique()
padded = (
    f0.pivot_table(index="bucket", columns="session", values="amount", aggfunc="sum")
    .reindex([label for label in bucket_grid if label in set(f0["bucket"])])
    .reindex(columns=sorted(f0["session"].unique()))
    .fillna(0.0)
)
profile = pd.DataFrame(
    {
        "avg_amount": padded.sum(axis=1) / sessions,
        "median_amount": padded.median(axis=1),
        "share": f0.groupby("bucket")["share"].sum().reindex(padded.index) / sessions,
        "spike_frequency": f0.groupby("bucket")["spike"].sum().reindex(padded.index),
    }
)
profile["avg_amount"] = profile["avg_amount"].round()
profile["median_amount"] = profile["median_amount"].round()
profile["share"] = profile["share"].round(4)
profile["spike_frequency"] = profile["spike_frequency"].astype("int64")
peak = profile["share"].idxmax()
result = profile.reset_index().rename(columns={"index": "bucket"})
result.attrs["point_roles"] = [
    "focus" if label == peak else None for label in result["bucket"]
]
result.attrs["labels"] = {
    "bucket": "Khung giờ",
    "avg_amount": amount_label + " trung bình",
    "median_amount": amount_label + " trung vị",
    "share": "Tỷ trọng trong phiên",
    "spike_frequency": spike_label,
}
result.attrs["unit"] = unit
"""

#: Sessions down, the full bucket grid across, share in the cells. The grid is
#: the full one even where a column is empty for this symbol; a cell the session
#: has no bucket for is ``None`` rather than a zero it never traded.
_HEATMAP_CODE = """
grid = pd.DataFrame(
    f0.pivot_table(
        index="session", columns="bucket", values="share_drawn", aggfunc="sum"
    )
).reindex(columns=bucket_grid)
grid = grid.round(4)
result = grid.reset_index()
result.attrs["labels"] = {"session": "Phiên"}
result.attrs["unit"] = "share"
"""

#: The same buckets, sorted by the share that is the answer, with the leader
#: marked. A tie at the top is still one leader: two marks spend the one that
#: means "this one".
#:
#: ``mergesort`` because pandas' default is not stable and the share is rounded
#: before it is sorted. Two quarter-hours a hundred-thousandth apart round to one
#: number, and an unstable sort would then hand row 0 — which is every KPI, the
#: ``focus`` mark and the whole headline — to whichever of them the partition
#: happened to leave first. Stable, a tie keeps clock order, which is also what
#: ``idxmax`` gives the ``focus`` mark on ``profile``: one leader, and the same
#: one on both pictures.
_RANKING_CODE = """
ordered = f0.sort_values(
    "share", ascending=False, kind="mergesort"
).reset_index(drop=True)
ordered.insert(0, "rank", ordered.index + 1)
result = ordered[["rank", "bucket", "share", "avg_amount", "spike_frequency"]]
result.attrs["point_roles"] = [
    "focus" if position == 1 else None for position in result["rank"]
]
result.attrs["labels"] = {
    "rank": "Hạng",
    "bucket": "Khung giờ",
    "share": "Tỷ trọng trong phiên",
    "avg_amount": amount_label + " trung bình",
    "spike_frequency": spike_label,
}
result.attrs["unit"] = unit
"""


#: The same shares as a percentage, on a frame whose unit says so.
#:
#: A frame carries one unit and ``ranking`` carries shares, so a strip figure
#: read out of it would be formatted as a count — ``0,14`` where a reader is owed
#: ``13,6%``. The strip and the caption read percentages, so the percentages are
#: a frame. Nothing draws it; it exists to be quoted.
_CONCENTRATION_CODE = """
ordered = f0.sort_values(
    "share", ascending=False, kind="mergesort"
).reset_index(drop=True)
result = pd.DataFrame(
    {"bucket": ordered["bucket"], "share_pct": (ordered["share"] * 100).round(2)}
)
result.attrs["labels"] = {
    "bucket": "Khung giờ",
    "share_pct": "Tỷ trọng trong phiên",
}
result.attrs["unit"] = "%"
"""


PLAN = (
    QueryStep(
        name="bars",
        title="Bucket 15 phút đã lưu",
        source="intraday_15m",
        symbols=_symbols,
        arguments=_bar_arguments,
        method_notes=(
            f"Một khung giờ được tính là đỉnh của phiên khi nằm trong "
            f"{SPIKE_TOP_N} khung giao dịch lớn nhất phiên đó.",
            "Tỷ trọng của mỗi khung giờ tính trên tổng của chính phiên đó, "
            "nên phiên sôi động và phiên trầm so được với nhau.",
        ),
        check=_enough_sessions,
    ),
    ComputeStep(
        name="buckets",
        title="Khung giờ theo từng phiên",
        code=_BUCKETS_CODE,
        inputs=("bars",),
        constants=_basis,
        output_kind="table",
    ),
    ComputeStep(
        name="profile",
        title="Thanh khoản trung bình theo khung giờ",
        code=_PROFILE_CODE,
        inputs=("buckets",),
        constants=_basis,
        output_kind="series",
    ),
    ComputeStep(
        name="heatmap",
        title="Tỷ trọng từng khung giờ theo phiên",
        code=_HEATMAP_CODE,
        inputs=("buckets",),
        constants=_basis,
        output_kind="matrix",
        # One session column and the exchange's seventeen quarter hours. The
        # ceiling a model answers to is twelve, which is the right number for
        # a calculation and the wrong one for a grid.
        max_columns=len(session_window.SESSION_BUCKET_LABELS) + 1,
    ),
    ComputeStep(
        name="concentration",
        title="Tỷ trọng khung giờ, theo phần trăm",
        code=_CONCENTRATION_CODE,
        inputs=("profile",),
        constants=_basis,
        output_kind="table",
    ),
    ComputeStep(
        name="ranking",
        title="Xếp hạng khung giờ",
        code=_RANKING_CODE,
        inputs=("profile",),
        constants=_basis,
        output_kind="table",
    ),
)


BOARD = {
    "title": "Thanh khoản trong phiên — {symbol}",
    "archetype": "profile",
    "kpis": [
        {
            "label": "Khung giờ đỉnh",
            "value": {"frame_id": "ranking", "column": "bucket", "row": 0},
            "role": "focus",
        },
        {
            "label": "Tỷ trọng thanh khoản",
            "value": {"frame_id": "concentration", "column": "share_pct", "row": 0},
        },
        {
            "label": "Trung bình khung giờ đỉnh",
            "value": {"frame_id": "ranking", "column": "avg_amount", "row": 0},
        },
        {
            "label": "Số phiên lặp lại",
            "value": {"frame_id": "ranking", "column": "spike_frequency", "row": 0},
        },
    ],
    "sections": [
        {
            "heading": "Tổng quan",
            "blocks": [
                {"kind": "visual", "frame_id": "profile", "columns": ["bucket", "share"]},
                {
                    "kind": "caption",
                    "template": (
                        "Khung giờ {a} chiếm {b} thanh khoản trung bình một "
                        "phiên và nằm trong nhóm lớn nhất phiên {c} lần."
                    ),
                    "refs": {
                        "a": {"frame_id": "ranking", "column": "bucket", "row": 0},
                        "b": {
                            "frame_id": "concentration",
                            "column": "share_pct",
                            "row": 0,
                        },
                        "c": {
                            "frame_id": "ranking",
                            "column": "spike_frequency",
                            "row": 0,
                        },
                    },
                },
            ],
        },
        {
            "heading": "Diễn biến từng phiên",
            "blocks": [
                {"kind": "visual", "frame_id": "heatmap"},
                {
                    "kind": "visual",
                    "frame_id": "ranking",
                    "columns": ["bucket", "share"],
                },
            ],
        },
    ],
    "appendix_frame_id": None,
}


def headline(params, frames):
    """The three hundred tokens the model reads, out of the frames and nothing else.

    Handed the frames rather than the numbers, so every figure here came out of a
    cell a picture also draws. The phase summary sums shares rather than
    averaging them: a phase's share is the share of the whole session that lands
    in it, so the four add to one, and averaging would make the four-bucket
    afternoon look comparable to the one-bucket close.
    """
    profile = _rows(frames["profile"])
    ranking = _rows(frames["ranking"])
    sessions = len(frames["heatmap"]["rows"])
    top = ranking[0]
    return {
        "symbol": params.symbol,
        "sessionsUsed": sessions,
        "metric": params.metric,
        "peakWindow": top["bucket"],
        "peakAvgAmount": top["avg_amount"],
        "peakShare": top["share"],
        "peakOccurrence": f"{int(top['spike_frequency'])}/{sessions}",
        "top3": [
            {
                "window": row["bucket"],
                "share": row["share"],
                "avgAmount": row["avg_amount"],
                "occurrence": f"{int(row['spike_frequency'])}/{sessions}",
            }
            for row in ranking[:3]
        ],
        "phaseSummary": _phases(profile),
    }


def _rows(frame):
    columns = list(frame["columns"])
    return [dict(zip(columns, row)) for row in frame["rows"]]


def _phases(profile):
    from datetime import time

    totals = {phase: 0.0 for phase in ("ato", "am", "pm", "atc")}
    for row in profile:
        hour, minute = str(row["bucket"]).split(":")
        phase = session_window.phase_of(time(int(hour), int(minute)))
        if phase is not None:
            totals[phase] += row["share"]
    return {phase: round(value, 4) for phase, value in totals.items()}


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
        archetype="profile",
        plan=PLAN,
        board=BOARD,
        headline=headline,
        precheck=_in_universe,
    )
)


__all__ = ["DEFINITION", "MIN_SESSIONS", "NAME", "PLAN", "VERSION"]
