"""Run the golden corpus through the real chat lane and write one artifact.

Three design decisions are load-bearing, and each of them is a correction of
something an earlier draft got wrong.

**The runner reads the store; it does not instrument the loop.** Everything a
score needs is already written down by the runtime — the trajectory in
``agent_tool_call.result``, the source list and the round index in the assistant
message's ``tool_calls`` payload, the money in ``llm_call_usage``. Wrapping the
client instead would mean re-implementing the composition root, because
``build_alpha_desk`` builds the client inside itself and ``AgentLoop`` takes six
internals. A harness coupled to that constructor breaks the first time the loop
is touched, which is exactly what the phases after this one do.

**The web is frozen; the model is not.** A run today and a run in three weeks
have to be comparable, and ``WebLane`` serves search results fresh for thirty
minutes and pages for a day — so the difference between two artifacts would be
code plus the Internet plus sampling, three terms and one measurement. Recording
and replaying at the ``WebLane.read`` seam removes the middle term. The model
stays live on purpose: what the model chooses to search for and read is the
thing being measured.

**A half-green run is not a run.** Hitting the spend ceiling, losing a case, or
grading a corpus other than the one declared all end as ``incomplete`` rather
than as a slightly worse pass.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import json
import logging
import subprocess
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

logger = logging.getLogger("golden.run")

#: The runner's own account. A separate identity for two reasons that pull the
#: same way: the per-user ceilings below are relaxed for it and must not be
#: relaxed for anybody real, and every baseline query filters this address out
#: so that measuring the system does not pollute what is being measured.
GOLDEN_EMAIL = "golden-runner@stockmassive.local"
GOLDEN_NAME = "Golden Runner"

#: Bumped from ``@1`` when trials arrived. The bump is not cosmetic and the old
#: number is refused rather than tolerated: every ``@1`` artifact in this
#: repository was written *before* the Phase 0 teardown — they carry
#: ``run_study`` and ``render_signal_desk`` in their tool calls — so an ``@1``
#: file compared against an ``@2`` one would be comparing two different
#: products. ``grade.py`` calls them ``unusable``, which is the truth.
SCHEMA = "golden.artifact@2"
WEB_FIRST_MODE = "web_first"
MODES = (WEB_FIRST_MODE,)


def corpus_digest(corpus: Mapping[str, Any]) -> str:
    """Stable identity of the exact corpus a run measured."""
    payload = json.dumps(
        corpus,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# -- the frozen web --------------------------------------------------------


class ReplayLane:
    """``WebLane`` with a tape. Records on the first run, replays after.

    The key is ``(kind, key)`` — the same pair the real lane hashes — so a
    replay serves the search or the page the recording served, and two runs
    weeks apart differ only by what the model decided to do.

    A replay miss is not papered over. It falls through to the live lane so the
    run still finishes, and it is counted; any miss at all makes the run
    ``incomplete``, because a partly-replayed artifact is not comparable with
    the one it claims to be comparable with.
    """

    def __init__(self, inner: Any, tape: dict[str, Any], *, replay: bool) -> None:
        self._inner = inner
        self._tape = tape
        self._replay = replay
        # Strict only when the caller asked to replay a tape that already
        # existed. The auto-replay the later trials switch on is a different
        # situation with a different correct answer — see ``start_replaying``.
        self._strict = replay
        self.misses: list[str] = []
        self.fresh_reads: list[str] = []
        self.hits = 0
        self.recorded = 0

    @staticmethod
    def _slot(kind: str, key: str) -> str:
        return f"{kind}:{hashlib.sha256(key.strip().encode('utf-8')).hexdigest()}"

    def start_replaying(self) -> None:
        """Switch to the tape for the trials after the first.

        This is what makes a multi-trial run measure the model rather than the
        Internet: a query trial one already asked is served the page trial one
        saw, so two trials of one case differ only by what the model did.

        It does **not** make the run strict, and that distinction is the whole
        subtlety of multi-trial. A miss here means the model searched for
        something it had not searched for before — which is the model varying,
        the very thing being measured — so the read goes out live, joins the
        tape, and the run stays comparable. A miss under ``--replay`` means
        something else: the tape does not match the corpus it claims to, and
        that artifact is not comparable with anything, which is why that case
        alone ends the run ``incomplete``.
        """
        self._replay = True

    @property
    def replaying(self) -> bool:
        return self._replay

    def retrieval_times(self) -> dict[tuple[str, str], float]:
        """When each recorded read happened, keyed the way the lane keys it.

        The runner hands this down to every source so that ``retrieved_at``
        travels with the evidence. It is the *only* time a source carries today
        — the search provider returns no publication date on general-topic
        results — and a temporal grader with neither would have nothing to read.
        """
        return {
            (str(entry.get("kind") or ""), str(entry.get("key") or "")): float(
                entry.get("fetched_at") or 0.0
            )
            for entry in self._tape.values()
            if isinstance(entry, Mapping)
        }

    def read(self, kind: str, key: str, fetch: Callable[[], Any]) -> Any:
        from src.core.web_lane import WebRead

        slot = self._slot(kind, key)
        if self._replay and slot in self._tape:
            self.hits += 1
            entry = self._tape[slot]
            return WebRead(
                payload=entry["payload"],
                fetched_at=float(entry.get("fetched_at") or 0.0),
                age_seconds=0.0,
                stale=False,
            )
        if self._replay:
            (self.misses if self._strict else self.fresh_reads).append(f"{kind}:{key}")
        read = self._inner.read(kind, key, fetch)
        self._tape[slot] = {
            "kind": kind,
            "key": key,
            "payload": read.payload,
            "fetched_at": read.fetched_at,
        }
        self.recorded += 1
        return read


# -- identity and ceilings -------------------------------------------------


def ensure_golden_user() -> tuple[int, str]:
    """Find or create the runner's account. Returns ``(id, email)``."""
    from sqlalchemy import select

    from src.auth.models import User
    from src.auth.security import hash_password
    from src.core.database import sync_session_factory

    with sync_session_factory() as session:
        found = session.execute(
            select(User).where(User.email == GOLDEN_EMAIL)
        ).scalar_one_or_none()
        if found is not None:
            return found.id, found.email
        created = User(
            email=GOLDEN_EMAIL,
            hashed_password=hash_password(uuid.uuid4().hex),
            full_name=GOLDEN_NAME,
            is_active=True,
        )
        session.add(created)
        session.commit()
        session.refresh(created)
        logger.info("created the golden runner account (id=%s)", created.id)
        return created.id, created.email


