"""Fifteen-minute intraday bars: the session grid, the ingest, and the read.

New package rather than a return to ``src/stocks/realtime/``. That one is a
streaming spine — events, checkpoints, spills, reconciliation — and is still
frozen. This is history: one request answers a year of quarter-hour bars, so
there is no stream to keep alive, nothing to reconcile, and no reason for a
Study to wait on a socket.

``session_window`` is pure and has no import from the rest; ``ingest`` writes and
``reads`` serves, and a Study only ever touches ``reads``.
"""

from .ingest import IngestOutcome, IntradayIngestError, ensure_bars
from .reads import Bar15m, bars_for, latest_closed_session, sessions_available
from .session_window import (
    SESSION_BUCKET_LABELS,
    SESSION_BUCKETS,
    Phase,
    label_of,
    phase_of,
)

__all__ = [
    "Bar15m",
    "IngestOutcome",
    "IntradayIngestError",
    "Phase",
    "SESSION_BUCKETS",
    "SESSION_BUCKET_LABELS",
    "bars_for",
    "ensure_bars",
    "label_of",
    "latest_closed_session",
    "phase_of",
    "sessions_available",
]
