"""The summary a long Thread earns, and every way it declines to write one."""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timezone
from typing import Any

import pytest
from sqlalchemy import delete, select

from src.agent.compaction import (
    MAX_SOURCE_CHARS,
    MAX_SUMMARY_TEXT_CHARS,
    ThreadCompactor,
    plan_compaction,
    thread_turns,
)
from src.agent.loop import AgentLoop, ContextBudget
from src.agent.messages import SUMMARY_LABEL, Transcript, build_messages
from src.agent.persistence import (
    TURN_COMPLETE,
    AgentPersistence,
    MessageRecord,
    SummaryRecord,
    ThreadView,
    latest_summary,
)
from src.agent.prompt import RuntimeContext
from src.agent.router import _applicable_summary, history_of
from src.agent.turns import TurnService
from src.alpha.models import AgentMessage, AgentThread
from src.auth.models import User
from src.core.database import Base, get_sync_db, sync_engine, sync_session_factory
from src.core.llm import Completion, Usage, Workload

from .agent_tool_world import isolated_registry
from .test_agent_loop import FakeClient, config, install

TODAY = date(2026, 9, 1)
THREAD = uuid.UUID("22222222-2222-2222-2222-222222222222")
KEEP = ContextBudget().keep_intact_turns


# -- the transcript these tests are written against -------------------------


def record(
    seq: int,
    role: str,
    content: dict[str, Any],
    *,
    message_id: int | None = None,
) -> MessageRecord:
    return MessageRecord(
        id=message_id if message_id is not None else seq * 10,
        thread_id=THREAD,
        seq=seq,
        role=role,
        content=content,
        created_at=datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc),
    )


def conversation(turns: int, *, words: int = 6) -> list[MessageRecord]:
    """``turns`` complete question-and-answer pairs, numbered from one."""
    messages: list[MessageRecord] = []
    for index in range(turns):
        seq = index * 2 + 1
        messages.append(
            record(seq, "user", {"text": f"Câu hỏi số {index} " + "x " * words})
        )
        messages.append(
            record(
                seq + 1, "assistant", {"text": f"Trả lời số {index} " + "y " * words}
            )
        )
    return messages


def summary_row(
    seq: int, *, covers_to_seq: int, turns: int, text: str = "Bối cảnh trước đó."
) -> MessageRecord:
    return record(
        seq,
        "summary",
        {
            "summary": text,
            "covers_from_seq": 1,
            "covers_to_seq": covers_to_seq,
            "summarised_turns": turns,
            "source_message_ids": [],
            "previous_summary_message_id": None,
            "model": "batch-model",
            "created_at": "2026-09-01T08:00:00+00:00",
        },
    )


# -- what a pass would cover ------------------------------------------------


def test_the_newest_turns_are_never_inside_the_span() -> None:
    messages = conversation(6)

    plan = plan_compaction(messages, keep_intact_turns=KEEP, previous=None)

    assert plan is not None
    assert plan.summarised_turns == 6 - KEEP
    # The span stops at the last message of the fourth Turn, and the prose of
    # the two Turns behind it never reached the specialist.
    assert plan.covers_from_seq == 1
    assert plan.covers_to_seq == 8
    assert "Câu hỏi số 4" not in plan.body
    assert "Câu hỏi số 5" not in plan.body
    assert plan.source_message_ids == tuple(message.id for message in messages[:8])


def test_a_thread_no_longer_than_its_protected_tail_is_left_alone() -> None:
    short = conversation(KEEP)
    assert plan_compaction(short, keep_intact_turns=KEEP, previous=None) is None
    assert plan_compaction((), keep_intact_turns=KEEP, previous=None) is None


def test_a_second_pass_never_covers_less_than_the_first() -> None:
    messages = conversation(6)
    first = plan_compaction(messages, keep_intact_turns=KEEP, previous=None)
    assert first is not None
    written = SummaryRecord(
        message_id=999,
        seq=13,
        text="Bối cảnh trước đó.",
        covers_from_seq=first.covers_from_seq,
        covers_to_seq=first.covers_to_seq,
        summarised_turns=first.summarised_turns,
    )

    # Nothing new outside the tail: the anchor cannot move, so no call is made.
    assert plan_compaction(messages, keep_intact_turns=KEEP, previous=written) is None

    grown = plan_compaction(conversation(9), keep_intact_turns=KEEP, previous=written)
    assert grown is not None
    assert grown.summarised_turns > written.summarised_turns
    assert grown.covers_to_seq > written.covers_to_seq
    assert grown.covers_from_seq == written.covers_from_seq
    # The Turns the first summary already covered are not read a second time;
    # the summary itself carries them into the pass.
    assert "Câu hỏi số 0" not in grown.body
    assert written.text in grown.body


