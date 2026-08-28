"""Fifteen-minute intraday bars: the session grid, the ingest, and the read.

New package rather than a return to ``src/stocks/realtime/``. That one is a
streaming spine — events, checkpoints, spills, reconciliation — and is still
frozen. This is history: one request answers a year of quarter-hour bars, so
there is no stream to keep alive, nothing to reconcile, and no reason for a
Study to wait on a socket.

``session_window`` is pure and has no import from the rest; ``ingest`` writes and
``reads`` serves, and a Study only ever touches ``reads``.

**Nothing is re-exported here on purpose.** ``ingest`` imports pandas and
vnstock at module load, so a package that pulled it in eagerly put both behind
every reader of ``reads`` — including ``trading_day``, which the whole serving
path goes through for the market's closing time. Every caller already imports
the submodule it wants by name.
"""
