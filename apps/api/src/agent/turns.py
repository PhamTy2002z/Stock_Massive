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
the boundaries the loop names — a tool round, a cancellation, a terminal state.
Per-token writes would turn one conversation into thousands of row versions for
no recoverable benefit, and the only thing a reader wants back is the current
state of the answer, which is what a checkpoint is.

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
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any

from src.alpha.refusals import AlphaRefusal
from src.core.llm.config import LLMConfig

from .events import (
    Subscriber,
    TurnPublisher,
    snapshot_from_draft,
    terminal_event_for,
)
from .loop import (
    TurnAttachment,
    TurnDraft,
    TurnOutcome,
    TurnRequest,
    TurnStatus,
)
from .persistence import TURN_INCOMPLETE, AgentPersistence, TurnRecord
from .prompt import RuntimeContext

logger = logging.getLogger(__name__)

# What ``TurnService`` is handed instead of building an ``AgentLoop`` itself: the
# loop needs a Tool Catalog, an LLM client and a budget, none of which are this
# module's business, and the checkpoint and publisher are.
LoopFactory = Callable[..., Any]
CheckpointPayload = Callable[[TurnDraft], dict[str, Any]]

# The cap on what a reader typed. It is on encoded bytes rather than characters,
# because that is what the request actually carries and what a Vietnamese
# sentence costs three times over.
#
# It used to read "no attachments, and no user-supplied URL is ever fetched",
# and that was the last surviving record of a decision taken in a document tree
# since deleted. Half of it still holds: no user-supplied URL is ever fetched
# here. The other half was reversed on 2026-08-29 by
# ``plans/260829-0010-composer-attachments`` — a Turn may now carry attachments.
# They do not travel through this cap: a Turn references them by id, and their
# size is held down by the attachment store's own per-file cap, per-user quota
# and token ceiling (``agent/attachments.py``). Widening this number would
# therefore buy nothing an attachment needs.
MAX_USER_INPUT_BYTES = 8 * 1024

# The wall-clock ceiling for one Turn, including the time it
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
    # deadline or by shutdown leaves behind, and the only place the prose it
    # managed to produce still exists in this process.
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


def _elapsed_ms(record: TurnRecord) -> int:
    """How long a Turn ran, for a Turn no publisher in this process is holding.

    Off the stored timestamps rather than a monotonic clock, because the process
    that started this Turn may be gone: a restart, another worker, or simply a
    Turn that finished yesterday. A Turn still running is measured to now.

    Never negative. Two timestamps written by different transactions can arrive
    a hair out of order, and a Turn that reports having taken minus one second
    is a worse answer than one that reports zero.
    """
    started = record.started_at
    if started is None:
        return 0
    finished = record.finished_at or datetime.now(timezone.utc)
    return max(0, int((finished - started).total_seconds() * 1000))


def draft_content(draft: TurnDraft) -> dict[str, Any]:
    """The checkpoint payload: the answer so far, and the calls behind it.

    ``text`` is the whole answer rather than the last delta, because what a
    reconnecting browser needs is the current state of the answer and not the
    history of how it arrived. It is the same string the snapshot restates and
    the same string the canonical message will store, which is what keeps a
    reader who followed the stream and a reader who rebuilt from here from
    disagreeing about what was said.

    ``answer`` and ``thoughts`` are that same prose split the way a screen draws
    it — the reply, and what was said on the way to it. Both are checkpointed
    rather than recomputed, because the split is made from a fact only the loop
    has (whether a round went on to call tools), and a reader rebuilding from
    here has no way to work it out from ``text`` alone.

    """
    return {
        "text": draft.text or "",
        "answer": draft.answer or "",
        "thoughts": [dict(thought) for thought in draft.thoughts],
        "tool_calls": [call.as_wire() for call in draft.tool_calls],
        "rounds_used": draft.rounds_used,
    }


def assistant_message(
    *,
    text: str,
    tool_calls: Sequence[Mapping[str, Any]] = (),
    status: str,
    answer: str | None = None,
    thoughts: Sequence[Mapping[str, Any]] = (),
    elapsed_ms: int = 0,
) -> dict[str, Any]:
    """The canonical assistant message, in the one place its shape is decided.

    ``status`` is carried on the content and not only on the ``agent_turn`` row.
    A reopened Thread renders the transcript alone, so without it a reader could
    not tell an answer that finished from one a deadline cut off — and the
    transcript would read every truncated answer as complete.

    ``text`` and ``answer`` are both stored, and they are not the same field
    wearing two names. ``text`` is every piece of prose the Turn produced, and
    it is what the next Turn's transcript is built from; ``answer`` is that
    minus the narration, and it is what the reader is shown as the reply. They
    coincide on a Turn that narrated nothing, which is most of them. Keeping
    both means the model's view of the conversation is unaffected by how a
    surface chooses to draw it.

    ``answer`` defaults to ``text``, which is what a message written before this
    split existed means: no narration was recorded, so all of it is the reply.

    """
    content: dict[str, Any] = {
        "text": text,
        "answer": text if answer is None else answer,
        "thoughts": [dict(thought) for thought in thoughts],
        "tool_calls": [dict(call) for call in tool_calls],
        "status": status,
        "elapsed_ms": elapsed_ms,
    }
    return content


