"""A ``FieldWindow`` over bars a test built by hand, with no store behind it.

Every registered reading takes the window the gateway serves rather than a bare
frame, which is what lets a field read the cross-sectional standing and the band
the gateway measured. Most of the arithmetic in this package does not care about
any of that, and a test pinning Yang-Zhang against a series with a known answer
should not have to stand a database up to say so.

So this builds the health a served window of exactly these bars would have
carried — the counts derived from the bars themselves, no refusal, no
degradation — and nothing else. It is deliberately test-only: production code
reaches a window through ``prepare_bars()`` or not at all, and a factory like
this one on the production side would be the second path the gateway exists to
prevent.
"""

from __future__ import annotations

from src.stocks.signals.bars import (
    AdjustmentReport,
    AdtvStanding,
    BarFrame,
    WindowBandRegime,
    WindowHealth,
)
from src.stocks.signals.fields import FieldWindow
from src.stocks.signals.issues import SignalIssue


def health_of(
    frame: BarFrame,
    *,
    min_sessions: int | None = None,
    adtv: AdtvStanding | None = None,
    band_regime: WindowBandRegime | None = None,
    degradations: tuple[SignalIssue, ...] = (),
) -> WindowHealth:
    """What the gateway would have reported about a window of exactly these bars."""
    sessions = len(frame.bars)
    return WindowHealth(
        symbol=frame.symbol,
        window_days=sessions,
        min_sessions=sessions if min_sessions is None else min_sessions,
        sessions_used=sessions,
        first_session=frame.bars[0].session_date if frame.bars else None,
        last_session=frame.bars[-1].session_date if frame.bars else None,
        limit_lock_days=sum(1 for item in frame.bars if item.limit_locked),
        limit_lock_dates=tuple(
            item.session_date for item in frame.bars if item.limit_locked
        ),
        band_regime=band_regime,
        adjustment=AdjustmentReport(
            applied=False, actions_applied=0, actions_in_window=0
        ),
        adtv=adtv,
        band_undecided_days=sum(1 for item in frame.bars if item.band is None),
        band_undecided_reasons=(),
        refusal=None,
        degradations=degradations,
    )


def window_of(frame: BarFrame, **health: object) -> FieldWindow:
    """The frame, dressed as the window a reading is handed."""
    return FieldWindow(frame=frame, health=health_of(frame, **health))  # type: ignore[arg-type]