def release_stranded_turns(user_id: int) -> int:
    """Free Turns an earlier run left active — for this account only.

    ``active_turns_per_user`` is **1**, so a single Turn left ``running`` by a
    killed run refuses every Turn of the next one, and the whole corpus comes
    back empty for a reason that has nothing to do with what is being measured.
    That happened once and cost a full run.

    Deliberately narrower than ``sweep_interrupted_turns``, which frees every
    active Turn in the deployment. This process is not the application starting
    up; freeing a real reader's in-flight Turn because a measurement wants a
    clear runway would be the harness reaching into production, which is the
    thing this whole directory is arranged to prevent.
    """
    from sqlalchemy import select

    from src.agent.persistence import (
        ACTIVE_TURN_STATUSES,
        INTERRUPTED_REASON,
        TURN_INCOMPLETE,
    )
    from src.alpha.models import AgentThread, AgentTurn
    from src.core.database import sync_session_factory

    with sync_session_factory() as session:
        rows = list(
            session.execute(
                select(AgentTurn)
                .join(AgentThread, AgentThread.id == AgentTurn.thread_id)
                .where(
                    AgentThread.user_id == user_id,
                    AgentTurn.status.in_(ACTIVE_TURN_STATUSES),
                )
            ).scalars()
        )
        for row in rows:
            row.status = TURN_INCOMPLETE
            row.terminal_reason = INTERRUPTED_REASON
            row.finished_at = datetime.now(timezone.utc)
        if rows:
            session.commit()
            logger.warning(
                "released %d Turn(s) an earlier run left active for the golden account",
                len(rows),
            )
    return len(rows)