def frozen_message(record: TurnRecord) -> Mapping[str, Any] | None:
    """The canonical message for a Turn some restart interrupted.

    Built from the checkpoint, and only from it. Two fields are this process's
    to know — how the Turn ended, and why — and everything else in the message
    is what the build that was actually answering had already written down.

    A checkpoint with no prose in it produces no message: a Turn that was
    interrupted before it said anything has nothing for a reader to keep, and an
    empty assistant bubble in the transcript would be worse than none.
    """
    draft = record.draft_content or {}
    text = str(draft.get("text") or "")
    if not text:
        return None
    return assistant_message(
        text=text,
        # ``None`` rather than ``""`` when the checkpoint predates the split, so
        # the whole of what was said stays the reply instead of becoming an
        # empty one.
        answer=draft.get("answer") or None,
        thoughts=tuple(draft.get("thoughts") or ()),
        tool_calls=tuple(draft.get("tool_calls") or ()),
        status=TURN_INCOMPLETE,
    )


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
        deadline_seconds: float = TURN_DEADLINE_SECONDS,
        shutdown_seconds: float = GRACEFUL_SHUTDOWN_SECONDS,
    ) -> None:
        self._store = store
        self._loop_factory = loop_factory
        self._config = config
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
        attachments: Sequence[TurnAttachment] = (),
    ) -> TurnHandle:
        """Commit the Turn, then start it. Never the other way round.

        A crash between the commit and the task start is recoverable as an
        incomplete Turn rather than as an invisible or duplicated request, which
        is the whole reason the order is this way.

        ``attachments`` splits the two directions on purpose. The committed
        request gets metadata, because that is what a reopened Thread needs to
        draw and what the idempotency key needs to compare. The run gets the
        payload, because only the newest Turn sends pixels.
        """
        assert_input_within_cap(user_text)
        attached = tuple(attachments)
        creation = await self._store.create_turn(
            user_id=user_id,
            thread_id=thread_id,
            turn_id=turn_id,
            user_text=user_text,
            symbols=symbols,
            retry_of_turn_id=retry_of_turn_id,
            # Metadata only, and derived in one place: the committed request
            # records what was attached, and the payload goes to the run.
            attachments=[entry.as_metadata() for entry in attached],
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
            turn_id=record.id,
            request_message_id=record.request_message_id,
            user_id=user_id,
            user_text=user_text,
            runtime=runtime,
            history=tuple(history),
            summary=summary,
            summarised_turns=summarised_turns,
            attachments=attached,
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
            return draft_content(draft)

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


    async def _finish(self, running: RunningTurn, outcome: TurnOutcome) -> TurnRecord:
        """The one terminal transaction, then the terminal event."""
        status, terminal_reason = _terminal_state(running, outcome)
        text = outcome.text or ""
        calls = [call.as_wire() for call in outcome.tool_calls]
        message = (
            assistant_message(
                text=text,
                answer=outcome.answer,
                thoughts=outcome.thoughts,
                tool_calls=calls,
                status=status,
                elapsed_ms=outcome.elapsed_ms,
            )
            if text
            else None
        )
        record = await self._store.finish_turn(
            running.turn.id,
            status=status,
            terminal_reason=terminal_reason,
            message=message,
            draft=draft_content(
                TurnDraft(
                    text=outcome.text,
                    rounds_used=outcome.rounds_used,
                    tool_calls=outcome.tool_calls,
                )
            ),
            last_event_seq=running.publisher.next_seq,
        )
        data: dict[str, Any] = {"message_id": record.response_message_id}
        running.publisher.terminal(
            terminal_event_for(status, has_content=bool(text)),
            status=status,
            terminal_reason=terminal_reason,
            data=data,
        )
        return record

    async def _finish_bare(
        self,
        running: RunningTurn,
        status: str,
        terminal_reason: str,
    ) -> TurnRecord:
        """End a Turn whose loop never handed back an outcome.

        A deadline, a shutdown or an unexpected failure leaves whatever was
        already checkpointed and nothing else. It is still written to a
        canonical message, because a partial answer the user can read is the
        difference between ``incomplete`` and ``failed``.
        """
        draft = running.draft
        text = "" if draft is None else (draft.text or "")
        calls = [] if draft is None else [call.as_wire() for call in draft.tool_calls]
        message = (
            assistant_message(
                text=text,
                # The checkpoint's own split, not a recomputed one: this path
                # never saw the loop finish, so what it has is what was written
                # down at the last boundary.
                answer=None if draft is None else (draft.answer or None),
                thoughts=() if draft is None else draft.thoughts,
                tool_calls=calls,
                status=status,
            )
            if text
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
            terminal_event_for(status, has_content=bool(text)),
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
            elapsed_ms=_elapsed_ms(record),
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
    Shutdown settles as ``incomplete`` for exactly that reason, and this is
    the one place that knows which it was.
    """
    if (
        outcome.status is TurnStatus.CANCELLED
        and running.shutting_down
        and not running.cancel_requested
    ):
        return TURN_INCOMPLETE, "shutdown"
    return outcome.status.value, outcome.terminal_reason


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
    "assistant_message",
    "draft_content",
    "frozen_message",
    "sweep_interrupted_turns",
]