def test_a_summary_row_belongs_to_no_turn() -> None:
    messages = [*conversation(3), summary_row(7, covers_to_seq=4, turns=2)]

    assert len(thread_turns(messages)) == 3
    assert len(history_of(messages)) == 3


def test_too_much_prose_narrows_the_span_rather_than_the_reading() -> None:
    messages = conversation(8, words=1500)

    plan = plan_compaction(messages, keep_intact_turns=KEEP, previous=None)

    assert plan is not None
    assert plan.summarised_turns < 8 - KEEP
    assert len(plan.body) <= MAX_SOURCE_CHARS
    # Whatever it claims to cover, it read: the last Turn of the span is in the
    # body it was built from.
    covered = plan.summarised_turns - 1
    assert f"Câu hỏi số {covered}" in plan.body
    assert plan.covers_to_seq == covered * 2 + 2


# -- the specialist ---------------------------------------------------------


class FakeStore:
    """A Thread in memory, with the two methods the compactor reaches for."""

    def __init__(self, messages: list[MessageRecord], *, refuse: bool = False) -> None:
        self.messages = list(messages)
        self.refuse = refuse
        self.writes: list[dict[str, Any]] = []

    async def read_thread(self, user_id: int, thread_id: Any) -> ThreadView | None:
        return ThreadView(
            id=THREAD,
            user_id=user_id,
            title="Thread",
            symbols=(),
            pinned_at=None,
            created_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            messages=tuple(self.messages),
        )

    async def append_message(
        self, thread_id: Any, *, role: str, content: Any, symbols: Any = ()
    ) -> MessageRecord:
        if self.refuse:
            raise RuntimeError("the store refused the write")
        self.writes.append({"role": role, "content": dict(content)})
        written = record(
            self.messages[-1].seq + 1,
            role,
            dict(content),
            message_id=5000 + len(self.writes),
        )
        self.messages.append(written)
        return written


class Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


def summarised(text: str = "- Người dùng hỏi về lãi suất.") -> Completion:
    return Completion(
        model="batch-model", text=text, usage=Usage(input_tokens=100, output_tokens=20)
    )


def compactor(client: Any, store: Any, **overrides: Any) -> ThreadCompactor:
    return ThreadCompactor(
        client=client, config=config(), store=store, **overrides
    )


@pytest.mark.asyncio
async def test_a_written_summary_carries_the_span_it_covers() -> None:
    store = FakeStore(conversation(6))
    written = await compactor(FakeClient([summarised()]), store).compact(
        thread_id=THREAD, user_id=7
    )

    assert written is not None and written.role == "summary"
    content = store.writes[0]["content"]
    assert content["summarised_turns"] == 6 - KEEP
    assert content["covers_from_seq"] == 1
    assert content["covers_to_seq"] == 8
    assert content["source_message_ids"] == [
        message.id for message in store.messages[:8]
    ]
    assert content["previous_summary_message_id"] is None
    assert content["model"] == config().model_for(Workload.BATCH)
    assert datetime.fromisoformat(content["created_at"]).tzinfo is not None
    # And it is readable as a span by the one function that applies it.
    read = latest_summary(store.messages)
    assert read is not None
    assert read.summarised_turns == content["summarised_turns"]
    assert read.covers_to_seq == content["covers_to_seq"]


@pytest.mark.asyncio
async def test_the_specialist_asks_for_one_call_with_no_tools() -> None:
    client = FakeClient([summarised()])
    await compactor(client, FakeStore(conversation(6))).compact(
        thread_id=THREAD, user_id=7
    )

    assert len(client.requests) == 1
    request = client.requests[0]
    assert request.tools == ()
    assert request.tool_choice == "none"
    assert request.stream is False
    spend = client.spends[0]
    assert spend.workload.value == "batch"
    assert spend.lane.value == "analysis"
    assert spend.input_tokens > 0


@pytest.mark.asyncio
async def test_the_summary_stays_out_of_what_a_search_reads() -> None:
    """``session_search`` reads ``content->>'text'``, and must reach the Turns.

    A summary filed under that key would answer a search with the compression
    of the very message the reader was looking for.
    """
    store = FakeStore(conversation(6))
    await compactor(FakeClient([summarised()]), store).compact(thread_id=THREAD, user_id=7)

    assert "text" not in store.writes[0]["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "script",
    [
        [RuntimeError("the route fell over")],
        [asyncio.TimeoutError()],
        [Completion(model="batch-model", text="")],
        [Completion(model="batch-model", text="   ")],
    ],
    ids=["provider_error", "timeout", "empty_reply", "blank_reply"],
)
async def test_a_failed_pass_writes_nothing_at_all(script: list[Any]) -> None:
    store = FakeStore(conversation(6))

    written = await compactor(FakeClient(script), store).compact(
        thread_id=THREAD, user_id=7
    )

    assert written is None
    assert store.writes == []
    assert [message.role for message in store.messages] == ["user", "assistant"] * 6


