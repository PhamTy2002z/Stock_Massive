"""Thread, transcript, and Tool Call Trace behavior through the public store."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from src.agent.persistence import (
    THREAD_TITLE_LENGTH,
    TURN_COMPLETE,
    TURN_INCOMPLETE,
    TURN_RUNNING,
    AgentPersistence,
    QuestionAlreadyResolved,
    QuestionOptionInvalid,
    thread_title_from,
)
from src.agent.executor import ToolCall, ToolExecutor
from src.agent.messages import ToolCallStatus, TurnToolCall
from src.agent.parts import (
    QUESTION_ANSWERED,
    QUESTION_PENDING,
    QUESTION_SKIPPED,
    QUESTION_SUPERSEDED,
    QuestionOption,
    QuestionPart,
)
from src.agent.registry import ToolAccess, ToolContext
from src.agent.turns import assistant_message, frozen_message
from src.alpha.models import AgentQuestion, AgentThread, AgentTurn
from src.auth.models import User
from src.core.database import Base, get_sync_db, sync_engine, sync_session_factory
from .agent_tool_world import ADVERSARIAL_PAGE, stub_entry

SYMBOL = "PATHS"


def _at(day: int) -> datetime:
    """One August instant, so a row's age is decided by the test and not the clock."""
    return datetime(2026, 8, day, 9, 30, tzinfo=timezone.utc)


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


def _account():
    email = f"paths-{uuid.uuid4().hex}@example.com"
    with get_sync_db() as session:
        user = User(email=email, hashed_password="x")
        session.add(user)
        session.flush()
        user_id = user.id

    yield user_id

    with get_sync_db() as session:
        session.execute(delete(AgentThread).where(AgentThread.user_id == user_id))
        session.execute(delete(User).where(User.id == user_id))


@pytest.fixture
def owner():
    yield from _account()


@pytest.fixture
def stranger():
    """A second reader, for the questions that are none of their business."""
    yield from _account()


def persistence() -> AgentPersistence:
    return AgentPersistence(session_factory=sync_session_factory)


@pytest.mark.asyncio
async def test_thread_lifecycle_deletes_only_the_owned_thread(owner):
    store = persistence()
    older = await store.create_thread(owner, title="Older")
    newer = await store.create_thread(owner, title="Newer")
    message = await store.append_message(
        older.id,
        role="user",
        content={"text": "Phân tích PATHS"},
        symbols=(SYMBOL,),
    )
    await store.record_tool_call(
        {
            "thread_id": older.id,
            "request_message_id": message.id,
            "tool_name": "get_analysis",
            "arguments": {"symbol": SYMBOL},
            "result": {"found": False},
            "status": "ok",
            "error": None,
            "latency_ms": 2,
        }
    )
    listed = await store.list_threads(owner)
    loaded = await store.read_thread(owner, older.id)
    discussing = await store.threads_discussing(owner, SYMBOL)

    assert [item.id for item in listed] == [older.id, newer.id]
    assert [item.seq for item in loaded.messages] == [1]
    assert loaded.symbols == (SYMBOL,)
    assert [item.id for item in discussing] == [older.id]

    assert await store.delete_thread(owner, older.id) is True
    assert await store.read_thread(owner, older.id) is None
    assert await store.traces_for_request(message.id) == ()


@pytest.mark.asyncio
async def test_concurrent_writers_receive_distinct_gapless_sequences(owner):
    store = persistence()
    thread = await store.create_thread(owner)

    messages = await asyncio.gather(
        *(
            store.append_message(
                thread.id,
                role="user" if index == 0 else "assistant",
                content={"index": index},
            )
            for index in range(8)
        )
    )
    loaded = await store.read_thread(owner, thread.id)

    assert sorted(item.seq for item in messages) == list(range(1, 9))
    assert [item.seq for item in loaded.messages] == list(range(1, 9))


