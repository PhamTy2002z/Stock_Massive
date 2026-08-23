"""The real producer: evidence in, a published Analysis out, and the audit trail.

This is the thing the **Analysis Run** lifecycle has been taking as a parameter
since A2. It assembles the evidence envelope, sends it to the model, and merges
the validated fragment into a payload the backend owns — and it is the only place
those three steps meet. The lifecycle still imports none of it: a producer
arrives as an argument, which is what let the state machine ship before any of
this existed and what lets a test drive every state with a three-line function.

**The middle step has two shapes and this module chooses between them.** The
evidence loop (``analysis_loop.py``) lets the model read more of the evidence
plane before it answers; the one shot (``generation.py``) hands it a fixed
envelope and takes what comes back. Which one runs is configuration, because the
loop trades reproducibility for audit and that trade belongs to a deployment
rather than to a release. Everything after the choice is identical — the same six
semantic rules, the same payload split, the same publication order — and the
``promptVersion`` in the audit block is what says which shape produced a row.

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
whoever called it owns every commit.

**Nothing here is an entry point.** There is one caller in the system, the
dispatcher, and it claims its own runs. A convenience wrapper pairing this
producer with the state machine would be a second way to produce, which is
exactly the shape the retired stub got published through.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.database import get_sync_db
from src.core.llm import (
    LLMClient,
    LLMConfig,
    Workload,
    build_client,
    llm_config_from_settings,
)
from src.stocks.signals.serving import CrossSection

from .analysis_loop import LOOP_PROMPT_VERSION, generate_fragment_in_loop
from .analysis_run import stored_run
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
    prompt_version: str = PROMPT_VERSION,
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

    ``prompt_version`` is a parameter rather than the constant it used to be,
    because there are now two instruction sets: the one-shot contract and the
    loop's, which adds to it. Two Analyses generated under different
    instructions cannot be compared, and this stamp is the only thing that says
    which was which.
    """
    return {
        "audit": {
            "schemaVersion": ANALYSIS_SCHEMA_VERSION,
            "fieldProfileVersion": envelope.field_profile_version,
            "promptVersion": prompt_version,
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
    evidence_loop: bool | None = None,
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

    ``evidence_loop`` chooses which generation runs: the loop that may read more
    of the evidence plane (``analysis_loop.py``), or the single fixed call it
    replaced (``generation.py``). Both are kept reachable because the loop trades
    a real property away — an Analysis it produced cannot be rebuilt from the
    store, only audited — and a deployment that finds that trade wrong turns it
    off rather than waiting for a revert. ``None`` reads the configured default.
    """
    resolved_config = config or llm_config_from_settings()
    model = resolved_config.model_for(Workload.BATCH)
    route = resolved_config.route.base_url
    now = clock or (lambda: datetime.now(timezone.utc))
    open_session = session_factory or get_sync_db
    looping = (
        get_settings().analysis_evidence_loop_enabled
        if evidence_loop is None
        else evidence_loop
    )
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

        # The envelope comes back as well as the fragment, because the loop may
        # have added figures to it and the payload is rendered from an envelope.
        # A figure the model cited has to be in the one that is rendered, or the
        # citation points at nothing.
        fragment, evidence, prompt_version = _run_generation(
            envelope,
            client=client,
            config=resolved_config,
            model=model,
            run_id=run_id,
            looping=looping,
            open_session=open_session,
            clock=now,
        )
        return AnalysisDraft(
            verdict=fragment.verdict.value,
            payload=analysis_payload(
                evidence,
                fragment,
                model=model,
                route=route,
                generated_at=now(),
                prompt_version=prompt_version,
            ),
        )

    return produce


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
    looping: bool,
    open_session: Callable[[], Any],
    clock: Callable[[], datetime],
) -> tuple[AnalysisFragment, EvidenceEnvelope, str]:
    """Run the async generation from synchronous code, either shape of it.

    Answers the fragment, the evidence it is to be rendered against, and the
    instruction set it was produced under. Three values rather than one because
    the looping shape can widen the envelope, and a payload rendered from the
    seed while the fragment cited a figure the loop fetched would carry a
    citation pointing at nothing.

    The one-shot shape widens nothing, so it hands back the envelope it was
    given — the tuple is the same shape for both, which is what keeps the caller
    free of a branch.
    """

    async def run() -> tuple[AnalysisFragment, EvidenceEnvelope, str]:
        llm = client if client is not None else build_client(config)
        try:
            if not looping:
                fragment = await generate_fragment(
                    llm, envelope, model=model, run_id=run_id
                )
                return fragment, envelope, PROMPT_VERSION
            outcome = await generate_fragment_in_loop(
                llm,
                envelope,
                model=model,
                run_id=run_id,
                session_opener=open_session,
                clock=clock,
            )
            if outcome.fetched_field_ids:
                logger.info(
                    "Analysis Run %s read %d field(s) the profile does not name "
                    "over %d round(s): %s",
                    run_id,
                    len(outcome.fetched_field_ids),
                    outcome.rounds_used,
                    ", ".join(outcome.fetched_field_ids),
                )
            return outcome.fragment, outcome.envelope, LOOP_PROMPT_VERSION
        finally:
            if client is None:
                await llm.aclose()

    return asyncio.run(run())


__all__ = [
    "AUDIT_FIELDS",
    "analysis_payload",
    "analysis_producer",
]