@pytest.mark.asyncio
async def test_a_call_that_never_answers_is_given_up_on() -> None:
    class Hanging:
        async def complete(self, request: Any, spend: Any = None) -> Completion:
            await asyncio.sleep(30)
            raise AssertionError("the call should have been abandoned")

    store = FakeStore(conversation(6))
    written = await compactor(Hanging(), store, timeout_seconds=0.01).compact(
        thread_id=THREAD, user_id=7
    )

    assert written is None
    assert store.writes == []


@pytest.mark.asyncio
async def test_a_store_that_refuses_the_write_leaves_the_thread_untouched() -> None:
    store = FakeStore(conversation(6), refuse=True)

    written = await compactor(FakeClient([summarised()]), store).compact(
        thread_id=THREAD, user_id=7
    )

    assert written is None
    assert store.writes == []


@pytest.mark.asyncio
async def test_a_failure_stops_the_next_settled_turn_from_asking_again() -> None:
    store = FakeStore(conversation(6))
    clock = Clock()
    client = FakeClient([RuntimeError("the route fell over"), summarised()])
    specialist = compactor(client, store, clock=clock, cooldown_seconds=900.0)

    assert await specialist.compact(thread_id=THREAD, user_id=7) is None
    # Immediately after, with a route that would now answer: still nothing, and
    # no second call was made.
    assert await specialist.compact(thread_id=THREAD, user_id=7) is None
    assert len(client.requests) == 1

    clock.now += 901.0
    assert await specialist.compact(thread_id=THREAD, user_id=7) is not None


@pytest.mark.asyncio
async def test_an_oversized_reply_is_cut_rather_than_stored_whole() -> None:
    store = FakeStore(conversation(6))
    await compactor(FakeClient([summarised("dài " * 4000)]), store).compact(
        thread_id=THREAD, user_id=7
    )

    assert len(store.writes[0]["content"]["summary"]) <= MAX_SUMMARY_TEXT_CHARS + 1


# -- what the next Turn does with it ----------------------------------------


def constructed(messages: list[MessageRecord]):
    """The context the next Turn would build from this transcript."""
    history = history_of(messages)
    summary = _applicable_summary(latest_summary(messages), history)
    return history, build_messages(
        Transcript(
            system_prompt="p",
            turns=history,
            summary=None if summary is None else summary.text,
            summarised_turns=0 if summary is None else summary.summarised_turns,
        ),
        ContextBudget(max_tokens=100_000),
    )


@pytest.mark.asyncio
async def test_the_next_turn_applies_the_summary_and_drops_what_it_covers() -> None:
    store = FakeStore(conversation(6))
    await compactor(
        FakeClient([summarised("- Người dùng hỏi về lãi suất.")]), store
    ).compact(thread_id=THREAD, user_id=7)

    history, context = constructed(store.messages)

    assert len(history) == 6
    assert context.summary_used is True
    prose = "".join(message.content or "" for message in context.messages)
    assert "lãi suất" in prose
    # Exactly the Turns the span claims are gone, and the protected tail is not.
    assert "Câu hỏi số 3" not in prose
    assert "Câu hỏi số 4" in prose
    assert "Câu hỏi số 5" in prose


@pytest.mark.asyncio
async def test_a_thread_whose_compaction_failed_still_builds_its_context() -> None:
    store = FakeStore(conversation(6))
    await compactor(FakeClient([RuntimeError("no")]), store).compact(
        thread_id=THREAD, user_id=7
    )

    _history, context = constructed(store.messages)

    assert context.summary_used is False
    prose = "".join(message.content or "" for message in context.messages)
    assert all(f"Câu hỏi số {index}" in prose for index in range(6))


def test_the_summary_message_says_how_to_get_the_detail_back() -> None:
    """The recovery path is a sentence, not a sixth tool.

    Nothing was deleted to make the summary, so the model has to be told that
    the turns behind it are still reachable — otherwise it either answers from
    the compression or tells the reader the detail is gone, and the second is a
    false statement about this system.
    """
    _history, context = constructed(
        [*conversation(6), summary_row(13, covers_to_seq=8, turns=4)]
    )

    line = next(
        message.content
        for message in context.messages
        if (message.content or "").startswith(SUMMARY_LABEL)
    )
    assert "session_search" in line
    assert SUMMARY_LABEL.count("\n") == 0


def test_a_span_that_would_leave_no_live_turn_is_not_applied() -> None:
    messages = [*conversation(3), summary_row(7, covers_to_seq=6, turns=3)]

    history = history_of(messages)
    assert _applicable_summary(latest_summary(messages), history) is None


