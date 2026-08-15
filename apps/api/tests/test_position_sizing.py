"""Fractional Kelly as caller-owned arithmetic, never an edge estimate."""

import dataclasses

import pytest

from src.stocks.signals.position_sizing import fractional_kelly_sizing


def test_fractional_kelly_uses_only_the_callers_edge_and_variance():
    sizing = fractional_kelly_sizing(edge=0.02, variance=0.04)

    assert sizing.edge_input == 0.02
    assert sizing.variance_input == 0.04
    assert sizing.quarter_kelly == pytest.approx(0.125)
    assert sizing.half_kelly == pytest.approx(0.25)
    assert sizing.full_kelly_ceiling == pytest.approx(0.5)
    assert sizing.input_sensitivity_range == pytest.approx((0.125, 0.375))
    assert "full_kelly" not in {field.name for field in dataclasses.fields(sizing)}


@pytest.mark.parametrize(
    ("edge", "variance", "message"),
    [
        (-0.01, 0.04, "edge"),
        (float("nan"), 0.04, "edge"),
        (0.02, 0.0, "variance"),
        (0.02, float("inf"), "variance"),
    ],
)
def test_fractional_kelly_refuses_inputs_that_are_not_long_only_estimates(
    edge: float,
    variance: float,
    message: str,
):
    with pytest.raises(ValueError, match=message):
        fractional_kelly_sizing(edge=edge, variance=variance)
