"""Which picture a frame wants, on twelve frames shaped like the real ones.

The fixtures are the shapes the store actually produces — a session series, a
quarter series, a symbols-against-metrics table, a volume-at-price profile, a
condition list, an intraday matrix — because a rule table tested on invented
shapes is a rule table tested against its own author.
"""

from __future__ import annotations

import pytest

from src.studies import composer


def f(kind, columns, rows, unit=None):
    return {
        "kind": kind,
        "columns": list(columns),
        "rows": [list(row) for row in rows],
        "unit": unit,
        "labels": {name: name for name in columns},
    }


SESSIONS = f(
    "series",
    ("session", "close"),
    [(f"2026-08-{day:02d}", 20.0 + day) for day in range(1, 31)],
    "VND",
)
SESSIONS_TWO_MEASURES = f(
    "series",
    ("session", "close", "volume"),
    [(f"2026-08-{day:02d}", 20.0 + day, 1000.0 * day) for day in range(1, 31)],
)
QUARTERS_WIDE = f(
    "series",
    ("quarter", "revenue", "profit", "margin"),
    [(f"2025Q{q}", 100.0, 20.0, 20.0) for q in range(1, 5)],
)
SESSIONS_WIDE = f(
    "series",
    ("session", "a", "b", "c"),
    [(f"2026-08-{day:02d}", 1.0, 2.0, 3.0) for day in range(1, 31)],
)
CATEGORIES = f(
    "series",
    ("bucket", "share"),
    [("09:15", 12.0), ("10:00", 20.0), ("11:00", 18.0), ("13:00", 25.0), ("14:00", 25.0)],
    "%",
)
COMPARISON = f(
    "table",
    ("symbol", "roe", "roa", "margin"),
    [("VIC", 8.0, 1.2, 14.0), ("VCB", 18.0, 1.9, 42.0)],
    "%",
)
BIG_COMPARISON = f(
    "table",
    ("symbol", "roe", "roa"),
    [(name, 1.0, 2.0) for name in ("VIC", "VCB", "HPG", "MWG", "STB")],
    "%",
)
PARTS = f(
    "table",
    ("bucket", "share"),
    [("A", 40.0), ("B", 30.0), ("C", 20.0), ("D", 10.0)],
    "%",
)
MANY_PARTS = f(
    "table",
    ("bucket", "share"),
    [(chr(65 + index), 100.0 / 8) for index in range(8)],
    "%",
)
TWO_AXES = f(
    "table",
    ("name", "risk", "reward"),
    [("A", 1.0, 2.0), ("B", 3.0, 4.0), ("C", 5.0, 6.0)],
)
ONE_ROW = f("table", ("label", "value"), [("Sharpe", 1.2)])
CHECKLIST = f(
    "table",
    ("label", "status", "value"),
    [("Trên MA20", "met", 1.0), ("Khối lượng", "unmet", 0.0)],
)
MATRIX = f(
    "matrix",
    ("session", "09:15", "10:00"),
    [("2026-08-01", 1.0, 2.0), ("2026-08-02", 3.0, 4.0)],
)


@pytest.mark.parametrize(
    "frame, expected",
    [
        (SESSIONS, "line_series"),
        (SESSIONS_TWO_MEASURES, "line_series"),
        (QUARTERS_WIDE, "grouped_bar"),
        (SESSIONS_WIDE, "line_series"),
        (CATEGORIES, "bar_series"),
        (COMPARISON, "comparison_table"),
        (BIG_COMPARISON, "comparison_table"),
        (PARTS, "donut"),
        (MANY_PARTS, "ranked_bars"),
        (TWO_AXES, "scatter_quadrant"),
        (ONE_ROW, "stat_tiles"),
        (CHECKLIST, "condition_checklist"),
        (MATRIX, "session_heatmap"),
    ],
)
def test_the_shape_decides_the_picture(frame, expected):
    assert composer.infer_widget(frame).widget == expected


def test_a_wide_series_over_many_points_says_what_it_left_out():
    """Three measures across thirty sessions is two lines and a note.

    Not a silent truncation: the reader is told the rest is in the table, which
    is a hole they can see rather than one they cannot.
    """
    choice = composer.infer_widget(SESSIONS_WIDE)
    assert choice.downgraded is not None
    assert "table" in choice.downgraded


def test_a_comparison_small_enough_to_draw_earns_its_bars_as_well():
    assert composer.infer_widget(COMPARISON).companion == "grouped_bar"


def test_a_comparison_of_five_symbols_is_the_table_alone():
    assert composer.infer_widget(BIG_COMPARISON).companion is None


def test_a_hint_the_kind_admits_is_kept():
    assert composer.infer_widget(CATEGORIES, "line_series").widget == "line_series"


def test_a_pie_of_too_many_slices_is_replaced_and_the_replacement_is_recorded():
    choice = composer.infer_widget(MANY_PARTS, "donut")
    assert choice.widget == "ranked_bars"
    assert choice.upgraded_from == "donut"


def test_a_table_asked_for_where_a_series_belongs_is_replaced():
    choice = composer.infer_widget(SESSIONS, "data_table")
    assert choice.widget == "line_series"
    assert choice.upgraded_from == "data_table"


def test_a_hint_the_kind_refuses_is_replaced():
    choice = composer.infer_widget(SESSIONS, "session_heatmap")
    assert choice.widget == "line_series"
    assert choice.upgraded_from == "session_heatmap"


def test_a_hint_nothing_registers_is_simply_ignored():
    choice = composer.infer_widget(SESSIONS, "sparkline")
    assert choice.widget == "line_series"
    assert choice.upgraded_from is None


def test_a_column_that_is_entirely_refused_is_not_a_measure():
    """Every cell null is a column nothing can draw, whatever its name says."""
    frame = f("table", ("label", "value"), [("A", None), ("B", None)])
    assert composer.shape_of(frame).numeric_columns == ()


def test_a_hole_in_a_column_does_not_change_what_the_column_is():
    frame = f("table", ("label", "value"), [("A", 1.0), ("B", None), ("C", 3.0)])
    assert composer.shape_of(frame).numeric_columns == ("value",)


def test_presentation_names_the_columns_the_widget_draws():
    assert composer.presentation("line_series", SESSIONS) == {
        "x": "session",
        "y": "close",
    }
    assert composer.presentation("comparison_table", COMPARISON) == {
        "entity": "symbol",
        "metrics": ["roe", "roa", "margin"],
    }
    # The model's narrowing is applied to the drawing and never to the frame:
    # the table under the chart still carries every column.
    assert composer.presentation("comparison_table", COMPARISON, ["roe"]) == {
        "entity": "symbol",
        "metrics": ["roe"],
    }


def test_the_widgets_that_never_share_a_row_are_the_ones_a_half_width_would_break():
    assert "comparison_table" in composer.FULL_WIDTH
    assert "session_heatmap" in composer.FULL_WIDTH
    assert "line_series" not in composer.FULL_WIDTH
