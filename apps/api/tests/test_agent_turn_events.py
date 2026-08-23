"""The in-process publisher, its sequence, and its bounded subscribers (#81)."""

from __future__ import annotations

import asyncio
import uuid

import pytest

from src.agent.events import (
    ENVELOPE_VERSION,
    EventType,
    TurnPublisher,
    snapshot_from_draft,
    terminal_event_for,
)

TURN = uuid.UUID("11111111-2222-3333-4444-555555555555")

CALL = {
    "id": "call_0",
    "name": "web_search",
    "status": "running",
    "summary": "Tìm trên web: lãi suất",
}


def publisher(**kwargs) -> TurnPublisher:
    return TurnPublisher(TURN, **kwargs)


def test_every_event_type_carries_a_monotonic_sequence_and_an_envelope():
    published = publisher()

    emitted = [
        published.content_delta("một"),
        published.tool_call(CALL),
        published.terminal(
            EventType.COMPLETED, status="complete", terminal_reason=None
        ),
    ]
    terminal = emitted[-1]

    assert [event.seq for event in emitted] == [1, 2, 3]
    assert [event.type for event in emitted] == [
        EventType.CONTENT_DELTA,
        EventType.TOOL_CALL,
        EventType.COMPLETED,
    ]
    assert published.seq == 3
    assert terminal.as_wire()["version"] == ENVELOPE_VERSION
    assert terminal.as_wire()["turn_id"] == str(TURN)


def test_a_delta_carries_what_was_appended_and_not_the_whole_answer():
    published = publisher()

    first = published.content_delta("một")
    second = published.content_delta("\n\nhai")

    assert first.data == {"text": "một", "kind": "answer", "round": 0}
    assert second.data == {"text": "\n\nhai", "kind": "answer", "round": 0}
    assert published.text == "một\n\nhai"


def test_narration_joins_the_timeline_and_never_the_answer():
    published = publisher()

    published.content_delta("Đang tra đã", kind="thought", round=0)
    published.content_delta("rồi tra tiếp", kind="thought", round=1)
    published.content_delta("Xong.")

    # The answer is the answer deltas and nothing else.
    assert published.text == "Xong."
    # Two rounds narrated, so two timeline entries, in round order.
    assert published.thoughts == (
        {"round": 0, "text": "Đang tra đã"},
        {"round": 1, "text": "rồi tra tiếp"},
    )


def test_several_thought_deltas_in_one_round_join_into_one_line():
    """A round narrating across two deltas said one sentence, not two."""
    published = publisher()

    published.content_delta("Đang tra ", kind="thought", round=0)
    published.content_delta("tin hôm nay", kind="thought", round=0)

    assert published.thoughts == ({"round": 0, "text": "Đang tra tin hôm nay"},)


def test_a_tool_call_carries_the_contract_fields_and_never_its_arguments():
    """A page's own text must not travel on the channel the client renders."""
    published = publisher()

    event = published.tool_call(
        {**CALL, "arguments": {"query": "lãi suất"}, "result_text": "…"}
    )

    assert set(event.data) == {
        "id",
        "name",
        "status",
        "summary",
        "round",
        "results",
        "result_count",
        # Which kind of evidence the call went and got. On the allowlist so a
        # surface can draw a store read differently from a stranger's page,
        # which is the distinction the whole evidence boundary rests on.
        "kind",
    }
    assert event.data["summary"] == "Tìm trên web: lãi suất"
    # Widening the allowlist for the sources a reader is shown did not let the
    # arguments or the whole result through with them.
    assert "arguments" not in event.data
    assert "result_text" not in event.data


def test_a_second_event_for_one_call_replaces_it_rather_than_adding_a_row():
    published = publisher()
    published.tool_call(CALL)
    published.tool_call({**CALL, "status": "ok"})

    assert [call["status"] for call in published.tool_calls] == ["ok"]
    assert published.seq == 2, "both events still consumed a sequence"


def test_a_snapshot_consumes_no_sequence_and_restates_what_came_before():
    published = publisher()
    published.content_delta("một ")
    published.content_delta("hai")
    published.tool_call(CALL)

    subscriber = published.subscribe()

    assert published.seq == 3
    assert subscriber.snapshot.seq == 3
    assert subscriber.snapshot.data["through_seq"] == 3
    assert subscriber.snapshot.data["text"] == "một hai"
    assert [call["id"] for call in subscriber.snapshot.data["tool_calls"]] == ["call_0"]


@pytest.mark.asyncio
async def test_a_subscriber_that_joins_mid_turn_gets_no_duplicate_and_no_gap():
    published = publisher()
    published.content_delta("một")

    subscriber = published.subscribe()
    published.content_delta("hai")
    published.content_delta("ba")
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
        published.content_delta(str(index))
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
async def test_a_dropped_subscriber_recovers_the_whole_answer_from_a_snapshot():
    """What is discarded is the stream, never the answer.

    The point of dropping a slow reader rather than slowing the Turn: a tab that
    missed events resubscribes and is handed the same string it would have
    assembled from the deltas it never read.
    """
    published = publisher(queue_size=2)
    slow = published.subscribe()
    for piece in ("một ", "hai ", "ba ", "bốn"):
        published.content_delta(piece)

    assert slow.dropped
    assert published.subscribe().snapshot.data["text"] == "một hai ba bốn"


@pytest.mark.asyncio
async def test_a_turn_that_finished_before_the_subscriber_connected_ends_at_once():
    published = publisher()
    published.content_delta("một")
    published.terminal(
        EventType.INCOMPLETE, status="incomplete", terminal_reason="turn_deadline"
    )

    subscriber = published.subscribe()

    assert subscriber.snapshot.data["status"] == "incomplete"
    assert subscriber.snapshot.data["terminal_reason"] == "turn_deadline"
    assert [event async for event in subscriber.events()] == []


def test_a_terminal_snapshot_names_the_message_that_replaces_the_draft():
    published = publisher()
    published.content_delta("một")
    published.terminal(
        EventType.COMPLETED,
        status="complete",
        terminal_reason=None,
        data={"message_id": 42},
    )

    assert published.subscribe().snapshot.data["message_id"] == 42


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
        {"text": "một hai", "tool_calls": [CALL]},
        status="incomplete",
        terminal_reason="interrupted_restart",
        through_seq=7,
    )

    assert snapshot.type is EventType.SNAPSHOT
    assert snapshot.seq == 7
    assert snapshot.data["through_seq"] == 7
    assert snapshot.data["text"] == "một hai"
    assert snapshot.data["tool_calls"] == [CALL]


def test_a_checkpoint_with_nothing_in_it_still_answers_with_the_shape():
    """A reader must not have to tell an empty answer from a missing key."""
    snapshot = snapshot_from_draft(
        TURN, None, status="running", terminal_reason=None, through_seq=0
    )

    assert snapshot.data["text"] == ""
    assert snapshot.data["tool_calls"] == []


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
            published.content_delta(str(index))
            await asyncio.sleep(0)

    task = asyncio.create_task(talk())
    await asyncio.sleep(0)  # one delta published, publisher between awaits
    subscriber = published.subscribe()
    await task
    published.terminal(EventType.COMPLETED, status="complete", terminal_reason=None)

    streamed = [event async for event in subscriber.events()]
    assert subscriber.snapshot.data["text"] == "0"
    assert [event.seq for event in streamed] == [2, 3, 4]
    assert "".join(event.data["text"] for event in streamed[:2]) == "12"
