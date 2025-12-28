"""Sector-specific cache instances for financial data."""

from src.core.cache import TradingHoursCache

# Sector peers cache: 4h trading hours, 24h off-hours
# Key format: sector:peers:{symbol}:{limit}
sector_peers_cache = TradingHoursCache(
    key_prefix="sector:peers:",
    ttl_trading=4 * 3600,     # 4 hours during trading
    ttl_off_hours=24 * 3600,  # 24 hours off-hours
)
