"""The Turn lifecycle: a Turn with a life of its own (#81).

**A Turn must survive a dropped connection.**  That is the A5 exit criterion
this module owns, and it decides everything below: execution is never attached
to a request.

The create transaction commits the user message and the ``agent_turn`` row
*before* execution begins.  Only then does execution start, held as an
``asyncio.Task`` in a process-local registry.  A later subscriber attaches to
the registry; it starts nothing, and its disappearance stops nothing.  Reloading,
navigating away, closing the tab, or losing the network closes one subscriber
and no more.

## Four things worth reading the code for

**The Turn id is an owner-scoped idempotency key.**  The browser chooses the
UUID before the ``POST``, so a reconnecting browser can ask about the Turn it
started rather than the one it hopes it started.  Same id and payload returns
the existing Turn; same id with different payload is a conflict; a Turn under
another user's Thread is not reachable at all.  This layer enforces it; A6 maps
it onto status codes.

**Checkpointing is bounded, not per token.**  At most one write a second, plus
the boundaries ``docs/adr/0013`` names — activity, Widget, cancellation and
terminal.  Per-token writes would turn one conversation into thousands of row
versions for no recoverable benefit, and the only thing a reader wants back is
the current state of the answer, which is what a checkpoint is.

**One terminal transaction.**  The draft is frozen into the canonical assistant
``agent_message`` while ``status``, ``terminal_reason``, ``response_message_id``
and ``finished_at`` are set — together, or not at all.  Before it commits, the
canonical transcript simply does not contain a half-written answer.  The
terminal *event* is published after that transaction, because the client refetches
the Thread when it arrives and must not race the row it is refetching.

**A restart never resumes.**  A Turn left ``running`` by a crash or a deploy is
frozen ``incomplete`` on startup.  Resuming would mean replaying a
non-deterministic model against a store that has moved; an honest ``incomplete``
with everything that ran attached is worth more than a plausible continuation.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from src.alpha.refusals import AlphaRefusal
from src.core.config import get_settings
from src.core.llm import Workload
from src.core.llm.config import LLMConfig

from .events import (
    Subscriber,
    TurnPublisher,
    snapshot_from_draft,
    terminal_event_for,
)
from .grounding import GROUNDING_FAILED, ReleasedBlock
from .loop import TurnDraft, TurnOutcome, TurnRequest, TurnStatus
from .manifest import GateOutcome, assemble_message, build_manifest
from .persistence import (
    INTERRUPTED_REASON,
    TURN_INCOMPLETE,
    TURN_RUNNING,
    AgentPersistence,
    TurnRecord,
)
from .prompt import AnswerKind, RuntimeContext

logger = logging.getLogger(__name__)

# What ``TurnService`` is handed instead of building an ``AgentLoop`` itself: the
# loop needs a Tool Catalog, an LLM client and a budget, none of which are this
# module's business, and the checkpoint and publisher are.
LoopFactory = Callable[..., Any]
CheckpointPayload = Callable[[TurnDraft], dict[str, Any]]

# ``docs/adr/0015``: no attachments, and no user-supplied URL is ever fetched.
# The cap is on encoded bytes rather than characters, because that is what the
# request actually carries and what a Vietnamese sentence costs three times over.
MAX_USER_INPUT_BYTES = 8 * 1024

# ``docs/adr/0013``'s wall-clock ceiling for one Turn, including the time it
# spends waiting for an execution slot.
TURN_DEADLINE_SECONDS = 600.0

# How long active Turns get to reach a safe checkpoint. The container's stop
# grace must exceed it, or the checkpoint this buys never lands.
GRACEFUL_SHUTDOWN_SECONDS = 30.0

# At most one checkpoint a second of ordinary progress. Boundaries bypass it —
# a cancellation or a terminal state that waited out a rate limiter is a
# checkpoint that did not happen.
CHECKPOINT_INTERVAL_SECONDS = 1.0


class UserInputTooLarge(AlphaRefusal):
    """A user message past the 8 KiB UTF-8 cap, refused before dispatch.

    An :class:`AlphaRefusal` so the application's existing handler answers it
    with the same body shape as every other refusal. Refused *before* dispatch,
    which is also why it does not consume the Turn start allowance.
    """

    def __init__(self, size: int, limit: int = MAX_USER_INPUT_BYTES) -> None:
        super().__init__(
            reason="user_input_too_large",
            message="That message is too long. Shorten it and send it again.",
            status_code=413,
        )
        self.size = size
        self.limit = limit


@dataclass
class RunningTurn:
    """One executing Turn, as the process-local registry holds it."""

    turn: TurnRecord
    publisher: TurnPublisher
    task: asyncio.Task[Any] | None = None
    cancel_requested: bool = False
    shutting_down: bool = False
    # The last draft the loop checkpointed. It is what a Turn killed by the
    # deadline or by shutdown leaves behind, and the only place its proven
    # blocks, its citations and its answer kind still exist in this process.
    draft: TurnDraft | None = None

    def cancelled(self) -> bool:
        return self.cancel_requested or self.shutting_down


class Checkpointer:
    """At most one write a second, and always one at a boundary.

    A rate limiter rather than a debounce: a debounce would delay the write, and
    the write that matters most is the one taken as the process is being asked
    to stop.
    """

    def __init__(
        self,
        store: AgentPersistence,
        turn_id: uuid.UUID,
        publisher: TurnPublisher,
        *,
        payload: CheckpointPayload | None = None,
        interval: float = CHECKPOINT_INTERVAL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._store = store
        self._turn_id = turn_id
        self._publisher = publisher
        self._payload = payload or draft_content
        self._interval = interval
        self._clock = clock
        self._last: float | None = None
        self.writes = 0

    async def __call__(self, draft: TurnDraft) -> None:
        now = self._clock()
        if not draft.boundary and self._last is not None:
            if now - self._last < self._interval:
                return
        self._last = now
        self.writes += 1
        await self._store.checkpoint_turn(
            self._turn_id,
            self._payload(draft),
            last_event_seq=self._publisher.seq,
        )


def draft_content(draft: TurnDraft) -> dict[str, Any]:
    """The checkpoint payload, which is the blocks and nothing unproven.

    ``text`` is deliberately absent. The model's raw answer is not a thing a
    reconnecting browser may render — it has not been through the Gate — and a
    checkpoint carrying it would be a route around the validator that nobody
    wrote on purpose.
    """
    return {
        "blocks": [block.as_wire() for block in draft.blocks],
        "rounds_used": draft.rounds_used,
        "tool_calls": len(draft.tool_calls),
    }


def frozen_message(record: TurnRecord) -> Mapping[str, Any] | None:
    """The canonical message for a Turn some restart interrupted.

    Taken from the checkpoint rather than rebuilt, and that is the whole point:
    the Evidence Manifest of an interrupted Turn belongs to the build that
    *produced* it — its prompt version, its model, its git SHA — and this
    process is by definition a different one. Rebuilding it here would stamp
    today's identity on yesterday's answer, which is the one thing a Manifest
    exists to make impossible.

    Only two fields are patched, because only two are this process's to know:
    how the Turn ended, and why.
    """
    draft = record.draft_content or {}
    message = draft.get("message")
    if not isinstance(message, Mapping) or not message.get("blocks"):
        return None
    frozen = dict(message)
    manifest = dict(frozen.get("evidence_manifest") or {})
    manifest["status"] = TURN_INCOMPLETE
    manifest["terminal_reason"] = INTERRUPTED_REASON
    frozen["evidence_manifest"] = manifest
    return frozen


async def sweep_interrupted_turns(
    store: AgentPersistence | None = None,
) -> tuple[TurnRecord, ...]:
    """Freeze whatever a crash or a deploy left active. Resume nothing.

    A free function as well as a :class:`TurnService` method, because the
    application's startup runs it before anything has composed a service, and
    it genuinely needs nothing else: the message it writes comes out of the
    checkpoint, and no execution is started.
    """
    frozen = await (store or AgentPersistence()).freeze_interrupted_turns(
        frozen_message
    )
    if frozen:
        logger.warning(
            "Froze %d Turn(s) left active by a restart; v1 resumes none", len(frozen)
        )
    return frozen


@dataclass(frozen=True)
class TurnHandle:
    """What a caller gets back from ``create``: the row, and whether it is new."""

    turn: TurnRecord
    created: bool
    publisher: TurnPublisher | None = None


class TurnService:
    """Create, execute, observe, cancel, sweep and shut down Turns."""

    def __init__(
        self,
        *,
        store: AgentPersistence,
        loop_factory: LoopFactory,
        config: LLMConfig,
        tool_catalog_version: str,
        git_sha: str | None = None,
        deadline_seconds: float = TURN_DEADLINE_SECONDS,
        shutdown_seconds: float = GRACEFUL_SHUTDOWN_SECONDS,
    ) -> None:
        self._store = store
        self._loop_factory = loop_factory
        self._config = config
        self._tool_catalog_version = tool_catalog_version
        # Read from configuration rather than defaulted to a literal: a Manifest
        # that records "unknown" for every answer records nothing anyone can
        # dispute, and the deployment is the only thing that knows the SHA.
        self._git_sha = git_sha or get_settings().git_sha
        self._deadline = deadline_seconds
        self._shutdown_seconds = shutdown_seconds
        self._running: dict[uuid.UUID, RunningTurn] = {}

    # -- creation ---------------------------------------------------------

    async def create(
        self,
        *,
        user_id: int,
        thread_id: uuid.UUID | str,
        turn_id: uuid.UUID | str,
        user_text: str,
        runtime: RuntimeContext,
        symbols: Sequence[str] = (),
        history: Sequence[Any] = (),
        summary: str | None = None,
        summarised_turns: int = 0,
        retry_of_turn_id: uuid.UUID | str | None = None,
    ) -> TurnHandle:
        """Commit the Turn, then start it. Never the other way round.

        A crash between the commit and the task start is recoverable as an
        incomplete Turn rather than as an invisible or duplicated request, which
        is the whole reason the order is this way.
        """
        assert_input_within_cap(user_text)
        creation = await self._store.create_turn(
            user_id=user_id,
            thread_id=thread_id,
            turn_id=turn_id,
            user_text=user_text,
            symbols=symbols,
            retry_of_turn_id=retry_of_turn_id,
        )
        if not creation.created:
            # Idempotent: the same id and payload returns the Turn that already
            # exists, and starts nothing at all.
            existing = self._running.get(creation.turn.id)
            return TurnHandle(
                turn=creation.turn,
                created=False,
                publisher=None if existing is None else existing.publisher,
            )

        record = creation.turn
        publisher = TurnPublisher(record.id)
        running = RunningTurn(turn=record, publisher=publisher)
        self._running[record.id] = running
        request = TurnRequest(
            thread_id=record.thread_id,
            request_message_id=record.request_message_id,
            user_id=user_id,
            user_text=user_text,
            runtime=runtime,
            history=tuple(history),
            summary=summary,
            summarised_turns=summarised_turns,
        )
        running.task = asyncio.create_task(
            self._execute(running, request),
            name=f"turn-{record.id}",
        )
        return TurnHandle(turn=record, created=True, publisher=publisher)

    # -- execution --------------------------------------------------------

    async def _execute(self, running: RunningTurn, request: TurnRequest) -> TurnRecord:
        turn_id = running.turn.id
        publisher = running.publisher
        def remember(draft: TurnDraft) -> dict[str, Any]:
            running.draft = draft
            return self._checkpoint_payload(draft)

        checkpointer = Checkpointer(self._store, turn_id, publisher, payload=remember)
        agent = self._loop_factory(checkpoint=checkpointer, publisher=publisher)
        await self._store.mark_turn_running(turn_id)
        # The registry entry outlives execution by exactly one step: the Turn
        # stays reachable until its terminal event has been published, so a
        # subscriber attaching in that window is told how the Turn ended rather
        # than being handed a snapshot that still says ``running``.
        try:
            try:
                outcome = await asyncio.wait_for(
                    agent.run(request, running.cancelled),
                    self._deadline,
                )
            except TimeoutError:
                return await self._finish_bare(running, "incomplete", "turn_deadline")
            except asyncio.CancelledError:
                # The shutdown path cancels the task after asking politely; the
                # checkpoint it already reached is what survives, and the
                # startup sweep writes the terminal state.
                raise
            except AlphaRefusal as refusal:
                return await self._finish_bare(running, "incomplete", refusal.reason)
            except Exception:
                logger.exception("Turn %s failed", turn_id)
                return await self._finish_bare(running, "incomplete", "turn_failed")
            return await self._finish(running, outcome)
        finally:
            self._running.pop(turn_id, None)

    @staticmethod
    def _rendered(blocks: Sequence[ReleasedBlock]) -> tuple[list[dict[str, Any]], str]:
        """The two forms every assistant message needs, derived once.

        Three call sites wanted the same pair — checkpoint, terminal, and the
        bare terminal — and the third had already drifted to reading the text
        back out of the wire form it had just written.
        """
        return (
            [block.as_wire() for block in blocks],
            "\n\n".join(block.text for block in blocks),
        )

    def _checkpoint_payload(self, draft: TurnDraft) -> dict[str, Any]:
        """One checkpoint: the proven blocks, and the message they would form.

        The whole assembled message is checkpointed, not just the blocks, so
        that a Turn a restart interrupts can be frozen into a canonical message
        carrying *its own* Evidence Manifest — the prompt version, model and git
        SHA of the build that actually answered. A later process cannot
        reconstruct those, and stamping its own on the answer would defeat the
        Manifest.
        """
        payload = draft_content(draft)
        blocks, text = self._rendered(draft.blocks)
        payload["message"] = (
            self._message(
                blocks=blocks,
                text=text,
                answer_kind=draft.answer_kind,
                status=TURN_RUNNING,
                terminal_reason=None,
                citations=draft.citations,
                outcomes=GateOutcome(grounding="in_progress"),
            )
            if draft.blocks
            else None
        )
        return payload

    def _message(
        self,
        *,
        blocks: Sequence[Mapping[str, Any]],
        text: str,
        answer_kind: AnswerKind,
        status: str,
        terminal_reason: str | None,
        citations: Sequence[Any] = (),
        outcomes: GateOutcome | None = None,
        provider_request_id: str | None = None,
    ) -> dict[str, Any]:
        """One assistant message, Notice and Manifest attached by the backend."""
        manifest = build_manifest(
            git_sha=self._git_sha,
            model=self._config.model_for(Workload.SESSION),
            route=self._config.route.base_url,
            provider_request_id=provider_request_id,
            tool_catalog_version=self._tool_catalog_version,
            answer_kind=answer_kind,
            status=status,
            terminal_reason=terminal_reason,
            citations=citations,
            outcomes=outcomes,
        )
        return assemble_message(
            blocks=blocks,
            text=text,
            answer_kind=answer_kind,
            manifest=manifest,
            citations=citations,
        )

    async def _finish(self, running: RunningTurn, outcome: TurnOutcome) -> TurnRecord:
        """The one terminal transaction, then the terminal event."""
        status, terminal_reason = _terminal_state(running, outcome)
        blocks, text = self._rendered(outcome.blocks)
        message = (
            self._message(
                blocks=blocks,
                text=text,
                answer_kind=outcome.answer_kind,
                status=status,
                terminal_reason=terminal_reason,
                citations=outcome.citations,
                outcomes=_outcomes(outcome),
                provider_request_id=outcome.provider_request_id,
            )
            if outcome.blocks
            else None
        )
        record = await self._store.finish_turn(
            running.turn.id,
            status=status,
            terminal_reason=terminal_reason,
            message=message,
            symbols=_symbols_of(outcome),
            draft=draft_content(
                TurnDraft(
                    text=None,
                    rounds_used=outcome.rounds_used,
                    tool_calls=outcome.tool_calls,
                    blocks=outcome.blocks,
                )
            ),
            last_event_seq=running.publisher.next_seq,
        )
        running.publisher.terminal(
            terminal_event_for(status, has_content=bool(outcome.blocks)),
            status=status,
            terminal_reason=terminal_reason,
            data={"message_id": record.response_message_id},
        )
        return record

    async def _finish_bare(
        self,
        running: RunningTurn,
        status: str,
        terminal_reason: str,
    ) -> TurnRecord:
        """End a Turn whose loop never handed back an outcome.

        A deadline, a shutdown or an unexpected failure leaves the blocks that
        were already checkpointed and nothing else. They are still written to a
        canonical message, because a partial answer the user can read is the
        difference between ``incomplete`` and ``failed``.
        """
        draft = running.draft
        blocks, text = self._rendered(() if draft is None else draft.blocks)
        message = (
            self._message(
                blocks=blocks,
                text=text,
                answer_kind=(
                    AnswerKind.EDUCATION if draft is None else draft.answer_kind
                ),
                status=status,
                terminal_reason=terminal_reason,
                citations=() if draft is None else draft.citations,
                outcomes=GateOutcome(grounding="not_reached"),
            )
            if blocks
            else None
        )
        record = await self._store.finish_turn(
            running.turn.id,
            status=status,
            terminal_reason=terminal_reason,
            message=message,
            last_event_seq=running.publisher.next_seq,
        )
        running.publisher.terminal(
            terminal_event_for(status, has_content=bool(blocks)),
            status=status,
            terminal_reason=terminal_reason,
            data={"message_id": record.response_message_id},
        )
        return record

    # -- observation and cancellation -------------------------------------

    async def subscribe(
        self, user_id: int, turn_id: uuid.UUID | str
    ) -> Subscriber | None:
        """Attach to a running Turn, or answer from its checkpoint.

        Starts nothing. A Turn that finished before the subscriber connected is
        returned as a terminal snapshot rather than as an empty stream, and a
        Turn under another user's Thread is not found.
        """
        record = await self._store.read_turn(user_id, turn_id)
        if record is None:
            return None
        running = self._running.get(record.id)
        if running is not None:
            return running.publisher.subscribe()
        snapshot = snapshot_from_draft(
            record.id,
            record.draft_content,
            status=record.status,
            terminal_reason=record.terminal_reason,
            through_seq=record.last_event_seq,
            message_id=record.response_message_id,
        )
        subscriber = Subscriber(snapshot)
        subscriber.close()
        return subscriber

    async def cancel(self, user_id: int, turn_id: uuid.UUID | str) -> TurnRecord | None:
        """Authenticated and idempotent; dispatches no new call.

        A read-only call already in flight is allowed to finish, as the loop
        requires. Its trace is kept and its result is simply not fed into
        another round.
        """
        record = await self._store.request_turn_cancel(user_id, turn_id)
        if record is None:
            return None
        running = self._running.get(record.id)
        if running is not None:
            running.cancel_requested = True
        return record

    # -- startup and shutdown ---------------------------------------------

    async def sweep(self) -> tuple[TurnRecord, ...]:
        """Freeze whatever a crash or a deploy left active. Resume nothing."""
        return await sweep_interrupted_turns(self._store)

    async def shutdown(self, timeout: float | None = None) -> None:
        """Give every active Turn its window to reach a safe checkpoint."""
        deadline = self._shutdown_seconds if timeout is None else timeout
        running = list(self._running.values())
        if not running:
            return
        for entry in running:
            entry.shutting_down = True
        tasks = [entry.task for entry in running if entry.task is not None]
        _done, pending = await asyncio.wait(tasks, timeout=deadline)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.wait(pending, timeout=1.0)
            # Whatever did not reach a terminal state inside the window is left
            # for the startup sweep, which is the same honest ``incomplete`` a
            # crash would have produced.
            logger.warning(
                "%d Turn(s) did not reach a checkpoint within %.0fs of shutdown",
                len(pending),
                deadline,
            )

    @property
    def running_ids(self) -> tuple[uuid.UUID, ...]:
        return tuple(self._running)

    def running(self, turn_id: uuid.UUID | str) -> RunningTurn | None:
        """The registry entry for one Turn, or ``None`` once it is terminal.

        Read-only access to the process-local registry, for the two callers
        that legitimately need the task itself: the shutdown path, and a test
        asserting that a Turn outlived its subscriber.
        """
        key = turn_id if isinstance(turn_id, uuid.UUID) else uuid.UUID(str(turn_id))
        return self._running.get(key)


def assert_input_within_cap(user_text: str, limit: int = MAX_USER_INPUT_BYTES) -> None:
    """Refuse an oversized message before anything is committed or dispatched."""
    size = len(user_text.encode("utf-8"))
    if size > limit:
        raise UserInputTooLarge(size, limit)


def _terminal_state(running: RunningTurn, outcome: TurnOutcome) -> tuple[str, str | None]:
    """How the Turn ended, as the lifecycle rather than the loop sees it.

    The loop is handed one ``cancelled`` predicate and cannot tell a user
    pressing stop from a container being asked to stop, so it reports both as
    ``cancelled_by_user``. The difference matters to the reader: a cancellation
    is something they did, and a shutdown is something that happened to them.
    ``docs/adr/0013`` lists shutdown under ``incomplete`` for exactly that
    reason, and this is the one place that knows which it was.
    """
    if (
        outcome.status is TurnStatus.CANCELLED
        and running.shutting_down
        and not running.cancel_requested
    ):
        return TURN_INCOMPLETE, "shutdown"
    return outcome.status.value, outcome.terminal_reason


def _outcomes(outcome: TurnOutcome) -> GateOutcome:
    """What the three validators decided, in the Manifest's own vocabulary."""
    blocked = outcome.terminal_reason == GROUNDING_FAILED
    recommendation = "not_applicable"
    if any(block.kind.value == "recommendation" for block in outcome.blocks):
        recommendation = "released"
    if blocked:
        recommendation = "blocked"
    return GateOutcome(
        scope="refused" if outcome.answer_kind is AnswerKind.REFUSAL else "in_scope",
        grounding="blocked" if blocked else "passed",
        recommendation=recommendation,
        failure_code=outcome.grounding_failure_code,
    )


def _symbols_of(outcome: TurnOutcome) -> tuple[str, ...]:
    """The symbols this Turn discussed, for the Thread's GIN-indexed array."""
    return tuple(sorted({block.symbol for block in outcome.blocks if block.symbol}))


__all__ = [
    "CHECKPOINT_INTERVAL_SECONDS",
    "GRACEFUL_SHUTDOWN_SECONDS",
    "MAX_USER_INPUT_BYTES",
    "TURN_DEADLINE_SECONDS",
    "Checkpointer",
    "RunningTurn",
    "TurnHandle",
    "TurnService",
    "UserInputTooLarge",
    "assert_input_within_cap",
    "draft_content",
    "frozen_message",
    "sweep_interrupted_turns",
]
