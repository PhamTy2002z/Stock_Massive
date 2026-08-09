"""Tests for pivoting the provider's metrics-by-period ratio frame.

The frames here copy the real provider response shape: metric rows labelled by
`item`/`item_id`, period columns out of order, and a repeated period carrying
the `_1` suffix.
"""
import pandas as pd

from src.stocks.financial.ratio_frame import (
    is_wide_ratio_frame,
    wide_ratio_frame_to_records,
)


def _frame():
    return pd.DataFrame(
        {
            "item": ["P/E", "P/B", "ROE 4 quý"],
            "item_id": ["pe_ratio", "pb_ratio", "roe_trailling"],
            "2026-Q2": [12.38, 2.33, 16.72],
            "2025-Q4": [10.60, 2.61, 17.51],
            "2026-Q1": [11.10, 2.40, 17.00],
            "2025-Q4_1": [99.0, 99.0, 99.0],
        }
    )


def test_a_period_per_row_frame_is_left_alone():
    narrow = pd.DataFrame({"yearReport": [2026], "P/E": [12.38]})
    assert is_wide_ratio_frame(narrow) is False
    assert is_wide_ratio_frame(_frame()) is True


def test_records_come_back_newest_first_regardless_of_column_order():
    records = wide_ratio_frame_to_records(_frame(), periods=3)

    assert [r["period"] for r in records] == ["2026-Q2", "2026-Q1", "2025-Q4"]
    assert [(r["year"], r["quarter"]) for r in records] == [
        (2026, 2),
        (2026, 1),
        (2025, 4),
    ]


def test_metrics_are_keyed_by_provider_id():
    newest = wide_ratio_frame_to_records(_frame(), periods=1)[0]

    assert newest["pe_ratio"] == 12.38
    assert newest["pb_ratio"] == 2.33
    assert newest["roe_trailling"] == 16.72


def test_a_repeated_period_does_not_displace_a_real_one():
    """`2025-Q4_1` restates Q4; it must not occupy a second slot."""
    records = wide_ratio_frame_to_records(_frame(), periods=4)

    assert len(records) == 3
    assert records[-1]["pe_ratio"] == 10.60


def test_periods_caps_how_many_records_are_built():
    assert len(wide_ratio_frame_to_records(_frame(), periods=1)) == 1
    assert wide_ratio_frame_to_records(_frame(), periods=0) == []


def test_missing_values_become_none_rather_than_nan():
    frame = _frame()
    frame.loc[0, "2026-Q2"] = float("nan")

    newest = wide_ratio_frame_to_records(frame, periods=1)[0]

    assert newest["pe_ratio"] is None


def test_an_annual_frame_sorts_by_year():
    annual = pd.DataFrame(
        {
            "item_id": ["pe_ratio"],
            "2024": [9.0],
            "2026": [12.0],
            "2025": [10.0],
        }
    )

    records = wide_ratio_frame_to_records(annual, periods=3)

    assert [r["period"] for r in records] == ["2026", "2025", "2024"]
    assert records[0]["quarter"] is None


def test_an_empty_frame_yields_no_records():
    assert wide_ratio_frame_to_records(pd.DataFrame(), periods=4) == []