def runner_config(concurrency: int = 1) -> Any:
    """The production configuration with the per-user ceilings lifted.

    ``turn_starts_per_day`` defaults to twenty, which a twenty-case corpus hits
    exactly — one retry and the run dies. It is the binding ceiling here, and it
    is a per-account policy rather than a spend guard, so lifting it for one
    synthetic account changes nothing about what a real one may do.

    The spend ceilings go with it, and the run's own ``--ceiling-usd`` takes
    over. That is a deliberate swap, not a removal: this process refuses to
    start without a ceiling and stops at it, and every call is still reserved
    and reconciled into ``llm_call_usage`` the same way.

    ``concurrency`` lifts the two active-Turn ceilings, and they are not the
    same kind of ceiling. ``active_turns_per_user`` is a per-account policy, so
    raising it for one synthetic account changes nothing about what a real
    account may do. ``active_turns_system`` is a **deployment-wide** cap of
    three, and raising it means this process may take slots a reader would
    otherwise get: it is raised only as far as the run asks for, only inside
    this process's own config object, and a measurement run is expected to be
    the only workload on the deployment while it runs. At ``concurrency=1``,
    the default, neither number moves.
    """
    from src.core.config import get_settings
    from src.core.llm import llm_config_from_settings
    from src.core.llm.config import UserCeilings

    base = llm_config_from_settings(get_settings())
    system = base.ceilings.active_turns_system
    if system is not None and concurrency > 1:
        system = max(int(system), concurrency)
    return dataclasses.replace(
        base,
        ceilings=UserCeilings(
            turn_starts_per_day=None,
            active_turns_per_user=max(1, concurrency),
            active_turns_system=system,
            daily_usd=None,
            rolling_30d_usd=None,
        ),
    )


def runtime_constants(config: Any) -> dict[str, Any]:
    """The ceilings in force during this run, read at run time.

    Read rather than hard-coded so the artifact records the build it measured.
    Phase 04 changes one of these numbers; without this block, the artifact from
    before and the artifact from after would look comparable when they are not.
    """
    from src.agent.domain import active_pack
    from src.agent.executor import MAX_EXTERNAL_CALLS_PER_ROUND
    from src.agent.loop import MAX_EXTERNAL_TOOL_CALLS, MAX_TOOL_ROUNDS
    from src.agent.prompt.sections import PROMPT_VERSION
    from src.agent.tools.web import (
        MAX_PAGE_TEXT_CHARS,
        MAX_RESULTS,
        MAX_SNIPPET_CHARS,
    )
    from src.agent.toolsets import CHAT_TOOLSETS, resolve_toolset
    from src.core.llm.admission import TURN_COST_MICRO_USD

    pack = active_pack()
    catalogue = resolve_toolset(CHAT_TOOLSETS)
    return {
        # The surface the model was actually offered, resolved at run time. An
        # artifact that records the ceilings but not the tool list cannot tell
        # a regression in behaviour from a capability that was switched on
        # between two runs — and this is the phase where a capability plane
        # starts adding them.
        "tool_catalog": list(catalogue),
        "toolsets": list(CHAT_TOOLSETS),
        "MAX_EXTERNAL_TOOL_CALLS": MAX_EXTERNAL_TOOL_CALLS,
        "MAX_TOOL_ROUNDS": MAX_TOOL_ROUNDS,
        "MAX_EXTERNAL_CALLS_PER_ROUND": MAX_EXTERNAL_CALLS_PER_ROUND,
        "MAX_RESULTS": MAX_RESULTS,
        "MAX_SNIPPET_CHARS": MAX_SNIPPET_CHARS,
        "MAX_PAGE_TEXT_CHARS": MAX_PAGE_TEXT_CHARS,
        "TURN_COST_MICRO_USD": TURN_COST_MICRO_USD,
        "PROMPT_VERSION": PROMPT_VERSION,
        "domain_pack": {
            "name": pack.name,
            "version": pack.version,
            "identity": pack.identity,
        },
        "model": config.model_for(_session_workload()),
    }


def _session_workload() -> Any:
    from src.core.llm import Workload

    return Workload.SESSION


def check_mode(mode: str) -> str:
    """Validate the harness lane name and hand it back.

    It used to map onto a Turn mode the service took as a keyword. That keyword
    is gone — the Phase 0 teardown removed the board mode and left ``chat`` as
    the only thing persistence records — so ``mode`` here is now purely the
    harness's own label for which corpus lane produced an artifact. Kept because
    the artifact records it and two lanes are not comparable; validated because
    a lane name nobody registered should fail loudly rather than land in an
    artifact as a string.
    """
    if mode not in MODES:
        raise ValueError(f"unknown golden mode: {mode!r}")
    return mode


# -- reading one finished Turn back out of the store -----------------------


def _domain(url: str) -> str | None:
    host = urlsplit(url or "").netloc.lower()
    return host or None


