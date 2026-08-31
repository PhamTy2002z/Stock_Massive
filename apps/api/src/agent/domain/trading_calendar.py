"""Which calendar days the Vietnamese equity market actually trades.

The harness learned this the expensive way. Asked "hôm nay thị trường ra sao?"
on 31/8/2026 — the first day of the National Day break — the agent narrated a
trading session that did not happen, in three runs out of five. One of the three
had already fetched HOSE's own holiday notice and narrated the phantom session
anyway.

The mechanism is worth stating precisely, because it decides where the fix
belongs. Vietnamese price boards (vneconomy, investing, 24h) keep showing the
last session's numbers when the market is shut, and most of them print no
session date beside those numbers. The model reads a figure with no date on it,
reaches for the only date it has — ``today`` from the system prompt — and staples
the two together. Nothing in the transcript is false on its own; the label is.

So the missing fact is not "what happened today". It is "is there a today to
have happened", and no tool in the catalog answers that. That puts it in the
same class as ``today`` itself: a value the harness must supply, in the trusted
half of the prompt, because a page saying so in ``untrusted_tool_result`` has
already been shown not to be enough.

**Weekends are derived; holidays are data.** A Saturday is a Saturday in every
year, so :func:`market_day` answers that from the date alone and keeps
answering it correctly long after this file stops being maintained. Holidays are
a published list that changes annually, so they carry :data:`COVERED_YEARS` with
them, and a date outside those years resolves to
:attr:`MarketPhase.UNKNOWN` rather than to a confident wrong answer. A stale
table that still sounds certain would be worse than the bug this module fixes.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..prompt.contract import MarketDay, MarketPhase

#: Years :data:`HOLIDAYS` is complete for. A date in any other year gets
#: :attr:`MarketPhase.UNKNOWN` unless the weekend rule already settled it.
COVERED_YEARS = frozenset({2026})

#: Non-trading days announced by HOSE for 2026, cross-checked against two
#: independent reports of the same notice.
#:
#: 22/8/2026 is the odd one: a Saturday made a working day by the National Day
#: schedule swap, on which HOSE still holds no session. The weekend rule covers
#: it, and it is listed anyway so a reader comparing this table against the
#: notice finds every line of the notice in it.
HOLIDAYS: dict[date, str] = {
    date(2026, 1, 1): "Tết Dương lịch",
    date(2026, 2, 16): "Tết Nguyên đán",
    date(2026, 2, 17): "Tết Nguyên đán",
    date(2026, 2, 18): "Tết Nguyên đán",
    date(2026, 2, 19): "Tết Nguyên đán",
    date(2026, 2, 20): "Tết Nguyên đán",
    date(2026, 4, 27): "Giỗ Tổ Hùng Vương",
    date(2026, 4, 30): "Ngày Giải phóng miền Nam",
    date(2026, 5, 1): "Ngày Quốc tế Lao động",
    date(2026, 8, 22): "ngày làm bù, không tổ chức giao dịch",
    date(2026, 8, 31): "Quốc khánh",
    date(2026, 9, 1): "Quốc khánh",
    date(2026, 9, 2): "Quốc khánh",
}

#: How far back :func:`market_day` will walk to name the previous session. Tết
#: closes the market for five trading days inside nine calendar days, so a
#: fortnight is the real bound with room to spare; the constant exists so the
#: walk cannot become unbounded if the table ever gains a longer break.
_MAX_LOOKBACK_DAYS = 21


def _is_weekend(day: date) -> bool:
    return day.weekday() >= 5


def _is_closed(day: date) -> bool:
    """Whether the market is shut on a day this table can speak for.

    Callers must have established that ``day`` is inside :data:`COVERED_YEARS`;
    outside them a ``False`` here would mean "open" when it means "unknown".
    """
    return _is_weekend(day) or day in HOLIDAYS


def previous_trading_day(today: date) -> date | None:
    """The last session strictly before ``today``, when it can be known.

    ``None`` rather than a guess whenever the walk would leave the years the
    holiday table covers — including the common case of a January date whose
    previous session sits in an uncovered December.
    """
    if today.year not in COVERED_YEARS:
        return None
    day = today
    for _ in range(_MAX_LOOKBACK_DAYS):
        day -= timedelta(days=1)
        if day.year not in COVERED_YEARS:
            return None
        if not _is_closed(day):
            return day
    return None


def market_day(today: date) -> MarketDay:
    """What the harness knows about trading on ``today``.

    The weekend test runs first and without consulting the table, so the
    answer stays right for every year rather than only for the maintained ones.
    """
    if _is_weekend(today):
        return MarketDay(
            phase=MarketPhase.CLOSED_WEEKEND,
            previous_trading_day=previous_trading_day(today),
        )
    if today.year not in COVERED_YEARS:
        return MarketDay(phase=MarketPhase.UNKNOWN)
    holiday = HOLIDAYS.get(today)
    if holiday is not None:
        return MarketDay(
            phase=MarketPhase.CLOSED_HOLIDAY,
            holiday=holiday,
            previous_trading_day=previous_trading_day(today),
        )
    return MarketDay(phase=MarketPhase.OPEN)


__all__ = ["COVERED_YEARS", "HOLIDAYS", "market_day", "previous_trading_day"]
