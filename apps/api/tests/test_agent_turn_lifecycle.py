"""A Turn that survives a dropped connection, and how it ends (#81, #83)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import delete, select

from src.agent import registry, toolsets
from src.agent.events import EventType
from src.agent.lanes import DEEP, DEFAULT_REASON, LIGHT, LaneProfile
from src.agent.loop import AgentLoop, ContextBudget, TurnDraft
from src.agent.persistence import (
    TURN_COMPLETE,
    TURN_INCOMPLETE,
    TURN_RUNNING,
    AgentPersistence,
    TurnPayloadConflict,
)
from src.agent.prompt import RuntimeContext
from src.agent.turns import (
    MAX_USER_INPUT_BYTES,
    Checkpointer,
    TurnService,
    UserInputTooLarge,
    assert_input_within_cap,
    settle_orphan_calls,
)
from src.alpha.models import (
    AgentMessage,
    AgentThread,
    AgentToolCall,
    AgentTurn,
    LlmCallUsage,
)
from src.auth.models import User
from src.core.database import Base, get_sync_db, sync_engine, sync_session_factory
from src.core.llm import Completion, ModelRefusal, ToolCall, Usage
from src.core.llm.admission import _read_turn_state

from .agent_tool_world import isolated_registry
from .test_agent_loop import FakeClient, config, entry, install

TODAY = date(2026, 8, 14)


@pytest.fixture(autouse=True)
def _tools():
    """A registry of this file's own, so a tool here reaches no other test."""
    with isolated_registry():
        original_memory = toolsets.TOOLSETS["memory"]
        toolsets.TOOLSETS["memory"] = {
            **original_memory,
            "tools": (*original_memory.get("tools", ()), "slow", "sleepy"),
        }
        toolsets.clear_memo()
        try:
            install()
            yield
        finally:
            toolsets.TOOLSETS["memory"] = original_memory
            toolsets.clear_memo()


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture
def owner():
    email = f"turns-{uuid.uuid4().hex}@example.com"
    with get_sync_db() as session:
        user = User(email=email, hashed_password="x")
        session.add(user)
        session.flush()
        user_id = user.id

    yield user_id

    with get_sync_db() as session:
        session.execute(delete(AgentThread).where(AgentThread.user_id == user_id))
        session.execute(delete(User).where(User.id == user_id))


def store() -> AgentPersistence:
    return AgentPersistence(session_factory=sync_session_factory)


def runtime(_user_id: int) -> RuntimeContext:
    return RuntimeContext(today=TODAY, user_name="Ty")


def answer(text: str) -> Completion:
    return Completion(
        model="gpt-5.6-terra",
        text=text,
        usage=Usage(input_tokens=10, output_tokens=5),
        request_id="req_abc",
    )


def wants(name: str) -> Completion:
    return Completion(
        model="gpt-5.6-terra",
        tool_calls=(
            ToolCall(id="c1", name=name, arguments={"query": "FPT"}, output_index=0),
        ),
        usage=Usage(input_tokens=10, output_tokens=5),
    )


def service(client, *, loop=None, **overrides) -> TurnService:
    loop_kwargs = loop or {}

    def loop_factory(*, checkpoint, publisher, lane):
        return AgentLoop(
            client=client,
            config=config(),
            budget=ContextBudget(max_tokens=30_000),
            lane=lane,
            checkpoint=checkpoint,
            publisher=publisher,
            **loop_kwargs,
        )

    return TurnService(
        store=store(),
        loop_factory=loop_factory,
        config=config(),
        **overrides,
    )


async def thread_for(user_id: int) -> uuid.UUID:
    return (await store().create_thread(user_id, title="Turns")).id


def messages_of(thread_id: uuid.UUID) -> list[AgentMessage]:
    with get_sync_db() as session:
        return list(
            session.execute(
                select(AgentMessage)
                .where(AgentMessage.thread_id == thread_id)
                .order_by(AgentMessage.seq)
            ).scalars()
        )


# --- creation and idempotency ---------------------------------------------


@pytest.mark.asyncio
async def test_the_user_message_and_the_turn_commit_before_execution(owner):
    thread_id = await thread_for(owner)
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow(_context, _arguments):
        started.set()
        await release.wait()
        return {"symbol": "FPT", "ok": True}

    install(entry("slow", slow))
    client = FakeClient([wants("slow"), answer("Xong.")])
    turns = service(client)
    turn_id = uuid.uuid4()

    handle = await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    await started.wait()

    # Committed before the first tool call ran, and only the user message so far.
    rows = messages_of(thread_id)
    assert [row.role for row in rows] == ["user"]
    assert rows[0].content["text"] == "FPT thế nào?"
    assert handle.created is True
    record = await store().read_turn(owner, turn_id)
    assert record.status == TURN_RUNNING

    release.set()
    await turns.running(turn_id).task


