"""The in-process publisher a Turn emits through, and the subscription seam.

``docs/adr/0026`` fixes the seven event types and the replay contract; this
module builds them, and :mod:`src.agent.sse` puts them on the wire. The split is
deliberate: the publisher is what the loop emits through, so it has to exist
before there is anywhere to stream from.

Three properties are the reason this is a module rather than a queue in the
loop.

**Registration and snapshot capture are atomic.** :meth:`TurnPublisher.subscribe`
captures the snapshot and registers the queue in one synchronous block, and
:meth:`TurnPublisher.publish` is synchronous too. Neither awaits, so on a single
event loop no event can land between the two halves — there is no window in
which an event is in neither the snapshot nor the stream. That is the whole
proof, and it is why ``publish`` returns the event instead of awaiting delivery.

**The snapshot consumes no sequence.** It restates everything already published
up to ``through_seq`` rather than adding to it; a per-subscriber event that
advanced the Turn's own counter would make the sequence depend on how many tabs
were open.

**A subscriber cannot apply backpressure.** Each one holds a bounded queue, and
a queue that fills drops *that subscriber* rather than slowing the Turn. The
canonical content is never what is discarded: it is checkpointed and, at the
end, written to the transcript, so a dropped tab recovers everything from a
fresh snapshot.

**The answer is a string, and the snapshot restates the whole of it.** A reader
that reconnects mid-Turn replaces what it holds rather than merging, which is
what makes the concatenation of every ``content.delta`` and the ``text`` on the
snapshot the same string.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.alpha.models import ACTIVE_TURN_STATUSES, TURN_RUNNING

logger = logging.getLogger(__name__)

# Bumped when the envelope's own shape changes, never when a payload gains a
# key: a client that reads ``version`` to decide how to parse must not be made
# to re-parse for an addition it can ignore. Two since the harness swap replaced
# the blocks, widgets and activity phases of v1 with prose and tool calls.
ENVELOPE_VERSION = 2

# Roughly a minute of a talkative Turn. Large enough that an ordinary tab under
# a slow network never trips it, small enough that a tab which has stopped
# reading altogether is dropped long before its queue is a memory problem.
SUBSCRIBER_QUEUE_SIZE = 256


class EventType(str, Enum):
    """The seven v2 event types."""

    SNAPSHOT = "turn.snapshot"
    CONTENT_DELTA = "content.delta"
    TOOL_CALL = "tool.call"
    COMPLETED = "turn.completed"
    INCOMPLETE = "turn.incomplete"
    FAILED = "turn.failed"
    CANCELLED = "turn.cancelled"


TERMINAL_EVENTS = frozenset(
    {
        EventType.COMPLETED,
        EventType.INCOMPLETE,
        EventType.FAILED,
        EventType.CANCELLED,
    }
)

#: The keys a ``tool.call`` payload is allowed to carry. An allowlist rather
#: than whatever the loop happens to hand over: a tool call's arguments and its
#: result belong in the Tool Call Trace, and an event that carried them would put
#: a page's own text on a channel the client renders.
TOOL_CALL_FIELDS = ("id", "name", "status", "summary")


@dataclass(frozen=True)
class TurnEvent:
    """One versioned envelope, whose ``seq`` is also the SSE ``id``."""

    seq: int
    type: EventType
    turn_id: uuid.UUID
    data: Mapping[str, Any] = field(default_factory=dict)
    version: int = ENVELOPE_VERSION

    def as_wire(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "seq": self.seq,
            "type": self.type.value,
            "turn_id": str(self.turn_id),
            "data": dict(self.data),
        }


class Subscriber:
    """One connection's bounded view of a Turn.

    The snapshot is handed over at construction rather than pushed through the
    queue, because it is the thing that has to be true *before* the first
    streamed event — a subscriber that read its snapshot out of the same queue
    could be dropped before it ever saw one.
    """

    def __init__(
        self,
        snapshot: TurnEvent,
        *,
        queue_size: int = SUBSCRIBER_QUEUE_SIZE,
    ) -> None:
        self.snapshot = snapshot
        self.through_seq = snapshot.seq
        self._queue: asyncio.Queue[TurnEvent | None] = asyncio.Queue(queue_size)
        self._dropped = False
        self._closed = False

    @property
    def dropped(self) -> bool:
        """True once this subscriber stopped reading and was let go."""
        return self._dropped

    def offer(self, event: TurnEvent) -> bool:
        """Try to deliver one event; never block, never raise."""
        if self._dropped or self._closed:
            return False
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            self._dropped = True
            return False
        return True

    def close(self) -> None:
        """End the iteration, whether the Turn finished or the reader left."""
        if self._closed:
            return
        self._closed = True
        # A dropped subscriber's queue is full by definition, so the sentinel
        # has nowhere to go; ``events`` reads ``_closed`` for exactly that case.
        try:
            self._queue.put_nowait(None)
        except asyncio.QueueFull:
            pass

    async def events(self) -> AsyncIterator[TurnEvent]:
        """Everything with ``seq > through_seq``, in order, until the end.

        A dropped subscriber ends here rather than draining what is left in its
        queue: it has already missed an event, so what remains is a stream with
        a gap in it, and a gap forces a fresh snapshot rather than a partial
        replay.
        """
        while not self._dropped:
            event = await self._queue.get()
            if event is None:
                return
            yield event


class TurnPublisher:
    """Per-Turn sequence, live state, and the subscribers watching it."""

    def __init__(
        self,
        turn_id: uuid.UUID | str,
        *,
        queue_size: int = SUBSCRIBER_QUEUE_SIZE,
        seq: int = 0,
    ) -> None:
        self.turn_id = turn_id if isinstance(turn_id, uuid.UUID) else uuid.UUID(str(turn_id))
        self._seq = seq
        self._queue_size = queue_size
        self._subscribers: list[Subscriber] = []
        # The answer so far, as one string. Appended to by every delta, which is
        # what makes the snapshot able to restate it rather than replay.
        self._text = ""
        # Tool calls by id, in the order they were first announced: a call is
        # published twice — running, then its outcome — and the second event
        # replaces the first rather than adding a row.
        self._tool_calls: dict[str, dict[str, Any]] = {}
        self._status = TURN_RUNNING
        self._terminal_reason: str | None = None
        # The canonical assistant message, once the terminal transaction has
        # written one. It rides the snapshot as well as the terminal event so
        # that a reader arriving *after* the Turn ended learns the same fact a
        # reader who watched it end already knows: which message replaces the
        # draft it is holding. Without it that reader shows both.
        self._message_id: int | None = None

    @property
    def seq(self) -> int:
        """The highest sequence published so far, persisted as ``last_event_seq``."""
        return self._seq

    @property
    def next_seq(self) -> int:
        """The sequence the next published event will carry.

        Named rather than left as ``seq + 1`` at the call site, because the one
        caller that needs it is the terminal transaction: it persists
        ``last_event_seq`` *before* publishing the terminal event, so that a
        subscriber arriving after the commit and before the publish is not told
        the Turn got further than it did.
        """
        return self._seq + 1

    @property
    def text(self) -> str:
        """The answer as the stream has delivered it so far."""
        return self._text

    @property
    def tool_calls(self) -> tuple[Mapping[str, Any], ...]:
        """Every tool call announced, in the order it was first announced."""
        return tuple(dict(call) for call in self._tool_calls.values())

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def publish(
        self,
        event_type: EventType,
        data: Mapping[str, Any] | None = None,
    ) -> TurnEvent:
        """Advance the sequence, update the live state, and fan out."""
        if event_type is EventType.SNAPSHOT:
            raise ValueError("a snapshot is captured per subscriber, never published")
        self._seq += 1
        event = TurnEvent(
            seq=self._seq,
            type=event_type,
            turn_id=self.turn_id,
            data=dict(data or {}),
        )
        self._remember(event)
        self._fan_out(event)
        return event

    def content_delta(self, text: str) -> TurnEvent:
        """Emit exactly the text just appended to the answer.

        The delta is what was added and not what the answer now says, so a
        client appends rather than replaces. The loop owns the separator between
        two pieces of prose and puts it *inside* the delta, which is what keeps
        the concatenation of the deltas equal to the stored answer.
        """
        return self.publish(EventType.CONTENT_DELTA, {"text": text})

    def tool_call(self, payload: Mapping[str, Any]) -> TurnEvent:
        """Emit one tool call's current state, by the id it is upserted under."""
        return self.publish(
            EventType.TOOL_CALL,
            {key: payload.get(key) for key in TOOL_CALL_FIELDS},
        )

    def terminal(
        self,
        event_type: EventType,
        *,
        status: str,
        terminal_reason: str | None = None,
        data: Mapping[str, Any] | None = None,
    ) -> TurnEvent:
        """Publish the Turn's last event and close every subscriber."""
        if event_type not in TERMINAL_EVENTS:
            raise ValueError(f"{event_type.value} is not a terminal event")
        self._status = status
        self._terminal_reason = terminal_reason
        payload = {"status": status, "terminal_reason": terminal_reason, **(data or {})}
        message_id = payload.get("message_id")
        self._message_id = message_id if isinstance(message_id, int) else None
        event = self.publish(event_type, payload)
        for subscriber in self._subscribers:
            subscriber.close()
        self._subscribers.clear()
        return event

    def subscribe(self) -> Subscriber:
        """Capture a snapshot and register, with nothing in between.

        A later subscriber attaches to a Turn that is already running; it starts
        nothing, and its disappearance stops nothing.
        """
        snapshot = TurnEvent(
            seq=self._seq,
            type=EventType.SNAPSHOT,
            turn_id=self.turn_id,
            data={
                "through_seq": self._seq,
                "status": self._status,
                "terminal_reason": self._terminal_reason,
                "text": self._text,
                "tool_calls": [dict(call) for call in self._tool_calls.values()],
                "message_id": self._message_id,
            },
        )
        subscriber = Subscriber(snapshot, queue_size=self._queue_size)
        if self._status not in ACTIVE_TURN_STATUSES:
            # A Turn that finished before EventSource connected is returned
            # complete as a terminal snapshot, and the stream ends immediately
            # rather than staying open on a Turn that will never speak again.
            subscriber.close()
        else:
            self._subscribers.append(subscriber)
        return subscriber

    def _remember(self, event: TurnEvent) -> None:
        if event.type is EventType.CONTENT_DELTA:
            self._text += str(event.data.get("text") or "")
        elif event.type is EventType.TOOL_CALL:
            call = dict(event.data)
            identifier = call.get("id")
            if identifier:
                self._tool_calls[str(identifier)] = call

    def _fan_out(self, event: TurnEvent) -> None:
        surviving: list[Subscriber] = []
        for subscriber in self._subscribers:
            if subscriber.offer(event):
                surviving.append(subscriber)
            else:
                logger.info(
                    "Dropped a subscriber of Turn %s at seq %d: its queue is full",
                    self.turn_id,
                    event.seq,
                )
                subscriber.close()
        self._subscribers = surviving


