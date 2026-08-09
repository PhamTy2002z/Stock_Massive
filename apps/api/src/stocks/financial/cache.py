"""Sector-specific cache instances for financial data."""

from src.core.cache import TradingHoursCache

# Sector peers cache: 4h trading hours, 24h off-hours
# Key format: sector:peers:{symbol}:{limit}
sector_peers_cache = TradingHoursCache(
    key_prefix="sector:peers:",
    ttl_trading=4 * 3600,     # 4 hours during trading
    ttl_off_hours=24 * 3600,  # 24 hours off-hours
)

# A partially built peer set (upstream ran out of quota mid-fan-out) is still
# useful to render, but must expire fast so a complete set replaces it soon.
SECTOR_PEERS_PARTIAL_TTL = 300

# Quarterly ratios per symbol. Sector comparison fans out over every peer in an
# industry, and those peers repeat across requests, so caching one symbol at a
# time is what keeps the fan-out from re-hitting the provider for each request.
ratio_history_cache = TradingHoursCache(
    key_prefix="stock:ratio-history:",
    ttl_trading=4 * 3600,
    ttl_off_hours=24 * 3600,
)

# A throttled provider can answer with an empty frame rather than an error, so
# "no ratios" is not reliably a fact about the symbol. Remember it long enough
# to stop a retry storm, briefly enough that real data replaces it the same
# session.
RATIO_HISTORY_EMPTY_TTL = 300