@pytest.mark.asyncio
async def test_each_trace_survives_independently(owner):
    store = persistence()
    thread = await store.create_thread(owner)
    request = await store.append_message(
        thread.id, role="user", content={"text": "two calls"}
    )

    for index in range(2):
        await store.record_tool_call(
            {
                "thread_id": thread.id,
                "request_message_id": request.id,
                "tool_name": f"tool_{index}",
                "arguments": {"index": index},
                "result": {"index": index},
                "status": "ok",
                "error": None,
                "latency_ms": index + 1,
            }
        )

    traces = await store.traces_for_request(request.id)

    assert [trace.tool_name for trace in traces] == ["tool_0", "tool_1"]
    assert [trace.result for trace in traces] == [{"index": 0}, {"index": 1}]
    assert [trace.latency_ms for trace in traces] == [1, 2]


@pytest.mark.asyncio
async def test_a_traced_result_keeps_its_body_and_is_scoped_to_its_request(owner):
    """The trace is the only record of what an answer rested on.

    With no citations and no manifest, a row holding a character count would
    answer no question anyone opens it to ask — so the body is stored, and it is
    readable back under the id the call was made with. Scoped to the request
    message, so a call id from another Turn cannot be read through it.
    """
    store = persistence()
    thread = await store.create_thread(owner)
    request = await store.append_message(
        thread.id, role="user", content={"text": "one big call"}
    )
    body = {"text": "lãi suất điều hành giữ nguyên", "chars": 29, "dispatched": True}
    await store.record_tool_call(
        {
            "thread_id": thread.id,
            "request_message_id": request.id,
            "tool_name": "web_search",
            "tool_call_id": "call_0",
            "arguments": {"query": "lãi suất"},
            "result": body,
            "status": "ok",
            "error": None,
        }
    )

    (trace,) = await store.traces_for_request(request.id)

    assert trace.tool_call_id == "call_0"
    assert trace.result == body
    assert await store.tool_result(request.id, "call_0") == body
    assert await store.tool_result(request.id + 1_000, "call_0") is None


@pytest.mark.asyncio
async def test_a_tool_the_registry_does_not_have_is_persisted_as_unknown(owner):
    """The one status the ops query counts by name, written by the executor."""
    store = persistence()
    thread = await store.create_thread(owner)
    request = await store.append_message(
        thread.id, role="user", content={"text": "call missing"}
    )

    async def trace(entry):
        await store.record_tool_call(
            {
                "thread_id": thread.id,
                "request_message_id": request.id,
                "tool_name": entry["tool"],
                "tool_call_id": entry["call_id"],
                "arguments": dict(entry["arguments"]),
                "result": {"text": entry["result_text"]},
                "status": "ok" if entry["ok"] else entry["error"],
            }
        )

    executor = ToolExecutor(
        context=ToolContext(
            user_id=owner, thread_id=thread.id, now=datetime.now(timezone.utc)
        ),
        trace=trace,
    )
    await executor.run([ToolCall(id="call_0", name="missing", arguments={})])

    (written,) = await store.traces_for_request(request.id)
    assert written.status == "unknown_tool"
    assert written.tool_name == "missing"


@pytest.mark.asyncio
async def test_the_opening_question_names_the_thread(owner):
    store = persistence()
    thread = await store.create_thread(owner)

    await store.create_turn(
        user_id=owner,
        thread_id=thread.id,
        turn_id=uuid.uuid4(),
        user_text="  Vì sao PATHS bị hạ điểm\n phiên hôm qua?  ",
    )

    named = await store.read_thread(owner, uuid.UUID(str(thread.id)))
    assert named is not None
    assert named.title == "Vì sao PATHS bị hạ điểm phiên hôm qua?"


@pytest.mark.asyncio
async def test_a_later_question_does_not_rename_the_thread(owner):
    store = persistence()
    thread = await store.create_thread(owner)

    for text in ("Câu hỏi đầu", "Câu hỏi sau"):
        await store.create_turn(
            user_id=owner,
            thread_id=thread.id,
            turn_id=uuid.uuid4(),
            user_text=text,
        )

    named = await store.read_thread(owner, uuid.UUID(str(thread.id)))
    assert named is not None
    assert named.title == "Câu hỏi đầu"


@pytest.mark.asyncio
async def test_a_thread_the_user_named_keeps_that_name(owner):
    store = persistence()
    thread = await store.create_thread(owner, title="Sổ tay phiên chiều")

    await store.create_turn(
        user_id=owner,
        thread_id=thread.id,
        turn_id=uuid.uuid4(),
        user_text="Phân tích PATHS giúp tôi",
    )

    named = await store.read_thread(owner, uuid.UUID(str(thread.id)))
    assert named is not None
    assert named.title == "Sổ tay phiên chiều"


