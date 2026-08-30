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
52-week high, RSI — all exist as registered Signal Fields. All three are also
pure functions of a close series, this Study already holds the close series it
needs for its other conditions, and reading three Signal Fields would be three
window preparations for numbers already in hand. ``bar_daily`` holds an adjusted
series, which is the right input for all three, since adjustment is exactly what
one wants when measuring what holding the share returned.

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

## What the port changed, and what it could not

The band, the position, the return, the RSI, the zone, the eight quarters and the
six condition rows are the same arithmetic in the same order, and the regression
fixture holds four of the five frames equal to the cell. Four things moved.

*The ``tiles`` frame is gone.* It existed to feed a v1 ``stat_tiles`` block, and
the board's KPI strip is that block's replacement — its five figures are now five
references into ``range_band``, ``rates`` and ``readings``. The checklist's
``evidence`` column still says "Các số dẫn dắt" for the RSI row, and that still
reads true: the leading figures are the strip.

*Raw and rounded are two frames now.* ``momentum`` holds what the arithmetic
produced and ``readings`` holds what a person is shown. The split is the old
``_price``/``_pct`` boundary made addressable: every condition compares the raw
measurement, exactly as before, and every figure a reader meets is rounded once,
in one place.

*The checklist note is a caption.* Under v1 it was an option on the checklist
widget; under v2 the server decides a widget's options from the frame's shape, so
the fixed prose is the one caption on the board — which is where a disclosure
belongs anyway, under the block it discloses.

*The mixed-basis guard is gone, and nothing replaces it.* ``bars_for`` handed
back ``price_basis`` per session and this Study refused a window that mixed two;
the store's own reader (``agent/tools/query.py::_read_bar_daily``) offers open,
high, low, close and volume and not the basis, and a template does not get a
second road to the same table. Every row written today is ``adjusted_at_source``,
so the guard was one nobody had seen fire — but it is a guard, and it is worth
saying plainly that it is not here.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from src.stocks.signals.issues import SignalIssue

from .. import reads_fundamental
from ..contracts import (
    ComputeStep,
    Frame,
    Provenance,
    QueryStep,
    ReadStep,
    StudyContext,
    StudyDefinition,
    StudyRefused,
)
from ..registry import register
from .params import RANGE_SESSIONS, ConditionReviewParams

NAME = "entry_condition_review"
VERSION = 2

#: Below this the study refuses. The band, the return and every condition that
#: names "52 tuần" would otherwise be a claim about ten months labelled as a
#: year, which is worse than no answer.
MIN_SESSIONS = RANGE_SESSIONS

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

#: How many decimals a rate is shown at, and a price. A rate at two decimals is
#: more precision than any of these earns; a price is quoted in whole đồng.
RATE_DIGITS = 2
PRICE_DIGITS = 0

#: The condition wording, fixed here and nowhere else. Each one is a statement
#: about a measurement, in the indicative: no imperative verb, no price tied to
#: an action, nothing a reader could read as an instruction.
LABEL_OFF_HIGH = "Giá đóng cửa còn cách đỉnh 52 tuần trên 5%"
LABEL_RSI = "RSI 14 phiên dưới ngưỡng quá mua 70"
LABEL_RETURN_12M = "Lợi nhuận nắm giữ 12 tháng dương"
LABEL_IN_ZONE = "Giá đóng cửa nằm trong vùng giá đóng cửa tập trung 60 phiên"
LABEL_PROFIT_POSITIVE = "Lợi nhuận quý gần nhất dương"
LABEL_PROFIT_IMPROVED = "Lợi nhuận quý gần nhất cao hơn cùng kỳ năm trước"

#: The six rows, in the order a reader meets the axes on the board.
CONDITION_LABELS: tuple[str, ...] = (
    LABEL_OFF_HIGH,
    LABEL_IN_ZONE,
    LABEL_RETURN_12M,
    LABEL_RSI,
    LABEL_PROFIT_POSITIVE,
    LABEL_PROFIT_IMPROVED,
)

#: The unit each row's measurement is in. ``None`` for the RSI, which is an index
#: and not a quantity of anything.
CONDITION_UNITS: tuple[str | None, ...] = ("%", "đ", "%", None, "VND", "%")

