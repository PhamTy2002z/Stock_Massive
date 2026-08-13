"""Signals computed from stored sessions, and the provenance they carry.

Nothing in here reaches a Provider Source. A signal is arithmetic over what the
Collector and the Warm-up already wrote, so an evening the provider is down
still answers — with an older session, and saying so.
"""

from .price_band import (
    BAND_LIMIT_BY_EXCHANGE,
    EXCHANGE_MIGRATIONS,
    MIGRATION_PROGRAMME_END,
    BandAnchorBasis,
    BandIssue,
    BandLimits,
    BandReading,
    BandRegime,
    ExchangeAsOf,
    ExchangeMigration,
    LimitLock,
    band_limits,
    detect_limit_lock,
    resolve_band_regime,
    tick_size,
)
from .volume_spike import (
    BASELINE_TRADING_DAYS,
    CoverageState,
    Freshness,
    SignalIssue,
    SignalScope,
    VolumeSpikeSignal,
    signal_cache_key,
    volume_spike_signal,
)

__all__ = [
    "BAND_LIMIT_BY_EXCHANGE",
    "BASELINE_TRADING_DAYS",
    "BandAnchorBasis",
    "BandIssue",
    "BandLimits",
    "BandReading",
    "BandRegime",
    "CoverageState",
    "EXCHANGE_MIGRATIONS",
    "ExchangeAsOf",
    "ExchangeMigration",
    "Freshness",
    "LimitLock",
    "MIGRATION_PROGRAMME_END",
    "SignalIssue",
    "SignalScope",
    "VolumeSpikeSignal",
    "band_limits",
    "detect_limit_lock",
    "resolve_band_regime",
    "signal_cache_key",
    "tick_size",
    "volume_spike_signal",
]