def _retrieved_at(
    call: Mapping[str, Any], times: Mapping[tuple[str, str], float]
) -> str | None:
    """When the read behind one call happened, as an ISO instant.

    Reconstructs the lane's own key from the call's arguments rather than
    storing a second copy of it: ``web_search`` keys on the query and its
    recency window, ``fetch_url`` on the validated URL. A key the tape does not
    hold returns ``None`` — a source with no retrieval time is a source the
    temporal grader declines to judge, which is the honest outcome and not a
    pass.
    """
    arguments = call.get("arguments") or {}
    name = call.get("name")
    if name == "web_search":
        query = str(arguments.get("query") or "").strip()
        recency = arguments.get("recency_days")
        key = f"{query}\n{int(recency) if recency is not None else ''}"
        stamp = times.get(("search", key))
    elif name == "fetch_url":
        url = str(arguments.get("url") or "").strip()
        stamp = times.get(("url", url))
        if stamp is None:
            # ``validate_public_url`` normalises before the lane sees the key,
            # so an argument that differs only in its tail still names the same
            # read. Matching on the suffix recovers those without pretending a
            # different page is the same one.
            stamp = next(
                (
                    value
                    for (kind, key), value in times.items()
                    if kind == "url" and url and (key.startswith(url) or url.startswith(key))
                ),
                None,
            )
    else:
        stamp = None
    if not stamp:
        return None
    return datetime.fromtimestamp(float(stamp), tz=timezone.utc).isoformat()


def spend_for(request_message_id: int) -> dict[str, Any]:
    """What one Turn cost, summed over every LLM call it made.

    Summed, not sampled. A web-first Turn averages several calls, so reading one
    row and calling it the price of a Turn understates it by that factor.

    Four token counters rather than two, because ``input_tokens`` is not the
    input. The transport splits what the provider reports (``transport._usage``)
    so the cheap cached part is not billed at the full input price — which means
    the column holds the *fresh* prompt only, and an artifact calling it the
    prompt would report a Turn as having sent less than it sent. The cached read
    and the cache write are the rest of it, and a run cannot say whether the
    automatic prefix cache is working without them.
    """
    from sqlalchemy import func, select

    from src.alpha.models import LlmCallUsage
    from src.core.database import sync_session_factory

    columns = {
        "fresh_input_tokens": LlmCallUsage.input_tokens,
        "cached_read_tokens": LlmCallUsage.cached_read_tokens,
        "cache_write_tokens": LlmCallUsage.cache_write_tokens,
        "output_tokens": LlmCallUsage.output_tokens,
    }
    with sync_session_factory() as session:
        row = session.execute(
            select(
                func.coalesce(
                    func.sum(
                        func.coalesce(
                            LlmCallUsage.actual_micro_usd,
                            LlmCallUsage.reserved_micro_usd,
                        )
                    ),
                    0,
                ),
                *(func.coalesce(func.sum(column), 0) for column in columns.values()),
                func.count(),
            ).where(
                LlmCallUsage.owner_type == "turn_request_message",
                LlmCallUsage.owner_id == str(request_message_id),
            )
        ).one()
    totals = {name: int(value) for name, value in zip(columns, row[1:-1], strict=True)}
    return {
        "micro_usd": int(row[0]),
        # Kept under its old name and holding the same column it always held, so
        # every artifact written before this line stays comparable with every
        # one written after it. What changed is that the three counters beside
        # it say what the name never did.
        "input_tokens": totals["fresh_input_tokens"],
        **totals,
        "prompt_tokens": (
            totals["fresh_input_tokens"]
            + totals["cached_read_tokens"]
            + totals["cache_write_tokens"]
        ),
        "llm_calls": int(row[-1]),
    }


