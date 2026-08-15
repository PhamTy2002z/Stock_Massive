"""The seam the nightly pipeline plugs into, and the stub standing in for it.

Everything about *generating* an Analysis — the evidence envelope, the Analysis
Field Profile, the strict structured-output call, the semantic validation — is a
later milestone's. What the state machine needs from it is small enough to write
down now: given a symbol and a Trading Day, either a draft or a named failure.

Keeping that contract here rather than inside the state machine is what lets the
pipeline land without touching a line of the lifecycle. The producer is passed
in as an argument, never imported by the machine that calls it.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Callable

# The template version stamped on rows this system writes today. Readers handle
# several values — that is what the column is for — and it is deliberately not
# part of `analysis`'s unique key.
ANALYSIS_SCHEMA_VERSION = 1

# The pipeline's failure taxonomy. Closed on purpose: a run's `error_code` is a
# vocabulary the interface branches on, so a code invented at the call site is a
# code nothing downstream knows how to render.
FAILURE_CODES = frozenset(
    {
        "missing_market_snapshot",
        "insufficient_core_evidence",
        "auth_unavailable",
        "llm_transport_error",
        "invalid_model_output",
        "persistence_error",
    }
)

# The longest reason that fits `analysis_run.error_message`.
MAX_REASON_LENGTH = 500


def sanitized_reason(message: str) -> str:
    """A reason bounded and flattened to one line.

    The guarantee that a stack trace never reaches this column is structural —
    the state machine stores the message a `ProductionFailure` declared and
    never `str(exception)` — and this is the second, weaker line: whatever was
    declared arrives short and single-line, so a reason cannot become a wall of
    text in the interface.
    """
    return " ".join(message.split())[:MAX_REASON_LENGTH]


@dataclass(frozen=True)
class AnalysisDraft:
    """A complete Analysis, before it is published.

    ``verdict`` is lifted out of the payload for the reason `Analysis` records
    (``src/alpha/models.py``), so the draft arrives shaped like the row.
    """

    verdict: str
    payload: dict = field(default_factory=dict)
    schema_version: int = ANALYSIS_SCHEMA_VERSION


class ProductionFailure(Exception):
    """An Analysis that could not be produced, for a reason with a name.

    The only exception the state machine treats as a failure. Anything else is a
    crash, and a crash is left to look like one — see `produce_analysis`.
    """

    def __init__(self, code: str, message: str) -> None:
        if code not in FAILURE_CODES:
            raise ValueError(
                f"{code!r} is not a production failure code. The taxonomy is "
                f"closed: {sorted(FAILURE_CODES)}"
            )
        reason = sanitized_reason(message)
        super().__init__(f"{code}: {reason}")
        self.code = code
        self.message = reason


# What a milestone has to supply to produce Analyses for real: given a symbol and
# a Trading Day, return a complete draft or raise `ProductionFailure`. A plain
# callable rather than a Protocol, so a test producer is a three-line function
# and the real pipeline is whatever shape it wants to be.
Producer = Callable[[str, date], AnalysisDraft]


def stub_producer(symbol: str, trading_day: date) -> AnalysisDraft:
    """A STUB. It produces no analysis and must never run in the nightly lane.

    It exists so every state of the lifecycle can be driven before the pipeline
    is written, and it says so in the row it writes: the payload carries
    ``stub: True``, so a stubbed Analysis that somehow reached a user is
    identifiable in the database rather than merely disappointing on screen.
    """
    return AnalysisDraft(
        verdict="watch",
        payload={
            "stub": True,
            "symbol": symbol,
            "trading_day": trading_day.isoformat(),
            "note": "Placeholder for the nightly Analysis pipeline (milestone A4).",
        },
    )
