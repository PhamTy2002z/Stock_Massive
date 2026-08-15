"""The newest quarterly statement behind a symbol, and how old it is.

The factor percentiles are the one part of the signals package whose inputs are
not sessions. They rank a symbol on earnings, book value and profitability, and
those arrive quarterly from the ``fundamental`` Capability rather than daily from
``market`` — so they need a read of their own, and they need it batched: a
cross-section of a hundred symbols asking one query each would make a percentile
cost a hundred round trips to answer one question.

**Age travels with the figure, always.** A quarterly statement is stamped by its
own ``period_end``, and a Q2 number quoted in November is five months old — a
false positive by a mechanism no threshold catches, because nothing about the
number itself says when it stopped being current. ADR-0010 makes that stamp the
condition on which a ``stored`` field is exempt from the null at all.

Nothing here reaches a Provider Source. A statement this system has not collected
is a symbol excluded from a ranking with a reason, never a live call made to fill
a slot.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.stocks.models import ProviderSnapshot

from ..providers.contracts import Capability, FundamentalSnapshot, main_source
from ..providers.normalize import VN_TZ

# How old a quarterly figure may be before a percentile drawn from it is
# degraded. Five months: a Vietnamese issuer has 20 days after a quarter to file
# and 45 after a half-year, so a figure four months old is ordinary and one past
# five is a company that has missed a filing or a collector that has stopped
# running. A domain choice rather than a null derivation — a staleness bound is
# a question about a filing calendar, and a null has no opinion on one.
FUNDAMENTAL_STALE_DAYS = 150

_FUNDAMENTAL = Capability.FUNDAMENTAL.value


@dataclass(frozen=True)
class FundamentalStanding:
    """One symbol's newest statement at a cutoff date, with its age on it."""

    symbol: str
    period_end: date
    trailing_12_month_net_income_vnd: float | None
    parent_equity_vnd: float | None
    age_days: int

    @property
    def stale(self) -> bool:
        return self.age_days > FUNDAMENTAL_STALE_DAYS


def fundamentals_on_or_before(
    session: Session,
    symbols: Sequence[str],
    day: date,
) -> dict[str, FundamentalStanding]:
    """Each symbol's newest quarterly statement at or before this date, in one query.

    Dated by ``period_end`` rather than by when it was read, which is how the
    Adapter writes it: a statement is a fact about a quarter and re-reading it
    does not make it newer. That is also what makes "at or before" answerable —
    a cutoff in the past gets the quarter that was current then rather than the
    quarter that is current now, so a percentile recomputed for an old date does
    not quietly acquire figures nobody had.

    Symbols with no statement are simply absent. A missing quarter is an
    exclusion from a ranking with a reason, and inventing an empty standing for
    it would make the two indistinguishable.
    """
    if not symbols:
        return {}

    wanted = sorted({symbol.upper() for symbol in symbols})
    cutoff = datetime.combine(day + timedelta(days=1), time.min, tzinfo=VN_TZ)
    rows = session.execute(
        select(ProviderSnapshot)
        .where(
            ProviderSnapshot.capability == _FUNDAMENTAL,
            ProviderSnapshot.symbol.in_(wanted),
            ProviderSnapshot.source == main_source(Capability.FUNDAMENTAL).value,
            ProviderSnapshot.effective_at < cutoff,
        )
        .order_by(
            ProviderSnapshot.effective_at.asc(),
            ProviderSnapshot.observed_at.asc(),
        )
    ).scalars()

    # Ordered oldest first, so the last row written for a symbol is the newest
    # quarter, and the newest observation of that quarter wins within it.
    standing: dict[str, FundamentalStanding] = {}
    for row in rows:
        snapshot = FundamentalSnapshot.model_validate(row.payload)
        standing[row.symbol] = FundamentalStanding(
            symbol=row.symbol,
            period_end=snapshot.period_end,
            trailing_12_month_net_income_vnd=(
                snapshot.trailing_12_month_net_income_vnd
            ),
            parent_equity_vnd=snapshot.parent_equity_vnd,
            age_days=(day - snapshot.period_end).days,
        )
    return standing