async def await_terminal(
    turn_id: uuid.UUID, *, timeout: float = 60.0
) -> tuple[str, str | None]:
    """Block until the Turn's row is terminal, not merely until its task returned.

    ``active_turns_per_user`` is **1**, and admission counts what the *table*
    says is active. Awaiting the asyncio task is not the same fact: the task can
    return a moment before the terminal write is visible to another session, and
    in that window the next case is refused with ``user_active_turn`` — a case
    lost to the harness rather than to anything being measured. It cost two cases
    of one run before this existed.

    Polls rather than listens, because there is nothing to listen to from
    outside the process that owns the Turn, and a bounded poll is honest about
    that. Returns the status it settled on so the caller can record it.
    """
    from sqlalchemy import select

    from src.agent.persistence import ACTIVE_TURN_STATUSES
    from src.alpha.models import AgentTurn
    from src.core.database import sync_session_factory

    deadline = time.monotonic() + timeout

    def state() -> tuple[str, str | None]:
        with sync_session_factory() as session:
            row = session.execute(
                select(AgentTurn.status, AgentTurn.terminal_reason).where(
                    AgentTurn.id == turn_id
                )
            ).one_or_none()
            return (str(row[0]), row[1]) if row else ("missing", None)

    while True:
        current, reason = await asyncio.to_thread(state)
        if current not in ACTIVE_TURN_STATUSES:
            return current, reason
        if time.monotonic() > deadline:
            logger.warning(
                "Turn %s was still %s after %.0fs; going on anyway",
                turn_id, current, timeout,
            )
            return current, reason
        await asyncio.sleep(0.5)


async def read_case(
    store: Any,
    *,
    case: Mapping[str, Any],
    user_id: int,
    thread_id: uuid.UUID,
    turn_id: uuid.UUID,
    request_message_id: int,
    wall_ms: int,
    terminal_reason: str | None = None,
    mode: str = WEB_FIRST_MODE,
    trial: int = 1,
    retrieval_times: Mapping[tuple[str, str], float] | None = None,
) -> dict[str, Any]:
    """Assemble one case's slice of the artifact from what the runtime wrote.

    Two reads, because they answer different questions. The assistant message
    carries the projection a reader sees — the round index, the source list, and
    the ``external``/``store`` label that the evidence boundary rests on. The
    tool-call traces carry the full result text, which the source list has
    already been trimmed out of and which the citation grader needs.
    """
    view = await store.read_thread(user_id, thread_id)
    traces = await store.traces_for_request(request_message_id)

    answer_text = ""
    payloads: tuple[Mapping[str, Any], ...] = ()
    turn_status = "unknown"
    for message in reversed(view.messages if view else ()):
        if message.role != "assistant":
            continue
        content = message.content or {}
        answer_text = str(content.get("answer") or content.get("text") or "")
        payloads = tuple(
            item for item in (content.get("tool_calls") or ()) if isinstance(item, Mapping)
        )
        turn_status = str(content.get("status") or "unknown")
        break

    full_text_by_call: dict[str, str] = {}
    trace_by_call: dict[str, Any] = {}
    for trace in traces:
        result = trace.result or {}
        call_id = str(trace.tool_call_id or "")
        full_text_by_call[call_id] = str(result.get("text") or "")
        trace_by_call[call_id] = trace

    calls: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    external_chunks: list[str] = []
    store_chunks: list[str] = []
    seen_source: set[tuple[str, str]] = set()

    times = dict(retrieval_times or {})
    for payload in payloads:
        call_id = str(payload.get("id") or "")
        kind = str(payload.get("kind") or "external")
        body = full_text_by_call.get(call_id, "")
        trace = trace_by_call.get(call_id)
        arguments = dict(trace.arguments) if trace is not None else {}
        retrieved_at = _retrieved_at({"name": payload.get("name"), "arguments": arguments}, times)
        calls.append(
            {
                "id": call_id,
                "name": payload.get("name"),
                "round": payload.get("round"),
                "status": payload.get("status"),
                "kind": kind,
                "summary": payload.get("summary"),
                "result_count": payload.get("result_count"),
                "result_chars": len(body),
                "arguments": arguments,
                "retrieved_at": retrieved_at,
                "result_text": body,
                # What the advisory threat scan made of this result. Read off
                # the persisted call payload rather than a column of its own,
                # which is the whole reason the verdict is stored there: a
                # measurement of how often the scan fires on ordinary pages is
                # the number phase 08 sets its false-positive bar from, and it
                # would not exist if the flag were live-only.
                "scan": payload.get("scan"),
            }
        )
        (external_chunks if kind == "external" else store_chunks).append(body)
        for item in payload.get("results") or ():
            if not isinstance(item, Mapping):
                continue
            url = str(item.get("url") or "")
            title = str(item.get("title") or "")
            marker = (url, title)
            if marker in seen_source:
                continue
            seen_source.add(marker)
            sources.append(
                {
                    "url": url,
                    "domain": _domain(url),
                    "title": title,
                    "snippet": item.get("snippet"),
                    "published_at": item.get("published_at"),
                    # When this Turn read the page, as opposed to when the page
                    # was published. The two are different facts and the
                    # temporal rules of §2 need both; this is the one the
                    # runtime can supply today.
                    "retrieved_at": retrieved_at,
                    "from_call": call_id,
                }
            )

    model_visible_parts = [str(case.get("question") or "")]
    for call in calls:
        model_visible_parts.append(json.dumps(call.get("arguments") or {}, ensure_ascii=False))
        model_visible_parts.append(str(call.get("result_text") or ""))

    return {
        "id": case.get("id"),
        "trial": trial,
        "question": case.get("question"),
        "family": case.get("family"),
        "expect": dict(case.get("expect") or {}),
        "as_of": case.get("as_of"),
        "traps": list(case.get("traps") or ()),
        "ground_truth": dict(case.get("ground_truth") or {}) or None,
        "mode": mode,
        "why_a_fluent_answer_fails": case.get("why_a_fluent_answer_fails"),
        "turn": {
            "id": str(turn_id),
            "thread_id": str(thread_id),
            "request_message_id": request_message_id,
            "status": turn_status,
            "terminal_reason": terminal_reason,
            "wall_ms": wall_ms,
        },
        "answer_text": answer_text,
        "tool_calls": calls,
        "model_visible_text": "\n".join(model_visible_parts),
        "external_calls": sum(1 for call in calls if call.get("kind") == "external"),
        "sources": sources,
        "external_evidence_text": "\n".join(external_chunks),
        "store_evidence_text": "\n".join(store_chunks),
        "cost": spend_for(request_message_id),
    }


