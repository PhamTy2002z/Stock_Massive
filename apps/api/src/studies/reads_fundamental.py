"""One symbol's recent quarters, out of the store, for the earnings axis.

The quarters are already in ``provider_snapshots`` under the ``fundamental``
Capability: the collector writes one snapshot per ``(symbol, period_end)``, so
the store accumulates a quarterly history rather than overwriting a single row.
Measured 2026-08-27: every one of the thirty declared symbols has at least eight
quarters there, and roughly a thousand other symbols have exactly one.

That measurement is why this is a read and not an ingest. A Study that called
the provider's ``Finance`` endpoint while a reader waited would spend two or
three of the round's thirty seconds to fetch numbers the store already had, and
would put the answer at the mercy of a provider with no SLA.

**A null is absent, never zero.** Most keys in the payload are null for most
symbols — a bank files no cash flow line the way an industrial does — and the
one arithmetic mistake that matters here is reading an unfiled quarter as a
quarter of no profit. So every figure is ``float | None`` and the caller decides
what missing means.

**The line read is recorded.** ``parent_net_profit_vnd`` is the profit a
shareholder owns and ``net_profit_after_tax_vnd`` includes minority interests;
for the banks measured today they are identical, and for a holding company they
are not. The reader prefers the parent line, falls back to the consolidated one,
and says which it used — a year-on-year comparison that switched lines halfway
would be a change in the question rather than in the company.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.stocks.models import ProviderSnapshot
from src.stocks.providers.contracts import (
    Capability,
    FundamentalSnapshot,
    main_source,
)

#: How many quarters an earnings axis is drawn from. Eight, because a
#: year-on-year reading of the four most recent quarters needs the four before
#: them, and four is the shortest run in which a seasonal business does not look
#: like a trend.
QUARTERS = 8

ProfitLine = Literal["parent", "consolidated"]

_FUNDAMENTAL = Capability.FUNDAMENTAL.value


@dataclass(frozen=True)
class Quarter:
    """One filed quarter, with every statement line optional."""

    symbol: str
    period_end: date
    parent_net_profit_vnd: float | None
    net_profit_after_tax_vnd: float | None
    pre_tax_profit_vnd: float | None
    trailing_12_month_net_income_vnd: float | None
    parent_equity_vnd: float | None

    @property
    def net_profit_vnd(self) -> float | None:
        """The profit line this system compares quarters on.

        The parent line first: it is what a holder of the share owns. The
        consolidated line is the fallback rather than the default because a
        quarter where minority interests moved would otherwise look like a
        quarter where the business did.
        """
        if self.parent_net_profit_vnd is not None:
            return self.parent_net_profit_vnd
        return self.net_profit_after_tax_vnd

    @property
    def net_profit_line(self) -> ProfitLine | None:
        """Which line :attr:`net_profit_vnd` came from, or ``None`` for neither."""
        if self.parent_net_profit_vnd is not None:
            return "parent"
        if self.net_profit_after_tax_vnd is not None:
            return "consolidated"
        return None


def quarters_for(
    session: Session, symbol: str, count: int = QUARTERS
) -> tuple[Quarter, ...]:
    """The ``count`` newest filed quarters of one symbol, oldest first.

    Newest-first out of the index and reversed here, for the same reason
    :mod:`reads_daily` hands back a forward walk: a year-on-year reading is
    written as an index arithmetic over a series in time order.

    One row per ``period_end``, and the newest observation of a quarter wins.
    A restated quarter arrives as a second row under a later ``observed_at``,
    and showing both would draw the same quarter twice.
    """
    if count <= 0:
        return ()

    rows = session.execute(
        select(ProviderSnapshot)
        .where(
            ProviderSnapshot.capability == _FUNDAMENTAL,
            ProviderSnapshot.symbol == symbol.strip().upper(),
            ProviderSnapshot.source == main_source(Capability.FUNDAMENTAL).value,
        )
        .order_by(
            ProviderSnapshot.effective_at.desc(),
            ProviderSnapshot.observed_at.desc(),
        )
        # Room for a restatement or a second schema version of the same quarter,
        # both of which are rows this read collapses rather than counts.
        .limit(count * 3)
    ).scalars()

    newest: dict[date, Quarter] = {}
    for row in rows:
        snapshot = FundamentalSnapshot.model_validate(row.payload)
        if snapshot.period_end in newest:
            continue
        newest[snapshot.period_end] = Quarter(
            symbol=row.symbol,
            period_end=snapshot.period_end,
            parent_net_profit_vnd=snapshot.parent_net_profit_vnd,
            net_profit_after_tax_vnd=snapshot.net_profit_after_tax_vnd,
            pre_tax_profit_vnd=snapshot.pre_tax_profit_vnd,
            trailing_12_month_net_income_vnd=(
                snapshot.trailing_12_month_net_income_vnd
            ),
            parent_equity_vnd=snapshot.parent_equity_vnd,
        )
        if len(newest) == count:
            break

    return tuple(newest[period] for period in sorted(newest))


__all__ = ["QUARTERS", "ProfitLine", "Quarter", "quarters_for"]