def test_a_long_question_is_cut_at_a_word_with_an_ellipsis():
    title = thread_title_from(
        "Vì sao nhóm ngân hàng vẫn giữ được đà tăng trong khi thanh khoản "
        "toàn thị trường giảm mạnh?"
    )
    assert title is not None
    assert len(title) <= THREAD_TITLE_LENGTH + 1
    assert title.endswith("…")
    assert not title.endswith(" …")


def test_a_blank_question_names_nothing():
    assert thread_title_from("   \n  ") is None


# -- the advisory verdict, written down and read back -------------------------


#: The same page the executor and wrapper tests use. Exact rather than merely
#: hostile, because the verdict below is compared name by name.

BULLETIN = "https://example.com/bulletin"


async def dispatched(user_id: int, name: str, body: str, *, external: bool = True):
    """One tool call, run for real, so the verdict is computed and not written.

    The declaration is handed to the executor rather than registered globally:
    the process-wide registry belongs to whichever module imported a tool
    surface first, and a test that depended on that would pass or fail by
    collection order.
    """

    async def handler(_context, _arguments):
        return body

    entry = stub_entry(
        name,
        handler=handler,
        access=ToolAccess.NETWORK if external else ToolAccess.STORE,
        reads_external=external,
    )
    outcome = await ToolExecutor(
        context=ToolContext(user_id=user_id),
        lookup={name: entry}.get,
        availability=lambda _name: True,
    ).run([ToolCall(id="call_0", name=name, arguments={"url": BULLETIN})])
    return outcome.results[0]


def committed(result) -> dict:
    """The assistant message a finished Turn writes, carrying this one call."""
    call = TurnToolCall(
        id=result.call_id,
        name=result.tool_name,
        arguments={"url": BULLETIN},
        status=ToolCallStatus.OK,
        result_text=result.text,
        scan=result.scan,
    )
    return assistant_message(
        text="Trang này cố ra lệnh, nên tôi chỉ đọc nó như dữ liệu.",
        tool_calls=[call.as_wire()],
        status=TURN_COMPLETE,
    )


async def reopened(store: AgentPersistence, owner: int, thread_id) -> dict:
    """The persisted assistant message, read back the way a reopened Thread is."""
    view = await store.read_thread(owner, thread_id)
    assert view is not None
    message = next(
        item for item in reversed(view.messages) if item.role == "assistant"
    )
    return dict(message.content or {})


@pytest.mark.asyncio
async def test_a_flagged_page_is_still_flagged_when_the_thread_is_reopened(owner):
    """The verdict is durable without a column of its own, and that is the design.

    ``TurnToolCall.as_wire`` is already written to ``agent_message.content``
    when the answer commits, so the flag survives a reopen with no migration, no
    second column on the hot trace table, and without touching the trace's own
    invariant that ``result`` holds exactly what the model saw.
    """
    store = persistence()
    thread = await store.create_thread(owner)
    await store.append_message(
        thread.id, role="user", content={"text": "Phiên hôm nay ra sao?"}
    )
    result = await dispatched(owner, "market_bulletin", ADVERSARIAL_PAGE)

    await store.append_message(
        thread.id, role="assistant", content=committed(result)
    )
    content = await reopened(store, owner, thread.id)
    (payload,) = content["tool_calls"]

    assert result.scan == {
        "risk": "high",
        "findings": [
            "instruction_override",
            "conceal_from_user",
            "role_reassignment",
            "prompt_disclosure",
        ],
    }
    assert payload["scan"] == result.scan
    assert payload["kind"] == "external"


@pytest.mark.asyncio
async def test_a_store_read_is_persisted_with_no_verdict_at_all(owner):
    """``None`` and ``low`` are different claims, and the round trip keeps both.

    A read of this deployment's own store is never scanned, so what is written
    down is the absence of a verdict rather than a clean one — otherwise the
    corpus that counts how often the scan fires would be counting reads it never
    looked at.
    """
    store = persistence()
    thread = await store.create_thread(owner)
    result = await dispatched(owner, "session_search", "{}", external=False)

    await store.append_message(
        thread.id, role="assistant", content=committed(result)
    )
    content = await reopened(store, owner, thread.id)
    (payload,) = content["tool_calls"]

    assert result.scan is None
    assert payload["scan"] is None


