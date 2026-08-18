"""The registered fields the cases name, in one place.

Categories A and E both ask for figures over windows the fixture deliberately
refuses, and they ask for some of the same ones — the price zone below
``min_sessions``, the twelve-month return across the ADR-0006 seam. Two copies
of those strings is two places a re-naming in the Signal Registry has to land,
and the failure of missing one is silent: ``Expectation.__post_init__`` refuses
an unregistered name, so a stale copy is caught, but a *renamed* field with both
copies updated in only one module leaves half the battery asking the old
question.

Every name here is validated against ``REGISTRY`` at import, for the same
reason: a field this module names and the registry does not have is a case that
would pass whatever the answer said.
"""

from __future__ import annotations

from src.stocks.signals import REGISTRY

#: The price-zone field the nightly artifact is built around, and the one a
#: window below ``min_sessions`` cannot serve.
PRICE_ZONE = "price_zone.ordinary_range_pct"

#: A cross-sectional percentile over a formation window plus a skip.
MOMENTUM = "momentum_rank.percentile_12_2"

#: A twelve-month return, which is the widest window in ordinary use and so the
#: one most likely to cross a price-basis seam.
TWELVE_MONTH_RETURN = "trend_signal.total_return_12m_pct"

#: A risk-adjusted ratio, which needs a year of returns behind it.
SHARPE = "risk_adjusted.sharpe_annualized"

#: The deepest peak-to-trough fall in the window.
MAX_DRAWDOWN = "drawdown_stats.max_drawdown_pct"

#: A regression against the benchmark index, which needs 250 sessions.
BETA = "relative_strength.beta_vs_market_index"


_NAMED = (
    PRICE_ZONE,
    MOMENTUM,
    TWELVE_MONTH_RETURN,
    SHARPE,
    MAX_DRAWDOWN,
    BETA,
)

_unknown = sorted(name for name in _NAMED if name not in REGISTRY)
if _unknown:  # pragma: no cover - an import-time refusal, not a branch
    raise ValueError(
        "these are not registered fields, so a case naming one would pass "
        "whatever the answer said: " + ", ".join(_unknown)
    )


__all__ = [
    "BETA",
    "MAX_DRAWDOWN",
    "MOMENTUM",
    "PRICE_ZONE",
    "SHARPE",
    "TWELVE_MONTH_RETURN",
]
