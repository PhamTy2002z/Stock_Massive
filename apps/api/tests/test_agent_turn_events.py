"""The in-process publisher, its sequence, and its bounded subscribers (#81)."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from src.agent.events import (
    ENVELOPE_VERSION,
    Activity,
    EventType,
    TurnPublisher,
    snapshot_from_draft,
    terminal_event_for,
)

TURN = uuid.UUID("11111111-2222-3333-4444-555555555555")


def publisher(**kwargs) -> TurnPublisher:
    return TurnPublisher(TURN, **kwargs)


async def drain(subscriber, count: int) -> list:
    collected = []
    async for event in subscriber.events():
        collected.append(event)
        if len(collected) == count:
            break
    return collected


def test_every_event_type_carries_a_monotonic_sequence_and_an_envelope():
    published = publisher()

    emitted = [
        published.activity(Activity.READING_DATA),
        published.content_block({"text": "một"}),
        published.widget_ready({"kind": "line_chart"}),
        published.terminal(
            EventType.COMPLETED, status="complete", terminal_reason=None
        ),
    ]
    terminal = emitted[-1]

    assert [event.seq for event in emitted] == [1, 2, 3, 4]
    assert [event.type for event in emitted] == [
        EventType.ACTIVITY,
        EventType.CONTENT_BLOCK,
        EventType.WIDGET_READY,
        EventType.COMPLETED,
    ]
    assert published.seq == 4
    assert terminal.as_wire()["version"] == ENVELOPE_VERSION
    assert terminal.as_wire()["turn_id"] == str(TURN)


def test_the_activity_line_exposes_a_phase_and_nothing_else():
    published = publisher()

    event = published.activity(Activity.SEARCHING)

    assert event.data == {"phase": "searching"}


def test_a_snapshot_consumes_no_sequence_and_restates_what_came_before():
    published = publisher()
    published.content_block({"text": "một"})
    published.content_block({"text": "hai"})

    subscriber = published.subscribe()

    assert published.seq == 2
    assert subscriber.snapshot.seq == 2
    assert subscriber.snapshot.data["through_seq"] == 2
    assert [block["text"] for block in subscriber.snapshot.data["blocks"]] == [
        "một",
        "hai",
    ]


@pytest.mark.asyncio
async def test_a_subscriber_that_joins_mid_turn_gets_no_duplicate_and_no_gap():
    published = publisher()
    published.content_block({"text": "một"})

    subscriber = published.subscribe()
    published.content_block({"text": "hai"})
    published.content_block({"text": "ba"})
    published.terminal(EventType.COMPLETED, status="complete", terminal_reason=None)

    received = [event async for event in subscriber.events()]

    assert [event.seq for event in received] == [2, 3, 4]
    assert all(event.seq > subscriber.through_seq for event in received)


@pytest.mark.asyncio
async def test_a_subscriber_that_stops_reading_is_dropped_without_slowing_the_turn():
    published = publisher(queue_size=2)
    slow = published.subscribe()
    healthy = published.subscribe()

    # The healthy tab reads as it goes; the slow one never does.
    for index in range(5):
        published.content_block({"text": str(index)})
        if not healthy.dropped:
            await drain_available(healthy)

    assert slow.dropped
    assert not healthy.dropped
    assert published.seq == 5  # the loop was never held up
    assert published.subscriber_count == 1


async def drain_available(subscriber) -> None:
    """Read everything already queued, without waiting for more."""
    queue = subscriber._queue  # noqa: SLF001 - the test is about the queue itself
    while not queue.empty():
        queue.get_nowait()


@pytest.mark.asyncio
async def test_a_turn_that_finished_before_the_subscriber_connected_ends_at_once():
    published = publisher()
    published.content_block({"text": "một"})
    published.terminal(
        EventType.INCOMPLETE, status="incomplete", terminal_reason="turn_deadline"
    )

    subscriber = published.subscribe()

    assert subscriber.snapshot.data["status"] == "incomplete"
    assert subscriber.snapshot.data["terminal_reason"] == "turn_deadline"
    assert [event async for event in subscriber.events()] == []


@pytest.mark.asyncio
async def test_a_terminal_event_closes_every_subscriber():
    published = publisher()
    first = published.subscribe()
    second = published.subscribe()

    published.terminal(
        EventType.CANCELLED, status="cancelled", terminal_reason="cancelled_by_user"
    )

    for subscriber in (first, second):
        assert [event.type async for event in subscriber.events()] == [
            EventType.CANCELLED
        ]
    assert published.subscriber_count == 0


def test_a_snapshot_is_never_published_as_an_event():
    with pytest.raises(ValueError):
        publisher().publish(EventType.SNAPSHOT)


def test_incomplete_splits_by_whether_anything_useful_survived():
    assert terminal_event_for("complete", has_content=True) is EventType.COMPLETED
    assert terminal_event_for("cancelled", has_content=False) is EventType.CANCELLED
    assert terminal_event_for("incomplete", has_content=True) is EventType.INCOMPLETE
    assert terminal_event_for("incomplete", has_content=False) is EventType.FAILED
    with pytest.raises(ValueError):
        terminal_event_for("running", has_content=False)


def test_a_turn_with_no_publisher_left_answers_from_its_checkpoint():
    snapshot = snapshot_from_draft(
        TURN,
        {"blocks": [{"text": "một"}]},
        status="incomplete",
        terminal_reason="interrupted_restart",
        through_seq=7,
    )

    assert snapshot.type is EventType.SNAPSHOT
    assert snapshot.seq == 7
    assert snapshot.data["through_seq"] == 7
    assert snapshot.data["blocks"] == [{"text": "một"}]


@pytest.mark.asyncio
async def test_registration_and_snapshot_capture_leave_no_window():
    """Both halves are synchronous, so nothing can land between them.

    The property is proven by construction rather than by timing: a subscriber
    taken while a publishing coroutine is scheduled sees exactly the events
    published before it, and the first event it streams is the next sequence.
    """
    published = publisher()

    async def talk() -> None:
        for index in range(3):
            published.content_block({"text": str(index)})
            await asyncio.sleep(0)

    task = asyncio.create_task(talk())
    await asyncio.sleep(0)  # one block published, publisher between awaits
    subscriber = published.subscribe()
    await task
    published.terminal(EventType.COMPLETED, status="complete", terminal_reason=None)

    streamed = [event async for event in subscriber.events()]
    seen = [block["text"] for block in subscriber.snapshot.data["blocks"]]
    assert seen == ["0"]
    assert [event.seq for event in streamed] == [2, 3, 4]