#: Which picture on the board a checklist row can be checked against, in the way
#: a reader would point at it. The rows used to carry the frame's own key, and
#: the browser printed "Số liệu trong khối price_context" into a tooltip — a name
#: that told a reader nothing, in English.
CONDITION_EVIDENCE: tuple[str, ...] = (
    "Dải giá 52 tuần",
    "Dải giá 52 tuần",
    "Đường giá",
    "Các số dẫn dắt",
    "Lợi nhuận theo quý",
    "Lợi nhuận theo quý",
)

#: The three words a status reads as. Only the Vietnamese is sent: the frame is
#: also what the "xem dạng bảng" disclosure prints, so a reader who opened the
#: table used to meet a column of ``met`` and ``not_met`` beside the column that
#: had already translated them.
STATUS_LABELS: dict[str, str] = {
    "met": "Đạt",
    "not_met": "Chưa đạt",
    "unknown": "Chưa rõ",
}

#: The same three, read back. The headline reports the token because that is what
#: a caller comparing two runs can match on; the frame carries the Vietnamese
#: because that is what a person reads.
STATUS_TOKENS: dict[str, str] = {word: token for token, word in STATUS_LABELS.items()}

#: The note under the checklist. Fixed prose, describing what the panel measured
#: and what it does not know — the shape a brokerage disclosure takes, without a
#: single "nên" or "hãy" in it. It carries no digit, which is also what lets it
#: be a caption: a board's captions quote figures through cells or not at all.
CHECKLIST_NOTE = (
    "Bảng điều kiện mô tả trạng thái dữ liệu tại phiên đã đóng gần nhất: mỗi "
    "dòng nêu một mức đo được và ngưỡng nó được so với. Các mức này thay đổi "
    "theo từng phiên, và bảng không xét mục tiêu, kỳ hạn hay khả năng chịu lỗ "
    "của người đọc."
)

#: What the four axes were measured over, on the frame the quarters come from.
#: A note about method rather than about thinness — the two answer different
#: questions and reach a reader through different fields.
QUARTER_METHOD_NOTES: tuple[str, ...] = (
    "Lợi nhuận lấy dòng lãi của cổ đông công ty mẹ, và lấy dòng hợp nhất khi "
    "báo cáo quý không có dòng đó.",
    "So cùng kỳ cần tám quý liên tiếp, nên bốn quý đầu của bảng không có mức "
    "so sánh nào.",
)

#: How the four price axes were measured, in the words the hand-written Study
#: put on the strip. Kept verbatim rather than rewritten: a reader who saw this
#: panel last month and sees it again should read the same sentence, and the
#: pre-port fixture holds these four exactly.
MOMENTUM_METHOD_NOTES: tuple[str, ...] = (
    "Dải cao – thấp lấy trên 250 phiên đã đóng gần nhất, xấp xỉ 52 tuần giao "
    "dịch.",
    "Vùng giá tập trung là hai bậc giá dày phiên nhất trong 60 phiên gần nhất.",
    "Chỉ báo sức mạnh giá tính trên 14 phiên, đo trên 100 phiên gần nhất nên "
    "không đổi theo độ dài biểu đồ.",
    "Giá đã điều chỉnh cho sự kiện quyền, nên so được giữa các mốc thời gian.",
)

#: Vietnamese for every column of the two frames nothing draws. They are stored
#: artifacts a person can open, so a heading that read ``off_high_pct`` would be
#: this system's spelling reaching a reader.
FIGURE_LABELS: dict[str, str] = {
    "last": "Giá đóng cửa gần nhất",
    "high_52w": "Đỉnh 52 tuần",
    "low_52w": "Đáy 52 tuần",
    "percentile": "Vị thế trong dải (%)",
    "off_high_pct": "Cách đỉnh 52 tuần (%)",
    "return_12m_pct": "Lợi nhuận 12 tháng (%)",
    "rsi_14": "RSI 14 phiên",
    "zone_low": "Đáy vùng giá đóng cửa tập trung",
    "zone_high": "Đỉnh vùng giá đóng cửa tập trung",
    "zone_sessions": "Số phiên trong vùng",
    "zone_window": "Số phiên đã xét",
}

BAND_LABELS: dict[str, str] = {
    "low": "Đáy 52 tuần",
    "high": "Đỉnh 52 tuần",
    "current": "Giá đóng cửa gần nhất",
    "percentile": "Vị thế trong dải (%)",
    "zone_low": "Đáy vùng giá đóng cửa tập trung",
    "zone_high": "Đỉnh vùng giá đóng cửa tập trung",
}