@pytest.mark.asyncio
async def test_the_question_picks_the_lane_once_and_the_loop_is_built_from_it(owner):
    thread_id = await thread_for(owner)
    built: list[LaneProfile] = []

    def loop_factory(*, checkpoint, publisher, lane):
        built.append(lane)
        return AgentLoop(
            client=FakeClient([answer("Xong.")]),
            config=config(),
            lane=lane,
            checkpoint=checkpoint,
            publisher=publisher,
        )

    turns = TurnService(store=store(), loop_factory=loop_factory, config=config())
    turn_id = uuid.uuid4()

    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="Viết memo về FPT giúp tôi.",
        runtime=runtime(owner),
    )
    running = turns.running(turn_id)
    await running.task

    # Routed once, carried on the running Turn with the reason it was routed,
    # and the loop is built from that same lane rather than a second reading of
    # the question.
    assert built == [DEEP]
    assert running.lane is DEEP
    assert running.lane_reason == "keyword:memo"


@pytest.mark.asyncio
async def test_an_ordinary_question_runs_on_the_lane_this_build_always_had(owner):
    thread_id = await thread_for(owner)
    turns = service(FakeClient([answer("Xong.")]))
    turn_id = uuid.uuid4()

    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    running = turns.running(turn_id)
    await running.task

    assert running.lane is LIGHT
    assert running.lane_reason == DEFAULT_REASON


@pytest.mark.asyncio
async def test_the_same_id_and_payload_returns_the_existing_turn(owner):
    thread_id = await thread_for(owner)
    turns = service(FakeClient([answer("Xong.")]))
    turn_id = uuid.uuid4()

    first = await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    await turns.running(turn_id).task
    second = await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )

    assert second.created is False
    assert second.turn.id == first.turn.id
    assert len([row for row in messages_of(thread_id) if row.role == "user"]) == 1


@pytest.mark.asyncio
async def test_the_same_id_with_a_different_payload_is_a_conflict(owner):
    thread_id = await thread_for(owner)
    turns = service(FakeClient([answer("Xong.")]))
    turn_id = uuid.uuid4()

    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    await turns.running(turn_id).task

    with pytest.raises(TurnPayloadConflict):
        await turns.create(
            user_id=owner,
            thread_id=thread_id,
            turn_id=turn_id,
            user_text="Một câu hỏi khác.",
            runtime=runtime(owner),
        )


@pytest.mark.asyncio
async def test_a_turn_belonging_to_another_user_is_never_reachable(owner):
    thread_id = await thread_for(owner)
    turns = service(FakeClient([answer("Xong.")]))
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    await turns.running(turn_id).task

    stranger = owner + 10_000
    assert await store().read_turn(stranger, turn_id) is None
    assert await turns.subscribe(stranger, turn_id) is None
    assert await turns.cancel(stranger, turn_id) is None