@pytest.mark.asyncio
async def test_the_projection_the_model_read_never_reaches_the_persisted_call(owner):
    """``context_text`` is the model's copy, and it stops at the model.

    The persisted payload is what a reopened Thread draws and what the golden
    runner counts. A shorter copy of a result leaking into it would make both of
    them describe a Turn that never happened — a search that found fewer pages
    than it found.
    """
    store = persistence()
    thread = await store.create_thread(owner)
    result = await dispatched(owner, "web_search", '{"results":[{"url":"https://a.vn"}]}')

    call = TurnToolCall(
        id=result.call_id,
        name=result.tool_name,
        arguments={"query": "lãi suất"},
        status=ToolCallStatus.OK,
        result_text=result.text,
        context_text="{}",
        scan=result.scan,
    )
    await store.append_message(
        thread.id,
        role="assistant",
        content=assistant_message(
            text="Xong.", tool_calls=[call.as_wire()], status=TURN_COMPLETE
        ),
    )
    content = await reopened(store, owner, thread.id)
    (payload,) = content["tool_calls"]

    assert "context_text" not in payload
    assert "result_text" not in payload
    assert call.model_text == "{}"


@pytest.mark.asyncio
async def test_the_trace_row_holds_the_whole_result_not_the_projection(owner):
    """The audit invariant: ``result`` is what the tool returned.

    Written through the same ``record_tool_call`` the loop's trace writer calls,
    and read back through the same ``tool_result`` a spilled preview is resolved
    through, so what this asserts is the round trip rather than a dictionary.
    """
    store = persistence()
    thread = await store.create_thread(owner)
    whole = '{"results":[{"url":"https://a.vn"},{"url":"https://b.vn"}]}'
    result = await dispatched(owner, "web_search", whole)
    asked = await store.append_message(
        thread.id, role="user", content={"text": "lãi suất"}
    )

    await store.record_tool_call(
        {
            "thread_id": str(thread.id),
            "request_message_id": asked.id,
            "tool_name": result.tool_name,
            "tool_call_id": result.call_id,
            "arguments": {"query": "lãi suất"},
            "result": {"text": result.text, "chars": len(result.text)},
            "status": "ok",
        }
    )
    stored = await store.tool_result(asked.id, result.call_id)

    assert stored is not None
    assert stored["text"] == whole


# -- a question, and the three things that can become of it -------------------


def card(**overrides) -> QuestionPart:
    fields = {
        "question_id": str(uuid.uuid4()),
        "prompt": "Bạn mua mới hay trung bình giá?",
        "options": [
            QuestionOption(id="new", label="Mua mới"),
            QuestionOption(id="average", label="Trung bình giá"),
        ],
    }
    fields.update(overrides)
    return QuestionPart(**fields)


async def asked(
    store: AgentPersistence,
    owner: int,
    thread_id,
    part: QuestionPart,
    *,
    text: str = "Trước khi kết luận, tôi cần một dữ kiện.",
):
    """One Turn that ended by asking, committed the way the lifecycle commits it.

    Through ``create_turn`` and ``finish_turn`` rather than by inserting rows: the
    thing under test is that the message and the question row are written by the
    same terminal transaction, and a hand-built row would prove nothing about it.
    """
    turn_id = uuid.uuid4()
    await store.create_turn(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="VCB thế nào?",
    )
    await store.finish_turn(
        turn_id,
        status=TURN_COMPLETE,
        terminal_reason=None,
        message=assistant_message(
            text=text, status=TURN_COMPLETE, question=part.as_wire()
        ),
        question=part.as_wire(),
    )
    return turn_id


def question_row(question_id) -> AgentQuestion | None:
    with get_sync_db() as session:
        return session.get(AgentQuestion, uuid.UUID(str(question_id)))


async def card_in_transcript(store: AgentPersistence, owner: int, thread_id) -> dict:
    """The question as a reopened Thread sees it, live state and all."""
    view = await store.read_thread(owner, thread_id)
    assert view is not None
    message = next(
        item
        for item in reversed(view.messages)
        if item.role == "assistant" and item.content.get("question")
    )
    return dict(message.content["question"])