RATE_LABELS: dict[str, str] = {
    "percentile": "Vị thế trong dải 52 tuần",
    "return_12m_pct": "Lợi nhuận 12 tháng",
    "off_high_pct": "Cách đỉnh 52 tuần",
}

QUARTER_LABELS: dict[str, str] = {
    "quarter": "Quý",
    "net_profit_vnd": "Lợi nhuận sau thuế",
    "yoy_pct": "So cùng kỳ (%)",
}

EARNINGS_LABELS: dict[str, str] = {
    **QUARTER_LABELS,
    "improved": "Cao hơn cùng kỳ",
    "direction": "Chiều so cùng kỳ",
}

CHECKLIST_LABELS: dict[str, str] = {
    "label": "Điều kiện",
    "status": "Trạng thái",
    "value": "Mức đo được",
    "unit": "Đơn vị",
    "evidence": "Đối chiếu ở",
}


# -- the plan --------------------------------------------------------------


def _symbols(context: StudyContext) -> list[str]:
    return [context.params.symbol]


def _bar_arguments(context: StudyContext) -> dict[str, object]:
    # ``high`` and ``low`` as well as ``close`` because the 52-week band is the
    # extremes of the sessions rather than of their closes — a year's high is a
    # price something traded at, not the best close.
    return {
        "window": context.params.horizon_sessions,
        "columns": ["close", "high", "low"],
    }


def _enough_sessions(frame: Frame, context: StudyContext) -> None:
    """A year of sessions, or a refusal — never a shorter window relabelled."""
    position = frame.columns.index("session")
    sessions = len({row[position] for row in frame.rows})
    if sessions < MIN_SESSIONS:
        raise StudyRefused(
            SignalIssue.INSUFFICIENT_SESSIONS,
            f"{sessions} closed daily sessions stored for "
            f"{context.params.symbol}, {MIN_SESSIONS} needed for a 52-week "
            "review",
        )


def _quarter_label(period_end: date) -> str:
    return f"Q{(period_end.month - 1) // 3 + 1}/{period_end.year}"


def _read_quarters(context: StudyContext) -> tuple[Frame, Provenance]:
    """The stored quarters, oldest first, with the profit line already chosen.

    A read the query layer does not offer. ``query``'s ``statement`` source
    reads ``financial_statement_line`` — the filer's own template, line by line —
    and the earnings axis wants one figure per quarter under one definition:
    the profit a holder of the share owns, which is the parent line where a
    company files one and the consolidated line where it does not
    (``reads_fundamental.Quarter.net_profit_vnd``). Resolving that per filer is
    a fact about the store's shape rather than arithmetic, which is what makes
    it a read; the year-on-year comparison over these rows is arithmetic, and it
    goes through the sandbox like every other number here.
    """
    symbol = context.params.symbol
    quarters = reads_fundamental.quarters_for(context.session, symbol)
    rows = tuple(
        (_quarter_label(quarter.period_end), quarter.net_profit_vnd)
        for quarter in quarters
    )
    # Fewer than eight quarters means fewer than four comparable pairs, and the
    # earnings axis then answers "unknown" while the rest of the review still
    # answers. Roughly a thousand symbols in this store hold exactly one quarter,
    # so this is the ordinary case rather than the edge.
    thin = len(rows) < reads_fundamental.QUARTERS
    frame = Frame(
        kind="table",
        columns=("quarter", "net_profit_vnd"),
        rows=rows,
        unit="VND",
        labels={
            "quarter": QUARTER_LABELS["quarter"],
            "net_profit_vnd": QUARTER_LABELS["net_profit_vnd"],
        },
    )
    provenance = Provenance(
        source="store",
        as_of=context.as_of,
        sessions_used=len(rows),
        health="degraded" if thin else "normal",
        reason=(
            f"Mới có {len(rows)}/{reads_fundamental.QUARTERS} quý lợi nhuận "
            "đã lưu"
            if thin
            else None
        ),
        method_notes=QUARTER_METHOD_NOTES,
        query={"symbol": symbol, "quarters": reads_fundamental.QUARTERS},
    )
    return frame, provenance


# -- the assumptions the calculations are handed ---------------------------


