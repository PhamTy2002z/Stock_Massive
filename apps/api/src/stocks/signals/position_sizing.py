"""Position sizing arithmetic whose edge remains owned by the caller."""

from __future__ import annotations

import math
from dataclasses import dataclass

KELLY_EDGE_SENSITIVITY = 0.50


@dataclass(frozen=True)
class FractionalKellySizing:
    """Long-only capital fractions from inputs supplied by the caller.

    The full-Kelly number is deliberately named only as a ceiling. The two
    usable answers stop at half Kelly, and the sensitivity range repeats the
    half-Kelly arithmetic after moving the dominant input — the mean edge — by
    plus or minus fifty percent.
    """

    edge_input: float
    variance_input: float
    quarter_kelly: float
    half_kelly: float
    full_kelly_ceiling: float
    input_sensitivity_range: tuple[float, float]


def fractional_kelly_sizing(*, edge: float, variance: float) -> FractionalKellySizing:
    """Size from caller-owned estimates; this function has no market-data input."""
    if not math.isfinite(edge) or edge < 0.0:
        raise ValueError("edge must be a finite non-negative caller estimate")
    if not math.isfinite(variance) or variance <= 0.0:
        raise ValueError("variance must be a finite positive caller estimate")
    full_kelly_ceiling = edge / variance
    quarter_kelly = 0.25 * full_kelly_ceiling
    half_kelly = 0.50 * full_kelly_ceiling
    sensitivity = (
        0.50 * (edge * (1.0 - KELLY_EDGE_SENSITIVITY) / variance),
        0.50 * (edge * (1.0 + KELLY_EDGE_SENSITIVITY) / variance),
    )
    return FractionalKellySizing(
        edge_input=edge,
        variance_input=variance,
        quarter_kelly=quarter_kelly,
        half_kelly=half_kelly,
        full_kelly_ceiling=full_kelly_ceiling,
        input_sensitivity_range=sensitivity,
    )
