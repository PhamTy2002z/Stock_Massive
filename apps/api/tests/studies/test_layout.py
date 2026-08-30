"""Every row of the grid adds to twelve, and it is the same twelve everywhere.

The property is not decoration. A row that adds to eight leaves a gap on the
panel, and a reader cannot tell a gap from a block that failed to render — so
the packer is the one place the invariant lives and this is where it is held.
"""

from __future__ import annotations

import pytest

from src.studies import layout


def rows_of(placed):
    grouped: dict[int, int] = {}
    for entry in placed:
        grouped[entry.row] = grouped.get(entry.row, 0) + entry.span
    return grouped


@pytest.mark.parametrize("count", range(1, 13))
def test_every_row_adds_to_twelve_whatever_is_packed_into_it(count):
    placed = layout.assign(layout.natural_spans([False] * count))
    assert set(rows_of(placed).values()) == {layout.COLUMNS}


@pytest.mark.parametrize(
    "flexible, expected",
    [
        (1, [12]),
        (2, [6, 6]),
        (3, [4, 4, 4]),
        (4, [6, 6, 6, 6]),
    ],
)
def test_a_run_of_charts_divides_the_way_the_plan_says(flexible, expected):
    assert layout.natural_spans([False] * flexible) == expected


def test_a_full_width_widget_gets_a_row_of_its_own():
    spans = layout.natural_spans([False, True, False])
    assert spans == [12, 12, 12]
    placed = layout.assign(spans)
    assert [entry.row for entry in placed] == [0, 1, 2]


def test_two_charts_beside_a_full_width_one_still_pair_up():
    spans = layout.natural_spans([False, False, True])
    assert spans == [6, 6, 12]
    placed = layout.assign(spans)
    assert [(entry.span, entry.row) for entry in placed] == [(6, 0), (6, 0), (12, 1)]


def test_a_short_row_widens_its_last_block_rather_than_leaving_a_hole():
    placed = layout.assign([6, 4])
    assert [entry.span for entry in placed] == [6, 6]
    assert rows_of(placed) == {0: 12}


def test_a_block_wider_than_the_grid_is_clamped_to_it():
    placed = layout.assign([20])
    assert placed[0].span == layout.COLUMNS


def test_no_blocks_lays_out_nothing():
    assert layout.assign([]) == []


@pytest.mark.parametrize(
    "count, expected",
    [
        (3, [4, 4, 4]),
        (4, [3, 3, 3, 3]),
        (5, [4, 4, 4, 6, 6]),
        (6, [4, 4, 4, 4, 4, 4]),
    ],
)
def test_the_kpi_strip_divides_the_way_the_plan_says(count, expected):
    assert layout.kpi_spans(count) == expected


@pytest.mark.parametrize("count", [3, 4, 5, 6])
def test_the_kpi_strip_also_fills_every_row_it_starts(count):
    assert set(rows_of(layout.assign(layout.kpi_spans(count))).values()) == {
        layout.COLUMNS
    }