def _windows(context: StudyContext) -> dict[str, Any]:
    """Every window and every threshold, declared where a reader can see it."""
    return {
        "range_sessions": RANGE_SESSIONS,
        "zone_sessions": ZONE_SESSIONS,
        "zone_bins": ZONE_BINS,
        "zone_band_bins": ZONE_BAND_BINS,
        "rsi_period": RSI_PERIOD,
        "rsi_window": RSI_WINDOW_SESSIONS,
        "figure_labels": FIGURE_LABELS,
    }


def _rounding(context: StudyContext) -> dict[str, Any]:
    return {
        "rate_digits": RATE_DIGITS,
        "price_digits": PRICE_DIGITS,
        "figure_labels": FIGURE_LABELS,
        "band_labels": BAND_LABELS,
        "rate_labels": RATE_LABELS,
    }


def _quarter_shape(context: StudyContext) -> dict[str, Any]:
    return {
        "rate_digits": RATE_DIGITS,
        "earnings_labels": EARNINGS_LABELS,
        "quarter_labels": QUARTER_LABELS,
    }


def _checklist(context: StudyContext) -> dict[str, Any]:
    return {
        "near_high_pct": NEAR_HIGH_PCT,
        "rsi_overbought": RSI_OVERBOUGHT,
        "rate_digits": RATE_DIGITS,
        "price_digits": PRICE_DIGITS,
        "condition_labels": list(CONDITION_LABELS),
        "condition_units": list(CONDITION_UNITS),
        "evidence_labels": list(CONDITION_EVIDENCE),
        "status_labels": STATUS_LABELS,
        "checklist_labels": CHECKLIST_LABELS,
    }


# -- the calculations ------------------------------------------------------


#: The four axes, as the arithmetic produced them and before anybody rounded.
#:
#: Raw on purpose. Every status below is a comparison against a threshold, and a
#: comparison against a figure that has already been rounded to two decimals is a
#: comparison that flips at ``-4,996`` — the reader is shown ``-5,00`` either way
#: and the tick changes. So the measurement stays here at full width and the
#: rounding happens once, in the step whose whole job is what a person sees.
#:
#: A zero-width band answers a position of a hundred: the price is at the high,
#: which is also the low, and a null there would make every condition downstream
#: unknown for a symbol that traded at one price all year.
_MOMENTUM_CODE = """
ordered = f0.sort_values("session")
closes = ordered["close"].astype("float64").to_list()
last = closes[-1]

year = ordered.tail(range_sessions)
year_closes = closes[-range_sessions:]
high_52w = float(year["high"].astype("float64").max())
low_52w = float(year["low"].astype("float64").min())
span = high_52w - low_52w
percentile = 100.0 if span <= 0 else (last - low_52w) / span * 100
off_high_pct = (last - high_52w) / high_52w * 100 if high_52w > 0 else 0.0
first_of_year = year_closes[0]
return_12m_pct = (last / first_of_year - 1) * 100 if first_of_year > 0 else None

recent = closes[-rsi_window:]
changes = [later - earlier for earlier, later in zip(recent, recent[1:])]
gains = [max(change, 0.0) for change in changes]
losses = [max(-change, 0.0) for change in changes]
rsi_14 = None
if len(recent) > rsi_period:
    average_gain = sum(gains[:rsi_period]) / rsi_period
    average_loss = sum(losses[:rsi_period]) / rsi_period
    for gain, loss in zip(gains[rsi_period:], losses[rsi_period:]):
        average_gain = (average_gain * (rsi_period - 1) + gain) / rsi_period
        average_loss = (average_loss * (rsi_period - 1) + loss) / rsi_period
    if average_loss == 0:
        rsi_14 = None if average_gain == 0 else 100.0
    else:
        rsi_14 = 100.0 - 100.0 / (1.0 + average_gain / average_loss)

zone_closes = closes[-zone_sessions:]
zone_floor = min(zone_closes)
zone_ceiling = max(zone_closes)
if zone_ceiling <= zone_floor:
    zone_low = zone_floor
    zone_high = zone_ceiling
    zone_inside = len(zone_closes)
else:
    width = (zone_ceiling - zone_floor) / zone_bins
    counts = [0] * zone_bins
    for close in zone_closes:
        slot = min(int((close - zone_floor) / width), zone_bins - 1)
        counts[slot] = counts[slot] + 1
    best = 0
    best_count = -1
    for start in range(zone_bins - zone_band_bins + 1):
        inside = sum(counts[start:start + zone_band_bins])
        if inside > best_count:
            best_count = inside
            best = start
    zone_low = zone_floor + best * width
    zone_high = zone_floor + (best + zone_band_bins) * width
    zone_inside = best_count

result = pd.DataFrame(
    [
        {
            "last": last,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "percentile": percentile,
            "off_high_pct": off_high_pct,
            "return_12m_pct": return_12m_pct,
            "rsi_14": rsi_14,
            "zone_low": zone_low,
            "zone_high": zone_high,
            "zone_sessions": zone_inside,
            "zone_window": len(zone_closes),
        }
    ]
)
result.attrs["labels"] = figure_labels
"""