@pytest.mark.asyncio
async def test_the_terminal_transaction_writes_the_message_and_the_question(owner):
    """A card with no row behind it would take an answer nothing can record."""
    store = persistence()
    thread = await store.create_thread(owner)
    part = card()

    turn_id = await asked(store, owner, thread.id, part)

    view = await store.read_thread(owner, thread.id)
    assistant = next(item for item in view.messages if item.role == "assistant")
    row = question_row(part.question_id)
    assert row is not None
    assert row.state == QUESTION_PENDING
    assert row.turn_id == turn_id
    assert row.message_id == assistant.id
    # The owner is a column rather than a join, because the endpoints that
    # resolve a question are reached by question id alone.
    assert row.user_id == owner
    assert row.selected_option_ids is None
    assert row.resolved_at is None
    # The part is in the transcript exactly as it was asked, and the state the
    # store merged in is the row's.
    assert assistant.content["question"]["prompt"] == part.prompt
    assert assistant.content["question"]["state"] == QUESTION_PENDING


@pytest.mark.asyncio
async def test_a_turn_that_answered_carries_no_question_key_at_all(owner):
    """Absent rather than null, so a message from before this existed reads alike."""
    store = persistence()
    thread = await store.create_thread(owner)
    turn_id = uuid.uuid4()
    await store.create_turn(
        user_id=owner, thread_id=thread.id, turn_id=turn_id, user_text="VCB thế nào?"
    )
    await store.finish_turn(
        turn_id,
        status=TURN_COMPLETE,
        terminal_reason=None,
        message=assistant_message(text="Xong.", status=TURN_COMPLETE),
    )

    view = await store.read_thread(owner, thread.id)
    assistant = next(item for item in view.messages if item.role == "assistant")
    assert "question" not in assistant.content


@pytest.mark.asyncio
async def test_a_question_without_the_message_that_asked_it_is_refused(owner):
    store = persistence()
    thread = await store.create_thread(owner)
    turn_id = uuid.uuid4()
    await store.create_turn(
        user_id=owner, thread_id=thread.id, turn_id=turn_id, user_text="VCB thế nào?"
    )

    with pytest.raises(ValueError):
        await store.finish_turn(
            turn_id,
            status=TURN_COMPLETE,
            terminal_reason=None,
            question=card().as_wire(),
        )


@pytest.mark.asyncio
async def test_an_answer_is_written_once_and_a_second_tap_changes_nothing(owner):
    store = persistence()
    thread = await store.create_thread(owner)
    part = card()
    await asked(store, owner, thread.id, part)

    first = await store.answer_question(owner, part.question_id, ["average"])
    again = await store.answer_question(owner, part.question_id, ["average"])

    assert first.state == QUESTION_ANSWERED
    assert first.selected_option_ids == ("average",)
    assert first.resolved_at is not None
    # The same decision, so the stamp does not move: a double tap is one choice.
    assert again.resolved_at == first.resolved_at
    assert (await card_in_transcript(store, owner, thread.id))["state"] == (
        QUESTION_ANSWERED
    )


@pytest.mark.asyncio
async def test_changing_a_settled_answer_is_a_conflict_and_not_a_rewrite(owner):
    """The work has continued from the first answer; the next Turn is the way back."""
    store = persistence()
    thread = await store.create_thread(owner)
    part = card()
    await asked(store, owner, thread.id, part)
    await store.answer_question(owner, part.question_id, ["new"])

    with pytest.raises(QuestionAlreadyResolved) as conflict:
        await store.answer_question(owner, part.question_id, ["average"])
    with pytest.raises(QuestionAlreadyResolved):
        await store.skip_question(owner, part.question_id)

    assert conflict.value.state == QUESTION_ANSWERED
    row = question_row(part.question_id)
    assert row.selected_option_ids == ["new"]


