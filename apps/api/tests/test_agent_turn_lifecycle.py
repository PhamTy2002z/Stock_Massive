"""A Turn that survives a dropped connection, and how it ends (#81, #83)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import delete, select

from src.agent.context import ContextBudget
from src.agent.events import EventType
from src.agent.loop import AgentLoop, TurnDraft
from src.agent.persistence import (
    TURN_COMPLETE,
    TURN_INCOMPLETE,
    TURN_RUNNING,
    AgentPersistence,
    TurnPayloadConflict,
)
from src.agent.manifest import assemble_message, build_manifest
from src.agent.prompt import AnswerKind, MarketState, RuntimeContext
from src.agent.turns import (
    MAX_USER_INPUT_BYTES,
    Checkpointer,
    TurnService,
    UserInputTooLarge,
    assert_input_within_cap,
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

from tests.test_agent_loop import FakeClient, catalog, config, spec

TRADING_DAY = date(2026, 8, 14)


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


def runtime(user_id: int) -> RuntimeContext:
    return RuntimeContext(
        user_id=user_id,
        trading_day=TRADING_DAY,
        market_state=MarketState.POST_CLOSE,
        active_symbol="FPT",
    )


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
            ToolCall(id="c1", name=name, arguments={"symbol": "FPT"}, output_index=0),
        ),
        usage=Usage(input_tokens=10, output_tokens=5),
    )


def service(client, *, tools=None, loop=None, **overrides) -> TurnService:
    loop_kwargs = loop or {}

    def loop_factory(*, checkpoint, publisher):
        return AgentLoop(
            client=client,
            catalog=tools or catalog(),
            config=config(),
            budget=ContextBudget(max_tokens=30_000),
            checkpoint=checkpoint,
            publisher=publisher,
            **loop_kwargs,
        )

    return TurnService(
        store=store(),
        loop_factory=loop_factory,
        config=config(),
        tool_catalog_version="catalog-v1",
        git_sha="9f2c1ab",
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

    client = FakeClient([wants("slow"), answer("Xong.")])
    turns = service(client, tools=catalog(spec("slow", slow)))
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

    client = FakeClient([wants("slow"), answer("Kết luận cuối cùng.")])
    turns = service(client, tools=catalog(spec("slow", slow), traces=traces))
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
    assert assistant.content["risk_notice"]["version"]
    assert assistant.content["evidence_manifest"]["git_sha"] == "9f2c1ab"
    assert assistant.content["evidence_manifest"]["provider_request_id"] == "req_abc"
    assert assistant.content["evidence_manifest"]["tool_catalog_version"] == "catalog-v1"
    assert assistant.content["answer_kind"] in {"analysis", "education", "refusal"}


@pytest.mark.asyncio
async def test_no_half_written_answer_is_visible_before_that_transaction(owner):
    thread_id = await thread_for(owner)
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow(_context, _arguments):
        started.set()
        await release.wait()
        return {"symbol": "FPT", "ok": True}

    turns = service(
        FakeClient([wants("slow"), answer("Kết luận cuối cùng.")]),
        tools=catalog(spec("slow", slow)),
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

    turns = service(
        FakeClient([wants("sleepy"), answer("Không tới đây.")]),
        tools=catalog(spec("sleepy", sleepy)),
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

    client = FakeClient([wants("slow"), answer("Không tới đây.")])
    turns = service(client, tools=catalog(spec("slow", slow)))
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
    assert finished == ["done"]  # the read-only call in flight was allowed to end
    assert len(client.requests) == 1
    record = await store().read_turn(owner, turn_id)
    assert record.status == "cancelled"
    assert record.terminal_reason == "cancelled_by_user"


# --- checkpointing ---------------------------------------------------------


class _RecordingStore:
    def __init__(self) -> None:
        self.saved: list[dict] = []

    async def checkpoint_turn(self, _turn_id, draft, *, last_event_seq=None):
        self.saved.append({"draft": draft, "seq": last_event_seq})


class _Publisher:
    seq = 3


def draft(blocks=(), *, boundary: bool = False) -> TurnDraft:
    return TurnDraft(
        text="raw", rounds_used=1, tool_calls=(), blocks=blocks, boundary=boundary
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
async def test_the_checkpoint_carries_proven_blocks_and_never_the_raw_answer():
    recording = _RecordingStore()
    checkpointer = Checkpointer(recording, uuid.uuid4(), _Publisher())

    await checkpointer(draft(boundary=True))

    assert "text" not in recording.saved[0]["draft"]
    assert recording.saved[0]["draft"]["blocks"] == []


@pytest.mark.asyncio
async def test_the_last_event_sequence_is_persisted_with_the_checkpoint(owner):
    thread_id = await thread_for(owner)
    turns = service(FakeClient([wants("get_analysis"), answer("Kết luận.")]))
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


# --- the startup sweep -----------------------------------------------------


def _checkpoint_of_an_older_build() -> dict:
    """A checkpoint written by the process a deploy replaced."""
    blocks = [{"kind": "prose", "text": "Một phần đã chứng minh.", "citations": []}]
    return {
        "blocks": blocks,
        "rounds_used": 2,
        "tool_calls": 3,
        "message": assemble_message(
            blocks=blocks,
            text="Một phần đã chứng minh.",
            answer_kind=AnswerKind.ANALYSIS,
            manifest=build_manifest(
                git_sha="older-build",
                model="gpt-5.6-terra",
                route="https://route.example",
                provider_request_id="req_old",
                tool_catalog_version="catalog-v0",
                answer_kind=AnswerKind.ANALYSIS,
                status=TURN_RUNNING,
                terminal_reason=None,
            ),
        ),
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
    assert assistant.content["text"] == "Một phần đã chứng minh."
    assert assistant.content["risk_notice"]["version"]
    assert assistant.content["evidence_manifest"]["terminal_reason"] == (
        "interrupted_restart"
    )
    assert assistant.content["evidence_manifest"]["status"] == TURN_INCOMPLETE
    # The Manifest belongs to the build that answered, not to the one sweeping.
    assert assistant.content["evidence_manifest"]["git_sha"] == "older-build"


@pytest.mark.asyncio
async def test_a_frozen_turn_with_nothing_proven_writes_no_message(owner):
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

    turns = service(
        FakeClient([wants("slow"), answer("Kết luận cuối cùng.")]),
        tools=catalog(spec("slow", slow)),
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

    await turns.shutdown(timeout=5.0)

    record = await store().read_turn(owner, turn_id)
    # A shutdown is something that happened to the user, not something they did.
    assert record.status == TURN_INCOMPLETE
    assert record.terminal_reason == "shutdown"
    assert record.finished_at is not None
    assert turns.running_ids == ()


# --- the Gate inside a Turn ------------------------------------------------


async def _grounded(_context, arguments):
    return {
        "symbol": arguments.get("symbol", "FPT"),
        "close": 95.4,
        "as_of": TRADING_DAY.isoformat(),
    }


@pytest.mark.asyncio
async def test_a_blocked_block_ends_the_turn_and_keeps_what_was_proven(owner):
    thread_id = await thread_for(owner)
    client = FakeClient(
        [
            wants("quote"),
            answer(
                "Giá đóng cửa 95.4 [ev:c1#close].\n\n"
                "RSI đang quanh 61.2 nhưng chưa có nguồn."
            ),
        ]
    )
    turns = service(client, tools=catalog(spec("quote", _grounded)))
    turn_id = uuid.uuid4()
    handle = await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    published: list = []
    subscriber = await turns.subscribe(owner, turn_id)
    await turns.running(turn_id).task
    published = [event async for event in subscriber.events()]

    record = await store().read_turn(owner, turn_id)
    assert record.status == TURN_INCOMPLETE
    assert record.terminal_reason == "grounding_failed"

    # The one proven block was emitted; the unprovable one never was, so there
    # is nothing to retract.
    blocks = [event for event in published if event.type is EventType.CONTENT_BLOCK]
    assert len(blocks) == 1
    assert blocks[0].data["block"]["text"] == "Giá đóng cửa 95.4."
    assert published[-1].type is EventType.INCOMPLETE

    assistant = [row for row in messages_of(thread_id) if row.role == "assistant"][0]
    assert assistant.content["text"] == "Giá đóng cửa 95.4."
    assert "61.2" not in assistant.content["text"]
    assert assistant.content["evidence_manifest"]["outcomes"]["grounding"] == "blocked"
    assert assistant.content["evidence_manifest"]["outcomes"]["failure_code"] == (
        "unreferenced_figure"
    )
    assert handle.publisher.blocks[0]["text"] == "Giá đóng cửa 95.4."


@pytest.mark.asyncio
async def test_a_grounded_answer_reaches_the_transcript_with_its_citations(owner):
    thread_id = await thread_for(owner)
    client = FakeClient(
        [wants("quote"), answer("Giá đóng cửa 95.4 [ev:c1#close] đồng.")]
    )
    turns = service(client, tools=catalog(spec("quote", _grounded)))
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
    assert assistant.content["text"] == "Giá đóng cửa 95.4 đồng."
    cited = assistant.content["evidence_manifest"]["cited_fields"]
    assert cited[0]["tool_call_id"] == "c1"
    assert cited[0]["value"] == 95.4
    assert cited[0]["as_of"] == TRADING_DAY.isoformat()
    assert assistant.content["sources_and_methods"][0]["tool_name"] == "quote"


# --- the Turn start allowance (#83) ---------------------------------------


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


# --- what survives, and what never happens (#83) ---------------------------


@pytest.mark.asyncio
async def test_the_manifest_outlives_the_traces_it_was_built_from(owner):
    """Traces keep a 90-day window; the Manifest is kept indefinitely."""
    thread_id = await thread_for(owner)
    traces: list[dict] = []
    client = FakeClient(
        [wants("quote"), answer("Giá đóng cửa 95.4 [ev:c1#close] đồng.")]
    )
    turns = service(client, tools=catalog(spec("quote", _grounded), traces=traces))
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    await turns.running(turn_id).task
    assert traces  # the trace existed while the Turn ran

    # Day 91: the cleanup job takes the traces away.
    with get_sync_db() as session:
        session.execute(delete(AgentToolCall).where(AgentToolCall.thread_id == thread_id))

    assistant = [row for row in messages_of(thread_id) if row.role == "assistant"][0]
    cited = assistant.content["evidence_manifest"]["cited_fields"][0]
    assert cited["value"] == 95.4
    assert cited["unit"] is None or cited["unit"]
    assert cited["as_of"] == TRADING_DAY.isoformat()
    assert cited["provenance"] == "quote"


@pytest.mark.asyncio
async def test_answer_kind_is_classified_by_the_harness_with_no_second_call(owner):
    thread_id = await thread_for(owner)
    client = FakeClient(
        [wants("quote"), answer("Giá đóng cửa 95.4 [ev:c1#close] đồng.")]
    )
    turns = service(client, tools=catalog(spec("quote", _grounded)))
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    await turns.running(turn_id).task

    assistant = [row for row in messages_of(thread_id) if row.role == "assistant"][0]
    assert assistant.content["answer_kind"] == "analysis"
    # Two calls: the tool round and the answer. A classifying model call would
    # be a third, and there is no code path that makes one.
    assert len(client.requests) == 2


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
    assert assistant.content["answer_kind"] == "refusal"
    assert assistant.content["evidence_manifest"]["outcomes"]["scope"] == "refused"
    # V1 records the reason and does nothing to the account.
    with get_sync_db() as session:
        user = session.get(User, owner)
        assert user is not None


@pytest.mark.asyncio
async def test_the_citation_payload_comes_from_the_trace_and_not_from_the_model(owner):
    """The model supplies evidence ids; the backend supplies the prose."""
    thread_id = await thread_for(owner)
    client = FakeClient(
        [
            wants("quote"),
            answer(
                "Theo Bloomberg, giá đóng cửa 95.4 [ev:c1#close] đồng."
            ),
        ]
    )
    turns = service(client, tools=catalog(spec("quote", _grounded)))
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    await turns.running(turn_id).task

    assistant = [row for row in messages_of(thread_id) if row.role == "assistant"][0]
    source = assistant.content["sources_and_methods"][0]

    # Whatever the model wrote in prose, the recorded source is the tool call.
    assert source["provider_source"] == "quote"
    assert source["tool_call_id"] == "c1"
    assert "Bloomberg" not in str(source)


# --- what a real Turn emits and records ------------------------------------


@pytest.mark.asyncio
async def test_a_completed_turn_emits_its_terminal_event_after_the_transaction(owner):
    thread_id = await thread_for(owner)
    client = FakeClient(
        [wants("quote"), answer("Giá đóng cửa 95.4 [ev:c1#close] đồng.")]
    )
    turns = service(client, tools=catalog(spec("quote", _grounded)))
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

    assert EventType.ACTIVITY in [event.type for event in seen]
    assert EventType.CONTENT_BLOCK in [event.type for event in seen]
    assert seen[-1].type is EventType.COMPLETED
    assert seen[-1].data["status"] == TURN_COMPLETE
    # The message exists by the time the terminal event names it, so a client
    # refetching the Thread on that event cannot race the row.
    assistant = [row for row in messages_of(thread_id) if row.role == "assistant"][0]
    assert seen[-1].data["message_id"] == assistant.id
    assert [event.seq for event in seen] == list(range(1, len(seen) + 1))


@pytest.mark.asyncio
async def test_a_cancelled_turn_emits_turn_cancelled(owner):
    thread_id = await thread_for(owner)
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow(_context, _arguments):
        started.set()
        await release.wait()
        return {"symbol": "FPT", "ok": True}

    turns = service(
        FakeClient([wants("slow"), answer("Không tới đây.")]),
        tools=catalog(spec("slow", slow)),
    )
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
async def test_an_activity_boundary_checkpoints_the_turn(owner):
    thread_id = await thread_for(owner)
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow(_context, _arguments):
        started.set()
        await release.wait()
        return {"symbol": "FPT", "ok": True}

    turns = service(
        FakeClient([wants("slow"), answer("Xong.")]),
        tools=catalog(spec("slow", slow)),
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

    # The reading-data activity fired before the tool ran, and its checkpoint
    # carries the sequence that activity consumed.
    record = await store().read_turn(owner, turn_id)
    assert record.last_event_seq >= 2

    release.set()
    await turns.running(turn_id).task


def test_the_git_sha_comes_from_configuration_when_nobody_names_one():
    from src.core.config import get_settings

    turns = TurnService(
        store=store(),
        loop_factory=lambda **_: None,
        config=config(),
        tool_catalog_version="catalog-v1",
    )

    assert turns._git_sha == get_settings().git_sha


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