def test_user_input_above_eight_kib_is_refused_before_dispatch():
    oversized = "á" * (MAX_USER_INPUT_BYTES // 2 + 1)  # two bytes each

    with pytest.raises(UserInputTooLarge) as raised:
        assert_input_within_cap(oversized)

    assert raised.value.reason == "user_input_too_large"
    assert raised.value.status_code == 413
    assert_input_within_cap("á" * (MAX_USER_INPUT_BYTES // 2))


@pytest.mark.asyncio
async def test_an_oversized_message_commits_no_turn_at_all(owner):
    thread_id = await thread_for(owner)
    turns = service(FakeClient([answer("Xong.")]))

    with pytest.raises(UserInputTooLarge):
        await turns.create(
            user_id=owner,
            thread_id=thread_id,
            turn_id=uuid.uuid4(),
            user_text="x" * (MAX_USER_INPUT_BYTES + 1),
            runtime=runtime(owner),
        )

    assert messages_of(thread_id) == []


# --- the Turn outlives its subscriber -------------------------------------


@pytest.mark.asyncio
async def test_a_subscriber_disconnecting_mid_turn_does_not_stop_execution(owner):
    thread_id = await thread_for(owner)
    release = asyncio.Event()
    started = asyncio.Event()
    traces: list[dict] = []

    async def slow(_context, _arguments):
        started.set()
        await release.wait()
        return {"symbol": "FPT", "ok": True}

    install(entry("slow", slow))
    client = FakeClient([wants("slow"), answer("Kết luận cuối cùng.")])
    turns = service(client, loop={"trace": traces.append})
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    subscriber = await turns.subscribe(owner, turn_id)
    await started.wait()

    # The tab goes away in the middle of the Turn.
    subscriber.close()
    release.set()
    await turns.running(turn_id).task

    record = await store().read_turn(owner, turn_id)
    assert record.status == TURN_COMPLETE
    assert record.response_message_id is not None
    assert record.finished_at is not None
    assert [row.role for row in messages_of(thread_id)] == ["user", "assistant"]
    assert traces  # the Tool Call Trace survived with it


@pytest.mark.asyncio
async def test_a_later_subscriber_attaches_and_starts_nothing(owner):
    thread_id = await thread_for(owner)
    client = FakeClient([answer("Kết luận cuối cùng.")])
    turns = service(client)
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    await turns.running(turn_id).task

    subscriber = await turns.subscribe(owner, turn_id)

    assert len(client.requests) == 1  # nothing was started a second time
    assert subscriber.snapshot.data["status"] == TURN_COMPLETE
    assert [event async for event in subscriber.events()] == []


# --- the terminal transaction ---------------------------------------------


@pytest.mark.asyncio
async def test_one_transaction_writes_the_message_and_the_terminal_fields(owner):
    thread_id = await thread_for(owner)
    turns = service(FakeClient([answer("Kết luận cuối cùng.")]))
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    await turns.running(turn_id).task

    record = await store().read_turn(owner, turn_id)
    assistant = [row for row in messages_of(thread_id) if row.role == "assistant"][0]

    assert record.status == TURN_COMPLETE
    assert record.terminal_reason is None
    assert record.response_message_id == assistant.id
    assert record.finished_at is not None
    assert assistant.content["text"] == "Kết luận cuối cùng."
    assert assistant.content["tool_calls"] == []
    # The status rides the content, because a reopened Thread renders the
    # transcript and nothing else: without it a truncated answer would read as
    # a finished one.
    assert assistant.content["status"] == TURN_COMPLETE


@pytest.mark.asyncio
async def test_no_half_written_answer_is_visible_before_that_transaction(owner):
    thread_id = await thread_for(owner)
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow(_context, _arguments):
        started.set()
        await release.wait()
        return {"symbol": "FPT", "ok": True}

    install(entry("slow", slow))
    turns = service(FakeClient([wants("slow"), answer("Kết luận cuối cùng.")]))
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    await started.wait()

    assert [row.role for row in messages_of(thread_id)] == ["user"]

    release.set()
    await turns.running(turn_id).task

    assert [row.role for row in messages_of(thread_id)] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_every_non_complete_terminal_state_carries_a_stable_reason(owner):
    thread_id = await thread_for(owner)

    async def sleepy(_context, _arguments):
        await asyncio.sleep(5)
        return {"ok": True}

    install(entry("sleepy", sleepy))
    turns = service(
        FakeClient([wants("sleepy"), answer("Không tới đây.")]),
        deadline_seconds=0.05,
    )
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    await turns.running(turn_id).task

    record = await store().read_turn(owner, turn_id)
    assert record.status == TURN_INCOMPLETE
    assert record.terminal_reason == "turn_deadline"


@pytest.mark.asyncio
async def test_a_cancel_is_idempotent_and_dispatches_no_further_call(owner):
    thread_id = await thread_for(owner)
    started = asyncio.Event()
    release = asyncio.Event()
    finished: list[str] = []

    async def slow(_context, _arguments):
        started.set()
        await release.wait()
        finished.append("done")
        return {"symbol": "FPT", "ok": True}

    install(entry("slow", slow))
    client = FakeClient([wants("slow"), answer("Không tới đây.")])
    turns = service(client)
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    await started.wait()

    # The cancel arrives while the read-only call is in flight.
    first = await turns.cancel(owner, turn_id)
    second = await turns.cancel(owner, turn_id)
    release.set()
    await turns.running(turn_id).task

    assert first.cancel_requested_at == second.cancel_requested_at
    assert finished == ["done"]  # the barrier in flight was allowed to end
    assert len(client.requests) == 1
    record = await store().read_turn(owner, turn_id)
    assert record.status == "cancelled"
    assert record.terminal_reason == "cancelled_by_user"


@pytest.mark.asyncio
async def test_a_cancel_reaches_the_work_in_flight_and_not_only_the_next_boundary(
    owner,
):
    """One stop, said twice: a flag a boundary can read and an event a wait can.

    The flag alone means a Turn holding a ninety-second model call keeps holding
    it after the reader has gone. The event is what the model call and a segment
    of read-only tools are woken by, and both are set by this one call.
    """
    thread_id = await thread_for(owner)
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow(_context, _arguments):
        started.set()
        await release.wait()
        return {"symbol": "FPT", "ok": True}

    install(entry("slow", slow))
    turns = service(FakeClient([wants("slow"), answer("Không tới đây.")]))
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    await started.wait()
    running = turns.running(turn_id)
    assert running.cancel_event.is_set() is False

    await turns.cancel(owner, turn_id)

    assert running.cancel_requested is True
    assert running.cancel_event.is_set() is True
    release.set()
    await running.task

    record = await store().read_turn(owner, turn_id)
    assert record.status == "cancelled"


# --- checkpointing ---------------------------------------------------------


class _RecordingStore:
    def __init__(self) -> None:
        self.saved: list[dict] = []

    async def checkpoint_turn(self, _turn_id, draft, *, last_event_seq=None):
        self.saved.append({"draft": draft, "seq": last_event_seq})


class _Publisher:
    seq = 3


def draft(text: str = "một phần", *, boundary: bool = False) -> TurnDraft:
    return TurnDraft(
        text=text, rounds_used=1, tool_calls=(), boundary=boundary
    )


@pytest.mark.asyncio
async def test_ordinary_progress_is_checkpointed_at_most_once_a_second():
    now = {"value": 100.0}
    recording = _RecordingStore()
    checkpointer = Checkpointer(
        recording, uuid.uuid4(), _Publisher(), clock=lambda: now["value"]
    )

    for _ in range(50):
        await checkpointer(draft())
        now["value"] += 0.01  # fifty "tokens" inside half a second

    assert checkpointer.writes == 1
    assert len(recording.saved) == 1


@pytest.mark.asyncio
async def test_a_boundary_is_checkpointed_whatever_the_rate_limiter_says():
    now = {"value": 100.0}
    recording = _RecordingStore()
    checkpointer = Checkpointer(
        recording, uuid.uuid4(), _Publisher(), clock=lambda: now["value"]
    )

    await checkpointer(draft())
    await checkpointer(draft())  # rate limited
    await checkpointer(draft(boundary=True))

    assert checkpointer.writes == 2
    assert recording.saved[-1]["seq"] == 3


@pytest.mark.asyncio
async def test_the_checkpoint_carries_the_answer_as_the_stream_delivered_it():
    """The whole answer, not the last delta.

    What a reconnecting browser needs is the current state of the answer, and it
    is the same string the snapshot restates and the canonical message stores —
    which is what keeps a reader who followed the stream and a reader who rebuilt
    from the checkpoint from disagreeing about what was said.
    """
    recording = _RecordingStore()
    checkpointer = Checkpointer(recording, uuid.uuid4(), _Publisher())

    await checkpointer(draft("một\n\nhai", boundary=True))

    assert recording.saved[0]["draft"]["text"] == "một\n\nhai"
    assert recording.saved[0]["draft"]["tool_calls"] == []
    assert recording.saved[0]["draft"]["rounds_used"] == 1


@pytest.mark.asyncio
async def test_the_last_event_sequence_is_persisted_with_the_checkpoint(owner):
    thread_id = await thread_for(owner)
    turns = service(FakeClient([wants("web_search"), answer("Kết luận.")]))
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    await turns.running(turn_id).task

    record = await store().read_turn(owner, turn_id)
    assert record.last_event_seq > 0


@pytest.mark.asyncio
async def test_the_checkpoint_and_the_replayed_snapshot_carry_the_loops_trail(owner):
    """The audit trail has to survive the process that produced it.

    A reader who reconnects after the Turn ended is answered from the
    checkpoint, so the trail on the stream and the trail in the store are the
    same trail or one of the two readers is being told a different story.
    """
    thread_id = await thread_for(owner)
    turns = service(FakeClient([wants("web_search"), answer("Kết luận.")]))
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    await turns.running(turn_id).task

    record = await store().read_turn(owner, turn_id)
    trail = record.draft_content["progress"]
    assert [part["kind"] for part in trail] == [
        "lane_selected",
        "model_attempt",
        "model_attempt",
        "tool_round",
        "model_attempt",
        "model_attempt",
    ]
    assert [part["seq"] for part in trail] == [1, 2, 3, 4, 5, 6]

    subscriber = await turns.subscribe(owner, turn_id)
    assert subscriber.snapshot.data["progress"] == trail


@pytest.mark.asyncio
async def test_the_canonical_message_says_which_lane_answered_and_why(owner):
    """The transcript is the only view a reopened Thread has of the trail."""
    thread_id = await thread_for(owner)
    turns = service(FakeClient([answer("Xong.")]))
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="Viết memo về FPT giúp tôi.",
        runtime=runtime(owner),
    )
    await turns.running(turn_id).task

    assistant = [row for row in messages_of(thread_id) if row.role == "assistant"][0]
    trail = assistant.content["progress"]
    # The router's decision, carried from where it was taken to where it is
    # read back: the loop reports the lane it was built with and the reason the
    # Turn was routed to it, rather than re-deriving either.
    assert trail[0]["kind"] == "lane_selected"
    assert trail[0]["payload"] == {"lane": DEEP.name, "reason": "keyword:memo"}
    assert [part["payload"]["status"] for part in trail[1:]] == [
        "running",
        "completed",
    ]


# --- nothing is left waiting when a Turn ends ------------------------------


def test_settling_a_leftover_call_says_nothing_about_its_effect():
    """Only the state changes. Whether the effect landed is not ours to invent."""
    calls = [
        {"id": "c1", "name": "remember_fact", "status": "pending", "dispatched": True},
        {"id": "c2", "name": "web_search", "status": "running", "dispatched": False},
        {"id": "c3", "name": "web_search", "status": "ok", "dispatched": True},
        # A call that already said why it stopped keeps its own reason.
        {
            "id": "c4",
            "name": "web_search",
            "status": "running",
            "error": "tool_call_timeout",
        },
    ]

    settled = settle_orphan_calls(calls, "interrupted")

    assert [call["status"] for call in settled] == ["error", "error", "ok", "error"]
    assert [call.get("error") for call in settled] == [
        "interrupted",
        "interrupted",
        None,
        "tool_call_timeout",
    ]
    assert [call.get("dispatched") for call in settled] == [True, False, True, None]
    # Pure: the caller's own list is untouched.
    assert calls[0]["status"] == "pending"


def narrating(name: str, text: str = "Đang ghi lại.") -> Completion:
    """A round that says something and then asks for one tool call."""
    return Completion(
        model="gpt-5.6-terra",
        text=text,
        tool_calls=(
            ToolCall(id="c1", name=name, arguments={"query": "FPT"}, output_index=0),
        ),
        usage=Usage(input_tokens=10, output_tokens=5),
    )


@pytest.mark.asyncio
async def test_a_deadline_settles_the_write_its_checkpoint_had_written_down(owner):
    """The intent survives the deadline, and it does not survive as a spinner.

    A call that changes durable state is checkpointed before it is dispatched, so
    a Turn the wall clock kills mid-write leaves a record of it. What that record
    must not do is stay ``pending`` for ever: the transcript and the snapshot a
    reconnecting reader is answered from both say the call was interrupted.
    """
    thread_id = await thread_for(owner)

    async def sleepy(_context, _arguments):
        await asyncio.sleep(5)
        return {"ok": True}

    registry.register(entry("remember_fact", sleepy), override=True)
    turns = service(
        FakeClient([narrating("remember_fact"), answer("Không tới đây.")]),
        deadline_seconds=0.05,
    )
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="Ghi nhớ giúp tôi.",
        runtime=runtime(owner),
    )
    await turns.running(turn_id).task

    record = await store().read_turn(owner, turn_id)
    assert record.status == TURN_INCOMPLETE
    assert record.terminal_reason == "turn_deadline"
    # The persisted draft, which is what a later subscriber is answered from.
    persisted = record.draft_content["tool_calls"]
    assert [call["id"] for call in persisted] == ["c1"]
    assert [call["status"] for call in persisted] == ["error"]
    assert [call["error"] for call in persisted] == ["interrupted"]
    # And the canonical message, which is what a reopened Thread renders.
    assistant = [row for row in messages_of(thread_id) if row.role == "assistant"][0]
    assert [call["status"] for call in assistant.content["tool_calls"]] == ["error"]
    subscriber = await turns.subscribe(owner, turn_id)
    assert [
        call["status"] for call in subscriber.snapshot.data["tool_calls"]
    ] == ["error"]


@pytest.mark.asyncio
async def test_the_sweep_freezes_no_call_anybody_is_still_waiting_on(owner):
    """A restart leaves calls mid-flight, and the freeze is where they settle.

    The build that was answering is gone, so nothing is coming back for them:
    frozen as they were, the transcript would draw a spinner on every one of
    them for as long as the Thread exists.
    """
    thread_id = await thread_for(owner)
    message = await store().append_message(
        thread_id, role="user", content={"text": "FPT thế nào?"}
    )
    turn_id = uuid.uuid4()
    with get_sync_db() as session:
        session.add(
            AgentTurn(
                id=turn_id,
                thread_id=thread_id,
                request_message_id=message.id,
                status=TURN_RUNNING,
                last_event_seq=4,
                started_at=datetime.now(timezone.utc),
                draft_content={
                    "text": "Một phần đã kịp nói.",
                    "tool_calls": [
                        {"id": "c1", "name": "web_search", "status": "ok"},
                        {"id": "c2", "name": "web_search", "status": "running"},
                        {"id": "c3", "name": "remember_fact", "status": "pending"},
                    ],
                    "rounds_used": 1,
                },
            )
        )

    await service(FakeClient([])).sweep()

    assistant = [row for row in messages_of(thread_id) if row.role == "assistant"][0]
    frozen = assistant.content["tool_calls"]
    # The call that had answered keeps its state; the two the restart caught are
    # settled, and neither is left in a state the surface draws as in flight.
    assert [call["status"] for call in frozen] == ["ok", "error", "error"]
    # The one that had answered gains no reason of its own.
    assert [call.get("error") for call in frozen] == [
        None,
        "interrupted",
        "interrupted",
    ]


# --- the startup sweep -----------------------------------------------------


def _checkpoint_of_an_older_build() -> dict:
    """A checkpoint written by the process a deploy replaced."""
    return {
        "text": "Một phần đã kịp nói.",
        "tool_calls": [
            {
                "id": "c1",
                "name": "web_search",
                "status": "ok",
                "summary": "Tìm trên web: FPT",
            }
        ],
        "rounds_used": 2,
    }




@pytest.mark.asyncio
async def test_a_turn_left_running_by_a_restart_is_frozen_incomplete(owner):
    thread_id = await thread_for(owner)
    message = await store().append_message(
        thread_id, role="user", content={"text": "FPT thế nào?"}
    )
    turn_id = uuid.uuid4()
    with get_sync_db() as session:
        session.add(
            AgentTurn(
                id=turn_id,
                thread_id=thread_id,
                request_message_id=message.id,
                status=TURN_RUNNING,
                last_event_seq=4,
                started_at=datetime.now(timezone.utc),
                draft_content=_checkpoint_of_an_older_build(),
            )
        )

    client = FakeClient([answer("Không được gọi.")])
    turns = service(client)
    frozen = await turns.sweep()

    record = await store().read_turn(owner, turn_id)
    assert [item.id for item in frozen] == [turn_id]
    assert record.status == TURN_INCOMPLETE
    assert record.terminal_reason == "interrupted_restart"
    assert client.requests == []  # nothing was resumed

    assistant = [row for row in messages_of(thread_id) if row.role == "assistant"][0]
    # Everything but the status comes from the build that was answering; only
    # how the Turn ended is this process's to know.
    assert assistant.content["text"] == "Một phần đã kịp nói."
    assert assistant.content["status"] == TURN_INCOMPLETE
    assert [call["id"] for call in assistant.content["tool_calls"]] == ["c1"]
    # A checkpoint written before parts existed reads as a Turn that reported no
    # loop events, rather than as one whose trail was lost.
    assert assistant.content["progress"] == []


@pytest.mark.asyncio
async def test_a_swept_turn_keeps_the_trail_its_checkpoint_held(owner):
    """The freeze knows two things — the status and the reason — and copies the rest."""
    thread_id = await thread_for(owner)
    message = await store().append_message(
        thread_id, role="user", content={"text": "FPT thế nào?"}
    )
    trail = [
        {
            "seq": 1,
            "kind": "lane_selected",
            "round": 0,
            "payload": {"lane": "light", "reason": "default"},
            "at": "2026-08-14T02:00:00+00:00",
        },
        {
            "seq": 2,
            "kind": "model_attempt",
            "round": 0,
            "payload": {"status": "running", "terminal_reason": None},
            "at": "2026-08-14T02:00:01+00:00",
        },
    ]
    turn_id = uuid.uuid4()
    with get_sync_db() as session:
        session.add(
            AgentTurn(
                id=turn_id,
                thread_id=thread_id,
                request_message_id=message.id,
                status=TURN_RUNNING,
                last_event_seq=6,
                started_at=datetime.now(timezone.utc),
                draft_content={**_checkpoint_of_an_older_build(), "progress": trail},
            )
        )

    await service(FakeClient([])).sweep()

    assistant = [row for row in messages_of(thread_id) if row.role == "assistant"][0]
    assert assistant.content["progress"] == trail
    assert assistant.content["status"] == TURN_INCOMPLETE


@pytest.mark.asyncio
async def test_a_frozen_turn_that_never_spoke_writes_no_message(owner):
    thread_id = await thread_for(owner)
    message = await store().append_message(
        thread_id, role="user", content={"text": "FPT thế nào?"}
    )
    turn_id = uuid.uuid4()
    with get_sync_db() as session:
        session.add(
            AgentTurn(
                id=turn_id,
                thread_id=thread_id,
                request_message_id=message.id,
                status="admitted",
                started_at=datetime.now(timezone.utc),
            )
        )

    await service(FakeClient([])).sweep()

    record = await store().read_turn(owner, turn_id)
    assert record.status == TURN_INCOMPLETE
    assert record.response_message_id is None
    assert [row.role for row in messages_of(thread_id)] == ["user"]


# --- graceful shutdown -----------------------------------------------------


@pytest.mark.asyncio
async def test_shutdown_gives_an_active_turn_its_window_to_checkpoint(owner):
    thread_id = await thread_for(owner)
    started = asyncio.Event()

    async def slow(_context, _arguments):
        started.set()
        await asyncio.sleep(0.05)
        return {"symbol": "FPT", "ok": True}

    install(entry("slow", slow))
    turns = service(FakeClient([wants("slow"), answer("Kết luận cuối cùng.")]))
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    await started.wait()

    await turns.shutdown(timeout=5.0)

    record = await store().read_turn(owner, turn_id)
    # A shutdown is something that happened to the user, not something they did.
    assert record.status == TURN_INCOMPLETE
    assert record.terminal_reason == "shutdown"
    assert record.finished_at is not None
    assert turns.running_ids == ()


@pytest.mark.asyncio
async def test_shutdown_stops_every_running_turn_the_way_a_reader_would(owner):
    """The window is for reaching a checkpoint, not for waiting out a route.

    A Turn that spends the grace period inside a model call this process will not
    be alive to read from is a Turn that reaches no checkpoint at all, so a
    shutdown says the same stop a reader says — to every Turn it finds running.
    """
    thread_id = await thread_for(owner)
    started = asyncio.Event()

    async def slow(_context, _arguments):
        started.set()
        await asyncio.sleep(0.05)
        return {"symbol": "FPT", "ok": True}

    install(entry("slow", slow))
    turns = service(FakeClient([wants("slow"), answer("Kết luận cuối cùng.")]))
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    await started.wait()
    running = turns.running(turn_id)

    await turns.shutdown(timeout=5.0)

    assert running.shutting_down is True
    assert running.cancel_event.is_set() is True
    record = await store().read_turn(owner, turn_id)
    assert record.status == TURN_INCOMPLETE
    assert record.terminal_reason == "shutdown"


def _reservation(user_id: int, owner_id: str, when: datetime) -> LlmCallUsage:
    """One committed reservation, which is what "this Turn dispatched" means."""
    return LlmCallUsage(
        owner_type="turn_request_message",
        owner_id=owner_id,
        user_id=user_id,
        lane="turn",
        route="https://route.example",
        model="gpt-5.6-terra",
        reserved_input_tokens=100,
        reserved_output_tokens=100,
        pricing_version="2026-08",
        input_token_price_usd=0,
        cached_read_token_price_usd=0,
        cache_write_token_price_usd=0,
        output_token_price_usd=0,
        reserved_micro_usd=10,
        status="reserved",
        provider_called_at=when,
    )


@pytest.mark.asyncio
async def test_the_start_allowance_is_consumed_at_dispatch_and_not_at_admission(owner):
    """An admitted Turn that never dispatched costs the user nothing."""
    thread_id = await thread_for(owner)
    message = await store().append_message(
        thread_id, role="user", content={"text": "FPT thế nào?"}
    )
    now = datetime.now(timezone.utc)
    with get_sync_db() as session:
        session.add(
            AgentTurn(
                id=uuid.uuid4(),
                thread_id=thread_id,
                request_message_id=message.id,
                status="admitted",
                started_at=now,
            )
        )

    with get_sync_db() as session:
        before = _read_turn_state(session, owner, now, str(message.id))

    # Only the candidate itself: the admitted Turn never reached the provider.
    assert before.starts_today == 1

    with get_sync_db() as session:
        session.add(_reservation(owner, "999999", now))

    with get_sync_db() as session:
        after = _read_turn_state(session, owner, now, str(message.id))

    assert after.starts_today == 2

    with get_sync_db() as session:
        session.execute(
            delete(LlmCallUsage).where(LlmCallUsage.user_id == owner)
        )


@pytest.mark.asyncio
async def test_a_turns_own_later_calls_do_not_each_cost_a_start(owner):
    thread_id = await thread_for(owner)
    message = await store().append_message(
        thread_id, role="user", content={"text": "FPT thế nào?"}
    )
    now = datetime.now(timezone.utc)
    owner_id = str(message.id)
    with get_sync_db() as session:
        for _ in range(5):  # five rounds of one Turn
            session.add(_reservation(owner, owner_id, now))

    with get_sync_db() as session:
        state = _read_turn_state(session, owner, now, owner_id)

    assert state.starts_today == 1

    with get_sync_db() as session:
        session.execute(
            delete(LlmCallUsage).where(LlmCallUsage.user_id == owner)
        )


@pytest.mark.asyncio
async def test_a_refusal_records_its_reason_and_suspends_nobody(owner):
    thread_id = await thread_for(owner)
    client = FakeClient(
        [ModelRefusal("Tôi không thể giúp với yêu cầu này.", usage=Usage())]
    )
    turns = service(client)
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="Giúp tôi thao túng giá.",
        runtime=runtime(owner),
    )
    await turns.running(turn_id).task

    record = await store().read_turn(owner, turn_id)
    assistant = [row for row in messages_of(thread_id) if row.role == "assistant"][0]

    assert record.status == TURN_COMPLETE
    assert record.terminal_reason == "model_refusal"
    # A refusal is an answer, and it reaches the reader.
    assert assistant.content["text"] == "Tôi không thể giúp với yêu cầu này."
    assert assistant.content["status"] == TURN_COMPLETE
    # V1 records the reason and does nothing to the account.
    with get_sync_db() as session:
        user = session.get(User, owner)
        assert user is not None


