"""Short-lived persistence operations for Threads and Tool Call Traces.

Every public method is async for the agent path, but the work runs in a thread
over the repository's synchronous SQLAlchemy factory.  A method owns exactly
one short transaction; a Turn never owns a database session.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from types import EllipsisType
from typing import Any, TypeVar

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.alpha.models import (
    ACTIVE_TURN_STATUSES,
    FLAG_REASONS,
    TURN_ADMITTED,
    TURN_COMPLETE,
    TURN_INCOMPLETE,
    TURN_RUNNING,
    AgentMessage,
    AgentThread,
    AgentToolCall,
    AgentTurn,
)
from src.core.database import sync_session_factory
from src.stocks.shared import validate_symbol

T = TypeVar("T")
SessionFactory = Callable[[], Session]
MessageBuilder = Callable[["TurnRecord"], Mapping[str, Any] | None]
MAX_SEQUENCE_RETRIES = 20
TOOL_CALL_RETENTION_DAYS = 90

# How much of the opening question a Thread is named by. Long enough for a
# whole short question, short enough to sit on one line of the sidebar.
THREAD_TITLE_LENGTH = 60

# The stable reason a Turn frozen by the startup sweep carries. V1 never resumes
# execution after a restart, so this is a terminal reason and not a state a
# later pass reconsiders.
INTERRUPTED_REASON = "interrupted_restart"


def flag_counts_between(
    session: Session,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
) -> dict[str, int]:
    """How many messages carry each reason, over a half-open window.

    A module-level function over a lent session rather than only a method,
    because it has two callers that reach the database differently: the agent
    path through :meth:`AgentPersistence.flag_counts`, and the fixed ops query
    (``src/agent/ops.py``) which is already holding a read-only session onto the
    application store. One implementation, because a second copy is the one that
    would stop agreeing about what a window includes.

    Every reason is a key even at zero — a report that omits a reason nobody
    chose reads as a reason nobody can choose.
    """
    counts = dict.fromkeys(FLAG_REASONS, 0)
    query = select(AgentMessage.flagged_reason, func.count()).where(
        AgentMessage.flagged_reason.is_not(None)
    )
    if since is not None:
        query = query.where(AgentMessage.flagged_at >= since)
    if until is not None:
        query = query.where(AgentMessage.flagged_at < until)
    for reason, total in session.execute(
        query.group_by(AgentMessage.flagged_reason)
    ):
        # A reason outside the vocabulary cannot be written through this module,
        # and a row carrying one would be a fact about the database rather than
        # a category — so it is left out of the count rather than silently
        # folded into ``other``.
        if reason in counts:
            counts[reason] = int(total)
    return counts


@dataclass(frozen=True)
class MessageRecord:
    id: int
    thread_id: uuid.UUID
    seq: int
    role: str
    content: Mapping[str, Any]
    created_at: datetime
    # The whole of v1's dispute surface, and null on almost every message.
    # Carried on the record rather than fetched separately so that a reopened
    # Thread renders what was already flagged from the read it already does.
    flagged_reason: str | None = None
    flagged_at: datetime | None = None
    # The opposite mark, and one column because it carries no reason. Read on
    # the same transcript read for the same purpose: an answer already marked
    # helpful must come back marked.
    helpful_at: datetime | None = None


@dataclass(frozen=True)
class ThreadRecord:
    id: uuid.UUID
    user_id: int
    title: str | None
    symbols: tuple[str, ...]
    pinned_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ThreadView(ThreadRecord):
    messages: tuple[MessageRecord, ...]


@dataclass(frozen=True)
class ToolCallRecord:
    id: int
    thread_id: uuid.UUID
    request_message_id: int
    tool_name: str
    arguments: Mapping[str, Any]
    result: Mapping[str, Any] | None
    status: str
    error: str | None
    latency_ms: int | None
    prompt_tokens: int | None
    completion_tokens: int | None
    started_at: datetime
    #: The route's id for the call, when it sent one. Absent on rows written
    #: before the column existed.
    tool_call_id: str | None = None
    #: Left over from the harness that recorded a preview and its full size in
    #: two places. The size the model was shown a preview of now rides
    #: ``result`` beside the preview itself, so nothing writes this column.
    spilled_bytes: int | None = None


@dataclass(frozen=True)
class TurnRecord:
    """One row of the lifecycle table, as the service layer reads it."""

    id: uuid.UUID
    thread_id: uuid.UUID
    request_message_id: int
    response_message_id: int | None
    retry_of_turn_id: uuid.UUID | None
    status: str
    terminal_reason: str | None
    cancel_requested_at: datetime | None
    started_at: datetime
    finished_at: datetime | None
    last_event_seq: int
    draft_content: Mapping[str, Any] | None

    @property
    def is_terminal(self) -> bool:
        return self.status not in ACTIVE_TURN_STATUSES


@dataclass(frozen=True)
class TurnCreation:
    """The Turn the create transaction settled on, and whether it is new.

    ``created`` is what tells a caller whether to start execution. A resubmitted
    id returns the Turn that already exists and starts nothing — which is the
    whole point of an idempotency key on a flaky network.
    """

    turn: TurnRecord
    created: bool


class UnflaggableMessage(ValueError):
    """The message exists and is the caller's, and is still not markable.

    Separate from "not found" on purpose. A user's own question and a context
    summary are both real rows this caller owns, so answering 404 would say
    something false; a verdict is an action on what the *assistant* said, and
    that is the sentence this exception carries. The transport maps it to 409.

    ``verb`` is what the caller was trying to do, because both verdicts share
    this guard: one exception type means one 409 mapping, and the sentence still
    names the action that was refused rather than the wrong one.
    """

    def __init__(self, message_id: int, role: str, verb: str = "flagged") -> None:
        super().__init__(
            f"Message {message_id} has role {role!r}; only an assistant message "
            f"can be {verb}"
        )
        self.message_id = message_id
        self.role = role


class TurnPayloadConflict(ValueError):
    """The same Turn id was submitted with a different payload.

    Separate from "not found" on purpose: a client that reuses an id for new
    text has a bug, and answering it with the earlier Turn's content would be a
    silently wrong answer rather than a loud one. A6 maps this to ``409``.
    """

    def __init__(self, turn_id: uuid.UUID) -> None:
        super().__init__(
            f"Turn {turn_id} already exists with a different payload; a Turn id is "
            "an idempotency key and cannot be reused for new input"
        )
        self.turn_id = turn_id


def _uuid(value: uuid.UUID | str) -> uuid.UUID:
    """Coerce a Thread or Turn identifier, both of which arrive as either."""
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _turn_record(row: AgentTurn) -> TurnRecord:
    return TurnRecord(
        id=row.id,
        thread_id=row.thread_id,
        request_message_id=row.request_message_id,
        response_message_id=row.response_message_id,
        retry_of_turn_id=row.retry_of_turn_id,
        status=row.status,
        terminal_reason=row.terminal_reason,
        cancel_requested_at=row.cancel_requested_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        last_event_seq=int(row.last_event_seq or 0),
        draft_content=(
            dict(row.draft_content) if row.draft_content is not None else None
        ),
    )


def _thread_record(row: AgentThread) -> ThreadRecord:
    return ThreadRecord(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        symbols=tuple(row.symbols or ()),
        pinned_at=row.pinned_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _message_record(row: AgentMessage) -> MessageRecord:
    return MessageRecord(
        id=row.id,
        thread_id=row.thread_id,
        seq=row.seq,
        role=row.role,
        content=dict(row.content),
        created_at=row.created_at,
        flagged_reason=row.flagged_reason,
        flagged_at=row.flagged_at,
        helpful_at=row.helpful_at,
    )


def _trace_record(row: AgentToolCall) -> ToolCallRecord:
    return ToolCallRecord(
        id=row.id,
        thread_id=row.thread_id,
        request_message_id=row.request_message_id,
        tool_name=row.tool_name,
        arguments=dict(row.arguments),
        result=dict(row.result) if row.result is not None else None,
        status=row.status,
        error=row.error,
        latency_ms=row.latency_ms,
        prompt_tokens=row.prompt_tokens,
        completion_tokens=row.completion_tokens,
        started_at=row.started_at,
        tool_call_id=row.tool_call_id,
        spilled_bytes=row.spilled_bytes,
    )


def thread_title_from(text: str) -> str | None:
    """Name a Thread by the question that opened it.

    The opening question, not a summary of the conversation: it is the one line
    the reader wrote themselves, so it is the line they will recognise the
    Thread by later. Whitespace is collapsed because a pasted question arrives
    with the newlines of wherever it was copied from, and a title that wraps a
    line break renders as a gap in the sidebar.

    A question cut mid-word keeps the ellipsis so the name reads as truncated
    rather than as a sentence that stops; a question that fits keeps its own
    punctuation. Empty text names nothing — the sidebar already falls back to
    the Thread's timestamp, which is a truer name than a blank one.
    """
    collapsed = re.sub(r"\s+", " ", text).strip()
    if not collapsed:
        return None
    if len(collapsed) <= THREAD_TITLE_LENGTH:
        return collapsed
    clipped = collapsed[:THREAD_TITLE_LENGTH]
    spaced = clipped.rsplit(" ", 1)[0] if " " in clipped else clipped
    return f"{spaced.rstrip()}…"


def _insert_message(
    session: Session,
    thread_id: uuid.UUID,
    role: str,
    content: Mapping[str, Any],
    symbols: Sequence[str],
) -> AgentMessage:
    """Append one transcript row inside the caller's transaction.

    Takes a session rather than opening one, because the terminal transaction of
    a Turn has to write the assistant message and the Turn's terminal fields
    together or not at all.
    """
    thread = session.execute(
        select(AgentThread).where(AgentThread.id == thread_id)
    ).scalar_one_or_none()
    if thread is None:
        raise LookupError(f"Thread {thread_id} does not exist")
    current = session.execute(
        select(func.max(AgentMessage.seq)).where(AgentMessage.thread_id == thread_id)
    ).scalar_one()
    message = AgentMessage(
        thread_id=thread_id,
        seq=(current or 0) + 1,
        role=role,
        content=dict(content),
    )
    held = list(thread.symbols or ())
    for symbol in symbols:
        if symbol not in held:
            held.append(symbol)
    thread.symbols = held
    thread.updated_at = datetime.now(timezone.utc)
    session.add(message)
    session.flush()
    return message


class AgentPersistence:
    """The complete read/write surface for ticket #74."""

    def __init__(self, session_factory: SessionFactory = sync_session_factory) -> None:
        self._session_factory = session_factory

    async def create_thread(self, user_id: int, title: str | None = None) -> ThreadRecord:
        return await asyncio.to_thread(self._create_thread, user_id, title)

    def _create_thread(self, user_id: int, title: str | None) -> ThreadRecord:
        with self._session_factory() as session:
            row = AgentThread(
                id=uuid.uuid4(),
                user_id=user_id,
                title=title,
                symbols=[],
            )
            session.add(row)
            session.commit()
            return _thread_record(row)

    async def list_threads(self, user_id: int) -> tuple[ThreadRecord, ...]:
        return await asyncio.to_thread(self._list_threads, user_id)

    def _list_threads(self, user_id: int) -> tuple[ThreadRecord, ...]:
        with self._session_factory() as session:
            rows = session.execute(
                select(AgentThread)
                .where(AgentThread.user_id == user_id)
                .order_by(
                    # Pinned first, and inside that group in the order they were
                    # pinned. Ordering happens here rather than in the sidebar
                    # because every reader of this list wants the same order,
                    # and a client that sorted it could disagree with the next.
                    AgentThread.pinned_at.desc().nullslast(),
                    AgentThread.updated_at.desc(),
                    AgentThread.created_at.desc(),
                    AgentThread.id.desc(),
                )
            ).scalars()
            return tuple(_thread_record(row) for row in rows)

    async def read_thread(
        self, user_id: int, thread_id: uuid.UUID | str
    ) -> ThreadView | None:
        return await asyncio.to_thread(self._read_thread, user_id, _uuid(thread_id))

    def _read_thread(self, user_id: int, thread_id: uuid.UUID) -> ThreadView | None:
        with self._session_factory() as session:
            row = session.execute(
                select(AgentThread).where(
                    AgentThread.id == thread_id,
                    AgentThread.user_id == user_id,
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            messages = session.execute(
                select(AgentMessage)
                .where(AgentMessage.thread_id == thread_id)
                .order_by(AgentMessage.seq.asc())
            ).scalars()
            base = _thread_record(row)
            return ThreadView(
                **base.__dict__,
                messages=tuple(_message_record(message) for message in messages),
            )

    async def read_message(self, user_id: int, message_id: int) -> MessageRecord | None:
        """One transcript row, but only if this user owns the Thread it is in.

        Ownership is a join for the same reason :meth:`_owned_turn` joins:
        ``agent_message`` has no ``user_id`` and should not grow one. The Widget
        replay route is the caller, and it resolves the descriptor *stored on
        the message* rather than one the client sent — so a reader can only ever
        get back the slice their own answer was written against.
        """
        return await asyncio.to_thread(self._read_message, user_id, message_id)

    def _read_message(self, user_id: int, message_id: int) -> MessageRecord | None:
        with self._session_factory() as session:
            row = session.execute(
                select(AgentMessage)
                .join(AgentThread, AgentThread.id == AgentMessage.thread_id)
                .where(AgentMessage.id == message_id, AgentThread.user_id == user_id)
            ).scalar_one_or_none()
            return None if row is None else _message_record(row)

    # -- flagging a message (#99) -----------------------------------------

    async def flag_message(
        self, user_id: int, message_id: int, *, reason: str
    ) -> MessageRecord | None:
        """Mark one assistant message with one reason. Idempotent per message.

        Writing the pair *replaces* whatever was there: a second flag on the
        same message is the reader correcting themselves, and accumulating both
        would need the table ``docs/adr/0016`` refuses. Pressing the *same*
        reason again writes nothing at all, stamp included. ``None`` means the
        message is not this user's to flag — the same answer as a message that
        does not exist, because a caller who can tell those apart has been told
        that an id exists.

        The vocabulary is checked here as well as at the request boundary, and
        both are load bearing: the schema's validator is what makes a bad label
        a 422 instead of a 500, and this one is what stops any other caller —
        a script, the ops lane — from writing a reason nothing can count.

        **This opens nothing.** No ticket, no notification, no suspension. The
        value is downstream and manual: a flag confirmed as a genuine failure is
        a defect somebody reads the transcript for.
        """
        if reason not in FLAG_REASONS:
            raise ValueError(
                f"{reason!r} is not a flag reason; expected one of "
                f"{', '.join(FLAG_REASONS)}"
            )
        return await asyncio.to_thread(self._set_flag, user_id, message_id, reason)

    async def unflag_message(
        self, user_id: int, message_id: int
    ) -> MessageRecord | None:
        """Clear both columns. Never one of them."""
        return await asyncio.to_thread(self._set_flag, user_id, message_id, None)

    def _set_flag(
        self, user_id: int, message_id: int, reason: str | None
    ) -> MessageRecord | None:
        with self._session_factory() as session:
            row = session.execute(
                # Ownership is the same join ``_read_message`` uses:
                # ``agent_message`` has no ``user_id`` and should not grow one.
                select(AgentMessage)
                .join(AgentThread, AgentThread.id == AgentMessage.thread_id)
                .where(AgentMessage.id == message_id, AgentThread.user_id == user_id)
            ).scalar_one_or_none()
            if row is None:
                return None
            if reason is not None and row.role != "assistant":
                raise UnflaggableMessage(message_id, row.role)
            if row.flagged_reason == reason:
                # Idempotent, and never a second stamp — the same rule
                # ``_request_turn_cancel`` follows. Re-stamping an unchanged
                # reason would move that flag out of one date window and into a
                # later one, and the counts read by date range are exactly what
                # the ops query reports.
                return _message_record(row)
            row.flagged_reason = reason
            row.flagged_at = None if reason is None else datetime.now(timezone.utc)
            session.commit()
            return _message_record(row)

    # -- marking a message helpful ----------------------------------------

    async def mark_helpful(
        self, user_id: int, message_id: int
    ) -> MessageRecord | None:
        """Stamp one assistant message as helpful. Idempotent per message.

        The mirror of :meth:`flag_message` with the reason taken out, because
        there is nothing to categorise about an answer that worked. Pressing it
        again on an already-marked message writes nothing, stamp included: the
        stamp answers *when the reader said so*, and a second press is the same
        reader saying the same thing.

        ``None`` means the message is not this user's to mark — the same answer
        as a message that does not exist, for the reason the flag gives.
        """
        return await asyncio.to_thread(self._set_helpful, user_id, message_id, True)

    async def clear_helpful(
        self, user_id: int, message_id: int
    ) -> MessageRecord | None:
        """Take the mark back. Nulls the stamp; touches no other column."""
        return await asyncio.to_thread(self._set_helpful, user_id, message_id, False)

    def _set_helpful(
        self, user_id: int, message_id: int, helpful: bool
    ) -> MessageRecord | None:
        with self._session_factory() as session:
            row = session.execute(
                # The same owner-scoped join the flag uses, for the same
                # reason: ``agent_message`` has no ``user_id``.
                select(AgentMessage)
                .join(AgentThread, AgentThread.id == AgentMessage.thread_id)
                .where(AgentMessage.id == message_id, AgentThread.user_id == user_id)
            ).scalar_one_or_none()
            if row is None:
                return None
            if helpful and row.role != "assistant":
                raise UnflaggableMessage(message_id, row.role, verb="marked helpful")
            if (row.helpful_at is not None) == helpful:
                return _message_record(row)
            # The flag is deliberately *not* cleared here. The two marks are
            # exclusive in the UI because a reader presses one thing at a time,
            # not because the store knows they contradict each other — an
            # answer that was useful and got one figure wrong is both.
            row.helpful_at = datetime.now(timezone.utc) if helpful else None
            session.commit()
            return _message_record(row)

    async def flag_counts(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict[str, int]:
        """How many messages carry each reason, over a half-open window.

        Service-wide and not scoped to a user: this is the field signal the
        fixed ops query reads, and it is reconciled against the battery rather
        than shown to anybody. The counting itself is
        :func:`flag_counts_between`, which the ops query calls directly.
        """
        return await asyncio.to_thread(self._flag_counts, since, until)

    def _flag_counts(
        self, since: datetime | None, until: datetime | None
    ) -> dict[str, int]:
        with self._session_factory() as session:
            return flag_counts_between(session, since=since, until=until)

    async def update_thread(
        self,
        user_id: int,
        thread_id: uuid.UUID | str,
        *,
        title: str | None | EllipsisType = ...,
        pinned: bool | EllipsisType = ...,
    ) -> ThreadRecord | None:
        """Rename a Thread, pin it, or both. ``None`` if it is not this user's.

        ``...`` means *not asked for* and ``None`` means *clear it*, because
        those are two different requests: a rename to nothing puts the Thread
        back under its timestamped name, while a pin that carried no title must
        not erase one.

        **``updated_at`` is preserved.** The column carries when the
        conversation was last worked in, and it is what the list is ordered by;
        letting the column's ``onupdate`` fire here would send a Thread to the
        top of the sidebar because somebody corrected its spelling. Naming the
        column in ``SET`` as its own value is what suppresses that default —
        which is also why this is a Core ``UPDATE`` and not an ORM attribute
        assignment: the unit of work re-applies ``onupdate`` for a column it
        thinks nothing wrote.
        """
        return await asyncio.to_thread(
            self._update_thread, user_id, _uuid(thread_id), title, pinned
        )

    def _update_thread(
        self,
        user_id: int,
        thread_id: uuid.UUID,
        title: str | None | EllipsisType,
        pinned: bool | EllipsisType,
    ) -> ThreadRecord | None:
        with self._session_factory() as session:
            # Named as itself, so the column's `onupdate` does not fire.
            values: dict[str, Any] = {"updated_at": AgentThread.updated_at}
            if not isinstance(title, EllipsisType):
                cleaned = title.strip() if title is not None else None
                values["title"] = cleaned[:255] if cleaned else None
            if not isinstance(pinned, EllipsisType):
                # Re-pinning an already pinned Thread keeps its original stamp,
                # so pressing Pin twice does not reorder the pinned group.
                values["pinned_at"] = (
                    func.coalesce(AgentThread.pinned_at, func.now())
                    if pinned
                    else None
                )

            owned = (
                AgentThread.id == thread_id,
                AgentThread.user_id == user_id,
            )
            result = session.execute(update(AgentThread).where(*owned).values(**values))
            if not result.rowcount:
                return None
            session.commit()
            row = session.execute(select(AgentThread).where(*owned)).scalar_one()
            return _thread_record(row)

    async def delete_thread(self, user_id: int, thread_id: uuid.UUID | str) -> bool:
        return await asyncio.to_thread(
            self._delete_thread, user_id, _uuid(thread_id)
        )

    def _delete_thread(self, user_id: int, thread_id: uuid.UUID) -> bool:
        with self._session_factory() as session:
            result = session.execute(
                delete(AgentThread).where(
                    AgentThread.id == thread_id,
                    AgentThread.user_id == user_id,
                )
            )
            session.commit()
            return bool(result.rowcount)

    async def append_message(
        self,
        thread_id: uuid.UUID | str,
        *,
        role: str,
        content: Mapping[str, Any],
        symbols: Sequence[str] = (),
    ) -> MessageRecord:
        if role not in {"user", "assistant", "summary"}:
            raise ValueError(f"unsupported transcript role: {role}")
        normalized = tuple(dict.fromkeys(validate_symbol(symbol) for symbol in symbols))
        return await asyncio.to_thread(
            self._append_message,
            _uuid(thread_id),
            role,
            dict(content),
            normalized,
        )

    def _append_message(
        self,
        thread_id: uuid.UUID,
        role: str,
        content: Mapping[str, Any],
        symbols: Sequence[str],
    ) -> MessageRecord:
        def write(session: Session) -> MessageRecord:
            message = _insert_message(session, thread_id, role, content, symbols)
            session.commit()
            return _message_record(message)

        return self._with_sequence_retry(write)

    def _with_sequence_retry(self, work: Callable[[Session], T]) -> T:
        """Run one transaction, retrying the ``UNIQUE(thread_id, seq)`` race.

        The retry lives here rather than in each caller because ``seq`` is
        allocated inside the writing transaction by design (``docs/specs/0003``
        §10.2), so every writer of a transcript row races the same way and none
        of them should have to remember it.
        """
        for attempt in range(MAX_SEQUENCE_RETRIES):
            with self._session_factory() as session:
                try:
                    return work(session)
                except IntegrityError:
                    session.rollback()
                    if attempt + 1 == MAX_SEQUENCE_RETRIES:
                        raise
        raise RuntimeError("sequence allocation retries were exhausted")

    async def threads_discussing(
        self, user_id: int, symbol: str
    ) -> tuple[ThreadRecord, ...]:
        normalized = validate_symbol(symbol)
        return await asyncio.to_thread(self._threads_discussing, user_id, normalized)

    def _threads_discussing(
        self, user_id: int, symbol: str
    ) -> tuple[ThreadRecord, ...]:
        with self._session_factory() as session:
            rows = session.execute(
                select(AgentThread)
                .where(
                    AgentThread.user_id == user_id,
                    AgentThread.symbols.contains([symbol]),
                )
                .order_by(AgentThread.updated_at.desc())
            ).scalars()
            return tuple(_thread_record(row) for row in rows)

    async def record_tool_call(self, trace: Mapping[str, Any]) -> ToolCallRecord:
        return await asyncio.to_thread(self._record_tool_call, dict(trace))

    def _record_tool_call(self, trace: Mapping[str, Any]) -> ToolCallRecord:
        thread_id = _uuid(trace["thread_id"])
        request_message_id = int(trace["request_message_id"])
        with self._session_factory() as session:
            anchor = session.execute(
                select(AgentMessage).where(AgentMessage.id == request_message_id)
            ).scalar_one_or_none()
            if (
                anchor is None
                or anchor.thread_id != thread_id
                or anchor.role != "user"
            ):
                raise ValueError(
                    "a Tool Call Trace must anchor to a user message in its Thread"
                )
            row = AgentToolCall(
                thread_id=thread_id,
                request_message_id=request_message_id,
                tool_name=str(trace["tool_name"]),
                tool_call_id=(
                    str(trace["tool_call_id"])[:128]
                    if trace.get("tool_call_id")
                    else None
                ),
                arguments=dict(trace.get("arguments") or {}),
                result=(
                    dict(trace["result"])
                    if trace.get("result") is not None
                    else None
                ),
                status=str(trace["status"]),
                error=str(trace["error"])[:500] if trace.get("error") else None,
                latency_ms=trace.get("latency_ms"),
                prompt_tokens=trace.get("prompt_tokens"),
                completion_tokens=trace.get("completion_tokens"),
                started_at=trace.get("started_at", datetime.now(timezone.utc)),
            )
            session.add(row)
            session.commit()
            return _trace_record(row)

    async def tool_result(
        self, request_message_id: int, tool_call_id: str
    ) -> Mapping[str, Any] | None:
        """The whole result of one call, by the id the model cites it under.

        What makes a spilled result *retrievable* rather than merely stored: the
        transcript carries a preview, and this is the route back to everything
        the preview stood in for. Scoped to the request message so a call id from
        another Turn cannot be read through it.
        """
        return await asyncio.to_thread(
            self._tool_result, request_message_id, tool_call_id
        )

    def _tool_result(
        self, request_message_id: int, tool_call_id: str
    ) -> Mapping[str, Any] | None:
        with self._session_factory() as session:
            row = session.execute(
                select(AgentToolCall.result).where(
                    AgentToolCall.request_message_id == request_message_id,
                    AgentToolCall.tool_call_id == tool_call_id,
                )
            ).scalar_one_or_none()
            return dict(row) if isinstance(row, Mapping) else None

    async def traces_for_request(
        self, request_message_id: int
    ) -> tuple[ToolCallRecord, ...]:
        return await asyncio.to_thread(self._traces_for_request, request_message_id)

    def _traces_for_request(
        self, request_message_id: int
    ) -> tuple[ToolCallRecord, ...]:
        with self._session_factory() as session:
            rows = session.execute(
                select(AgentToolCall)
                .where(AgentToolCall.request_message_id == request_message_id)
                .order_by(AgentToolCall.started_at.asc(), AgentToolCall.id.asc())
            ).scalars()
            return tuple(_trace_record(row) for row in rows)

    # -- the Turn lifecycle (#81) -----------------------------------------

    async def create_turn(
        self,
        *,
        user_id: int,
        thread_id: uuid.UUID | str,
        turn_id: uuid.UUID | str,
        user_text: str,
        symbols: Sequence[str] = (),
        retry_of_turn_id: uuid.UUID | str | None = None,
    ) -> TurnCreation:
        """Commit the user message and the Turn, before anything is executed."""
        normalized = tuple(dict.fromkeys(validate_symbol(symbol) for symbol in symbols))
        return await asyncio.to_thread(
            self._create_turn,
            user_id,
            _uuid(thread_id),
            _uuid(turn_id),
            user_text,
            normalized,
            None if retry_of_turn_id is None else _uuid(retry_of_turn_id),
        )

    def _create_turn(
        self,
        user_id: int,
        thread_id: uuid.UUID,
        turn_id: uuid.UUID,
        user_text: str,
        symbols: Sequence[str],
        retry_of_turn_id: uuid.UUID | None,
    ) -> TurnCreation:
        # The whole payload, compared as one value rather than field by field.
        # An idempotency key that only checks the text would return the earlier
        # Turn for a request that differed in the symbols it declared — the same
        # id answering a different question, which is what the key exists to
        # make impossible.
        payload: dict[str, Any] = {"text": user_text}
        if symbols:
            payload["symbols"] = list(symbols)

        def write(session: Session) -> TurnCreation:
            existing = self._owned_turn(session, user_id, turn_id)
            if existing is not None:
                request = session.get(AgentMessage, existing.request_message_id)
                stored = dict(request.content or {}) if request is not None else None
                if stored != payload or existing.thread_id != thread_id:
                    raise TurnPayloadConflict(turn_id)
                if existing.retry_of_turn_id != retry_of_turn_id:
                    raise TurnPayloadConflict(turn_id)
                return TurnCreation(turn=_turn_record(existing), created=False)

            thread = session.execute(
                select(AgentThread).where(
                    AgentThread.id == thread_id,
                    AgentThread.user_id == user_id,
                )
            ).scalar_one_or_none()
            if thread is None:
                raise LookupError(f"Thread {thread_id} does not exist")

            message = _insert_message(session, thread_id, "user", payload, symbols)
            # The opening question names the Thread. Only the opening one, and
            # only while the Thread is unnamed: a later question must not
            # rename a conversation the reader is already navigating by, and a
            # name they typed themselves outranks anything derived here.
            if thread.title is None and message.seq == 1:
                thread.title = thread_title_from(user_text)
            turn = AgentTurn(
                id=turn_id,
                thread_id=thread_id,
                request_message_id=message.id,
                retry_of_turn_id=retry_of_turn_id,
                status=TURN_ADMITTED,
                last_event_seq=0,
            )
            session.add(turn)
            session.commit()
            return TurnCreation(turn=_turn_record(turn), created=True)

        return self._with_sequence_retry(write)

    @staticmethod
    def _owned_turn(
        session: Session, user_id: int, turn_id: uuid.UUID
    ) -> AgentTurn | None:
        """The Turn, but only if this user owns the Thread it belongs to.

        Ownership is a join rather than a column: ``agent_turn`` has no
        ``user_id`` and should not grow one, because the Thread already answers
        the question and two answers can disagree.
        """
        return session.execute(
            select(AgentTurn)
            .join(AgentThread, AgentThread.id == AgentTurn.thread_id)
            .where(AgentTurn.id == turn_id, AgentThread.user_id == user_id)
        ).scalar_one_or_none()

    async def read_turn(
        self, user_id: int, turn_id: uuid.UUID | str
    ) -> TurnRecord | None:
        return await asyncio.to_thread(self._read_turn, user_id, _uuid(turn_id))

    def _read_turn(self, user_id: int, turn_id: uuid.UUID) -> TurnRecord | None:
        with self._session_factory() as session:
            row = self._owned_turn(session, user_id, turn_id)
            return None if row is None else _turn_record(row)

    async def mark_turn_running(self, turn_id: uuid.UUID | str) -> None:
        """Leave ``admitted`` at the moment the Turn commits to dispatching."""
        await asyncio.to_thread(self._mark_turn_running, _uuid(turn_id))

    def _mark_turn_running(self, turn_id: uuid.UUID) -> None:
        with self._session_factory() as session:
            row = session.get(AgentTurn, turn_id)
            if row is None or row.status != TURN_ADMITTED:
                return
            row.status = TURN_RUNNING
            session.commit()

    async def checkpoint_turn(
        self,
        turn_id: uuid.UUID | str,
        draft: Mapping[str, Any],
        *,
        last_event_seq: int | None = None,
    ) -> None:
        await asyncio.to_thread(
            self._checkpoint_turn, _uuid(turn_id), dict(draft), last_event_seq
        )

    def _checkpoint_turn(
        self,
        turn_id: uuid.UUID,
        draft: Mapping[str, Any],
        last_event_seq: int | None,
    ) -> None:
        with self._session_factory() as session:
            row = session.get(AgentTurn, turn_id)
            if row is None or row.status not in ACTIVE_TURN_STATUSES:
                # A terminal Turn is frozen. A checkpoint arriving after the
                # terminal transaction is a race, not a correction, and applying
                # it would put a half-written answer back on a finished Turn.
                return
            row.draft_content = dict(draft)
            if last_event_seq is not None:
                row.last_event_seq = last_event_seq
            session.commit()

    async def request_turn_cancel(
        self, user_id: int, turn_id: uuid.UUID | str
    ) -> TurnRecord | None:
        """Record the cancel request; idempotent, and never a second stamp."""
        return await asyncio.to_thread(
            self._request_turn_cancel, user_id, _uuid(turn_id)
        )

    def _request_turn_cancel(
        self, user_id: int, turn_id: uuid.UUID
    ) -> TurnRecord | None:
        with self._session_factory() as session:
            row = self._owned_turn(session, user_id, turn_id)
            if row is None:
                return None
            if row.cancel_requested_at is None and row.status in ACTIVE_TURN_STATUSES:
                row.cancel_requested_at = datetime.now(timezone.utc)
                session.commit()
            return _turn_record(row)

    async def finish_turn(
        self,
        turn_id: uuid.UUID | str,
        *,
        status: str,
        terminal_reason: str | None,
        message: Mapping[str, Any] | None = None,
        symbols: Sequence[str] = (),
        draft: Mapping[str, Any] | None = None,
        last_event_seq: int | None = None,
    ) -> TurnRecord:
        """The one terminal transaction (#81).

        The canonical assistant message, ``status``, ``terminal_reason``,
        ``response_message_id`` and ``finished_at`` are written together. Before
        it commits the transcript holds no half-written answer at all — the same
        invariant that makes a row in ``analysis`` mean *complete*.
        """
        if status in ACTIVE_TURN_STATUSES:
            raise ValueError(f"{status} is not a terminal Turn status")
        if status != TURN_COMPLETE and not terminal_reason:
            raise ValueError("a non-complete Turn must carry a terminal reason")
        normalized = tuple(dict.fromkeys(validate_symbol(symbol) for symbol in symbols))
        return await asyncio.to_thread(
            self._finish_turn,
            _uuid(turn_id),
            status,
            terminal_reason,
            None if message is None else dict(message),
            normalized,
            None if draft is None else dict(draft),
            last_event_seq,
        )

    def _finish_turn(
        self,
        turn_id: uuid.UUID,
        status: str,
        terminal_reason: str | None,
        message: Mapping[str, Any] | None,
        symbols: Sequence[str],
        draft: Mapping[str, Any] | None,
        last_event_seq: int | None,
    ) -> TurnRecord:
        def write(session: Session) -> TurnRecord:
            row = session.get(AgentTurn, turn_id)
            if row is None:
                raise LookupError(f"Turn {turn_id} does not exist")
            if row.status not in ACTIVE_TURN_STATUSES:
                # Already terminal: the startup sweep and a late finishing task
                # can both arrive here, and the first terminal state wins.
                return _turn_record(row)
            if message is not None:
                written = _insert_message(
                    session, row.thread_id, "assistant", message, symbols
                )
                row.response_message_id = written.id
            if draft is not None:
                row.draft_content = dict(draft)
            if last_event_seq is not None:
                row.last_event_seq = last_event_seq
            row.status = status
            row.terminal_reason = terminal_reason
            row.finished_at = datetime.now(timezone.utc)
            session.commit()
            return _turn_record(row)

        return self._with_sequence_retry(write)

    async def freeze_interrupted_turns(
        self, message_builder: MessageBuilder | None = None
    ) -> tuple[TurnRecord, ...]:
        """Freeze every Turn a crash or a deploy left active.

        Called once at startup. V1 never resumes execution: replaying a
        non-deterministic model against a store that has moved would produce a
        plausible continuation, and an honest ``incomplete`` carrying everything
        that actually ran is worth more than that.

        ``message_builder`` turns one frozen draft into the canonical assistant
        message, in the same transaction that freezes the Turn. It is a callback
        rather than logic here because what a useful incomplete message looks
        like is the lifecycle's business, and this module's business is the
        transaction.
        """
        return await asyncio.to_thread(self._freeze_interrupted_turns, message_builder)

    def _freeze_interrupted_turns(
        self, message_builder: MessageBuilder | None
    ) -> tuple[TurnRecord, ...]:
        return self._with_sequence_retry(
            lambda session: self._freeze(session, message_builder)
        )

    @staticmethod
    def _freeze(
        session: Session, message_builder: MessageBuilder | None
    ) -> tuple[TurnRecord, ...]:
        """Freeze every active Turn in one transaction, message included.

        Runs under :meth:`_with_sequence_retry` like every other writer of a
        transcript row: the sweep appends assistant messages, so it races the
        same ``UNIQUE(thread_id, seq)`` as the Turn that is still finishing in
        another process during a rolling deploy.
        """
        rows = list(
            session.execute(
                select(AgentTurn).where(AgentTurn.status.in_(ACTIVE_TURN_STATUSES))
            ).scalars()
        )
        frozen: list[TurnRecord] = []
        for row in rows:
            message = (
                None if message_builder is None else message_builder(_turn_record(row))
            )
            if message is not None:
                written = _insert_message(
                    session, row.thread_id, "assistant", message, ()
                )
                row.response_message_id = written.id
            row.status = TURN_INCOMPLETE
            row.terminal_reason = INTERRUPTED_REASON
            row.finished_at = datetime.now(timezone.utc)
            frozen.append(_turn_record(row))
        if frozen:
            session.commit()
        return tuple(frozen)


__all__ = [
    "ACTIVE_TURN_STATUSES",
    "FLAG_REASONS",
    "INTERRUPTED_REASON",
    "TURN_ADMITTED",
    "TURN_COMPLETE",
    "TURN_INCOMPLETE",
    "TURN_RUNNING",
    "AgentPersistence",
    "MessageRecord",
    "ThreadRecord",
    "ThreadView",
    "ToolCallRecord",
    "TurnCreation",
    "TurnPayloadConflict",
    "TurnRecord",
    "UnflaggableMessage",
    "flag_counts_between",
]
