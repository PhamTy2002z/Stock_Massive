"""The real producer: evidence in, a published Analysis out, and the audit trail.

This is the thing the **Analysis Run** lifecycle has been taking as a parameter
since A2. It assembles the evidence envelope, sends it to the model exactly once,
and merges the validated fragment into a payload the backend owns — and it is the
only place those three steps meet. The lifecycle still imports none of it: a
producer arrives as an argument, which is what let the state machine ship before
any of this existed and what lets a test drive every state with a three-line
function.

**The backend owns the envelope and merges in only the model's five things.**
Every displayed number lives under ``evidence``, which is the envelope verbatim;
the model's half is prose, an ordering of emphasis, and a list of ids. There is
no key in the payload where a fragment-supplied number could be rendered as a
figure, and that is a property of this shape rather than a rule somebody checks.

**The verdict is not in the payload.** It is lifted into ``analysis.verdict``,
so the rail shows one word for ten symbols without opening ten payloads. Written
in both places it would be one fact in two spellings, and the extracted column is
the one every reader already uses.

**No chain-of-thought, and no copy of the prompt.** The figures embedded in the
payload *are* the evidence snapshot the model was shown (spec 0003 §8.9), so a
dispute has what it needs; the instructions are a module constant with a version
stamped beside them, and duplicating them into every row would store the same
paragraph a thousand times to answer a question ``promptVersion`` already
answers.

**Publication order is A2's and is untouched here.** The Analysis is written
first and the run flipped ``ready`` second; a death between them leaves the run
``producing`` and the retry finds the Analysis already published and only repairs
the run state. This module never writes either row — it returns a draft, and
``produce_analysis`` owns every commit.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.core.database import get_sync_db
from src.core.llm import (
    LLMClient,
    LLMConfig,
    Workload,
    build_client,
    llm_config_from_settings,
)
from src.stocks.signals.serving import CrossSection

from .analysis_run import (
    RunOrigin,
    RunOutcome,
    produce_analysis,
    retry_analysis,
    stored_run,
)
from .envelope import EvidenceEnvelope, build_envelope, measure_cross_sections
from .generation import PROMPT_VERSION, AnalysisFragment, generate_fragment
from .producer import (
    ANALYSIS_SCHEMA_VERSION,
    AnalysisDraft,
    Producer,
    ProductionFailure,
)

logger = logging.getLogger(__name__)

# The seven things a dispute needs about how an Analysis came to exist, and the
# names it carries them under. Written down as a constant because an audit block
# missing a field is not a smaller audit block — it is one nobody can reconcile,
# and the test that counts them reads this rather than a list in a test file.
AUDIT_FIELDS = (
    "schemaVersion",
    "fieldProfileVersion",
    "promptVersion",
    "model",
    "route",
    "generatedAt",
    "inputFingerprint",
)


def analysis_payload(
    envelope: EvidenceEnvelope,
    fragment: AnalysisFragment,
    *,
    model: str,
    route: str,
    generated_at: datetime,
) -> dict[str, Any]:
    """The immutable payload, with the backend's half and the model's half apart.

    Three keys, and the split between them is the contract:

    ``audit`` is how this Analysis came to exist. ``inputFingerprint`` is the
    SHA-256 of the normalized envelope below it, so a reader can prove the
    evidence in this row is the evidence the model saw rather than taking the
    system's word for it.

    ``evidence`` is the envelope verbatim — every figure with its unit, its
    sanctioned reading, its health and its ``asOf``. **Every number an interface
    displays comes from here.**

    ``judgment`` is the model's, and carries no number at all: a verdict line, a
    thesis, and one reading per axis. ``verdict`` is absent because it is the
    extracted column, and ``citedFieldIds`` is stored complete beside it — the
    inline artifact shows how many there were, and an audit view shows which.
    """
    return {
        "audit": {
            "schemaVersion": ANALYSIS_SCHEMA_VERSION,
            "fieldProfileVersion": envelope.field_profile_version,
            "promptVersion": PROMPT_VERSION,
            "model": model,
            "route": route,
            "generatedAt": generated_at.isoformat(),
            "inputFingerprint": envelope.fingerprint(),
        },
        "evidence": envelope.as_wire(),
        "judgment": {
            "verdictLine": fragment.verdict_line,
            "thesis": fragment.thesis,
            "leadAxis": fragment.lead_axis.value,
            "axes": [axis.as_wire() for axis in fragment.axes],
        },
        "citedFieldIds": list(fragment.cited_field_ids),
    }


def analysis_producer(
    *,
    client: LLMClient | None = None,
    config: LLMConfig | None = None,
    session_factory: Callable[[], Session] | None = None,
    clock: Callable[[], datetime] | None = None,
    cross_sections: Mapping[str, CrossSection] | None = None,
) -> Producer:
    """A producer that publishes real Analyses, for one evening's worth of work.

    Returns a plain ``(symbol, trading_day) -> AnalysisDraft`` because that is
    the seam ``produce_analysis`` takes; everything configurable is closed over
    here rather than threaded through a signature the lifecycle would have to
    know about.

    **The cross-sectional rankings are measured once per Trading Day and reused.**
    A percentile is a position within a sample, so measuring it per symbol would
    both cost a Universe scan per symbol and rank each member against a sample
    measured at a different moment. One producer instance is one cohort's worth of
    work, and the cache below is scoped to it rather than to the process — a
    producer built tomorrow measures tomorrow's rankings.

    ``client`` is injected by tests and by anything that already holds one. Left
    out, a client is built and closed around each generation: an
    ``httpx.AsyncClient`` binds its connection pool to the event loop that made
    it, and this producer runs each generation in a loop of its own, so a pooled
    client kept across calls would be a pool bound to a loop that has closed.
    """
    resolved_config = config or llm_config_from_settings()
    model = resolved_config.model_for(Workload.BATCH)
    route = resolved_config.route.base_url
    now = clock or (lambda: datetime.now(timezone.utc))
    open_session = session_factory or get_sync_db
    rankings: dict[date, Mapping[str, CrossSection]] = {}

    def produce(symbol: str, trading_day: date) -> AnalysisDraft:
        # Before anything is read or reserved. A caller on the loop thread is
        # wired wrong, and finding that out after a Universe scan and a run
        # lookup would report it as whatever failed next.
        _refuse_on_the_event_loop()

        with open_session() as session:
            run = stored_run(session, symbol, trading_day)
            if run is None:
                # The lifecycle creates the run before it calls a producer, so
                # this is a caller that skipped it rather than a race: without a
                # run there is no owner to reserve spend against, and a
                # generation nobody could charge is one nobody can audit.
                raise ProductionFailure(
                    "persistence_error",
                    f"Không tìm thấy Analysis Run cho {symbol} "
                    f"{trading_day.isoformat()} để tính chi phí sinh Analysis.",
                )
            run_id = run.id

            if cross_sections is not None:
                sample = cross_sections
            else:
                if trading_day not in rankings:
                    rankings[trading_day] = measure_cross_sections(
                        session, trading_day
                    )
                sample = rankings[trading_day]

            envelope = build_envelope(
                session, symbol, trading_day, cross_sections=sample
            )

        fragment = _run_generation(
            envelope,
            client=client,
            config=resolved_config,
            model=model,
            run_id=run_id,
        )
        return AnalysisDraft(
            verdict=fragment.verdict.value,
            payload=analysis_payload(
                envelope,
                fragment,
                model=model,
                route=route,
                generated_at=now(),
            ),
        )

    return produce


def produce_pair(
    session: Session,
    symbol: str,
    trading_day: date,
    *,
    origin: RunOrigin = RunOrigin.NIGHTLY,
    producer: Producer | None = None,
) -> RunOutcome:
    """Produce one pair for real, through the lifecycle that owns the writes.

    The one entry point anything outside this package uses to produce. It exists
    so that "produce this pair" is a single call rather than the pairing of a
    state machine with a producer that every caller would have to get right —
    and getting it wrong once, with a stub, is exactly the failure mode this
    milestone retires.
    """
    return produce_analysis(
        session,
        symbol,
        trading_day,
        producer or analysis_producer(),
        origin=origin,
    )


def retry_pair(
    session: Session,
    user_id: int,
    symbol: str,
    trading_day: date,
    *,
    producer: Producer | None = None,
) -> RunOutcome:
    """Retry one pair on behalf of a watcher, producing for real.

    The standing checks stay in the lifecycle — a user who does not watch the
    symbol, and a symbol that has left the **Universe**, are refusals about the
    request rather than about production.
    """
    return retry_analysis(
        session,
        user_id,
        symbol,
        trading_day,
        producer or analysis_producer(),
    )


def _refuse_on_the_event_loop() -> None:
    """Refuse to produce from the loop thread, in words a reader can act on.

    The producer seam is synchronous because the lifecycle around it is: it holds
    a synchronous ``Session`` and owns its own transaction boundaries. The
    generation underneath is async because the LLM boundary is. Bridging them
    with ``asyncio.run`` is correct **only off the event loop thread**, which is
    where every caller in this system already is — the dispatcher and the request
    handlers both reach synchronous work through ``in_sync_write``, which is
    ``asyncio.to_thread``.

    Called on the loop thread ``asyncio.run`` raises something about a loop
    already running, which says nothing about what the caller did. A crash rather
    than a ``ProductionFailure``: the taxonomy describes attempts that could not
    finish, and this is a caller wired wrong.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    raise RuntimeError(
        "the Analysis producer is synchronous and runs its generation in a "
        "loop of its own; call it off the event loop thread, through "
        "in_sync_write or asyncio.to_thread"
    )


def _run_generation(
    envelope: EvidenceEnvelope,
    *,
    client: LLMClient | None,
    config: LLMConfig,
    model: str,
    run_id: int | str,
) -> AnalysisFragment:
    """Run the one async call from synchronous code."""

    async def run() -> AnalysisFragment:
        llm = client if client is not None else build_client(config)
        try:
            return await generate_fragment(
                llm, envelope, model=model, run_id=run_id
            )
        finally:
            if client is None:
                await llm.aclose()

    return asyncio.run(run())


__all__ = [
    "AUDIT_FIELDS",
    "analysis_payload",
    "analysis_producer",
    "produce_pair",
    "retry_pair",
]