# --- what a real Turn emits and records ------------------------------------


@pytest.mark.asyncio
async def test_a_completed_turn_emits_its_terminal_event_after_the_transaction(owner):
    thread_id = await thread_for(owner)
    install(entry("web_search"))
    client = FakeClient([wants("web_search"), answer("Giá đóng cửa 95,4 đồng.")])
    turns = service(client)
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    subscriber = await turns.subscribe(owner, turn_id)
    await turns.running(turn_id).task
    seen = [event async for event in subscriber.events()]

    assert EventType.TOOL_CALL in [event.type for event in seen]
    assert EventType.CONTENT_DELTA in [event.type for event in seen]
    assert seen[-1].type is EventType.COMPLETED
    assert seen[-1].data["status"] == TURN_COMPLETE
    # The message exists by the time the terminal event names it, so a client
    # refetching the Thread on that event cannot race the row.
    assistant = [row for row in messages_of(thread_id) if row.role == "assistant"][0]
    assert seen[-1].data["message_id"] == assistant.id
    assert [event.seq for event in seen] == list(range(1, len(seen) + 1))


@pytest.mark.asyncio
async def test_an_ordinary_turn_records_no_mode_at_all(owner):
    # The default writes nothing, which is what keeps the same question asked
    # before this existed comparing equal to itself under the idempotency key.
    thread_id = await thread_for(owner)
    turns = service(FakeClient([answer("Xong.")]))
    turn_id = uuid.uuid4()

    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    await turns.running(turn_id).task

    request = [row for row in messages_of(thread_id) if row.role == "user"][0]
    assert "mode" not in request.content