def test_a_summary_whose_span_cannot_be_read_is_ignored() -> None:
    broken = record(7, "summary", {"summary": "Bối cảnh.", "covers_from_seq": 1})
    older = summary_row(6, covers_to_seq=2, turns=1)

    assert latest_summary([older, broken]).seq == 6
    assert latest_summary([broken]) is None


# -- the lifecycle: settled first, summarised afterwards ---------------------


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture(autouse=True)
def _tools():
    with isolated_registry():
        install()
        yield


@pytest.fixture
def owner():
    email = f"compaction-{uuid.uuid4().hex}@example.com"
    with get_sync_db() as session:
        user = User(email=email, hashed_password="x")
        session.add(user)
        session.flush()
        user_id = user.id

    yield user_id

    with get_sync_db() as session:
        session.execute(delete(AgentThread).where(AgentThread.user_id == user_id))
        session.execute(delete(User).where(User.id == user_id))


def db_store() -> AgentPersistence:
    return AgentPersistence(session_factory=sync_session_factory)


def turn_service(client: Any, **overrides: Any) -> TurnService:
    def loop_factory(*, checkpoint, publisher, lane):
        return AgentLoop(
            client=client,
            config=config(),
            budget=ContextBudget(max_tokens=30_000),
            lane=lane,
            checkpoint=checkpoint,
            publisher=publisher,
        )

    return TurnService(
        store=db_store(), loop_factory=loop_factory, config=config(), **overrides
    )


def answered(text: str = "Xong.") -> Completion:
    return Completion(
        model="gpt-5.6-terra", text=text, usage=Usage(input_tokens=10, output_tokens=5)
    )


@pytest.mark.asyncio
async def test_a_turn_settles_without_waiting_for_its_summary(owner) -> None:
    """The reader has the answer before the specialist has even been asked."""
    thread_id = (await db_store().create_thread(owner, title="Long")).id
    started = asyncio.Event()
    release = asyncio.Event()
    finished: list[str] = []

    async def blocking(*, thread_id: Any, user_id: int) -> None:
        started.set()
        await release.wait()
        finished.append(str(thread_id))

    turns = turn_service(FakeClient([answered()]), compactor=blocking)
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=RuntimeContext(today=TODAY, user_name="Ty"),
        # Long enough that the constructor asks for a summary.
        history=history_of(conversation(9)),
    )
    running = turns.running(turn_id)
    record_ = await running.task

    # The Turn is terminal and its message is committed while the summary is
    # still blocked on a call nobody is waiting for.
    assert record_.status == TURN_COMPLETE
    assert record_.response_message_id is not None
    await asyncio.wait_for(started.wait(), 1.0)
    assert finished == []

    release.set()
    await turns.shutdown()


@pytest.mark.asyncio
async def test_a_short_thread_settles_without_asking_for_a_summary(owner) -> None:
    thread_id = (await db_store().create_thread(owner, title="Short")).id
    asked: list[str] = []

    async def counting(*, thread_id: Any, user_id: int) -> None:
        asked.append(str(thread_id))

    turns = turn_service(FakeClient([answered()]), compactor=counting)
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=RuntimeContext(today=TODAY, user_name="Ty"),
    )
    await turns.running(turn_id).task
    await asyncio.sleep(0)

    assert asked == []


@pytest.mark.asyncio
async def test_the_summary_row_survives_a_write_and_stays_off_the_transcript(
    owner,
) -> None:
    """One round trip through the real store, which is where the role lives."""
    store = db_store()
    thread_id = (await store.create_thread(owner, title="Round trip")).id
    for index in range(6):
        await store.append_message(
            thread_id, role="user", content={"text": f"Câu hỏi số {index}"}
        )
        await store.append_message(
            thread_id, role="assistant", content={"text": f"Trả lời số {index}"}
        )

    view = await store.read_thread(owner, thread_id)
    written = await compactor(FakeClient([summarised()]), store).compact(
        thread_id=thread_id, user_id=owner
    )
    assert written is not None

    reopened = await store.read_thread(owner, thread_id)
    assert [row.role for row in reopened.messages][-1] == "summary"
    # The Turns behind it are still there, word for word, which is what makes
    # the recovery search the summary message promises possible at all.
    assert len(history_of(reopened.messages)) == len(history_of(view.messages)) == 6
    read = latest_summary(reopened.messages)
    assert read is not None and read.summarised_turns == 6 - KEEP
    with get_sync_db() as session:
        rows = session.execute(
            select(AgentMessage.role, AgentMessage.content)
            .where(AgentMessage.thread_id == thread_id)
            .order_by(AgentMessage.seq)
        ).all()
    assert rows[-1][0] == "summary"
    assert "text" not in rows[-1][1]