#: The same eleven figures at the width a person reads them, rounded once.
#:
#: One rounding step rather than one per consumer: the band, the strip, the
#: checklist and the headline all quote these numbers, and four roundings of one
#: figure are four chances for the panel to disagree with itself by a đồng.
_READINGS_CODE = """
row = f0.iloc[0]


def present(value):
    return value is not None and value == value


def rate(value):
    return None if not present(value) else round(value, rate_digits)


def price(value):
    return None if not present(value) else round(value, price_digits)


def count(value):
    return None if not present(value) else int(value)


result = pd.DataFrame(
    [
        {
            "last": price(row["last"]),
            "high_52w": price(row["high_52w"]),
            "low_52w": price(row["low_52w"]),
            "percentile": rate(row["percentile"]),
            "off_high_pct": rate(row["off_high_pct"]),
            "return_12m_pct": rate(row["return_12m_pct"]),
            "rsi_14": rate(row["rsi_14"]),
            "zone_low": price(row["zone_low"]),
            "zone_high": price(row["zone_high"]),
            "zone_sessions": count(row["zone_sessions"]),
            "zone_window": count(row["zone_window"]),
        }
    ]
)
result.attrs["labels"] = figure_labels
"""


#: The band, the marker and the cluster — one row, because it is one picture.
_RANGE_BAND_CODE = """
result = f0[
    ["low_52w", "high_52w", "last", "percentile", "zone_low", "zone_high"]
].rename(columns={"low_52w": "low", "high_52w": "high", "last": "current"})
result.attrs["unit"] = "VND"
result.attrs["labels"] = band_labels
"""


#: The three percentages, on a frame whose unit says they are percentages.
#:
#: A frame carries one unit and the band carries đồng, so a position read out of
#: it would be formatted as money — ``29`` where a reader is owed ``29,4%``. The
#: strip reads percentages, so the percentages are a frame. Nothing draws it; it
#: exists to be quoted.
_RATES_CODE = """
result = f0[["percentile", "return_12m_pct", "off_high_pct"]].copy()
result.attrs["unit"] = "%"
result.attrs["labels"] = rate_labels
"""


#: The horizon the model asked for, as the line the band is read against.
_PRICE_CONTEXT_CODE = """
ordered = f0.sort_values("session")
result = pd.DataFrame(
    {
        "session": ordered["session"].to_list(),
        "close": ordered["close"].astype("float64").round().to_list(),
    }
)
result.attrs["unit"] = "VND"
result.attrs["labels"] = {"session": "Phiên", "close": "Giá đóng cửa"}
"""


#: Eight quarters, each against the same quarter a year earlier.
#:
#: ``yoy_pct`` needs a positive base: the percentage change from a loss is a
#: number a reader cannot use, and printing one is how a swing from -100 to +50
#: becomes "up 150%". ``improved`` is the sign of the change, which is defined
#: whatever the two signs are, and it is what the trend is classified on.
#:
#: ``direction`` is the same sign again as a role word, and it is computed here
#: rather than in the step that draws the bars so that the bar's colour and the
#: column beside it can never disagree. Nothing at zero as well as at nothing: a
#: quarter that matched the year before did not rise, and painting it in the up
#: colour because it is not negative would put a claim on the one number that
#: makes none.
_EARNINGS_CODE = """
profit = pd.to_numeric(f0["net_profit_vnd"], errors="coerce")
prior = profit.shift(4)
comparable = profit.notna() & prior.notna()
quarters = f0["quarter"].to_list()
profits = profit.to_list()
priors = prior.to_list()
flags = comparable.to_list()

yoy = []
improved = []
direction = []
for index in range(len(quarters)):
    if not flags[index]:
        improved.append(None)
        yoy.append(None)
        direction.append(None)
    else:
        current = profits[index]
        base = priors[index]
        change = (current / base - 1) * 100 if base > 0 else None
        improved.append(bool(current > base))
        yoy.append(None if change is None else round(change, rate_digits))
        if change is None or change == 0:
            direction.append(None)
        else:
            direction.append("up" if change > 0 else "down")

result = pd.DataFrame(
    {
        "quarter": quarters,
        "net_profit_vnd": profits,
        "yoy_pct": yoy,
        "improved": improved,
        "direction": direction,
    }
)
result.attrs["unit"] = "VND"
result.attrs["labels"] = earnings_labels
"""


