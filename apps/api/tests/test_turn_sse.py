"""The wire form of a Turn's events, and the heartbeat beside them (#85).

The publisher (#81) already proves ordering, atomic snapshot capture and the
bounded queue.  What is proven here is only what the transport adds: the SSE
framing, the ``seq`` that is also the SSE ``id``, and a comment heartbeat that
consumes no sequence.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest

from src.agent.events import EventType, TurnPublisher
from src.agent.sse import (
    HEARTBEAT_FRAME,
    SSE_HEARTBEAT_SECONDS,
    encode,
    frames,
)

TURN = uuid.UUID("11111111-2222-3333-4444-555555555555")

pytestmark = pytest.mark.asyncio


def parse(frame: str) -> dict:
    """One SSE frame back into its fields, so a test reads the wire not a dict."""
    fields: dict[str, str] = {}
    for line in frame.rstrip("\n").split("\n"):
        name, _, value = line.partition(": ")
        fields[name] = value
    return fields


async def collect(stream, count: int) -> list[str]:
    gathered: list[str] = []
    async for frame in stream:
        gathered.append(frame)
        if len(gathered) == count:
            break
    return gathered


class TestTheFrame:
    async def test_seq_is_the_sse_id_and_the_envelope_travels_whole(self):
        published = TurnPublisher(TURN)
        event = published.content_delta("VCB")

        fields = parse(encode(event))

        assert fields["id"] == "1"
        assert fields["event"] == "content.delta"
        assert json.loads(fields["data"]) == {
            "version": 2,
            "seq": 1,
            "type": "content.delta",
            "turn_id": str(TURN),
            "data": {"text": "VCB"},
        }

    async def test_the_data_field_is_one_line_so_no_payload_can_split_a_frame(self):
        # A newline inside the JSON would end the frame early and the rest would
        # be read as a second event with no type at all.
        published = TurnPublisher(TURN)
        event = published.content_delta("một\nhai")

        body = encode(event)

        assert body.count("\ndata: ") == 1
        assert body.endswith("\n\n")


class TestTheStream:
    async def test_the_snapshot_leads_and_every_later_event_follows_in_order(self):
        published = TurnPublisher(TURN)
        published.content_delta("already here")
        subscriber = published.subscribe()

        stream = frames(subscriber)
        first = await anext(stream)
        published.content_delta(" and this")
        second = await anext(stream)

        assert parse(first)["event"] == EventType.SNAPSHOT.value
        snapshot = json.loads(parse(first)["data"])
        assert snapshot["data"]["through_seq"] == 1
        assert snapshot["data"]["text"] == "already here"
        assert json.loads(parse(second)["data"])["seq"] == 2
        await stream.aclose()

    async def test_only_events_past_the_snapshot_reach_a_reconnecting_reader(self):
        published = TurnPublisher(TURN)
        published.content_delta("before")
        published.content_delta(" also before")
        subscriber = published.subscribe()
        published.content_delta(" after")

        stream = frames(subscriber)
        gathered = await collect(stream, 2)
        await stream.aclose()

        sequences = [json.loads(parse(frame)["data"])["seq"] for frame in gathered]
        # The snapshot restates 1 and 2 without renumbering them, and the stream
        # resumes at 3. No duplicate, and no gap.
        assert sequences == [2, 3]

    async def test_a_quiet_stream_beats_without_consuming_a_sequence(self):
        published = TurnPublisher(TURN)
        subscriber = published.subscribe()

        stream = frames(subscriber, heartbeat_seconds=0.01)
        await anext(stream)  # the snapshot
        beat = await anext(stream)
        published.content_delta("một")
        after = await anext(stream)
        await stream.aclose()

        assert beat == HEARTBEAT_FRAME
        assert beat.startswith(":")
        # The sequence the publisher hands out is untouched by the beat: the
        # first real event after it is still 1.
        assert json.loads(parse(after)["data"])["seq"] == 1
        assert published.seq == 1

    async def test_the_stream_ends_at_the_terminal_event_rather_than_hanging_open(self):
        published = TurnPublisher(TURN)
        subscriber = published.subscribe()

        stream = frames(subscriber, heartbeat_seconds=0.01)
        await anext(stream)
        published.terminal(
            EventType.COMPLETED, status="complete", terminal_reason=None
        )

        gathered = [frame async for frame in stream]

        assert [parse(frame)["event"] for frame in gathered] == ["turn.completed"]

    async def test_a_turn_already_terminal_is_one_snapshot_and_a_closed_stream(self):
        # A fast Turn must not look like a dead one: the reader gets the whole
        # answer and the connection ends, rather than an empty stream that only
        # a timeout would resolve.
        published = TurnPublisher(TURN)
        published.content_delta("done")
        published.terminal(
            EventType.COMPLETED, status="complete", terminal_reason=None
        )
        subscriber = published.subscribe()

        gathered = [frame async for frame in frames(subscriber, heartbeat_seconds=0.01)]

        assert len(gathered) == 1
        snapshot = json.loads(parse(gathered[0])["data"])
        assert snapshot["type"] == EventType.SNAPSHOT.value
        assert snapshot["data"]["status"] == "complete"
        assert snapshot["data"]["text"] == "done"

    async def test_a_terminal_snapshot_names_the_message_that_replaces_the_draft(self):
        # The reader that watched the Turn end learned the message id from the
        # terminal event; the reader that arrives afterwards gets only this
        # snapshot. Without the id on it, that reader holds a draft it can never
        # hand over and renders the answer twice.
        published = TurnPublisher(TURN)
        published.content_delta("done")
        published.terminal(
            EventType.COMPLETED,
            status="complete",
            terminal_reason=None,
            data={"message_id": 42},
        )

        snapshot = json.loads(parse(encode(published.subscribe().snapshot))["data"])

        assert snapshot["data"]["message_id"] == 42

    async def test_a_running_turn_has_no_message_to_name_yet(self):
        published = TurnPublisher(TURN)
        published.content_delta("so far")

        snapshot = json.loads(parse(encode(published.subscribe().snapshot))["data"])

        assert snapshot["data"]["message_id"] is None

    async def test_a_reader_that_walks_away_leaves_the_publisher_unblocked(self):
        published = TurnPublisher(TURN)
        subscriber = published.subscribe()

        stream = frames(subscriber, heartbeat_seconds=0.01)
        await anext(stream)
        await stream.aclose()

        # Publishing after the reader is gone neither raises nor waits.
        published.content_delta("một")
        assert published.seq == 1

    async def test_the_default_beat_is_the_fifteen_seconds_the_decision_names(self):
        assert SSE_HEARTBEAT_SECONDS == 15.0


async def test_a_pending_read_is_not_left_running_after_the_stream_closes():
    published = TurnPublisher(TURN)
    subscriber = published.subscribe()
    stream = frames(subscriber, heartbeat_seconds=0.01)
    await anext(stream)
    await anext(stream)  # a beat, so a read is in flight behind it
    await stream.aclose()

    # Anything the generator left running would surface here as a task that is
    # still pending after the connection it belonged to is gone.
    await asyncio.sleep(0)
    leftover = [
        task
        for task in asyncio.all_tasks()
        if task is not asyncio.current_task() and not task.done()
    ]
    assert leftover == []
