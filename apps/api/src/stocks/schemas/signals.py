"""Public shape of a signal, provenance included.

Coverage, freshness and issues are fields of the answer rather than something
the caller has to infer from what is missing. A body carrying five spikes says
whether those five came out of fifty companies or twelve, and how old the
session behind them is — the two facts that decide whether the list means
anything.

Issue codes travel as codes. The interface holds one Vietnamese sentence per
code in one place; prose written here would be prose the web app cannot group,
translate or style, and it would arrive in whatever tone the endpoint happened
to be written in.
"""

from datetime import date

from .common import StrictModel


class SignalCoverage(StrictModel):
    """How much of the Signal Scope the answer could be computed for."""

    state: str
    evaluated: int
    total: int


class SignalCohortVersion(StrictModel):
    """Which Cohort Version a profit-leaders answer was computed against.

    Null for the Universe scope, which has no ranking behind it.
    """

    id: int
    reporting_period: date


class VolumeSpikeItem(StrictModel):
    """One symbol that traded unlike the twenty sessions before it."""

    symbol: str
    exchange: str | None = None
    volume: int
    # The mean of twenty sessions, rounded to whole shares: the fraction is
    # arithmetic left over from the division, not a quantity anyone traded.
    baseline_average_volume: int
    ratio: float
    close_price: float | None = None
    change_pct: float | None = None
    issues: list[str] = []


class UnevaluableSymbol(StrictModel):
    """A symbol the store could not answer for, and why.

    Always in the response, never dropped: a list that quietly omits what it
    could not see presents a partial answer as a complete one.
    """

    symbol: str
    issues: list[str]


class VolumeSpikeSignalResponse(StrictModel):
    """The Volume Spike signal for one Signal Scope."""

    scope: str
    trading_day: date | None = None
    threshold: float
    coverage: SignalCoverage
    freshness: str
    cohort_version: SignalCohortVersion | None = None
    issues: list[str] = []
    spikes: list[VolumeSpikeItem] = []
    unevaluable: list[UnevaluableSymbol] = []
