"""Contracts for the Vietnamese trading calendar and how it reaches the prompt.

The bug these pin down: asked "hôm nay thị trường ra sao?" on a holiday, the
agent narrated a session that did not happen, because price boards keep showing
the last session's figures without a date and the only date in the prompt was
today's.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.agent.domain.trading_calendar import (
    COVERED_YEARS,
    HOLIDAYS,
    market_day,
    previous_trading_day,
)
from src.agent.prompt import MarketDay, MarketPhase, RuntimeContext, prefix, render


def test_national_day_break_is_closed_and_names_the_occasion():
    day = market_day(date(2026, 8, 31))
    assert day.phase is MarketPhase.CLOSED_HOLIDAY
    assert day.holiday == "Quốc khánh"
    # The Friday before the Monday holiday, not the Sunday in between.
    assert day.previous_trading_day == date(2026, 8, 28)


@pytest.mark.parametrize(
    "day",
    (date(2026, 8, 31), date(2026, 9, 1), date(2026, 9, 2)),
)
def test_every_day_of_the_break_is_closed(day: date):
    assert market_day(day).phase is MarketPhase.CLOSED_HOLIDAY


def test_the_session_after_the_break_is_open():
    day = market_day(date(2026, 9, 3))
    assert day.phase is MarketPhase.OPEN
    assert day.holiday is None
    assert day.previous_trading_day is None


def test_weekends_are_closed_without_consulting_the_holiday_table():
    saturday = market_day(date(2026, 8, 29))
    assert saturday.phase is MarketPhase.CLOSED_WEEKEND
    assert saturday.previous_trading_day == date(2026, 8, 28)


def test_weekend_rule_still_holds_outside_the_covered_years():
    """A Saturday is a Saturday in a year the holiday table cannot speak for."""
    far_saturday = date(2031, 1, 4)
    assert far_saturday.year not in COVERED_YEARS
    assert far_saturday.weekday() == 5
    assert market_day(far_saturday).phase is MarketPhase.CLOSED_WEEKEND


def test_a_weekday_outside_the_covered_years_is_unknown_not_open():
    """The table going stale must not read as a confident "open"."""
    far_weekday = date(2031, 1, 6)
    assert far_weekday.year not in COVERED_YEARS
    day = market_day(far_weekday)
    assert day.phase is MarketPhase.UNKNOWN
    assert day.previous_trading_day is None


def test_tet_closes_five_trading_days_in_a_row():
    for day in range(16, 21):
        assert market_day(date(2026, 2, day)).phase is MarketPhase.CLOSED_HOLIDAY
    assert market_day(date(2026, 2, 23)).phase is MarketPhase.OPEN
    # The session before the whole nine-day break is the Friday of the week
    # before, which only a walk over both weekends and holidays finds.
    assert previous_trading_day(date(2026, 2, 16)) == date(2026, 2, 13)


def test_the_makeup_saturday_holds_no_session():
    assert date(2026, 8, 22) in HOLIDAYS
    assert market_day(date(2026, 8, 22)).phase is MarketPhase.CLOSED_WEEKEND


def test_previous_session_is_unknown_when_the_walk_leaves_covered_years():
    """New Year's Day: the previous session sits in a year with no table."""
    assert previous_trading_day(date(2026, 1, 1)) is None


# -- what the model is actually told ---------------------------------------


def test_closed_day_reaches_the_prompt_with_its_previous_session():
    rendered = render(
        RuntimeContext(today=date(2026, 8, 31), market=market_day(date(2026, 8, 31)))
    )
    assert "- market_today: closed_holiday (Quốc khánh)" in rendered
    assert "- previous_trading_day: 2026-08-28" in rendered


def test_an_open_day_names_no_previous_session():
    rendered = render(
        RuntimeContext(today=date(2026, 9, 3), market=market_day(date(2026, 9, 3)))
    )
    assert "- market_today: open" in rendered
    # The name appears in the prose that explains the labels; what an open day
    # must not carry is the value line.
    assert "- previous_trading_day:" not in rendered


def test_a_caller_that_forgets_the_market_gets_unknown_not_silence():
    """There is no state in which the prompt simply says nothing about trading."""
    rendered = render(RuntimeContext(today=date(2026, 8, 31)))
    assert "- market_today: unknown" in rendered


def test_trading_status_stays_out_of_the_cacheable_prefix():
    """The prose explaining the labels is stable; only the values vary.

    A prefix that carried the day's status would void the cache daily and, worse,
    could be reused across a day boundary.
    """
    stable = prefix()
    assert "- market_today:" not in stable
    assert "closed_holiday (" not in stable
    assert "2026-08-28" not in stable


def test_an_open_day_cannot_carry_a_previous_session():
    with pytest.raises(ValueError):
        MarketDay(phase=MarketPhase.OPEN, previous_trading_day=date(2026, 8, 28))


def test_only_a_holiday_closure_names_a_holiday():
    with pytest.raises(ValueError):
        MarketDay(phase=MarketPhase.CLOSED_WEEKEND, holiday="Quốc khánh")
