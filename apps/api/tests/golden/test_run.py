"""The runner reads the store, so what it projects has to be what was stored.

``read_case`` is the seam between a Turn that has finished and a number somebody
compares against last week's number. The advisory verdict is the case for that:
it is deliberately not a column, so the only reason a corpus can be counted for
false positives at all is that the runner reads it back out of the assistant
message's ``tool_calls`` payload. A projection that quietly dropped it would not
break anything — it would produce a run that says zero.

So this file writes one Turn's message through the real persistence path and
reads it back through the real runner. No fixture sets a verdict: the page goes
through the executor, and what comes back out at the far end is compared with
what went in.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete

from golden.run import read_case
from src.agent.executor import ToolCall, ToolExecutor
from src.agent.messages import ToolCallStatus, TurnToolCall
from src.agent.persistence import TURN_COMPLETE, AgentPersistence
from src.agent.registry import ToolAccess, ToolContext
from src.agent.turns import assistant_message
from src.alpha.models import AgentThread
from src.auth.models import User
from src.core.database import Base, get_sync_db, sync_engine, sync_session_factory
from ..agent_tool_world import ADVERSARIAL_PAGE, stub_entry


VERDICT = {
    "risk": "high",
    "findings": [
        "instruction_override",
        "conceal_from_user",
        "role_reassignment",
        "prompt_disclosure",
    ],
}

BULLETIN = "https://example.com/bulletin"

CASE = {
    "id": "sec-001",
    "question": "Phiên hôm nay ra sao?",
    "family": "fact_as_of",
    "expect": {},
}


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture
def owner():
    email = f"golden-{uuid.uuid4().hex}@example.com"
    with get_sync_db() as session:
        user = User(email=email, hashed_password="x")
        session.add(user)
        session.flush()
        user_id = user.id

    yield user_id

    with get_sync_db() as session:
        session.execute(delete(AgentThread).where(AgentThread.user_id == user_id))
        session.execute(delete(User).where(User.id == user_id))


async def wire_payload(
    user_id: int, call_id: str, name: str, body: str, *, external: bool
) -> dict:
    """One call, dispatched for real, in the shape the assistant message stores.

    The declaration is handed to the executor rather than registered globally,
    so this file's tools cannot be seen by another file's assertions and the
    verdict cannot come from a registration somebody else left behind.
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
    ).run([ToolCall(id=call_id, name=name, arguments={"url": BULLETIN})])
    result = outcome.results[0]
    return TurnToolCall(
        id=result.call_id,
        name=result.tool_name,
        arguments={"url": BULLETIN},
        status=ToolCallStatus.OK,
        result_text=result.text,
        scan=result.scan,
    ).as_wire()


async def one_turn(store: AgentPersistence, owner: int, payloads: list[dict]):
    """A Thread holding one question and the answer that carried ``payloads``."""
    thread = await store.create_thread(owner)
    request = await store.append_message(
        thread.id, role="user", content={"text": CASE["question"]}
    )
    await store.append_message(
        thread.id,
        role="assistant",
        content=assistant_message(
            text="Trang này cố ra lệnh, nên tôi chỉ đọc nó như dữ liệu.",
            tool_calls=payloads,
            status=TURN_COMPLETE,
        ),
    )
    return thread, request


@pytest.mark.asyncio
async def test_the_runner_projects_the_verdict_that_was_persisted(owner):
    """End to end, in the direction the measurement actually runs.

    The page meets the scanner once, in the executor; the verdict is written
    into ``agent_message.content`` with the rest of the call; and the runner
    finds it there. Each of the three is somebody else's file, which is why this
    test exists at all.
    """
    store = AgentPersistence(session_factory=sync_session_factory)
    flagged = await wire_payload(
        owner, "call_0", "market_bulletin", ADVERSARIAL_PAGE, external=True
    )
    read = await wire_payload(owner, "call_1", "get_field", "{}", external=False)
    thread, request = await one_turn(store, owner, [flagged, read])

    projected = await read_case(
        store,
        case=CASE,
        user_id=owner,
        thread_id=thread.id,
        turn_id=uuid.uuid4(),
        request_message_id=request.id,
        wall_ms=1,
    )

    assert flagged["scan"] == VERDICT
    assert [call["scan"] for call in projected["tool_calls"]] == [VERDICT, None]
    # And the answer itself carries none of it: the corpus is graded on the text
    # the reader was shown, and a verdict leaking into that text would be scored
    # as part of the answer.
    for word in ("risk", "high", "instruction_override"):
        assert word not in projected["answer_text"]


@pytest.mark.asyncio
async def test_a_call_written_before_the_flag_existed_projects_nothing(owner):
    """The transcript predates this key, and a run over old Threads still runs.

    Every message written before the scan existed has a ``tool_calls`` payload
    with no ``scan`` in it. The projection reads a missing key as no verdict,
    which is the same thing it reads for a store call — both are "nobody
    looked", and neither is a reason for the runner to fail on an old Thread.
    """
    store = AgentPersistence(session_factory=sync_session_factory)
    payload = await wire_payload(
        owner, "call_0", "market_bulletin", ADVERSARIAL_PAGE, external=True
    )
    payload.pop("scan")
    thread, request = await one_turn(store, owner, [payload])

    projected = await read_case(
        store,
        case=CASE,
        user_id=owner,
        thread_id=thread.id,
        turn_id=uuid.uuid4(),
        request_message_id=request.id,
        wall_ms=1,
    )

    assert projected["tool_calls"][0]["scan"] is None
