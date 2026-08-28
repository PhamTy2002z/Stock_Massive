"""The one read-time map the signals package still asks the store for.

The full ``SnapshotStore`` / Redis-cache surface went with the provider adapters
and the collector. ``resolve_sessions`` went with the daily spine: it picked one
row out of the two that the Main Source and a cover source used to write for the
same session, and ``bar_daily`` is keyed ``(symbol, trading_day)`` — one session
is one row, and there is nothing left to pick between.

What stayed is the Capability-to-contract map, because ``signals/sessions.py``
still has to decide which session contract a stored bar becomes: a listed
equity's session carries figures a market index has no such thing as, and the
distinction is the type rather than a null.

Nothing here writes to Postgres or touches Redis. If the harness ever wants a
cached serving layer for signal fields, do it in a new module rather than by
growing this shim.
"""

from __future__ import annotations

from .contracts import (
    Capability,
    FundamentalSnapshot,
    MarketIndexSnapshot,
    MarketSnapshot,
    ReferenceSnapshot,
    ValuationSnapshot,
)

SNAPSHOT_MODEL_BY_CAPABILITY = {
    Capability.MARKET: MarketSnapshot,
    Capability.MARKET_INDEX: MarketIndexSnapshot,
    Capability.VALUATION: ValuationSnapshot,
    Capability.REFERENCE: ReferenceSnapshot,
    Capability.FUNDAMENTAL: FundamentalSnapshot,
}