#: The same quarters as the picture draws them.
#:
#: **A bar's colour is its year-on-year direction, never its height.** The bar is
#: the quarter's profit and the colour is whether that profit beat the same
#: quarter a year earlier, which is the comparison the column beside it makes and
#: the only one a season of earnings supports: four quarters read left to right
#: are four different seasons, and the tallest of them is usually just the
#: busiest one. A quarter with no comparable predecessor is left unpainted.
_EARNINGS_QUARTERS_CODE = """
result = f0[["quarter", "net_profit_vnd", "yoy_pct"]].copy()
result.attrs["unit"] = "VND"
result.attrs["labels"] = quarter_labels
result.attrs["point_roles"] = [
    None if role is None or role != role else role
    for role in f0["direction"].to_list()
]
"""


#: Six statements, in the order a reader meets the axes on the board.
#:
#: Every status is a comparison; none of them is a judgement. A missing input is
#: "chưa rõ" and never "chưa đạt" — those are different claims, and the second
#: one would make a company that has not filed look like a company whose profit
#: fell.
_CONDITIONS_CODE = """
def present(value):
    return value is not None and value == value


def status(held):
    if held is None:
        return status_labels["unknown"]
    if held:
        return status_labels["met"]
    return status_labels["not_met"]


def rate(value):
    return None if not present(value) else round(value, rate_digits)


def price(value):
    return None if not present(value) else round(value, price_digits)


row = f0.iloc[0]
last = row["last"]
off_high = row["off_high_pct"]
zone_low = row["zone_low"]
zone_high = row["zone_high"]
return_12m = row["return_12m_pct"]
rsi = row["rsi_14"]

latest_profit = None
latest_yoy = None
latest_improved = None
if len(f1) > 0:
    latest = f1.iloc[-1]
    latest_profit = latest["net_profit_vnd"]
    latest_yoy = latest["yoy_pct"]
    latest_improved = latest["improved"]

in_zone = None
if present(last) and present(zone_low) and present(zone_high):
    in_zone = bool(zone_low <= last) and bool(last <= zone_high)

rows = [
    [
        condition_labels[0],
        status(None if not present(off_high) else bool(off_high <= -near_high_pct)),
        rate(off_high),
        condition_units[0],
        evidence_labels[0],
    ],
    [
        condition_labels[1],
        status(in_zone),
        price(last),
        condition_units[1],
        evidence_labels[1],
    ],
    [
        condition_labels[2],
        status(None if not present(return_12m) else bool(return_12m > 0)),
        rate(return_12m),
        condition_units[2],
        evidence_labels[2],
    ],
    [
        condition_labels[3],
        status(None if not present(rsi) else bool(rsi < rsi_overbought)),
        rate(rsi),
        condition_units[3],
        evidence_labels[3],
    ],
    [
        condition_labels[4],
        status(None if not present(latest_profit) else bool(latest_profit > 0)),
        None if not present(latest_profit) else float(latest_profit),
        condition_units[4],
        evidence_labels[4],
    ],
    [
        condition_labels[5],
        status(None if not present(latest_improved) else bool(latest_improved)),
        rate(latest_yoy),
        condition_units[5],
        evidence_labels[5],
    ],
]
result = pd.DataFrame(
    rows, columns=["label", "status", "value", "unit", "evidence"]
)
result.attrs["labels"] = checklist_labels
"""


