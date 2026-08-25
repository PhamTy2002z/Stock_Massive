"""Analysis production error carrier — kept as a shim after the producer rip.

The full producer pipeline (draft, on-demand, nightly cohort) was removed with
the Analysis lane. Only ``ProductionFailure`` stays, because ``alpha.envelope``
raises it from ``build_envelope`` on missing snapshots and refused core evidence,
and callers that still reach ``build_envelope`` need a stable exception type.

Nothing in the chat lane calls ``build_envelope``. This module exists so the
few functions in ``envelope.py`` that still do can import their exception
without pulling back the whole producer surface.
"""

from __future__ import annotations


class ProductionFailure(Exception):
    """Envelope refused to assemble under a named reason."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message
