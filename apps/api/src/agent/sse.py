"""One Turn's events as ``text/event-stream``, and nothing else (#85).

The publisher in :mod:`src.agent.events` owns the sequence, the atomic snapshot
capture and the bounded queue.  This module owns only the wire: framing an
envelope, putting ``seq`` in the SSE ``id`` so the browser resends it as
``Last-Event-ID``, and keeping a quiet path observable.

**The heartbeat is an SSE comment.**  ``docs/adr/0013`` says it consumes no
sequence, and a comment is the only frame that can make that promise structural
rather than remembered: it has no ``id``, so there is nothing for it to number,
and ``EventSource`` discards it without dispatching an event.  A synthetic
``ping`` event would have needed either a sequence — making the stream's
numbering depend on how long the model thought — or an ``id``-less event, which
would silently reset the browser's ``Last-Event-ID``.

**The data field is exactly one line.**  A newline inside the payload would end
the frame early and the remainder would be read as a second event with no type,
so the envelope is serialised without indentation and without raw newlines.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import suppress

from .events import Subscriber, TurnEvent

# ``docs/adr/0013``: fifteen seconds, so a proxy with a sixty-second idle
# timeout sees traffic four times before it would have closed the connection.
SSE_HEARTBEAT_SECONDS = 15.0

# A comment frame. Deliberately not empty: some intermediaries drop a bare
# ``:\n\n``, and the point of the beat is to be bytes on the wire.
HEARTBEAT_FRAME = ": heartbeat\n\n"


def encode(event: TurnEvent) -> str:
    """One envelope as an SSE frame, with ``seq`` as the ``id``."""
    payload = json.dumps(
        event.as_wire(),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"id: {event.seq}\nevent: {event.type.value}\ndata: {payload}\n\n"


async def frames(
    subscriber: Subscriber,
    *,
    heartbeat_seconds: float = SSE_HEARTBEAT_SECONDS,
) -> AsyncIterator[str]:
    """The snapshot, then every event past it, with beats in the gaps.

    The snapshot is yielded from the subscriber's own captured state rather than
    read out of the queue, because it has to be true *before* the first streamed
    event: a subscriber that read its snapshot from the same queue could be
    dropped before it ever saw one.

    A terminal event closes the subscriber, so the iteration ends by itself and
    the response completes — a fast Turn that finished before this connection
    arrived is one snapshot and an immediate close, which is what keeps it from
    looking like a dead one.
    """
    yield encode(subscriber.snapshot)

    events = subscriber.events()
    pending: asyncio.Task[TurnEvent] | None = None
    try:
        while True:
            if pending is None:
                pending = asyncio.ensure_future(anext(events))
            # ``wait`` rather than ``wait_for``: a timeout here is a heartbeat,
            # not a failure, and the read must survive it. Cancelling and
            # re-reading each beat would drop whatever arrived in between.
            done, _ = await asyncio.wait({pending}, timeout=heartbeat_seconds)
            if not done:
                yield HEARTBEAT_FRAME
                continue
            finished, pending = pending, None
            try:
                event = finished.result()
            except StopAsyncIteration:
                return
            yield encode(event)
    finally:
        if pending is not None:
            # Awaited, not merely cancelled: cancellation is a request, and
            # closing the generator while a read is still inside it raises
            # "asynchronous generator is already running".
            pending.cancel()
            with suppress(asyncio.CancelledError, StopAsyncIteration):
                await pending
        with suppress(RuntimeError):
            await events.aclose()
        # The reader is gone whichever way this ended. Closing here is what
        # stops a publisher from fanning out to a queue nobody drains.
        subscriber.close()


__all__ = [
    "HEARTBEAT_FRAME",
    "SSE_HEARTBEAT_SECONDS",
    "encode",
    "frames",
]