PLAN = (
    QueryStep(
        name="bars",
        title="Phiên ngày đã đóng",
        source="bar_daily",
        symbols=_symbols,
        arguments=_bar_arguments,
        check=_enough_sessions,
    ),
    ReadStep(
        name="quarters",
        title="Lợi nhuận từng quý đã lưu",
        read=_read_quarters,
    ),
    ComputeStep(
        name="momentum",
        title="Bốn trục đo, chưa làm tròn",
        code=_MOMENTUM_CODE,
        inputs=("bars",),
        constants=_windows,
        output_kind="table",
        # The four sentences the hand-written Study put on the strip. They belong
        # to this step because all four describe how *these* axes were measured,
        # and no layer that builds a step's provenance on its own could know
        # them: the reader describes a table and the sandbox describes a
        # calculation. Declared notes lead the merged strip, so the six-note cap
        # falls on the engine's digest lines rather than on these.
        method_notes=MOMENTUM_METHOD_NOTES,
    ),
    ComputeStep(
        name="readings",
        title="Các mức đo được",
        code=_READINGS_CODE,
        inputs=("momentum",),
        constants=_rounding,
        output_kind="table",
    ),
    ComputeStep(
        name="range_band",
        title="Dải giá 52 tuần",
        code=_RANGE_BAND_CODE,
        inputs=("readings",),
        constants=_rounding,
        output_kind="table",
    ),
    ComputeStep(
        name="rates",
        title="Ba mức theo phần trăm",
        code=_RATES_CODE,
        inputs=("readings",),
        constants=_rounding,
        output_kind="table",
    ),
    ComputeStep(
        name="price_context",
        title="Đường giá đóng cửa",
        code=_PRICE_CONTEXT_CODE,
        # No assumptions: the line is the window the model asked for, drawn at
        # the width a share is quoted in, and a step that declared one would put
        # "this calculation used an assumption" on a strip where it is not true.
        inputs=("bars",),
        output_kind="series",
    ),
    ComputeStep(
        name="earnings",
        title="Lợi nhuận quý so cùng kỳ",
        code=_EARNINGS_CODE,
        inputs=("quarters",),
        constants=_quarter_shape,
        output_kind="table",
    ),
    ComputeStep(
        name="earnings_quarters",
        title="Lợi nhuận theo quý",
        code=_EARNINGS_QUARTERS_CODE,
        inputs=("earnings",),
        constants=_quarter_shape,
        output_kind="series",
    ),
    ComputeStep(
        name="conditions",
        title="Bảng điều kiện",
        code=_CONDITIONS_CODE,
        inputs=("momentum", "earnings"),
        constants=_checklist,
        output_kind="table",
    ),
)


#: Five figures, the band, the line, the quarters and the checklist.
#:
#: The checklist is last on purpose. It is the block a reader will look at first
#: and the one that means least without the measurements above it, and putting it
#: at the top would invite reading six ticks as a verdict.
#:
#: No KPI carries a role. The v1 tiles painted the twelve-month return by its
#: sign, and a board's roles are written before the numbers are known — so the
#: only honest choices here are a colour that is sometimes a lie and no colour at
#: all. The one place the sign is still painted is the earnings bars, where the
#: role is computed beside the number it describes.
BOARD = {
    "title": "Điều kiện hiện tại — {symbol}",
    "archetype": "profile",
    "kpis": [
        {
            "label": "Giá đóng cửa gần nhất",
            "value": {"frame_id": "range_band", "column": "current", "row": 0},
        },
        {
            "label": "Vị thế trong dải 52 tuần",
            "value": {"frame_id": "rates", "column": "percentile", "row": 0},
        },
        {
            "label": "Lợi nhuận 12 tháng",
            "value": {"frame_id": "rates", "column": "return_12m_pct", "row": 0},
        },
        {
            "label": "Cách đỉnh 52 tuần",
            "value": {"frame_id": "rates", "column": "off_high_pct", "row": 0},
        },
        {
            "label": "RSI 14 phiên",
            "value": {"frame_id": "readings", "column": "rsi_14", "row": 0},
        },
    ],
    "sections": [
        {
            "heading": "Vị thế giá",
            "blocks": [
                # The one widget hint whose frame would otherwise be read wrong:
                # a table of one row is a tile strip by shape, and these six
                # numbers are a ruler with a mark on it.
                {
                    "kind": "visual",
                    "frame_id": "range_band",
                    "widget": "range_strip",
                },
                {
                    "kind": "visual",
                    "frame_id": "price_context",
                    "columns": ["session", "close"],
                },
            ],
        },
        {
            "heading": "Lợi nhuận theo quý",
            "blocks": [
                # Eight quarters against a time axis read as a line by shape, and
                # a line between two seasons implies a path the business did not
                # take. They are groups being compared, so they are bars.
                {
                    "kind": "visual",
                    "frame_id": "earnings_quarters",
                    "widget": "bar_series",
                    "columns": ["quarter", "net_profit_vnd"],
                },
            ],
        },
        {
            "heading": "Bảng điều kiện",
            "blocks": [
                {"kind": "visual", "frame_id": "conditions"},
                {"kind": "caption", "template": CHECKLIST_NOTE},
            ],
        },
    ],
    "appendix_frame_id": None,
}


