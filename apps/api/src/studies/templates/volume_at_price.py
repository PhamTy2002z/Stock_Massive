"""Where inside its own price range a symbol actually traded.

The question this was written for is *mức giá được mua nhiều nhất của VCB trong
phiên hôm nay là?* — and the honest answer changes the question twice before it
can be given.

**"Mua nhiều nhất" is not measurable from what the store holds.** A
fifteen-minute bar carries open, high, low, close and volume. It does not carry
which side initiated, so a level that answers "the most shares changed hands
here" is available and a level that answers "the most shares were bought here"
is not. Every string this Study produces says *giao dịch* rather than *mua*, and
:data:`SIDE_CAVEAT` says why in the headline, because the model is the layer that
would otherwise quietly upgrade the one into the other.

**A fifteen-minute bar is a range, not a price.** Inside one bucket the store
knows a low, a high and a volume, and nothing about how that volume was spread
between them. So the volume is spread *evenly* over every quoting step the bar
covers — an estimate, stated as one, and the only one the inputs support. The
alternative that looks more precise, assigning the whole bucket to its close, is
not an estimate at all: it is a claim the data does not make, and it would
manufacture a spike at whichever price the quarter hour happened to end on.

The steps are the exchange's own (``signals/price_band.tick_size``), not a grid
invented here, so a level this Study reports is a price an order could have sat
at. That is also why the board has to be known: refusing is better than picking
a step, since the wrong step makes the ladder finer or coarser than the market
and moves the answer.

## "Hôm nay" means today, or it means a refusal

The one failure this Study is built to avoid is answering about yesterday under
today's name. So the session at the top of the window is checked rather than
taken: on a weekday, once the first quarter hour could have printed, the store
is expected to hold today — and when it does not, the Study refuses with
``session_not_ingested`` instead of relabelling the session before it.

A session that is *underway* is a different case and is served, degraded: the
numbers are true as far as they go, and the provenance says how far that is.

The known limitation is the exchange holiday. Nothing in the store distinguishes
"the market was shut" from "the bars have not arrived", so a question asked on a
weekday holiday refuses rather than answering about the last session held. That
is the safe direction of the two.

## What the port changed, and where the line between read and calculation falls

The ladder is the same arithmetic as before, in the same order, and the
regression fixture holds it equal to the cell. What moved is *who does which
half*.

The tick grid stayed a **read**. Which board a symbol was listed on, and what
step an order at 75.400 has to sit on, are facts about the exchange rather than
about these numbers: no amount of arithmetic over the bars recovers them, and a
calculation that guessed a step would make the ladder finer or coarser than the
market. So ``ladder_rungs`` resolves the board, walks the grid between each
bar's low and high, and spreads that bar's volume across the rungs it covers —
and stops there, holding one row per price with nothing derived from it.

Everything after that became a **calculation** in the sandbox, under the same
validator a model's ``compute`` answers to: folding the ladder into even zones,
the share each zone holds, the busiest step inside a folded zone, the mark on
the level the answer is about. Not one figure in this file is typed — ``bins``
travels as a declared constant, and the rest is read out of a frame.

The ``tiles`` frame is gone. It existed to feed a v1 ``stat_tiles`` block, and
the board's KPI strip is that block's replacement: the four figures it carried
are now references into ``summary`` and ``concentration``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta
from decimal import ROUND_CEILING, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.stocks.intraday.ingest import SETTLE_GRACE
from src.stocks.intraday.reads import SESSION_SETTLED_AT
from src.stocks.intraday.session_window import BUCKET_MINUTES
from src.stocks.models import BarIntraday15m
from src.stocks.providers import Exchange
from src.stocks.providers.normalize import VN_TZ
from src.stocks.signals.issues import SignalIssue
from src.stocks.signals.price_band import resolve_band_regime, tick_size

from ..contracts import (
    ComputeStep,
    Frame,
    Provenance,
    ReadStep,
    StudyContext,
    StudyDefinition,
    StudyRefused,
)
from ..registry import register
from .params import LADDER_SESSIONS_CEILING, VolumeAtPriceParams

NAME = "volume_at_price"

#: Two rather than one because the answer changed shape: the ``tiles`` frame is
#: gone and its figures are KPI cells. The ladder's numbers are the same to the
#: cell, and a version is about what a stored artifact renders as.
VERSION = 2

#: How many quoting steps one bar's volume may be spread across before the
#: spread is sampled rather than walked. A penny name whose whole daily band is
#: over a thousand ticks would otherwise cost a thousand divisions per bucket
#: for an answer that is folded into at most twenty-four rungs anyway. Sampling
#: keeps the spread even across the same range; only its granularity changes.
MAX_STEPS_PER_BAR = 200

#: The moment the last bucket of a session can be in the store — the close plus
#: the ingest's own settling grace. Until then the ATC bucket is still held back,
#: and a session judged "settled" a minute early would freeze a ladder missing
#: the whole closing auction under a healthy caption.
LADDER_SETTLED_AT = (
    datetime.combine(date.min, SESSION_SETTLED_AT) + SETTLE_GRACE
).time()

#: The first moment a completed bucket of today could be *in the store*. 09:15
#: is the first bucket a HOSE symbol prints, stamped at its start; the ingest
#: holds a bucket back until the quarter hour it covers has elapsed plus its own
#: settling grace. Derived from those two rather than written as a clock time,
#: so the Study can never expect today one second before the ingest allows it.
FIRST_BUCKET_SETTLED_AT = (
    datetime.combine(date.min, time(9, 15)) + timedelta(minutes=BUCKET_MINUTES) + SETTLE_GRACE
).time()

#: The sentence the model must not lose on the way to prose. A bar says how much
#: traded and never who initiated, so the level this Study finds is where the
#: most shares changed hands — which is not the same claim as where the most
#: buying happened, and is the claim a reader will hear unless it is said.
SIDE_CAVEAT = (
    "Dữ liệu nến 15 phút không tách bên mua và bên bán, nên đây là mức giá "
    "giao dịch nhiều nhất chứ không phải mức được mua nhiều nhất."
)

SPREAD_NOTE = (
    "Khối lượng mỗi nến 15 phút được rải đều cho các bước giá trong khoảng "
    "thấp nhất đến cao nhất của nến đó, nên đây là số ước lượng."
)

SIDE_NOTE = (
    "Nến 15 phút không ghi bên mua hay bên bán, nên bảng này đọc là khối "
    "lượng giao dịch tại mỗi mức giá."
)

ZONE_NOTE = (
    "Thang giá dài hơn số mức vẽ được nên đã gộp thành các vùng đều nhau; "
    "mức ghi cho mỗi vùng là mức khớp nhiều nhất trong vùng đó."
)

_PRICE_LABEL = "Mức giá (đồng)"
_VOLUME_LABEL = "Khối lượng giao dịch (ước lượng)"
_SHARE_LABEL = "Tỷ trọng khối lượng"


# -- the window ------------------------------------------------------------


def _in_universe(context: StudyContext) -> None:
    symbol = context.params.symbol
    if symbol not in context.universe:
        raise StudyRefused(
            SignalIssue.MISSING_TARGET_SESSION,
            f"{symbol} is not in the declared Universe",
        )


def _window(
    session: Session, symbol: str, local: datetime, sessions: int
) -> tuple[date, ...]:
    """The sessions this answer is about, oldest first, or a refusal.

    Today counts, unlike every other read in ``studies``: the question is about
    a session that may still be running, and a reader asking it at eleven in the
    morning is owed the eleven o'clock answer rather than yesterday's.

    Which is exactly why the top of the window is checked. On a weekday past the
    first quarter hour the store is *expected* to hold today, and a window whose
    newest session is the day before is a window that would answer the wrong
    question under the right name.
    """
    today = local.date()
    stored = _stored_days(session, symbol, today, sessions)
    expected = local.weekday() < 5 and local.time() >= FIRST_BUCKET_SETTLED_AT

    if expected and (not stored or stored[0] != today):
        raise StudyRefused(
            SignalIssue.SESSION_NOT_INGESTED,
            f"the store holds no fifteen-minute bars for {symbol} on {today}, "
            "which is the session being asked about",
        )
    if not stored:
        raise StudyRefused(
            SignalIssue.SESSION_NOT_INGESTED,
            f"the store holds no fifteen-minute bars for {symbol} at all",
        )
    return tuple(reversed(stored))


def _stored_days(
    session: Session, symbol: str, upto: date, limit: int
) -> list[date]:
    """The ``limit`` newest stored sessions up to and including ``upto``."""
    return list(
        session.execute(
            select(BarIntraday15m.trading_day)
            .where(
                BarIntraday15m.symbol == symbol,
                BarIntraday15m.trading_day <= upto,
            )
            .distinct()
            .order_by(BarIntraday15m.trading_day.desc())
            .limit(limit)
        ).scalars()
    )


def _bars(
    session: Session, symbol: str, days: Sequence[date]
) -> tuple[BarIntraday15m, ...]:
    """Every stored bucket of those sessions, in clock order."""
    return tuple(
        session.execute(
            select(BarIntraday15m)
            .where(
                BarIntraday15m.symbol == symbol,
                BarIntraday15m.trading_day.in_(list(days)),
            )
            .order_by(BarIntraday15m.bucket_start)
        ).scalars()
    )


def _board_on(session: Session, symbol: str, day: date) -> Exchange:
    """Which exchange's quoting steps apply, or a refusal naming that gap.

    Refused rather than defaulted. HOSE quotes in three steps by price level and
    the other two boards in one, so guessing changes how fine the ladder is and
    therefore which level comes out on top — the least detectable kind of wrong
    answer.
    """
    exchange = resolve_band_regime(session, symbol, day).exchange
    if exchange is None:
        raise StudyRefused(
            SignalIssue.EXCHANGE_UNKNOWN,
            f"no listed exchange is stored for {symbol}, so the quoting steps "
            "its prices sit on are unknown",
        )
    return exchange


def _underway(day: date, local: datetime) -> bool:
    """Whether this session is the one running right now."""
    return day == local.date() and local.time() < LADDER_SETTLED_AT


# -- the reads -------------------------------------------------------------
#
# Two of them, and both are on the read axis for the same reason: neither is
# reachable from ``query``. One is the window itself — every other read in this
# package answers about *closed* sessions, and this Study's whole point is that
# a question asked at eleven in the morning is about the session running now.
# The other is the exchange's quoting grid, which is a fact about the board a
# symbol is listed on rather than about the numbers on it.


#: Where the window and its bars are kept once they have been read.
_WINDOW_MEMO = "volume_at_price.window"


def _read_once(context: StudyContext) -> tuple[tuple[date, ...], tuple, ...]:
    """The window and its bars, read once for the whole plan.

    Both reads of this plan want the same rows, and asking twice is not only two
    queries: each statement is its own snapshot, and the question this Study is
    usually asked is about a session *running now*. A bucket landing between the
    two reads would leave the close and the "still open" flag describing one set
    of bars while the ladder describes another, with nothing on the board saying
    so.
    """
    held = context.scratch.get(_WINDOW_MEMO)
    if held is not None:
        return held

    params = context.params
    local = context.as_of.astimezone(VN_TZ)
    days = _window(context.session, params.symbol, local, params.price_sessions)
    read = (days, _bars(context.session, params.symbol, days))
    context.scratch[_WINDOW_MEMO] = read
    return read


def _read_session_state(context: StudyContext) -> tuple[Frame, Provenance]:
    """One row per session in the window: where it closed, and whether it is over.

    Small, and it exists because two of the four things a reader is told are
    facts about the *session* rather than about the ladder — the last price and
    whether the picture is of a finished day. Neither can be recovered from a
    ladder of prices, and both would otherwise have to be asserted by a layer
    that had not read them.
    """
    params = context.params
    local = context.as_of.astimezone(VN_TZ)
    days, bars = _read_once(context)
    if not bars:
        raise StudyRefused(
            SignalIssue.SESSION_NOT_INGESTED,
            f"the store holds no fifteen-minute bars for {params.symbol} on "
            f"{days[-1]}, which is the session being asked about",
        )

    # Clock order, so the last bucket of a day is the one that wins the slot.
    last_of_day: dict[date, BarIntraday15m] = {}
    for bar in bars:
        last_of_day[bar.trading_day] = bar

    frame = Frame(
        kind="table",
        columns=("session", "close", "underway"),
        rows=tuple(
            (
                day.isoformat(),
                _price(Decimal(last_of_day[day].close)),
                _underway(day, local),
            )
            for day in days
            if day in last_of_day
        ),
        unit=None,
        labels={
            "session": "Phiên",
            "close": "Giá đóng cửa (đồng)",
            "underway": "Phiên chưa đóng",
        },
    )
    return frame, _provenance(context, days, bars[-1], notes=())


def _read_ladder_rungs(context: StudyContext) -> tuple[Frame, Provenance]:
    """The quoting grid under each bucket, and the volume that bucket traded.

    **The grid and nothing derived from it.** One row per (bucket, price on the
    grid), carrying the bucket's own volume and how many prices it was quoted
    across — and no share, no sum, no rank, no zone. Spreading a bucket's volume
    over its prices *is* the estimate the whole board rests on, so it is a
    calculation and it belongs in the sandbox with every other one; what a read
    may contribute is which prices exist on this board at this level, which is a
    fact about the exchange rather than about the numbers on it.

    ``steps`` travels as a column for that reason: it is a count of prices, and
    the division that turns it into an estimate happens where the validator can
    read it.
    """
    params = context.params
    days, bars = _read_once(context)
    target = days[-1]

    exchange = _board_on(context.session, params.symbol, target)
    grid = _grid(bars, exchange)
    if not grid:
        raise StudyRefused(
            SignalIssue.NO_TRADED_SESSIONS,
            f"{params.symbol} has stored buckets for {target} and none of them "
            "traded, so there is no volume to place at a price",
        )

    notes = [SPREAD_NOTE, SIDE_NOTE]
    if len({price for _bucket, price, _volume, _steps in grid}) > params.bins:
        # The fold is the calculation's job, but whether there will *be* one is
        # a fact about the grid this read just walked: more steps than rungs the
        # picture can carry is exactly the condition ``ZONE_NOTE`` describes.
        notes.append(ZONE_NOTE)

    frame = Frame(
        kind="table",
        columns=("bucket", "price", "bucket_volume", "steps"),
        rows=tuple(
            (bucket, _price(price), volume, steps) for bucket, price, volume, steps in grid
        ),
        unit="shares",
        labels={
            "bucket": "Khung 15 phút",
            "price": _PRICE_LABEL,
            "bucket_volume": "Khối lượng của khung",
            "steps": "Số mức giá khung này được yết qua",
        },
    )
    return frame, _provenance(context, days, bars[-1], notes=tuple(notes))


def _grid(
    bars: Sequence[BarIntraday15m], exchange: Exchange
) -> list[tuple[int, Decimal, float, int]]:
    """Every (bucket, price) the window quoted at, with the bucket's own volume.

    A bucket that traded nothing is left out rather than spread over zero: it
    places nothing wherever it is put, and a row of zeroes would be a claim that
    those prices were quoted and untraded, which this read cannot know.
    """
    rows: list[tuple[int, Decimal, float, int]] = []
    for index, bar in enumerate(bars):
        volume = float(bar.volume)
        if volume <= 0:
            continue
        steps = _steps(exchange, Decimal(bar.low), Decimal(bar.high))
        rows.extend((index, price, volume, len(steps)) for price in steps)
    return rows


def _steps(exchange: Exchange, low: Decimal, high: Decimal) -> tuple[Decimal, ...]:
    """Every price inside this bar an order could have sat at.

    Walked rather than divided, because the step is a function of the price on
    HOSE: a bar straddling 50,000 is quoted in 50s below it and 100s above, and
    a single step applied to the whole range would place volume at prices that
    do not exist on one side of the boundary.
    """
    if high < low:  # pragma: no cover - guards a provider inversion
        low, high = high, low
    first = _first_step_at_or_above(exchange, low)
    if first > high:
        # A bar narrower than one step: everything traded at one price, and the
        # honest level is the one the range sits on.
        return (first if first == low else low,)

    prices: list[Decimal] = []
    price = first
    while price <= high and len(prices) < MAX_STEPS_PER_BAR:
        prices.append(price)
        price += tick_size(exchange, price)

    if price <= high:
        # The walk hit the ceiling before the range ended. Spread evenly over the
        # same range at a coarser granularity rather than truncating it, which
        # would pile the whole bucket into its lower end.
        return _sampled(low, high, MAX_STEPS_PER_BAR)
    return tuple(prices)


def _first_step_at_or_above(exchange: Exchange, price: Decimal) -> Decimal:
    step = tick_size(exchange, price)
    return (price / step).quantize(Decimal(1), rounding=ROUND_CEILING) * step


def _sampled(low: Decimal, high: Decimal, count: int) -> tuple[Decimal, ...]:
    """``count`` evenly spaced prices across a range too wide to walk."""
    span = high - low
    return tuple(
        (low + span * Decimal(index) / Decimal(count - 1)).quantize(Decimal(1))
        for index in range(count)
    )


def _provenance(
    context: StudyContext,
    days: Sequence[date],
    last: BarIntraday15m,
    *,
    notes: tuple[str, ...],
) -> Provenance:
    """What both reads may claim: one window, one health, one sentence about it."""
    asked = context.params.price_sessions
    underway = _underway(days[-1], context.as_of.astimezone(VN_TZ))
    return Provenance(
        # ``store`` and not ``"vnstock"``: the vocabulary closed at
        # ``FrameSource`` answers *where these numbers came from* — this
        # deployment's own store, a page on the web, or arithmetic done this
        # Turn — and which provider filled the store is a different fact, kept
        # below where a reader never meets it.
        source="store",
        query={"provider": "vnstock"},
        as_of=context.as_of,
        sessions_used=len(days),
        health="degraded" if underway or len(days) < asked else "normal",
        reason=_reason(underway, last, len(days), asked),
        method_notes=notes,
    )


def _reason(
    underway: bool, last: BarIntraday15m, used: int, asked: int
) -> str | None:
    """Why this picture is thinner than a whole one, in one sentence or none."""
    parts = []
    if underway:
        parts.append(f"Phiên chưa đóng, tính tới {_covered_through(last)}")
    if used < asked:
        parts.append(f"chỉ đọc được {used}/{asked} phiên gần nhất")
    return "; ".join(parts) if parts else None


def _covered_through(bar: BarIntraday15m) -> str:
    """The clock time the numbers actually run up to.

    The *end* of the last stored bucket, not its start. A bucket stamped 13:30
    covers 13:30 to 13:45, so "tính tới 13:30" hands back a quarter hour that was
    counted — and a reader comparing the sentence against the clock reads the
    answer as staler than it is.
    """
    local = bar.bucket_start.astimezone(VN_TZ) + timedelta(minutes=BUCKET_MINUTES)
    return f"{local.hour:02d}:{local.minute:02d}"


def _price(value: Decimal | float) -> float:
    """A price at the width a share is quoted in: whole dong."""
    return float(Decimal(str(value)).quantize(Decimal(1)))


# -- the calculations ------------------------------------------------------


def _labels(_context: StudyContext) -> dict[str, object]:
    """The two headings the spreading step writes, so a reader meets Vietnamese.

    Through ``constants`` because that is the only door into the sandbox, and
    they are strings: nothing here is a figure, and the note about declared
    assumptions counts figures.
    """
    return {"price_label": _PRICE_LABEL, "volume_label": _VOLUME_LABEL}


def _bins(context: StudyContext) -> dict[str, object]:
    """How many rungs the drawn ladder may have, as a declared assumption.

    The one figure the fold needs and the only one that is not in a frame: the
    picture is read as a shape — where the mass sits — and past roughly two
    dozen bars the bars are thinner than the gaps between them and the shape
    stops being visible. The tick ladder underneath is not capped by it.
    """
    return {"bin_count": context.params.bins}


#: The ladder as at most ``bin_count`` rungs, in price order, with the share of
#: the window's volume each one holds.
#:
#: A folded rung is labelled with the busiest step inside it rather than with the
#: middle of its range, so the price the answer names is a price the market
#: actually quotes; ties inside a zone go to the lower price, which is the only
#: tie-break that does not depend on the order rows arrived in. Its own range
#: travels beside it, because a reader told "74.500" about a zone six steps wide
#: has been told something narrower than what was measured.
#:
#: The share is taken before the volume is rounded — rounding twenty-four rungs
#: and dividing by their rounded sum is a different number from the one the
#: market made.
#: The estimate the whole board rests on, in the place every estimate belongs.
#:
#: A bucket traded some volume somewhere inside its own range, and nothing in the
#: store says where. Spread evenly over the prices it was quoted across is the
#: only assumption that adds no information — ``SPREAD_NOTE`` is the sentence
#: that says so to a reader — and it is a division, so the validator reads it.
_RUNGS_CODE = """
placed = f0.assign(volume=f0["bucket_volume"] / f0["steps"])
result = (
    placed.groupby("price", sort=True)["volume"].sum().reset_index()
)
result.attrs["labels"] = {"price": price_label, "volume": volume_label}
result.attrs["unit"] = "shares"
"""

_FOLD_CODE = """
rungs = f0.sort_values("price", kind="mergesort").reset_index(drop=True)
total = rungs["volume"].sum()
if len(rungs.index) > bin_count:
    floor = rungs["price"].iloc[0]
    span = rungs["price"].iloc[-1] - floor
    reach = (rungs["price"] - floor) * bin_count / span
    zone = reach.astype("int64").clip(upper=bin_count - 1)