@pytest.mark.asyncio
async def test_a_skip_is_a_decision_with_an_outcome_of_its_own(owner):
    """Null and not an empty list: choosing nothing is what a skip *is*."""
    store = persistence()
    thread = await store.create_thread(owner)
    part = card()
    await asked(store, owner, thread.id, part)

    skipped = await store.skip_question(owner, part.question_id)
    again = await store.skip_question(owner, part.question_id)

    assert skipped.state == QUESTION_SKIPPED
    assert skipped.selected_option_ids is None
    assert skipped.resolved_at is not None
    assert again.resolved_at == skipped.resolved_at
    assert (await card_in_transcript(store, owner, thread.id)) == {
        **part.as_wire(),
        "state": QUESTION_SKIPPED,
        "selected_option_ids": None,
    }


@pytest.mark.asyncio
async def test_only_the_options_the_card_offered_can_be_chosen(owner):
    store = persistence()
    single = card()
    multi = card(multi_select=True)
    # One card per Thread: a second Turn on the same Thread would supersede the
    # first card, which is the behaviour its own test asserts.
    await asked(store, owner, (await store.create_thread(owner)).id, single)
    await asked(store, owner, (await store.create_thread(owner)).id, multi)

    with pytest.raises(QuestionOptionInvalid):
        await store.answer_question(owner, single.question_id, ["hold"])
    with pytest.raises(QuestionOptionInvalid):
        await store.answer_question(owner, single.question_id, [])
    with pytest.raises(QuestionOptionInvalid):
        # Several choices on a question that takes one.
        await store.answer_question(owner, single.question_id, ["new", "average"])

    both = await store.answer_question(owner, multi.question_id, ["average", "new"])
    assert set(both.selected_option_ids) == {"new", "average"}
    # Nothing was written to the single-select question by any of the refusals.
    assert question_row(single.question_id).state == QUESTION_PENDING


@pytest.mark.asyncio
async def test_a_question_is_only_the_reader_it_was_asked_of(owner, stranger):
    """Not found rather than forbidden, the rule every row here follows."""
    store = persistence()
    thread = await store.create_thread(owner)
    part = card()
    await asked(store, owner, thread.id, part)

    assert await store.answer_question(stranger, part.question_id, ["new"]) is None
    assert await store.skip_question(stranger, part.question_id) is None
    assert await store.read_question(stranger, part.question_id) is None
    assert await store.answer_question(owner, uuid.uuid4(), ["new"]) is None
    assert question_row(part.question_id).state == QUESTION_PENDING


@pytest.mark.asyncio
async def test_typing_instead_of_tapping_supersedes_inside_the_create(owner):
    """A reader who moves past the card has answered it by moving past it."""
    store = persistence()
    thread = await store.create_thread(owner)
    other_thread = await store.create_thread(owner)
    part = card()
    elsewhere = card()
    await asked(store, owner, thread.id, part)
    await asked(store, owner, other_thread.id, elsewhere)

    await store.create_turn(
        user_id=owner,
        thread_id=thread.id,
        turn_id=uuid.uuid4(),
        user_text="Thôi, cho tôi hỏi cái khác.",
    )

    superseded = await store.read_question(owner, part.question_id)
    assert superseded.state == QUESTION_SUPERSEDED
    assert superseded.resolved_at is not None
    # Scoped to the Thread the reader typed in: a card on another conversation is
    # still theirs to answer.
    assert (await store.read_question(owner, elsewhere.question_id)).state == (
        QUESTION_PENDING
    )
    assert (await card_in_transcript(store, owner, thread.id))["state"] == (
        QUESTION_SUPERSEDED
    )
    # A card already settled is not re-settled, so its stamp survives.
    resolved = card()
    await asked(store, owner, other_thread.id, resolved)
    answered = await store.answer_question(owner, resolved.question_id, ["new"])
    await store.create_turn(
        user_id=owner,
        thread_id=other_thread.id,
        turn_id=uuid.uuid4(),
        user_text="Câu tiếp theo.",
    )
    kept = await store.read_question(owner, resolved.question_id)
    assert kept.state == QUESTION_ANSWERED
    assert kept.resolved_at == answered.resolved_at