def headline(params, frames):
    """The three hundred tokens the model reads, out of the frames and nothing else.

    Handed the frames rather than the numbers, so every figure here came out of a
    cell a picture also draws or a cell the strip quotes. Nothing is rounded on
    the way through: the readings were rounded once, in the sandbox, and rounding
    again here would be a second author of the same number.
    """
    readings = _first(frames["readings"])
    sessions = _rows(frames["price_context"])
    quarters = _rows(frames["earnings"])
    conditions = _rows(frames["conditions"])
    latest = quarters[-1] if quarters else None
    return {
        "symbol": params.symbol,
        "asOfSession": sessions[-1]["session"] if sessions else None,
        "sessionsUsed": len(sessions),
        "pricePosition": {
            "last": readings["last"],
            "high52w": readings["high_52w"],
            "low52w": readings["low_52w"],
            "percentile": readings["percentile"],
            "offHighPct": readings["off_high_pct"],
            "return12mPct": readings["return_12m_pct"],
            "rsi14": readings["rsi_14"],
            "closeCluster": {
                "low": readings["zone_low"],
                "high": readings["zone_high"],
                "sessions": (
                    f"{readings['zone_sessions']}/{readings['zone_window']}"
                ),
            },
        },
        "earningsTrend": _trend(quarters),
        "latestQuarter": (
            None
            if latest is None
            else {
                "period": latest["quarter"],
                "netProfitVnd": latest["net_profit_vnd"],
                "yoyPct": latest["yoy_pct"],
            }
        ),
        # Counts first, because a count is the whole of what this Study concludes.
        # The items travel with them because the model is asked to narrate which
        # conditions hold, and a model handed three integers would have to invent
        # the sentences — these are the fixed ones.
        "conditions": {
            **_tally(conditions),
            "items": [
                {
                    "label": row["label"],
                    "status": STATUS_TOKENS.get(row["status"], "unknown"),
                }
                for row in conditions
            ],
        },
    }


def _rows(frame):
    columns = list(frame["columns"])
    return [dict(zip(columns, row)) for row in frame["rows"]]


def _first(frame):
    rows = _rows(frame)
    return rows[0] if rows else {}


def _trend(quarters):
    """Four year-on-year readings, or ``unknown`` — never a partial verdict.

    Fewer than four comparable pairs means fewer than four readings, and three
    quarters of a trend read as a trend while being a different claim.
    """
    recent = [quarter["improved"] for quarter in quarters[-4:]]
    if len(recent) < 4 or any(flag is None for flag in recent):
        return "unknown"
    if all(recent):
        return "improving"
    if not any(recent):
        return "deteriorating"
    return "mixed"


def _tally(conditions):
    tokens = [
        STATUS_TOKENS.get(row["status"], "unknown") for row in conditions
    ]
    return {
        "met": tokens.count("met"),
        "notMet": tokens.count("not_met"),
        "unknown": tokens.count("unknown"),
    }


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
        archetype="profile",
        plan=PLAN,
        board=BOARD,
        headline=headline,
    )
)


__all__ = [
    "CHECKLIST_NOTE",
    "CONDITION_LABELS",
    "DEFINITION",
    "MIN_SESSIONS",
    "NAME",
    "PLAN",
    "RSI_PERIOD",
    "RSI_WINDOW_SESSIONS",
    "VERSION",
    "ZONE_BINS",
    "ZONE_SESSIONS",
]
