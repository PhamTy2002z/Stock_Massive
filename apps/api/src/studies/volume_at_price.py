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
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta
from decimal import ROUND_CEILING, Decimal

from pydantic import BaseModel, Field, field_validator
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

from .contracts import (
    Frame,
    Provenance,
    SignalDeskBlock,
    SignalDeskSpec,
    StudyContext,
    StudyDefinition,
    StudyRefused,
    StudyResult,
)
from .registry import register

NAME = "volume_at_price"
VERSION = 1

SESSIONS_FLOOR = 1
SESSIONS_CEILING = 5

#: How many rungs the drawn ladder may have. Twenty-four because the picture is
#: read as a shape — where the mass sits — and past roughly this the bars are
#: thinner than the gaps between them and the shape stops being visible. The
#: tick ladder underneath is not capped by it; it is folded into this many
#: even-width zones when it is longer.
BINS_FLOOR = 6
BINS_CEILING = 24

#: How many quoting steps one bar's volume may be spread across before the
#: spread is sampled rather than walked. A penny name whose whole daily band is
#: over a thousand ticks would otherwise cost a thousand divisions per bucket
#: for an answer that is folded into at most twenty-four rungs anyway. Sampling
#: keeps the spread even across the same range; only its granularity changes.
MAX_STEPS_PER_BAR = 200

#: The first moment a completed bucket of today could be *in the store*. 09:15
#: is the first bucket a HOSE symbol prints, stamped at its start; the ingest
#: holds a bucket back until the quarter hour it covers has elapsed plus its own
#: settling grace. Derived from those two rather than written as a clock time,
#: so the Study can never expect today one second before the ingest allows it.
#: The moment the last bucket of a session can be in the store — the close plus
#: the ingest's own settling grace. Until then the ATC bucket is still held back,
#: and a session judged "settled" a minute early would freeze a ladder missing
#: the whole closing auction under a healthy caption.
LADDER_SETTLED_AT = (
    datetime.combine(date.min, SESSION_SETTLED_AT) + SETTLE_GRACE
).time()

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


class VolumeAtPriceParams(BaseModel):
    """What the model fills in.

    ``price_sessions`` defaults to one because the question that reaches this Study is
    almost always about a single session — *phiên hôm nay* — and a default of
    several would answer a different question without saying so. It clamps
    rather than refuses, like every other Study's window.
    """

    symbol: str = Field(description="Mã chứng khoán trong Universe, vd VCB")
    price_sessions: int = Field(
        default=1,
        description=(
            f"Số phiên gần nhất gộp lại, {SESSIONS_FLOOR}–{SESSIONS_CEILING}; "
            "mặc định 1, tức phiên gần nhất, kể cả phiên đang diễn ra. Ngoài "
            "khoảng sẽ được kẹp về biên."
        ),
    )
    bins: int = Field(
        default=BINS_CEILING,
        description=(
            f"Số mức giá tối đa vẽ trên thang, {BINS_FLOOR}–{BINS_CEILING}; "
            "thang dài hơn sẽ được gộp thành đúng chừng này vùng đều nhau"
        ),
    )

    @field_validator("symbol")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("price_sessions")
    @classmethod
    def _clamp_sessions(cls, value: int) -> int:
        return max(SESSIONS_FLOOR, min(SESSIONS_CEILING, value))

    @field_validator("bins")
    @classmethod
    def _clamp_bins(cls, value: int) -> int:
        return max(BINS_FLOOR, min(BINS_CEILING, value))


class _Rung:
    """One price on the ladder, and the volume estimated to have traded there."""

    __slots__ = ("price", "volume", "low", "high")

    def __init__(
        self, price: Decimal, volume: float, low: Decimal, high: Decimal
    ) -> None:
        self.price = price
        self.volume = volume
        #: The zone this rung stands for. Equal to ``price`` while the ladder is
        #: drawn tick by tick, and wider once it has been folded.
        self.low = low
        self.high = high

    @property
    def folded(self) -> bool:
        return self.low != self.high