@pytest.mark.asyncio
async def test_every_state_of_a_card_survives_a_reopened_thread(owner):
    """The transcript read is the replay surface, so it merges the live state."""
    store = persistence()
    states = {}
    for outcome in (QUESTION_ANSWERED, QUESTION_SKIPPED, QUESTION_SUPERSEDED):
        thread = await store.create_thread(owner)
        part = card()
        await asked(store, owner, thread.id, part)
        if outcome == QUESTION_ANSWERED:
            await store.answer_question(owner, part.question_id, ["new"])
        elif outcome == QUESTION_SKIPPED:
            await store.skip_question(owner, part.question_id)
        else:
            await store.create_turn(
                user_id=owner,
                thread_id=thread.id,
                turn_id=uuid.uuid4(),
                user_text="Hỏi lại cách khác.",
            )
        states[outcome] = await card_in_transcript(store, owner, thread.id)

    assert [entry["state"] for entry in states.values()] == [
        QUESTION_ANSWERED,
        QUESTION_SKIPPED,
        QUESTION_SUPERSEDED,
    ]
    assert states[QUESTION_ANSWERED]["selected_option_ids"] == ["new"]
    assert states[QUESTION_SKIPPED]["selected_option_ids"] is None
    assert states[QUESTION_SUPERSEDED]["selected_option_ids"] is None


@pytest.mark.asyncio
async def test_a_card_whose_row_is_gone_is_left_exactly_as_it_was_written(owner):
    """No invented default: a state drawn off a missing row invites a dead answer."""
    store = persistence()
    thread = await store.create_thread(owner)
    part = card()
    await asked(store, owner, thread.id, part)
    with get_sync_db() as session:
        session.execute(
            delete(AgentQuestion).where(
                AgentQuestion.id == uuid.UUID(part.question_id)
            )
        )

    drawn = await card_in_transcript(store, owner, thread.id)
    assert drawn == part.as_wire()
    assert "state" not in drawn


@pytest.mark.asyncio
async def test_the_freeze_settles_the_checkpoint_it_leaves_behind(owner):
    """The snapshot a reconnecting reader gets comes from this column, not the message.

    So a checkpoint left as the dead process wrote it would keep drawing a call
    in flight that nothing is coming back for, while the transcript beside it
    already says the call was interrupted.
    """
    store = persistence()
    thread = await store.create_thread(owner)
    message = await store.append_message(
        thread.id, role="user", content={"text": "VCB thế nào?"}
    )
    turn_id = uuid.uuid4()
    with get_sync_db() as session:
        session.add(
            AgentTurn(
                id=turn_id,
                thread_id=thread.id,
                request_message_id=message.id,
                status=TURN_RUNNING,
                last_event_seq=3,
                started_at=datetime.now(timezone.utc),
                draft_content={
                    "text": "Một phần đã kịp nói.",
                    "tool_calls": [
                        {"id": "c1", "name": "web_search", "status": "ok"},
                        {"id": "c2", "name": "web_search", "status": "running"},
                        {
                            "id": "c3",
                            "name": "remember_fact",
                            "status": "pending",
                            "dispatched": True,
                        },
                    ],
                    "rounds_used": 1,
                },
            )
        )

    await store.freeze_interrupted_turns(frozen_message)

    record = await store.read_turn(owner, turn_id)
    assert record.status == TURN_INCOMPLETE
    persisted = record.draft_content["tool_calls"]
    assert [call["status"] for call in persisted] == ["ok", "error", "error"]
    assert [call.get("error") for call in persisted] == [
        None,
        "interrupted",
        "interrupted",
    ]
    # Whether the write landed is not this transaction's to invent.
    assert persisted[2]["dispatched"] is True


@pytest.mark.asyncio
async def test_a_freeze_with_nothing_outstanding_rewrites_no_checkpoint(owner):
    """The column of an ordinary interrupted Turn stays what its process wrote."""
    store = persistence()
    thread = await store.create_thread(owner)
    message = await store.append_message(
        thread.id, role="user", content={"text": "VCB thế nào?"}
    )
    turn_id = uuid.uuid4()
    checkpoint = {
        "text": "Một phần đã kịp nói.",
        "tool_calls": [{"id": "c1", "name": "web_search", "status": "ok"}],
        "rounds_used": 1,
    }
    with get_sync_db() as session:
        session.add(
            AgentTurn(
                id=turn_id,
                thread_id=thread.id,
                request_message_id=message.id,
                status=TURN_RUNNING,
                started_at=datetime.now(timezone.utc),
                draft_content=checkpoint,
            )
        )

    await store.freeze_interrupted_turns(frozen_message)

    record = await store.read_turn(owner, turn_id)
    assert record.draft_content == checkpoint


