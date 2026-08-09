"""Internal contracts for normalized stock data providers."""

from .contracts import (
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
    "ValuationDataProvider",
    "ValuationSnapshot",
    "cover_source",
    "main_source",
    "owns_capability",
]
