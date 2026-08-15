"""Signals computed from stored sessions, and the provenance they carry.

Nothing in here reaches a Provider Source. A signal is arithmetic over what the
Collector and the Warm-up already wrote, so an evening the provider is down
still answers — with an older session, and saying so.
"""

from .corporate_actions import (
    ActionKind,
    ActionTerms,
    Confirmation,
    ConfirmationReason,
    ConfirmationVerdict,
    CorporateActionStore,
    FactorReading,
    adjustment_factor,
    blend,
    classify,
    confirm_ex_date,
    terms_of,
)
from .issues import SignalIssue
from .price_band import (
    BAND_LIMIT_BY_EXCHANGE,
    EXCHANGE_MIGRATIONS,
    MIGRATION_PROGRAMME_END,
    BandAnchorBasis,
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
    SignalScope,
    VolumeSpikeSignal,
    signal_cache_key,
    volume_spike_signal,
)

__all__ = [
    "BAND_LIMIT_BY_EXCHANGE",
    "BASELINE_TRADING_DAYS",
    "ActionKind",
    "ActionTerms",
    "BandAnchorBasis",
    "BandLimits",
    "BandReading",
    "BandRegime",
    "Confirmation",
    "ConfirmationReason",
    "ConfirmationVerdict",
    "CorporateActionStore",
    "CoverageState",
    "EXCHANGE_MIGRATIONS",
    "ExchangeAsOf",
    "ExchangeMigration",
    "FactorReading",
    "Freshness",
    "LimitLock",
    "MIGRATION_PROGRAMME_END",
    "SignalIssue",
    "SignalScope",
    "VolumeSpikeSignal",
    "adjustment_factor",
    "band_limits",
    "blend",
    "classify",
    "confirm_ex_date",
    "detect_limit_lock",
    "resolve_band_regime",
    "signal_cache_key",
    "terms_of",
    "tick_size",
    "volume_spike_signal",
]