else:
    zone = pd.Series(np.arange(len(rungs.index)), index=rungs.index)
placed = rungs.assign(zone=zone)
busiest = placed.sort_values(
    ["zone", "volume", "price"], ascending=[True, False, True]
).groupby("zone", sort=True)["price"].first()
grouped = placed.groupby("zone", sort=True)
volume = grouped["volume"].sum()
result = pd.DataFrame(
    {
        "price": busiest,
        "volume": volume.round(),
        "share": (volume / total).round(4),
        "zone_low": grouped["price"].min(),
        "zone_high": grouped["price"].max(),
    }
).reset_index(drop=True)
result.attrs["labels"] = {
    "price": "Mức giá (đồng)",
    "volume": "Khối lượng giao dịch (ước lượng)",
    "share": "Tỷ trọng khối lượng",
    "zone_low": "Đáy vùng giá (đồng)",
    "zone_high": "Đỉnh vùng giá (đồng)",
}
result.attrs["unit"] = "shares"
"""

#: The three columns a reader meets, with the busiest level marked once.
#:
#: Marked here rather than by the drawing layer, which would mark the tallest bar
#: of whichever column the block happened to plot. A tie is still one leader: two
#: marks spend the one that means "this one", so the lowest of equal levels takes
#: it.
_LADDER_CODE = """
peak = f0["volume"].idxmax()
result = f0[["price", "volume", "share"]]
result.attrs["point_roles"] = [
    "focus" if position == peak else "series" for position in f0.index
]
result.attrs["labels"] = {
    "price": "Mức giá (đồng)",
    "volume": "Khối lượng giao dịch (ước lượng)",
    "share": "Tỷ trọng khối lượng",
}
result.attrs["unit"] = "shares"
"""

#: The same shares as a percentage, busiest first, on a frame whose unit says so.
#:
#: A frame carries one unit and ``ladder`` carries shares, so a strip figure read
#: out of it would be formatted as a count — ``0,11`` where a reader is owed
#: ``10,9%``. Nothing draws this; it exists to be quoted.
_CONCENTRATION_CODE = """
ordered = f0.sort_values(
    ["volume", "price"], ascending=[False, True]
).reset_index(drop=True)
result = pd.DataFrame(
    {"price": ordered["price"], "pct": (ordered["share"] * 100).round(2)}
)
result.attrs["labels"] = {"price": "Mức giá (đồng)", "pct": "Tỷ trọng khối lượng"}
result.attrs["unit"] = "%"
"""

#: The one-line answer, as the cells the KPI strip quotes.
#:
#: One row and no unit, because the three figures on it are a price, a price and
#: a count, and a frame carries one unit: leaving it off is what lets each of
#: them print as the whole number it is. The total is the *unrounded* one, for
#: the same reason the share is: the sum of twenty-four rounded rungs is not the
#: volume that traded.
_SUMMARY_CODE = """
busiest = f1.sort_values(["volume", "price"], ascending=[False, True])
result = pd.DataFrame(
    {
        "peak_price": [busiest["price"].iloc[0]],
        "close_price": [f0["close"].iloc[-1]],
        "sessions": [f0["session"].nunique()],
        "total_volume": [f2["volume"].sum().round()],
    }
)
result.attrs["labels"] = {
    "peak_price": "Mức giá giao dịch nhiều nhất",
    "close_price": "Giá đóng cửa gần nhất",
    "sessions": "Số phiên tính",
    "total_volume": "Tổng khối lượng",
}
"""


PLAN = (
    ReadStep(
        name="session_state",
        title="Phiên trong cửa sổ",
        read=_read_session_state,
    ),
    ReadStep(
        name="ladder_rungs",
        title="Khối lượng theo từng bước giá",
        read=_read_ladder_rungs,
    ),
    ComputeStep(
        name="rungs",
        title="Khối lượng ước lượng theo từng bước giá",
        code=_RUNGS_CODE,
        inputs=("ladder_rungs",),
        constants=_labels,
        output_kind="series",
        # A window of five sessions on a wide range walks more prices than a
        # model's calculation is allowed to answer with, and every one of them is
        # a rung the fold below needs. The literal ceiling is the validator's and
        # has no exception; this one is about how tall an answer may be.
        max_rows=MAX_STEPS_PER_BAR * LADDER_SESSIONS_CEILING,
    ),
    ComputeStep(
        name="folded",
        title="Thang giá đã gộp thành vùng",
        code=_FOLD_CODE,
        inputs=("rungs",),
        constants=_bins,
        output_kind="table",
    ),
    ComputeStep(
        name="ladder",
        title="Khối lượng theo mức giá",
        code=_LADDER_CODE,
        inputs=("folded",),
        output_kind="series",
    ),
    ComputeStep(
        name="concentration",
        title="Tỷ trọng từng mức giá, theo phần trăm",
        code=_CONCENTRATION_CODE,
        inputs=("folded",),
        output_kind="table",
    ),
    ComputeStep(
        name="summary",
        title="Mức giá đậm nhất và phiên đã tính",
        code=_SUMMARY_CODE,
        inputs=("session_state", "folded", "rungs"),
        output_kind="table",
    ),
)


BOARD = {
    "title": "Khối lượng theo mức giá — {symbol}",
    # What the volume of a session is made of, split by the price it traded at.
    # ``profile`` would also parse, and it would be the looser claim: this board
    # holds parts of one whole that add to it, which is the slot ``decompose``
    # asks for and the reason a reader can read a rung against the rest.
    "archetype": "decompose",
    "kpis": [
        {
            "label": "Mức giá giao dịch nhiều nhất",
            "value": {"frame_id": "summary", "column": "peak_price", "row": 0},
            "role": "focus",
        },
        {
            "label": "Tỷ trọng khối lượng tại mức đó",
            "value": {"frame_id": "concentration", "column": "pct", "row": 0},
        },
        {
            "label": "Giá đóng cửa gần nhất",
            "value": {"frame_id": "summary", "column": "close_price", "row": 0},
        },
        {
            "label": "Số phiên tính",
            "value": {"frame_id": "summary", "column": "sessions", "row": 0},
        },
    ],
    "sections": [
        {
            "heading": "Thang giá",
            "blocks": [
                # ``volume`` alone, and the narrowing is load-bearing: every
                # column of this frame is a number, so the drawing layer reads
                # the first of them as the measure unless it is told which one.
                # Price is the axis, volume is the bar.
                {"kind": "visual", "frame_id": "ladder", "columns": ["volume"]},
            ],
        },
    ],
    # No caption, and not for want of something to say: a board is expected to
    # be seven tenths picture, and one chart with one sentence under it is half.
    # The sentence a caption would carry is the headline's, which the model
    # reads anyway.
    "appendix_frame_id": None,
}


def headline(params, frames):
    """The three hundred tokens the model reads, out of the frames and nothing else.

    Handed the frames rather than the numbers, so every figure here came out of a
    cell the picture also draws. The ranking is by volume with the lower price
    breaking a tie, which is the order the ladder itself was marked in — two
    orderings of one fact would let the strip and the sentence name different
    levels.
    """
    sessions = _rows(frames["session_state"])
    rungs = _rows(frames["folded"])
    totals = _rows(frames["summary"])[0]
    ranked = sorted(rungs, key=lambda rung: (-rung["volume"], rung["price"]))
    latest = sessions[-1]
    peak = ranked[0]
    return {
        "symbol": params.symbol,
        "session": latest["session"],
        "sessionsUsed": len(sessions),
        "sessionUnderway": bool(latest["underway"]),
        "peakPrice": peak["price"],
        "peakZone": _zone_words(peak),
        "peakShare": peak["share"],
        "peakVolume": peak["volume"],
        "totalVolume": totals["total_volume"],
        "closePrice": latest["close"],
        "rangeLow": min(rung["zone_low"] for rung in rungs),
        "rangeHigh": max(rung["zone_high"] for rung in rungs),
        "levelCount": len(rungs),
        "grouped": _folded(peak),
        "top3": [
            {
                "price": rung["price"],
                "zone": _zone_words(rung),
                "share": rung["share"],
                "volume": rung["volume"],
            }
            for rung in ranked[:3]
        ],
        "caveat": SIDE_CAVEAT,
    }


def _rows(frame: Mapping[str, object]) -> list[dict[str, object]]:
    columns = list(frame["columns"])  # type: ignore[index]
    return [dict(zip(columns, row)) for row in frame["rows"]]  # type: ignore[index]


def _folded(rung: Mapping[str, object]) -> bool:
    return rung["zone_low"] != rung["zone_high"]


def _zone_words(rung: Mapping[str, object]) -> str | None:
    """The range a folded rung stands for, or ``None`` for a single price."""
    if not _folded(rung):
        return None
    low = f"{rung['zone_low']:,.0f}".replace(",", ".")
    high = f"{rung['zone_high']:,.0f}".replace(",", ".")
    return f"{low} – {high}"


DEFINITION = register(
    StudyDefinition(
        name=NAME,
        version=VERSION,
        question=(
            "Khối lượng của một mã tập trung ở những mức giá nào trong phiên "
            "gần nhất, và mức giá nào giao dịch nhiều nhất? Dùng cho câu hỏi về "
            "mức giá mua nhiều nhất, mức giá bán nhiều nhất, mức giá khớp nhiều "
            "nhất, vùng giá tập trung, hay khối lượng theo giá — kể cả khi câu "
            "hỏi nói \"hôm nay\". Dữ liệu không tách bên mua và bên bán, nên câu "
            "trả lời là mức giao dịch nhiều nhất."
        ),
        display_name="Khối lượng theo mức giá",
        params_model=VolumeAtPriceParams,
        requires=("intraday_bar_15m",),
        archetype="decompose",
        plan=PLAN,
        board=BOARD,
        headline=headline,
        precheck=_in_universe,
    )
)


__all__ = [
    "DEFINITION",
    "FIRST_BUCKET_SETTLED_AT",
    "LADDER_SETTLED_AT",
    "MAX_STEPS_PER_BAR",
    "NAME",
    "PLAN",
    "SIDE_CAVEAT",
    "SIDE_NOTE",
    "SPREAD_NOTE",
    "VERSION",
    "ZONE_NOTE",
]