@pytest.mark.asyncio
async def test_a_cancelled_turn_emits_turn_cancelled(owner):
    thread_id = await thread_for(owner)
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow(_context, _arguments):
        started.set()
        await release.wait()
        return {"symbol": "FPT", "ok": True}

    install(entry("slow", slow))
    turns = service(FakeClient([wants("slow"), answer("Không tới đây.")]))
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    subscriber = await turns.subscribe(owner, turn_id)
    await started.wait()
    await turns.cancel(owner, turn_id)
    release.set()
    await turns.running(turn_id).task

    seen = [event async for event in subscriber.events()]
    assert seen[-1].type is EventType.CANCELLED
    assert seen[-1].data["terminal_reason"] == "cancelled_by_user"


@pytest.mark.asyncio
async def test_a_turn_interrupted_mid_round_has_already_been_checkpointed(owner):
    """What a restart freezes has to exist before the restart.

    The loop checkpoints after every model call and again at the end of every
    tool round, so a Turn killed while a tool is in flight leaves the prose it
    had already produced — which is the difference between an ``incomplete`` a
    reader keeps and a ``failed`` they cannot.
    """
    thread_id = await thread_for(owner)
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow(_context, _arguments):
        started.set()
        await release.wait()
        return {"symbol": "FPT", "ok": True}

    install(entry("slow", slow))
    turns = service(
        FakeClient([wants("slow"), answer("Xong.")]),
        loop={"clock": lambda: datetime.now(timezone.utc)},
    )
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    await started.wait()

    mid_round = await store().read_turn(owner, turn_id)
    assert mid_round.draft_content is not None

    release.set()
    await turns.running(turn_id).task

    # And the boundary checkpoint after the round carries the sequence the
    # tool-call events consumed.
    finished = await store().read_turn(owner, turn_id)
    assert finished.last_event_seq >= 2


@pytest.mark.asyncio
async def test_the_same_id_with_different_symbols_is_also_a_conflict(owner):
    thread_id = await thread_for(owner)
    turns = service(FakeClient([answer("Xong.")]))
    turn_id = uuid.uuid4()

    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        symbols=("FPT",),
        runtime=runtime(owner),
    )
    await turns.running(turn_id).task

    with pytest.raises(TurnPayloadConflict):
        await turns.create(
            user_id=owner,
            thread_id=thread_id,
            turn_id=turn_id,
            user_text="FPT thế nào?",
            symbols=("VCB",),
            runtime=runtime(owner),
        )
