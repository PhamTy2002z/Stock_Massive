"""How a number reads, decided once on the server and drawn as a string.

The browser never formats a figure on a board — it is handed one. So this is the
only place the rules live, and a board re-opened next year renders the string it
was written with rather than one derived again against a build that has since
learned a different rule for ``tỷ``.
"""

from __future__ import annotations

import pytest

from src.studies import format


@pytest.mark.parametrize(
    "value, unit, expected",
    [
        (18.5, "%", "18,5%"),
        (-3.24, "%", "-3,2%"),
        (0.0, "%", "0,0%"),
        (1_234_000_000, "VND", "1,23 tỷ"),
        (2_500_000, "VND", "2,50 triệu"),
        (4_100_000_000_000, "VND", "4,10 nghìn tỷ"),
        (45_000, "VND", "45.000"),
        (1_234, None, "1.234"),
        (1.237, None, "1,24"),
        (12_500_000_000, None, "12,50 tỷ"),
        ("VIC", None, "VIC"),
        (None, None, ""),
        (True, None, "Có"),
    ],
)
def test_a_cell_reads_the_way_a_vietnamese_reader_reads_it(value, unit, expected):
    assert format.number(value, unit) == expected


def test_the_decimal_mark_is_a_comma_and_the_group_mark_is_a_stop():
    """Both, always. A page whose axis and whose KPI disagree is a page that
    tells the reader two different numbers."""
    assert format.number(1_234_567.89) == "1.234.567,89"


def test_a_count_is_not_shortened_because_it_is_large():
    """The unit decides the shape. Sessions do not come in billions."""
    assert format.number(1_500, "sessions") == "1.500"


def test_a_ticker_in_a_kpi_is_the_label_it_is_and_not_an_error():
    """A comparison's first column is text, and a figure naming it is a fact the
    reader asked for."""
    assert format.number("VCB", "%") == "VCB"
