"""The in-process publisher a Turn emits through, and the subscription seam.

``docs/adr/0013`` fixes the eight event types and the replay contract; this
module builds them, and **A6 builds the SSE transport over it** — the endpoints,
the heartbeat, the reconnect wiring, the Next proxy and the client reducer. The
split is deliberate: the publisher is what the Recommendation Gate emits
through, so it has to exist before there is anywhere to stream from.

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
# to re-parse for an addition it can ignore.
ENVELOPE_VERSION = 1

# Roughly a minute of a talkative Turn. Large enough that an ordinary tab under
# a slow network never trips it, small enough that a tab which has stopped
# reading altogether is dropped long before its queue is a memory problem.
SUBSCRIBER_QUEUE_SIZE = 256

# The activity trail's ceiling (``docs/adr/0020``). Eight tool rounds produce
# well under thirty steps, so this bounds the pathological case and nothing else:
# the trail rides every snapshot, and an unbounded one would make a snapshot grow
# with how chatty a Turn was.
MAX_TRAIL_STEPS = 60


class EventType(str, Enum):
    """The eight v1 event types of ``docs/adr/0013``."""

    SNAPSHOT = "turn.snapshot"
    ACTIVITY = "turn.activity"
    CONTENT_BLOCK = "content.block"
    WIDGET_READY = "widget.ready"
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


class Activity(str, Enum):
    """The generic phases ``turn.activity`` is allowed to expose.

    A closed enum because the constraint is what matters: the activity line
    never carries a tool name, symbol, argument, raw result, prompt or piece of
    reasoning for any lane that reads the store. All of that stays in the Tool
    Call Trace, and an enum is how a free-form phase string is kept from quietly
    becoming one.

    ``docs/adr/0020`` narrows that to the lanes it was written for and adds
    :data:`FOUND_SOURCES`. The open-web lane may attach a ``detail`` payload —
    the sentence it searched for, the public pages it found — because both are
    public and a reader who cannot see them cannot weigh the answer. The enum
    stays closed either way: a phase the backend cannot name is one it cannot
    publish.
    """

    SEARCHING = "searching"
    READING_DATA = "reading_data"
    ANALYZING = "analyzing"
    PREPARING_VISUAL = "preparing_visual"
    FOUND_SOURCES = "found_sources"


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
        a gap in it, and ``docs/adr/0013`` says a gap forces a fresh snapshot
        rather than a partial replay.
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
        self._blocks: list[Mapping[str, Any]] = []
        self._widgets: list[Mapping[str, Any]] = []
        self._activity: Activity | None = None
        # Every phase the Turn has been through, in order, with whatever the
        # open-web lane disclosed about it. A reconnecting browser rebuilds the
        # trail from this rather than from the events it missed
        # (``docs/adr/0020``).
        self._progress: list[dict[str, Any]] = []
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
    def blocks(self) -> tuple[Mapping[str, Any], ...]:
        """The released blocks, in order — the checkpointable draft."""
        return tuple(self._blocks)

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

    def activity(
        self, activity: Activity, detail: Mapping[str, Any] | None = None
    ) -> TurnEvent:
        """Say what phase the Turn is in, and — for the open web — with what.

        ``detail`` is omitted rather than sent empty when there is nothing to
        disclose, so a client can read its presence as "this lane discloses"
        instead of inspecting what is inside it (``docs/adr/0020``).
        """
        data: dict[str, Any] = {"phase": activity.value}
        if detail:
            data["detail"] = dict(detail)
        return self.publish(EventType.ACTIVITY, data)

    def content_block(self, block: Mapping[str, Any]) -> TurnEvent:
        """Emit one proven block.

        Called only by the Recommendation Validator's release path (#82). The
        ordering is not a convention that could be got wrong later: nothing else
        in the codebase constructs a ``content.block``.
        """
        return self.publish(EventType.CONTENT_BLOCK, {"block": dict(block)})

    def widget_ready(self, widget: Mapping[str, Any]) -> TurnEvent:
        """Emit one validated Widget spec.

        The emission point, not the producer: the typed Widget registry and its
        validation are A6's (``docs/adr/0012``), and a Turn in A5 has nothing to
        put here. The seam exists now because the publisher is what A6 emits
        through, and a transport built against a type that does not exist is a
        transport built against a guess.
        """
        return self.publish(EventType.WIDGET_READY, {"widget": dict(widget)})

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
                "activity": None if self._activity is None else self._activity.value,
                "progress": [dict(step) for step in self._progress],
                "blocks": [dict(block) for block in self._blocks],
                "widgets": [dict(widget) for widget in self._widgets],
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
        if event.type is EventType.CONTENT_BLOCK:
            self._blocks.append(dict(event.data.get("block") or {}))
        elif event.type is EventType.WIDGET_READY:
            self._widgets.append(dict(event.data.get("widget") or {}))
        elif event.type is EventType.ACTIVITY:
            phase = event.data.get("phase")
            self._activity = Activity(phase) if phase else None
            append_step(self._progress, event.data)

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


def append_step(trail: list[dict[str, Any]], data: Mapping[str, Any]) -> None:
    """Add one activity to the trail, collapsing a phase that merely repeated.

    The loop announces ``analyzing`` before every model call, so a Turn that ran
    four tool rounds would otherwise leave four identical *Thinking…* rows. A
    repeat with something new to say is still a step — that is what a second
    search with different queries is — so the collapse tests the payload rather
    than the phase alone.

    Bounded at :data:`MAX_TRAIL_STEPS`, which the eight-round ceiling puts well
    out of reach. The cap is not about the honest case: the trail rides every
    snapshot, and a publisher that could be made to emit activity in a loop is a
    publisher that could be made to grow one without it.
    """
    phase = data.get("phase")
    if not phase or len(trail) >= MAX_TRAIL_STEPS:
        return
    step: dict[str, Any] = {"phase": phase}
    detail = data.get("detail")
    if isinstance(detail, Mapping) and detail:
        step["detail"] = dict(detail)
    if trail and trail[-1] == step:
        return
    trail.append(step)


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
    blocks: Sequence[Mapping[str, Any]] = ()
    widgets: Sequence[Mapping[str, Any]] = ()
    progress: Sequence[Mapping[str, Any]] = ()
    if draft:
        blocks = tuple(draft.get("blocks") or ())
        widgets = tuple(draft.get("widgets") or ())
        # The trail survives the process that produced it, because the reader
        # reconnecting to a frozen Turn is exactly the reader who most needs to
        # see what it managed to do before it stopped.
        progress = tuple(draft.get("progress") or ())
    return TurnEvent(
        seq=through_seq,
        type=EventType.SNAPSHOT,
        turn_id=turn_id,
        data={
            "through_seq": through_seq,
            "status": status,
            "terminal_reason": terminal_reason,
            "activity": None,
            "progress": [dict(step) for step in progress],
            "blocks": [dict(block) for block in blocks],
            "widgets": [dict(widget) for widget in widgets],
            "message_id": message_id,
        },
    )


__all__ = [
    "ENVELOPE_VERSION",
    "MAX_TRAIL_STEPS",
    "SUBSCRIBER_QUEUE_SIZE",
    "TERMINAL_EVENTS",
    "Activity",
    "EventType",
    "Subscriber",
    "TurnEvent",
    "TurnPublisher",
    "append_step",
    "snapshot_from_draft",
    "terminal_event_for",
]
