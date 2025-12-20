"""Volume anomaly cache using generic TradingHoursCache."""
from src.core.cache import TradingHoursCache

# Global instance for volume anomaly caching
volume_anomaly_cache = TradingHoursCache(
    key_prefix="stock:volume_anomaly:",
    ttl_trading=60,
    ttl_off_hours=3600,
)
