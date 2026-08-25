"""Deterministic cross-sectional calculations for Market Monitor lenses."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.stocks.monitor.analytics import (
    advance_decline_line,
    breadth,
    index_pulse,
    sector_rotation,
    stock_readings,
    valuation_regime,
)
from src.stocks.monitor.frames import PreparedSymbol, ValuationObservation
from src.stocks.providers.contracts import Exchange
from src.stocks.signals.bars import Bar, BarFrame
from src.stocks.signals.price_band import LimitLock


START = date(2025, 9, 1)


def frame(
    symbol: str,
    closes: list[float],
    *,
    exchange: Exchange = Exchange.HOSE,
    sector: str = "10",
    values: list[float] | None = None,
    foreign: list[float] | None = None,
) -> PreparedSymbol:
    values = values or [1_000_000.0] * len(closes)
    foreign = foreign or [0.0] * len(closes)
    bars = tuple(
        Bar(
            session_date=START + timedelta(days=index),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=100,
            total_value_vnd=values[index],
            adjustment_factor=Decimal(1),
            limit_lock=LimitLock.NONE,
            foreign_net_value_vnd=foreign[index],
            change_pct=None,
        )
        for index, close in enumerate(closes)
    )
    return PreparedSymbol(
        symbol=symbol,
        name=symbol,
        exchange=exchange,
        sector_code=sector,
        sector_name=f"Sector {sector}",
        frame=BarFrame(symbol=symbol, bars=bars),
    )


def test_breadth_counts_direction_trend_highs_and_liquidity() -> None:
    rising = frame("AAA", list(range(1, 203)), values=[100.0] * 201 + [200.0])
    falling = frame("BBB", list(range(203, 1, -1)))
    flat = frame("CCC", [10.0] * 202)

    result = breadth((rising, falling, flat))

    assert (result.advancing, result.declining, result.unchanged) == (1, 1, 1)
    assert result.advance_decline_ratio == 1.0
    assert result.above_ma20_pct == pytest.approx(100 / 3)
    assert result.above_ma50_pct == pytest.approx(100 / 3)
    assert result.above_ma200_pct == pytest.approx(100 / 3)
    assert result.new_high_20 == 1
    assert result.new_low_20 == 1
    assert result.new_high_252 is None
    assert result.new_low_252 is None
    assert result.liquidity_ratio == pytest.approx((2.0 + 1.0 + 1.0) / 3)


def test_breadth_refuses_ratio_when_no_symbol_declines() -> None:
    result = breadth((frame("AAA", [1.0, 2.0]), frame("BBB", [1.0, 1.0])))

    assert result.advance_decline_ratio is None
    assert "declining_zero" in result.issues
    assert result.above_ma20_pct is None


def test_sector_rotation_uses_median_return_and_index_relative_strength() -> None:
    bank_a = frame("AAA", [100.0] * 21 + [110.0], sector="10")
    bank_b = frame("BBB", [100.0] * 21 + [120.0], sector="10")
    retail = frame("CCC", [100.0] * 21 + [90.0], sector="20")
    vnindex = frame("VNINDEX", [100.0] * 21 + [105.0], sector="INDEX")

    sectors = sector_rotation((bank_a, bank_b, retail), {Exchange.HOSE: vnindex})

    bank = next(item for item in sectors if item.code == "10")
    assert bank.return_1d_pct == pytest.approx(15.0)
    assert bank.relative_strength_1d_pct == pytest.approx(10.0)
    assert bank.relative_strength_5d_pct == pytest.approx(10.0)
    assert bank.relative_strength_20d_pct == pytest.approx(10.0)
    assert bank.advancing_pct == 100.0
    assert bank.rotation == "leading"


def test_valuation_regime_excludes_non_positive_and_reports_percentile() -> None:
    points = (
        ValuationObservation(START, "AAA", "10", 8.0, 1.0),
        ValuationObservation(START, "BBB", "10", 12.0, 2.0),
        ValuationObservation(START, "CCC", "20", -1.0, None),
        ValuationObservation(START + timedelta(days=1), "AAA", "10", 15.0, 2.0),
        ValuationObservation(START + timedelta(days=1), "BBB", "10", 25.0, 4.0),
    )

    result = valuation_regime(points, eligible=3, minimum_history_sessions=2)

    assert result.market_pe == 20.0
    assert result.market_pb == 3.0
    assert result.pe_percentile == 100.0
    assert result.pb_percentile == 100.0
    assert result.evaluated == 2
    assert result.eligible == 3


def test_valuation_regime_refuses_short_history_and_uses_market_eligibility() -> None:
    points = (ValuationObservation(START, "AAA", "10", 12.0, 1.5),)

    result = valuation_regime(points, eligible=329)

    assert result.eligible == 329
    assert result.evaluated == 1
    assert result.pe_percentile is None
    assert result.pb_percentile is None
    assert result.history_sessions == 1


def test_index_pulse_and_advance_decline_line_are_session_deterministic() -> None:
    rising = frame("AAA", [10.0, 11.0, 12.0])
    falling = frame("BBB", [10.0, 9.0, 8.0])
    benchmark = frame("VNINDEX", [100.0, 101.0, 103.0], sector="INDEX")

    pulse = index_pulse(benchmark)
    line = advance_decline_line((rising, falling))

    assert pulse.level == 103.0
    assert pulse.change == 2.0
    assert pulse.change_pct == pytest.approx(200 / 101)
    assert [(point.advancing, point.declining, point.cumulative) for point in line] == [
        (1, 1, 0),
        (1, 1, 0),
    ]


def test_stock_readings_filter_and_sort_without_fabricating_missing_flow() -> None:
    inflow = frame(
        "AAA",
        [100.0] * 21 + [110.0],
        values=[100.0] * 22,
        foreign=[1.0] * 22,
    )
    missing = frame(
        "BBB",
        [100.0] * 21 + [90.0],
        sector="20",
        foreign=[0.0] * 21 + [None],
    )

    rows = stock_readings(
        (inflow, missing),
        sector_code=None,
        sort_by="return_1d_pct",
        descending=True,
    )

    assert [row.symbol for row in rows] == ["AAA", "BBB"]
    assert rows[0].foreign_net_20d_vnd == 20.0
    assert rows[0].foreign_flow_over_adtv == pytest.approx(0.2)
    assert rows[1].foreign_net_1d_vnd is None
    assert "foreign_flow_not_stored" in rows[1].issues
    assert [row.symbol for row in stock_readings((inflow, missing), sector_code="20")] == [
        "BBB"
    ]