def compute(context: StudyContext) -> StudyResult:
    params = context.params
    assert isinstance(params, VolumeAtPriceParams)

    if params.symbol not in context.universe:
        raise StudyRefused(
            SignalIssue.MISSING_TARGET_SESSION,
            f"{params.symbol} is not in the declared Universe",
        )

    local = context.as_of.astimezone(VN_TZ)
    days = _window(context.session, params.symbol, local, params.price_sessions)
    target = days[-1]

    exchange = _board_on(context.session, params.symbol, target)
    bars = _bars(context.session, params.symbol, days)
    ladder, total = _ladder(bars, exchange)
    if not ladder or total <= 0:
        raise StudyRefused(
            SignalIssue.NO_TRADED_SESSIONS,
            f"{params.symbol} has stored buckets for {target} and none of them "
            "traded, so there is no volume to place at a price",
        )

    rungs = _fold(ladder, params.bins)
    peak = max(rungs, key=lambda rung: rung.volume)
    ranked = sorted(rungs, key=lambda rung: rung.volume, reverse=True)
    last = bars[-1]
    underway = target == local.date() and local.time() < LADDER_SETTLED_AT

    headline = {
        "symbol": params.symbol,
        "session": target.isoformat(),
        "sessionsUsed": len(days),
        "sessionUnderway": underway,
        "peakPrice": _price(peak.price),
        "peakZone": _zone_words(peak),
        "peakShare": round(peak.volume / total, 4),
        "peakVolume": _shares(peak.volume),
        "totalVolume": _shares(total),
        "closePrice": _price(Decimal(last.close)),
        "rangeLow": _price(min(rung.low for rung in rungs)),
        "rangeHigh": _price(max(rung.high for rung in rungs)),
        "levelCount": len(rungs),
        "grouped": peak.folded,
        "top3": [
            {
                "price": _price(rung.price),
                "zone": _zone_words(rung),
                "share": round(rung.volume / total, 4),
                "volume": _shares(rung.volume),
            }
            for rung in ranked[:3]
        ],
        "caveat": SIDE_CAVEAT,
    }

    notes = [SPREAD_NOTE, SIDE_NOTE]
    if any(rung.folded for rung in rungs):
        notes.append(ZONE_NOTE)

    return StudyResult(
        headline=headline,
        frames={
            "tiles": _tiles_frame(peak, total, last, len(days)),
            "ladder": _ladder_frame(rungs, peak, total),
        },
        provenance=Provenance(
            source="vnstock",
            as_of=context.as_of,
            sessions_used=len(days),
            health="degraded" if underway or len(days) < params.price_sessions else "normal",
            reason=_reason(underway, last, len(days), params.price_sessions),
            method_notes=tuple(notes),
        ),
    )


# -- the window ------------------------------------------------------------


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


# -- the ladder ------------------------------------------------------------


def _ladder(
    bars: Sequence[BarIntraday15m], exchange: Exchange
) -> tuple[dict[Decimal, float], float]:
    """Volume per quoting step across the window, and the total placed."""
    ladder: dict[Decimal, float] = {}
    total = 0.0
    for bar in bars:
        volume = float(bar.volume)
        if volume <= 0:
            continue
        steps = _steps(exchange, Decimal(bar.low), Decimal(bar.high))
        share = volume / len(steps)
        for price in steps:
            ladder[price] = ladder.get(price, 0.0) + share
        total += volume
    return ladder, total


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


def _fold(ladder: Mapping[Decimal, float], bins: int) -> tuple[_Rung, ...]:
    """The ladder as at most ``bins`` rungs, in price order.

    A folded rung is labelled with the busiest step inside it rather than with
    the middle of its range, so the price the answer names is a price the market
    actually quotes. Its own range travels with it, because a reader told
    "74,500" about a zone six steps wide has been told something narrower than
    what was measured.
    """
    prices = sorted(ladder)
    if len(prices) <= bins:
        return tuple(
            _Rung(price, ladder[price], price, price) for price in prices
        )

    low, high = prices[0], prices[-1]
    span = high - low
    grouped: dict[int, list[Decimal]] = {}
    for price in prices:
        # The last price would land one past the final bin on its own edge.
        index = min(bins - 1, int((price - low) / span * bins)) if span else 0
        grouped.setdefault(index, []).append(price)

    rungs = []
    for index in sorted(grouped):
        members = grouped[index]
        volume = sum(ladder[price] for price in members)
        busiest = max(members, key=lambda price: (ladder[price], -price))
        rungs.append(_Rung(busiest, volume, members[0], members[-1]))
    return tuple(rungs)


