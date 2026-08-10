"""Internal contracts for normalized stock data providers."""

from .contracts import (
    BatchTooLarge,
    Capability,
    FundamentalDataProvider,
    FundamentalSnapshot,
    MarketDataProvider,
    MarketSnapshot,
    PriceUnit,
    ProviderSource,
    ReferenceDataProvider,
    ReferenceSnapshot,
    SOURCE_OWNERSHIP_BY_CAPABILITY,
    ShareCount,
    ShareType,
    SnapshotMetadata,
    SourceOwnership,
    SymbolSnapshot,
    ValuationDataProvider,
    ValuationSnapshot,
    cover_source,
    main_source,
    owns_capability,
)
from .store import SnapshotRead, SnapshotStore

# Adapters are deliberately absent: importing one pulls in its provider library,
# and this package is what the contracts are imported from. Reach for an adapter
# by its own module, the way the collector and its tests do.

__all__ = [
    "BatchTooLarge",
    "Capability",
    "FundamentalDataProvider",
    "FundamentalSnapshot",
    "MarketDataProvider",
    "MarketSnapshot",
    "PriceUnit",
    "ProviderSource",
    "ReferenceDataProvider",
    "ReferenceSnapshot",
    "SOURCE_OWNERSHIP_BY_CAPABILITY",
    "ShareCount",
    "ShareType",
    "SnapshotMetadata",
    "SnapshotRead",
    "SnapshotStore",
    "SourceOwnership",
    "SymbolSnapshot",
    "ValuationDataProvider",
    "ValuationSnapshot",
    "cover_source",
    "main_source",
    "owns_capability",
]
