"""Signals computed from stored sessions, and the provenance they carry.

Nothing in here reaches a Provider Source. A signal is arithmetic over what the
Collector and the Warm-up already wrote, so an evening the provider is down
still answers — with an older session, and saying so.
"""

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
    "BASELINE_TRADING_DAYS",
    "CoverageState",
    "Freshness",
    "SignalIssue",
    "SignalScope",
    "VolumeSpikeSignal",
    "signal_cache_key",
    "volume_spike_signal",
]