# -- what a reader sees ----------------------------------------------------


def _tiles_frame(
    peak: _Rung, total: float, last: BarIntraday15m, sessions_used: int
) -> Frame:
    return Frame(
        kind="table",
        columns=("label", "value", "unit"),
        rows=(
            ("Mức giá giao dịch nhiều nhất", _price(peak.price), "đồng"),
            ("Tỷ trọng khối lượng tại mức đó", round(peak.volume / total * 100, 2), "%"),
            ("Giá đóng cửa gần nhất", _price(Decimal(last.close)), "đồng"),
            ("Số phiên tính", sessions_used, "phiên"),
        ),
        unit=None,
        labels={"label": "Chỉ số", "value": "Giá trị", "unit": "Đơn vị"},
        # The level is what was asked for; the three tiles after it are how
        # concentrated it is, where the price ended up, and over how long.
        point_roles=("focus", None, None, None),
    )


def _ladder_frame(rungs: Sequence[_Rung], peak: _Rung, total: float) -> Frame:
    """Price up the axis, volume across it, the busiest level marked once."""
    return Frame(
        kind="series",
        columns=("price", "volume", "share"),
        rows=tuple(
            (
                _price(rung.price),
                _shares(rung.volume),
                round(rung.volume / total, 4),
            )
            for rung in rungs
        ),
        unit="shares",
        # Marked here rather than by the drawing layer, which would mark the
        # tallest bar of whichever column the block happened to plot. A tie is
        # still one leader: two marks spend the one that means "this one".
        point_roles=tuple(
            "focus" if rung is peak else "series" for rung in rungs
        ),
        labels={
            "price": "Mức giá (đồng)",
            "volume": "Khối lượng giao dịch (ước lượng)",
            "share": "Tỷ trọng khối lượng",
        },
    )


def view(result: StudyResult) -> SignalDeskSpec:
    """Two blocks: the level, then the whole shape it stands out of.

    The tiles are first because the question has a one-line answer and a reader
    who reads nothing else has it. The ladder is under it because a level with
    twelve percent of the volume means one thing when the rest is flat and quite
    another when three neighbours are close behind.
    """
    symbol = result.headline["symbol"]
    return SignalDeskSpec(
        title=f"Khối lượng theo mức giá — {symbol}",
        blocks=(
            SignalDeskBlock(
                widget="stat_tiles",
                widget_version=2,
                frame="tiles",
                options={"label": "label", "value": "value", "unit": "unit"},
            ),
            SignalDeskBlock(
                widget="bar_series",
                widget_version=2,
                frame="ladder",
                options={"x": "price", "y": "volume"},
            ),
        ),
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


def _zone_words(rung: _Rung) -> str | None:
    """The range a folded rung stands for, or ``None`` for a single price."""
    if not rung.folded:
        return None
    return f"{_price(rung.low):,.0f} – {_price(rung.high):,.0f}".replace(",", ".")


def _price(value: Decimal | float) -> float:
    """A price at the width a share is quoted in: whole dong."""
    return float(Decimal(str(value)).quantize(Decimal(1)))


def _shares(value: float) -> float:
    """A share count at the width a share count is counted in."""
    return float(Decimal(str(value)).quantize(Decimal(1)))


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
        frames=("tiles", "ladder"),
        widgets=(("stat_tiles", 2), ("bar_series", 2)),
        compute=compute,
        view=view,
    )
)


__all__ = [
    "BINS_CEILING",
    "BINS_FLOOR",
    "DEFINITION",
    "FIRST_BUCKET_SETTLED_AT",
    "LADDER_SETTLED_AT",
    "MAX_STEPS_PER_BAR",
    "NAME",
    "SESSIONS_CEILING",
    "SESSIONS_FLOOR",
    "SIDE_CAVEAT",
    "VERSION",
    "VolumeAtPriceParams",
]