@pytest.mark.asyncio
async def test_the_first_terminal_wins_the_question_along_with_everything_else(owner):
    """A late finishing task and the startup sweep can both arrive here."""
    store = persistence()
    thread = await store.create_thread(owner)
    part = card()
    turn_id = await asked(store, owner, thread.id, part)
    await store.answer_question(owner, part.question_id, ["new"])

    second = card()
    await store.finish_turn(
        turn_id,
        status=TURN_COMPLETE,
        terminal_reason=None,
        message=assistant_message(
            text="Lần thứ hai.", status=TURN_COMPLETE, question=second.as_wire()
        ),
        question=second.as_wire(),
    )

    view = await store.read_thread(owner, thread.id)
    assert question_row(second.question_id) is None
    assert question_row(part.question_id).state == QUESTION_ANSWERED
    assert [row.role for row in view.messages] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_a_page_read_is_found_again_anywhere_in_its_own_thread(owner):
    """The read that lets evidence outlive the Turn that gathered it.

    Scoped to the Thread and matched by containment, so the URL identifies the
    read and the question that shaped it does not. The newest one answers: an
    older row is a reading this conversation has already superseded.
    """
    store = persistence()
    thread = await store.create_thread(owner)
    elsewhere = await store.create_thread(owner)
    url = "https://news.example/rates"

    async def read(thread_id, message_id, *, content, when, status="ok", tool="fetch_url"):
        await store.record_tool_call(
            {
                "thread_id": thread_id,
                "request_message_id": message_id,
                "tool_name": tool,
                "tool_call_id": f"call_{when.day}",
                "arguments": {"url": url, "looking_for": "lãi suất"},
                "result": {
                    "text": json.dumps({"url": url, "content": content}),
                    "chars": len(content),
                    "dispatched": True,
                },
                "status": status,
                "error": None,
                "started_at": when,
            }
        )

    first = await store.append_message(thread.id, role="user", content={"text": "one"})
    second = await store.append_message(thread.id, role="user", content={"text": "two"})
    other = await store.append_message(elsewhere.id, role="user", content={"text": "far"})
    await read(thread.id, first.id, content="giữ nguyên", when=_at(20))
    await read(thread.id, second.id, content="tăng 0,25 điểm", when=_at(21))
    await read(thread.id, second.id, content="không đọc được", when=_at(22), status="timeout")
    await read(elsewhere.id, other.id, content="thread khác", when=_at(23))

    served = await store.recorded_result(thread.id, "fetch_url", {"url": url})

    assert served == {"url": url, "content": "tăng 0,25 điểm"}
    # A Thread reads its own rows and no others. Another conversation of the
    # same user gathered its evidence for a question this one never asked.
    assert await store.recorded_result(
        elsewhere.id, "fetch_url", {"url": url}
    ) == {"url": url, "content": "thread khác"}
    assert (
        await store.recorded_result(
            thread.id, "fetch_url", {"url": "https://news.example/never"}
        )
        is None
    )
    assert await store.recorded_result(thread.id, "web_search", {"url": url}) is None


@pytest.mark.asyncio
async def test_a_result_too_big_to_have_been_stored_whole_is_no_record_at_all(owner):
    """A trimmed body leaves JSON that does not close, and half an object is
    worse than none: the caller reads the page again rather than acting on
    evidence nobody can reconstruct.
    """
    store = persistence()
    thread = await store.create_thread(owner)
    request = await store.append_message(
        thread.id, role="user", content={"text": "a very long page"}
    )
    whole = json.dumps({"url": "https://news.example/long", "content": "x" * 400})
    await store.record_tool_call(
        {
            "thread_id": thread.id,
            "request_message_id": request.id,
            "tool_name": "fetch_url",
            "tool_call_id": "call_0",
            "arguments": {"url": "https://news.example/long"},
            "result": {"text": whole[:120], "chars": len(whole), "dispatched": True},
            "status": "ok",
            "error": None,
        }
    )

    assert (
        await store.recorded_result(
            thread.id, "fetch_url", {"url": "https://news.example/long"}
        )
        is None
    )
