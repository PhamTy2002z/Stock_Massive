"""Flagging a message: the one dispute action v1 ships (#99).

Every claim here is one the obvious implementation gets wrong by being
conventional. A feedback feature normally accumulates rows, opens a ticket,
notifies somebody, and trusts the surface to decide who may press the button.
This one replaces a pair of columns in place, opens nothing, notifies nobody,
and resolves ownership through the Thread on every call.

The persistence half runs against a live database because owner scoping is a
statement about a join, and a fake store would let it pass. The HTTP half runs
against the real application for the same reason.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

from src.agent.persistence import AgentPersistence, UnflaggableMessage
from src.alpha.models import FLAG_REASONS, AgentMessage, AgentThread, AgentTurn
from src.auth.models import RefreshToken, User
from src.core.database import (
    Base,
    engine,
    get_sync_db,
    sync_engine,
    sync_session_factory,
)
from src.main import app

API = "/api/v1"


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


def persistence() -> AgentPersistence:
    return AgentPersistence(session_factory=sync_session_factory)


def _new_user() -> int:
    with get_sync_db() as session:
        user = User(email=f"flags-{uuid.uuid4().hex}@example.com", hashed_password="x")
        session.add(user)
        session.flush()
        return user.id


def _purge_user(user_id: int) -> None:
    with get_sync_db() as session:
        threads = (
            session.execute(select(AgentThread.id).where(AgentThread.user_id == user_id))
            .scalars()
            .all()
        )
        if threads:
            session.execute(delete(AgentTurn).where(AgentTurn.thread_id.in_(threads)))
            session.execute(
                delete(AgentMessage).where(AgentMessage.thread_id.in_(threads))
            )
            session.execute(delete(AgentThread).where(AgentThread.id.in_(threads)))
        session.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
        session.execute(delete(User).where(User.id == user_id))


@pytest.fixture
def owner():
    user_id = _new_user()
    yield user_id
    _purge_user(user_id)


@pytest.fixture
def stranger():
    user_id = _new_user()
    yield user_id
    _purge_user(user_id)


async def _answered_thread(store: AgentPersistence, user_id: int):
    """One question and one answer, which is the smallest flaggable transcript."""
    thread = await store.create_thread(user_id)
    question = await store.append_message(
        thread.id, role="user", content={"text": "VCB thế nào?"}
    )
    answer = await store.append_message(
        thread.id, role="assistant", content={"text": "Một câu trả lời."}
    )
    return thread, question, answer


# -- the write path --------------------------------------------------------


@pytest.mark.asyncio
async def test_flagging_writes_the_pair_and_re_flagging_replaces_it(owner):
    store = persistence()
    _, _, answer = await _answered_thread(store, owner)

    flagged = await store.flag_message(owner, answer.id, reason="wrong_figure")
    assert flagged is not None
    assert flagged.flagged_reason == "wrong_figure"
    assert flagged.flagged_at is not None
    first_stamp = flagged.flagged_at

    # Re-flagging is a correction, not a second opinion. One message carries at
    # most one reason, which is what makes the missing `message_flag` table the
    # right call rather than a shortcut.
    again = await store.flag_message(owner, answer.id, reason="overreach")
    assert again is not None
    assert again.flagged_reason == "overreach"
    assert again.flagged_at >= first_stamp

    with get_sync_db() as session:
        rows = session.execute(
            select(AgentMessage).where(AgentMessage.id == answer.id)
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].flagged_reason == "overreach"


@pytest.mark.asyncio
async def test_unflagging_clears_both_columns(owner):
    store = persistence()
    _, _, answer = await _answered_thread(store, owner)
    await store.flag_message(owner, answer.id, reason="other")

    cleared = await store.unflag_message(owner, answer.id)

    assert cleared is not None
    assert cleared.flagged_reason is None
    # Both, or neither. A stamp left behind would read as a flag with a reason
    # nobody wrote.
    assert cleared.flagged_at is None


@pytest.mark.asyncio
async def test_a_reason_outside_the_vocabulary_is_refused(owner):
    store = persistence()
    _, _, answer = await _answered_thread(store, owner)

    with pytest.raises(ValueError):
        await store.flag_message(owner, answer.id, reason="fraud")

    reread = await store.read_message(owner, answer.id)
    assert reread.flagged_reason is None


@pytest.mark.asyncio
async def test_only_an_assistant_message_can_be_flagged(owner):
    store = persistence()
    _, question, _ = await _answered_thread(store, owner)

    with pytest.raises(UnflaggableMessage):
        await store.flag_message(owner, question.id, reason="wrong_figure")


@pytest.mark.asyncio
async def test_another_users_message_is_not_reachable(owner, stranger):
    store = persistence()
    _, _, answer = await _answered_thread(store, owner)

    # Not "forbidden": a message under somebody else's Thread is a message this
    # caller has no way to name, so it is not found.
    assert await store.flag_message(stranger, answer.id, reason="other") is None
    assert await store.unflag_message(stranger, answer.id) is None
    assert (await store.read_message(owner, answer.id)).flagged_reason is None


@pytest.mark.asyncio
async def test_flagging_a_message_that_does_not_exist_is_not_found(owner):
    store = persistence()
    assert await store.flag_message(owner, 2**40, reason="other") is None


# -- what the flag deliberately does not do --------------------------------


@pytest.mark.asyncio
async def test_flagging_changes_the_pair_and_nothing_else(owner):
    store = persistence()
    thread, question, answer = await _answered_thread(store, owner)

    def snapshot() -> tuple:
        with get_sync_db() as session:
            row = session.execute(
                select(AgentMessage).where(AgentMessage.id == answer.id)
            ).scalar_one()
            turns = session.execute(
                select(func.count()).select_from(AgentTurn).where(
                    AgentTurn.thread_id == thread.id
                )
            ).scalar_one()
            active = session.execute(
                select(User.is_active).where(User.id == owner)
            ).scalar_one()
            return (row.seq, row.role, dict(row.content), row.created_at, turns, active)

    before = snapshot()
    await store.flag_message(owner, answer.id, reason="wrong_figure")
    after = snapshot()

    # The message a flag is about is never rewritten by the flag, no Turn is
    # dispatched to do anything about it, and the account is untouched. There
    # is no workflow here to start (`docs/adr/0016`).
    assert before == after

    # And the question the flagged answer replied to is left alone as well.
    assert (await store.read_message(owner, question.id)).flagged_reason is None


def test_the_flag_path_can_reach_nothing_that_notifies_anybody():
    """A source scan, because the risk is a helpful edit rather than a broken one.

    "Nothing opens a ticket, notifies anyone, or suspends a user" is invisible
    in a behavioural test the moment somebody adds a well-meaning email on the
    write path: the columns would still be right, and the assertion above would
    still pass. So the reachable surface is checked directly.
    """
    from pathlib import Path

    source = Path("src/agent/flag_router.py").read_text(encoding="utf-8")
    for token in (
        "scheduler",
        "add_job",
        "smtp",
        "send_mail",
        "notify",
        "is_active",
        "Ticket",
        "httpx",
        "webhook",
    ):
        assert token not in source, f"the flag path reached {token!r}"


# -- the read path the ops query needs -------------------------------------


@pytest.mark.asyncio
async def test_counts_are_queryable_by_reason_and_by_date_range(owner):
    store = persistence()
    thread = await store.create_thread(owner)
    await store.append_message(thread.id, role="user", content={"text": "hỏi"})
    answers = [
        await store.append_message(
            thread.id, role="assistant", content={"text": f"trả lời {index}"}
        )
        for index in range(3)
    ]

    opened = datetime.now(timezone.utc) - timedelta(seconds=5)
    before = await store.flag_counts()

    await store.flag_message(owner, answers[0].id, reason="wrong_figure")
    await store.flag_message(owner, answers[1].id, reason="wrong_figure")
    await store.flag_message(owner, answers[2].id, reason="overreach")

    # Every reason is a key even at zero: a report that omits a reason nobody
    # chose reads as a reason nobody can choose.
    after = await store.flag_counts()
    assert set(after) == set(FLAG_REASONS)
    assert after["wrong_figure"] - before.get("wrong_figure", 0) == 2
    assert after["overreach"] - before.get("overreach", 0) == 1

    window = await store.flag_counts(since=opened)
    assert window["wrong_figure"] >= 2

    # Half-open, and closed before these flags were written.
    empty = await store.flag_counts(since=opened - timedelta(days=2), until=opened)
    assert empty["wrong_figure"] == 0
    assert empty["overreach"] == 0


# -- the endpoints ---------------------------------------------------------


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    await engine.dispose()


@pytest.fixture
def account():
    email = f"flag-api-{uuid.uuid4().hex[:12]}@example.com"
    yield {"email": email, "password": "sup3r-secret-pw"}
    with get_sync_db() as session:
        user = session.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()
    if user is not None:
        _purge_user(user.id)


async def authenticate(client: AsyncClient, account: dict) -> dict:
    response = await client.post(f"{API}/auth/register", json=account)
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _answered_thread_over_http(client: AsyncClient, headers: dict) -> int:
    """A Thread with one answer in it, written through the store directly.

    The message is written rather than generated: this file is about the flag,
    and driving a whole Turn to produce something to flag would make it a test
    of the agent loop that happens to end in a flag.
    """
    store = persistence()
    me = await client.get(f"{API}/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    _, _, answer = await _answered_thread(store, int(me.json()["id"]))
    return answer.id


@pytest.mark.asyncio
async def test_the_endpoint_flags_replaces_and_clears(client, account):
    headers = await authenticate(client, account)
    message_id = await _answered_thread_over_http(client, headers)

    flagged = await client.post(
        f"{API}/messages/{message_id}/flag",
        json={"reason": "wrong_figure"},
        headers=headers,
    )
    assert flagged.status_code == 200, flagged.text
    assert flagged.json()["flagged_reason"] == "wrong_figure"
    assert flagged.json()["flagged_at"] is not None

    replaced = await client.post(
        f"{API}/messages/{message_id}/flag",
        json={"reason": "wrongly_refused"},
        headers=headers,
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["flagged_reason"] == "wrongly_refused"

    cleared = await client.delete(f"{API}/messages/{message_id}/flag", headers=headers)
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["flagged_reason"] is None
    assert cleared.json()["flagged_at"] is None


@pytest.mark.asyncio
async def test_the_transcript_carries_the_flag_back(client, account):
    headers = await authenticate(client, account)
    message_id = await _answered_thread_over_http(client, headers)
    await client.post(
        f"{API}/messages/{message_id}/flag",
        json={"reason": "overreach"},
        headers=headers,
    )

    threads = await client.get(f"{API}/threads", headers=headers)
    thread_id = threads.json()["threads"][0]["id"]
    detail = await client.get(f"{API}/threads/{thread_id}", headers=headers)

    flagged = [
        message
        for message in detail.json()["messages"]
        if message["id"] == message_id
    ]
    # A reopened Thread has to show what was already flagged, or the action
    # looks unpressed and the user presses it again.
    assert flagged[0]["flagged_reason"] == "overreach"
    assert flagged[0]["flagged_at"] is not None


@pytest.mark.asyncio
async def test_a_reason_outside_the_vocabulary_is_a_request_error(client, account):
    headers = await authenticate(client, account)
    message_id = await _answered_thread_over_http(client, headers)

    response = await client.post(
        f"{API}/messages/{message_id}/flag",
        json={"reason": "fraud"},
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_the_endpoint_refuses_a_message_the_user_wrote(client, account):
    headers = await authenticate(client, account)
    store = persistence()
    me = await client.get(f"{API}/auth/me", headers=headers)
    _, question, _ = await _answered_thread(store, int(me.json()["id"]))

    response = await client.post(
        f"{API}/messages/{question.id}/flag",
        json={"reason": "wrong_figure"},
        headers=headers,
    )

    # Not 404: the message exists and is theirs. It is simply not the kind of
    # message this action is about, and a stable reason says which.
    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "not_an_assistant_message"


@pytest.mark.asyncio
async def test_a_stranger_cannot_flag_this_users_message(client, account):
    headers = await authenticate(client, account)
    message_id = await _answered_thread_over_http(client, headers)
    intruder = {"email": f"intruder-{uuid.uuid4().hex[:12]}@example.com", "password": "sup3r-secret-pw"}
    intruder_headers = await authenticate(client, intruder)

    try:
        response = await client.post(
            f"{API}/messages/{message_id}/flag",
            json={"reason": "other"},
            headers=intruder_headers,
        )
        # Enforced in FastAPI, not in the UI, and answered as 404 rather than
        # 403: a stranger learning that the id exists is already a leak.
        assert response.status_code == 404
    finally:
        with get_sync_db() as session:
            row = session.execute(
                select(User).where(User.email == intruder["email"])
            ).scalar_one_or_none()
        if row is not None:
            _purge_user(row.id)


@pytest.mark.asyncio
async def test_flagging_without_a_session_is_refused(client, account):
    headers = await authenticate(client, account)
    message_id = await _answered_thread_over_http(client, headers)

    response = await client.post(
        f"{API}/messages/{message_id}/flag", json={"reason": "other"}
    )

    assert response.status_code == 401