# -- the run ---------------------------------------------------------------


async def run_corpus(
    *,
    corpus: Mapping[str, Any],
    ceiling_micro_usd: int,
    tape_path: Path,
    replay: bool,
    limit: int | None,
    git_sha: str | None = None,
    mode: str = WEB_FIRST_MODE,
    trials: int = 1,
    concurrency: int = 1,
) -> dict[str, Any]:
    from src.agent import tools
    from src.agent.prompt import RuntimeContext
    from src.agent.service import build_alpha_desk
    from src.agent.tools.web import register_web_tools
    from src.core.web_lane import WebLane

    started = datetime.now(timezone.utc)
    mode = check_mode(mode)
    user_id, email = ensure_golden_user()
    released = release_stranded_turns(user_id)
    config = runner_config(concurrency)
    desk = build_alpha_desk(config=config)

    # Registration replaces by name, so this swaps the two web tools for ones
    # sharing a taped lane. Ordering is the whole trick: the composition root
    # has already installed the defaults, and this is a legitimate refresh of
    # the same names rather than a second registry.
    tape: dict[str, Any] = {}
    if tape_path.exists():
        tape = json.loads(tape_path.read_text(encoding="utf-8")).get("entries", {})
    lane = ReplayLane(WebLane(), tape, replay=replay)
    register_web_tools(lane=lane)

    declared = list(corpus.get("cases") or ())
    cases = declared[:limit] if limit is not None else declared

    results: list[dict[str, Any]] = []
    spent = 0
    status = "complete"
    reason: str | None = None

    planned = len(cases) * trials
    gate = asyncio.Semaphore(max(1, concurrency))
    stopped = False

    async def run_one(trial: int, index: int, case: Mapping[str, Any]) -> None:
        """One case-trial, start to settled, holding one concurrency slot."""
        nonlocal spent, status, reason, stopped
        async with gate:
            if stopped or spent >= ceiling_micro_usd:
                if not stopped:
                    stopped = True
                    status = "incomplete"
                    reason = (
                        f"spend ceiling reached after {len(results)} of {planned} "
                        f"case-trial(s): {spent} of {ceiling_micro_usd} micro-USD"
                    )
                return

            thread = await desk.store.create_thread(
                user_id, title=f"{case.get('id')} t{trial}"
            )
            turn_id = uuid.uuid4()
            began = time.monotonic()
            handle = await desk.turns.create(
                user_id=user_id,
                thread_id=thread.id,
                turn_id=turn_id,
                user_text=str(case.get("question") or ""),
                runtime=RuntimeContext(today=datetime.now().date(), user_name=GOLDEN_NAME),
            )
            running = desk.turns.running(turn_id)
            if running is not None and running.task is not None:
                await asyncio.shield(asyncio.gather(running.task, return_exceptions=True))
            _settled, terminal_reason = await await_terminal(turn_id)
            wall_ms = int((time.monotonic() - began) * 1000)

            entry = await read_case(
                desk.store,
                case=case,
                user_id=user_id,
                thread_id=thread.id,
                turn_id=turn_id,
                request_message_id=handle.turn.request_message_id,
                wall_ms=wall_ms,
                terminal_reason=terminal_reason,
                mode=mode,
                trial=trial,
                retrieval_times=lane.retrieval_times(),
            )
            entry["_order"] = (trial, index)
            results.append(entry)
            spent += int(entry["cost"]["micro_usd"])
            logger.info(
                "%s t%d -> %s, %d source(s), %d micro-USD (%d/%d spent, %d/%d done)",
                case.get("id"),
                trial,
                entry["turn"]["status"],
                len(entry["sources"]),
                entry["cost"]["micro_usd"],
                spent,
                ceiling_micro_usd,
                len(results),
                planned,
            )

    try:
        # Trials stay sequential and cases inside a trial go wide. That split is
        # what keeps the tape meaningful: trial one must finish recording before
        # trial two can be served what it recorded, while two cases of the same
        # trial share nothing and can run side by side.
        for trial in range(1, trials + 1):
            if stopped:
                break
            if trial > 1 and not lane.replaying:
                lane.start_replaying()
            await asyncio.gather(
                *(run_one(trial, index, case) for index, case in enumerate(cases))
            )
    finally:
        await desk.aclose()

    # Completion order is not corpus order once cases run side by side, and an
    # artifact whose cases are shuffled by how fast each answer came back is
    # needlessly hard to read beside another one.
    results.sort(key=lambda entry: entry.pop("_order"))

    if lane.misses:
        status = "incomplete"
        reason = (
            f"web replay missed {len(lane.misses)} key(s); this artifact is not "
            "comparable with the one it replayed"
        )
    lost = [
        entry["id"]
        for entry in results
        if entry["turn"]["status"] == "unknown"
        or entry["turn"].get("terminal_reason") == "user_active_turn"
    ]
    if lost and status == "complete":
        status = "incomplete"
        reason = (
            f"{len(lost)} case(s) produced no assistant message at all "
            f"({', '.join(str(item) for item in lost[:5])}); the Turn never ran"
        )
    if len(results) != planned and status == "complete":
        status = "incomplete"
        reason = f"ran {len(results)} of {planned} case-trial(s)"
    if limit is not None and status == "complete":
        status = "partial"
        reason = f"--limit ran {len(cases)} of the corpus' {len(declared)} case(s)"

    tape_path.parent.mkdir(parents=True, exist_ok=True)
    tape_body = json.dumps({"entries": tape}, ensure_ascii=False)
    tape_path.write_text(tape_body, encoding="utf-8")
    tape_sha = hashlib.sha256(tape_body.encode("utf-8")).hexdigest()

    return {
        "schema": SCHEMA,
        "run": {
            "started_at": started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "git_sha": git_sha or _git_sha(),
            "mode": mode,
            "corpus_id": corpus.get("corpus_id"),
            # Which questions, not just how many. A corpus is edited between
            # rounds — a failing case reworded, a family topped up — and two
            # artifacts naming the same corpus_id are otherwise indistinguishable
            # from two runs of the same questions.
            "corpus_sha256": corpus_digest(corpus),
            "corpus_selection": dict(corpus.get("selection") or {}) or None,
            "corpus_cases": len(cases),
            # What the corpus file holds, beside what this run was asked for. A
            # ``--limit`` run is a smoke test rather than a shorter measurement,
            # and an artifact that cannot say which it was would be compared
            # with a full one sooner or later.
            "corpus_declared_cases": len(declared),
            # How many times each case was asked. One is a measurement of a
            # single sample; the baseline this phase exists to produce needs
            # several, because a pass rate read off one trial has no interval
            # around it and cannot support a threshold.
            "trials": trials,
            "planned_case_trials": planned,
            # How many Turns ran side by side. It changes no answer — Turns
            # share nothing — but it does change ``turn.wall_ms``, so two runs
            # at different concurrencies are comparable on every dimension
            # except latency, and this is the field that says so.
            "concurrency": concurrency,
            "limit": limit,
            "runner_user_id": user_id,
            "runner_email": email,
            "ceiling_micro_usd": ceiling_micro_usd,
            "spent_micro_usd": spent,
            "status": status,
            "incomplete_reason": reason,
            "runtime_constants": runtime_constants(config),
            "released_stranded_turns": released,
            "web_replay": {
                "mode": "replay" if replay else "record",
                "tape": str(tape_path),
                "tape_sha256": tape_sha,
                "hits": lane.hits,
                "recorded": lane.recorded,
                "misses": lane.misses,
                # Reads a later trial asked for that no earlier trial had. Not
                # misses: the model exploring differently is the thing a
                # multi-trial baseline exists to see, and the read is taped for
                # the trials after it.
                "fresh_reads": len(lane.fresh_reads),
            },
            # Everything needed to say what this artifact measured, gathered in
            # one place rather than spread across the block above. An eval log
            # a reader cannot re-identify months later is a log that quietly
            # gets compared with the wrong thing — the failure mode both
            # previous batteries died of.
            "provenance": {
                "artifact_schema": SCHEMA,
                "git_sha": git_sha or _git_sha(),
                "corpus_id": corpus.get("corpus_id"),
                "corpus_schema": corpus.get("schema"),
                "corpus_sha256": corpus_digest(corpus),
                "tape_sha256": tape_sha,
                "trials": trials,
                "concurrency": concurrency,
                # Filled in by the judge pass, which runs after this one and
                # writes into the artifact it reads. Named here so the shape of
                # the block does not depend on whether the judge ran.
                "judge_model": None,
                "judge_prompt_version": None,
            },
        },
        "cases": results,
    }


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:  # noqa: BLE001 - a run outside a checkout still measures
        return "unknown"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the golden corpus.")
    # No default. A runner that can start without a ceiling will eventually
    # start without one, and the whole envelope is $45 a month.
    parser.add_argument(
        "--ceiling-usd",
        type=float,
        required=True,
        help="hard spend ceiling for this run, in USD; required",
    )
    parser.add_argument("--mode", choices=MODES, default=WEB_FIRST_MODE)
    parser.add_argument("--corpus", default=None)
    parser.add_argument("--out", default=None, help="artifact path; defaults to a stamped file")
    parser.add_argument("--tape", default="golden/artifacts/web-tape.json")
    parser.add_argument(
        "--replay",
        action="store_true",
        help="serve web reads from the tape instead of the live lane",
    )
    parser.add_argument("--limit", type=int, default=None, help="run only the first N cases")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help=(
            "how many Turns of one trial may run side by side; raises the "
            "runner account's active-Turn ceilings and, above three, the "
            "deployment-wide one. Changes latency, not answers"
        ),
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=1,
        help=(
            "how many times to ask each case; trial 1 records the tape and the "
            "rest replay it, so only the model varies between them"
        ),
    )
    # Passed in when the run happens somewhere without a checkout — the API
    # container, for one. An artifact that cannot name the build it measured is
    # not comparable with another artifact, which is the whole job here.
    parser.add_argument("--git-sha", default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if args.ceiling_usd <= 0:
        parser.error("--ceiling-usd must be positive")
    if args.trials < 1:
        parser.error("--trials must be at least 1")
    if args.concurrency < 1:
        parser.error("--concurrency must be at least 1")

    corpus_path = args.corpus or "golden/web_first.json"
    corpus = json.loads(Path(corpus_path).read_text(encoding="utf-8"))
    stamp = datetime.now(timezone.utc).strftime("%y%m%d-%H%M%S")
    out = Path(args.out or f"golden/artifacts/{corpus.get('corpus_id', 'run')}-{stamp}.json")

    artifact = asyncio.run(
        run_corpus(
            corpus=corpus,
            ceiling_micro_usd=int(round(args.ceiling_usd * 1_000_000)),
            tape_path=Path(args.tape),
            replay=bool(args.replay),
            limit=args.limit,
            git_sha=args.git_sha,
            mode=args.mode,
            trials=args.trials,
            concurrency=args.concurrency,
        )
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"artifact: {out}")
    print(f"status:   {artifact['run']['status']}")
    print(f"spent:    {artifact['run']['spent_micro_usd']} micro-USD")
    return 0 if artifact["run"]["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
