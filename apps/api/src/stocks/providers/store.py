"""Store-side helpers that survived the market-data rip.

The full ``SnapshotStore`` / Redis-cache surface was removed with the provider
adapters and the collector. What stayed is the pair of read-time helpers the
signal fields still need — ``SNAPSHOT_MODEL_BY_CAPABILITY`` and
``resolve_sessions`` — because ``signals/sessions.py::sessions_in_range``
reaches for them by name to reconstruct a session series from the two rows the
Main Source and the cover source used to write in overlap.

Nothing here writes to Postgres or touches Redis anymore. If the harness ever
wants to reintroduce a cached serving layer for signal fields, do it in a new
module rather than by growing this shim.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from src.stocks.models import ProviderSnapshot

from .contracts import (
    Capability,
    FundamentalSnapshot,
    MarketIndexSnapshot,
    MarketSnapshot,
    ReferenceSnapshot,
    ValuationSnapshot,
    main_source,
)

SNAPSHOT_MODEL_BY_CAPABILITY = {
    Capability.MARKET: MarketSnapshot,
    Capability.MARKET_INDEX: MarketIndexSnapshot,
    Capability.VALUATION: ValuationSnapshot,
    Capability.REFERENCE: ReferenceSnapshot,
    Capability.FUNDAMENTAL: FundamentalSnapshot,
}


def resolve_sessions(
    rows: Iterable[ProviderSnapshot],
    capability: Capability,
) -> dict[datetime, ProviderSnapshot]:
    """One row per session, out of rows that may hold two copies of one.

    Kept as-is from the pre-rip store: the Main Source wins over a Cover Source
    row for the same effective_at, and among two rows from the same source the
    later write wins because callers query oldest-written first.
    """
    main = main_source(capability).value
    held: dict[datetime, ProviderSnapshot] = {}
    for row in rows:
        standing = held.get(row.effective_at)
        if standing is None or standing.source != main:
            held[row.effective_at] = row
    return held