def terminal_event_for(status: str, *, has_content: bool) -> EventType:
    """Map a terminal status onto the event the UI reads.

    Four terminal meanings, three statuses: ``incomplete`` splits by whether
    anything useful survived, because the UI must never replace useful content
    with a full-screen error. ``failed`` is that error; ``incomplete`` is the
    partial answer the user keeps.
    """
    if status == "complete":
        return EventType.COMPLETED
    if status == "cancelled":
        return EventType.CANCELLED
    if status == "incomplete":
        return EventType.INCOMPLETE if has_content else EventType.FAILED
    raise ValueError(f"{status} is not a terminal Turn status")


def snapshot_from_draft(
    turn_id: uuid.UUID,
    draft: Mapping[str, Any] | None,
    *,
    status: str,
    terminal_reason: str | None,
    through_seq: int,
    message_id: int | None = None,
) -> TurnEvent:
    """The snapshot a subscriber gets for a Turn no publisher is holding.

    A Turn frozen by the startup sweep, or one whose process-local registry
    entry is gone, still has to answer a reconnecting browser. The answer comes
    from the checkpoint rather than from memory, which is the reason the
    checkpoint exists.
    """
    text = ""
    tool_calls: Sequence[Mapping[str, Any]] = ()
    if draft:
        text = str(draft.get("text") or "")
        tool_calls = tuple(draft.get("tool_calls") or ())
    return TurnEvent(
        seq=through_seq,
        type=EventType.SNAPSHOT,
        turn_id=turn_id,
        data={
            "through_seq": through_seq,
            "status": status,
            "terminal_reason": terminal_reason,
            "text": text,
            "tool_calls": [dict(call) for call in tool_calls],
            "message_id": message_id,
        },
    )


__all__ = [
    "ENVELOPE_VERSION",
    "SUBSCRIBER_QUEUE_SIZE",
    "TERMINAL_EVENTS",
    "TOOL_CALL_FIELDS",
    "EventType",
    "Subscriber",
    "TurnEvent",
    "TurnPublisher",
    "snapshot_from_draft",
    "terminal_event_for",
]
