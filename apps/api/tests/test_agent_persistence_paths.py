"""Thread, transcript, and Tool Call Trace behavior through the public store."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from src.agent.persistence import (
    THREAD_TITLE_LENGTH,
    AgentPersistence,
    thread_title_from,
)
from src.agent.executor import ToolCall, ToolExecutor
from src.agent.registry import ToolContext
from src.alpha.models import AgentThread
from src.auth.models import User
from src.core.database import Base, get_sync_db, sync_engine, sync_session_factory

SYMBOL = "PATHS"


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture
def owner():
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
async def test_a_call_that_ran_and_answered_nothing_is_stored_as_such(owner):
    """``ok`` and empty are not a contradiction, and the row has to hold both.

    A store read that comes back with no figure is a successful call: the tool
    worked and the answer is that there is no number. Measured on the trace
    before this column existed, 42 of 151 ``get_field`` rows were exactly this
    and every one of them was indistinguishable from a row carrying a figure.
    """
    store = persistence()
    thread = await store.create_thread(owner)
    request = await store.append_message(
        thread.id, role="user", content={"text": "phân vị động lượng VHM"}
    )
    for call_id, outcome in (
        ("call_0", "value"),
        ("call_1", "no_value:market_cap_absent"),
        ("call_2", "cannot_read"),
    ):
        await store.record_tool_call(
            {
                "thread_id": thread.id,
                "request_message_id": request.id,
                "tool_name": "get_field",
                "tool_call_id": call_id,
                "arguments": {"field_id": "momentum_rank.percentile_12_2"},
                "result": {"text": "{}", "chars": 2, "dispatched": True},
                "status": "ok",
                "error": None,
                "outcome": outcome,
            }
        )

    traces = await store.traces_for_request(request.id)

    assert [trace.status for trace in traces] == ["ok", "ok", "ok"]
    assert [trace.outcome for trace in traces] == [
        "value",
        # The reason survives the round trip: which refusal it was is the whole
        # point of separating them.
        "no_value:market_cap_absent",
        "cannot_read",
    ]


@pytest.mark.asyncio
async def test_a_call_with_nothing_to_classify_stores_no_outcome(owner):
    """The default. A web search either failed or returned results, and there is
    no figure of its that could be missing."""
    store = persistence()
    thread = await store.create_thread(owner)
    request = await store.append_message(
        thread.id, role="user", content={"text": "tin tức"}
    )
    await store.record_tool_call(
        {
            "thread_id": thread.id,
            "request_message_id": request.id,
            "tool_name": "web_search",
            "arguments": {"query": "x"},
            "result": {"text": "…", "chars": 1, "dispatched": True},
            "status": "ok",
            "error": None,
            "outcome": None,
        }
    )

    (trace,) = await store.traces_for_request(request.id)

    assert trace.outcome is None


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
