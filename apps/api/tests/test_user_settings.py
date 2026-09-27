"""The reader's own account settings: profile, password, sessions, notes, history.

Runs against a throwaway Postgres database beside whatever ``DATABASE_URL``
points at, with the application's ``get_db`` pointed at it. Every claim here is
about who a statement reaches — this user's rows and nobody else's — and that
is a property of SQL against a real schema, not of a fake store.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from src.agent.registry import ToolContext
from src.agent.router import desk
from src.agent.tools.memory import CONVERSATION_SOURCE, MEMORY_DISABLED, MemoryTools
from src.alpha.models import AgentKnowledge, AgentMessage, AgentThread
from src.auth.models import RefreshToken, User
from src.auth.schemas import UserPreferences
from src.core.database import Base, get_db, to_asyncpg_url
from src.main import app

from .throwaway_db import create_database, drop_database

SETTINGS_DB = "stockmassive_settings_test"
API = "/api/v1"
PASSWORD = "sup3r-secret-pw"


class _EnabledDesk:
    """The one thing the thread routes ask of the desk before deleting."""

    def assert_enabled(self) -> None:
        return None


@pytest.fixture(scope="module")
def world():
    # Dropped first so a database left behind by an interrupted run cannot hand
    # this module a schema older than the models.
    drop_database(SETTINGS_DB)
    url = create_database(SETTINGS_DB)
    sync_engine = create_engine(url, future=True)
    Base.metadata.create_all(sync_engine)
    # NullPool: each request's connection is opened on the running test's event
    # loop and closed with it, so no pooled connection outlives its loop.
    async_engine = create_async_engine(to_asyncpg_url(url), poolclass=NullPool)
    async_factory = async_sessionmaker(async_engine, expire_on_commit=False)

    async def override_db():
        async with async_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[desk] = _EnabledDesk
    yield sessionmaker(bind=sync_engine, expire_on_commit=False, future=True)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(desk, None)
    sync_engine.dispose()
    drop_database(SETTINGS_DB)


@pytest_asyncio.fixture
async def client(world):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


async def _signed_up(client) -> dict:
    email = f"settings-{uuid.uuid4().hex[:12]}@example.com"
    response = await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Phạm Tý"},
    )
    assert response.status_code == 201, response.text
    tokens = response.json()
    me = await client.get(f"{API}/auth/me", headers=_bearer(tokens))
    return {**tokens, "id": me.json()["id"], "email": email}


def _bearer(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _refreshes(client, refresh_token: str) -> bool:
    response = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": refresh_token}
    )
    return response.status_code == 200


# -- profile and preferences ------------------------------------------------


@pytest.mark.asyncio
async def test_a_new_account_reads_default_preferences(client):
    account = await _signed_up(client)
    body = (await client.get(f"{API}/auth/me", headers=_bearer(account))).json()
    assert body["preferences"] == {
        "nickname": None,
        "investing_style": None,
        "custom_instructions": None,
        "memory_enabled": True,
    }


@pytest.mark.asyncio
async def test_patch_writes_only_the_keys_that_were_sent(client):
    account = await _signed_up(client)
    headers = _bearer(account)
    first = await client.patch(
        f"{API}/auth/me",
        headers=headers,
        json={
            "full_name": "  Phạm Văn Tý  ",
            "preferences": {
                "nickname": "  Ty ",
                "investing_style": "dividend",
                "custom_instructions": "Ngắn gọn.",
            },
        },
    )
    assert first.status_code == 200, first.text
    assert first.json()["full_name"] == "Phạm Văn Tý"

    # A second patch touching one key leaves the others and the name alone.
    second = await client.patch(
        f"{API}/auth/me", headers=headers, json={"preferences": {"memory_enabled": False}}
    )
    assert second.json()["full_name"] == "Phạm Văn Tý"
    assert second.json()["preferences"] == {
        "nickname": "Ty",
        "investing_style": "dividend",
        "custom_instructions": "Ngắn gọn.",
        "memory_enabled": False,
    }

    # Explicit null clears; an empty string is stored as null; a null switch is
    # the same as leaving it out.
    third = await client.patch(
        f"{API}/auth/me",
        headers=headers,
        json={
            "preferences": {
                "investing_style": None,
                "custom_instructions": "   ",
                "memory_enabled": None,
            }
        },
    )
    assert third.json()["preferences"] == {
        "nickname": "Ty",
        "investing_style": None,
        "custom_instructions": None,
        "memory_enabled": False,
    }
    reread = await client.get(f"{API}/auth/me", headers=headers)
    assert reread.json()["preferences"] == third.json()["preferences"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    (
        {"full_name": ""},
        {"full_name": "   "},
        {"full_name": "x" * 256},
        {"email": "other@example.com"},
        {"preferences": {"nickname": "x" * 65}},
        {"preferences": {"custom_instructions": "x" * 1501}},
        {"preferences": {"investing_style": "yolo"}},
        {"preferences": {"theme": "dark"}},
    ),
)
async def test_patch_refuses_what_the_contract_does_not_allow(client, body):
    account = await _signed_up(client)
    response = await client.patch(f"{API}/auth/me", headers=_bearer(account), json=body)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_a_stored_document_with_stale_keys_still_reads(client, world):
    account = await _signed_up(client)
    with world() as session:
        session.get(User, account["id"]).preferences = {
            "nickname": "Ty",
            "investing_style": "retired_code",
            "theme": "dark",
        }
        session.commit()
    body = (await client.get(f"{API}/auth/me", headers=_bearer(account))).json()
    assert body["preferences"] == {
        "nickname": "Ty",
        "investing_style": None,
        "custom_instructions": None,
        "memory_enabled": True,
    }


def test_the_lenient_reader_survives_anything_stored():
    assert UserPreferences.from_stored(None) == UserPreferences()
    assert UserPreferences.from_stored(["not", "a", "mapping"]) == UserPreferences()
    assert UserPreferences.from_stored({"nickname": "x" * 500}).nickname is None


# -- password and sessions --------------------------------------------------


@pytest.mark.asyncio
async def test_a_wrong_current_password_is_400_not_401(client):
    account = await _signed_up(client)
    response = await client.post(
        f"{API}/auth/password",
        headers=_bearer(account),
        json={"current_password": "not-the-password", "new_password": "an0ther-secret"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Current password is incorrect"
    assert await _refreshes(client, account["refresh_token"])


@pytest.mark.asyncio
async def test_the_new_password_must_differ_and_be_long_enough(client):
    account = await _signed_up(client)
    for new_password in (PASSWORD, "short"):
        response = await client.post(
            f"{API}/auth/password",
            headers=_bearer(account),
            json={"current_password": PASSWORD, "new_password": new_password},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_a_password_change_ends_every_other_session_and_keeps_this_one(client):
    account = await _signed_up(client)
    other_browser = (
        await client.post(
            f"{API}/auth/login", json={"email": account["email"], "password": PASSWORD}
        )
    ).json()

    response = await client.post(
        f"{API}/auth/password",
        headers=_bearer(account),
        json={"current_password": PASSWORD, "new_password": "an0ther-secret"},
    )
    assert response.status_code == 200, response.text
    fresh = response.json()
    assert fresh["access_token"] and fresh["refresh_token"]

    # The fresh token first: presenting a revoked one trips reuse detection,
    # which revokes everything this user has, the fresh token included.
    assert await _refreshes(client, fresh["refresh_token"])
    assert not await _refreshes(client, account["refresh_token"])
    assert not await _refreshes(client, other_browser["refresh_token"])

    old_login = await client.post(
        f"{API}/auth/login", json={"email": account["email"], "password": PASSWORD}
    )
    new_login = await client.post(
        f"{API}/auth/login", json={"email": account["email"], "password": "an0ther-secret"}
    )
    assert old_login.status_code == 401
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_logout_all_revokes_every_refresh_token_of_this_user_only(client, world):
    account = await _signed_up(client)
    second = (
        await client.post(
            f"{API}/auth/login", json={"email": account["email"], "password": PASSWORD}
        )
    ).json()
    bystander = await _signed_up(client)

    response = await client.post(f"{API}/auth/logout-all", headers=_bearer(account))
    assert response.status_code == 204

    assert not await _refreshes(client, account["refresh_token"])
    assert not await _refreshes(client, second["refresh_token"])
    assert await _refreshes(client, bystander["refresh_token"])
    with world() as session:
        live = session.scalar(
            select(func.count())
            .select_from(RefreshToken)
            .where(RefreshToken.user_id == account["id"], RefreshToken.revoked_at.is_(None))
        )
    assert live == 0


@pytest.mark.asyncio
async def test_the_settings_routes_need_a_session(client):
    assert (await client.patch(f"{API}/auth/me", json={})).status_code == 401
    assert (await client.post(f"{API}/auth/logout-all")).status_code == 401
    assert (await client.get(f"{API}/memory/facts")).status_code == 401
    assert (await client.delete(f"{API}/threads")).status_code == 401


# -- notes -------------------------------------------------------------------


def _note(world, user_id: int, title: str, *, source_url: str = CONVERSATION_SOURCE) -> int:
    with world() as session:
        row = AgentKnowledge(
            user_id=user_id,
            title=title,
            body=f"body of {title}",
            source_url=source_url,
            source_name="conversation",
            retrieved_at=datetime.now(timezone.utc),
        )
        session.add(row)
        session.commit()
        return row.id


@pytest.mark.asyncio
async def test_the_notes_list_is_this_users_newest_first(client, world):
    account = await _signed_up(client)
    stranger = await _signed_up(client)
    first = _note(world, account["id"], "first")
    second = _note(world, account["id"], "second", source_url="https://example.com/a")
    _note(world, stranger["id"], "not yours")

    body = (await client.get(f"{API}/memory/facts", headers=_bearer(account))).json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [second, first]
    assert set(body["items"][0]) == {
        "id", "title", "body", "symbol", "source_url", "source_name", "as_of", "created_at",
    }
    assert body["items"][0]["source_url"] == "https://example.com/a"
    # The conversation placeholder is not a page anybody could open.
    assert body["items"][1]["source_url"] is None

    page = await client.get(
        f"{API}/memory/facts", headers=_bearer(account), params={"limit": 1, "offset": 1}
    )
    assert page.json() == {"items": [body["items"][1]], "total": 2}
    for bad in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
        refused = await client.get(f"{API}/memory/facts", headers=_bearer(account), params=bad)
        assert refused.status_code == 422


@pytest.mark.asyncio
async def test_another_users_note_is_not_found_and_survives(client, world):
    account = await _signed_up(client)
    stranger = await _signed_up(client)
    theirs = _note(world, stranger["id"], "theirs")
    mine = _note(world, account["id"], "mine")

    assert (
        await client.delete(f"{API}/memory/facts/{theirs}", headers=_bearer(account))
    ).status_code == 404
    assert (
        await client.delete(f"{API}/memory/facts/999999999", headers=_bearer(account))
    ).status_code == 404
    # Past the BIGINT range: refused at the edge rather than overflowing the driver.
    assert (
        await client.delete(f"{API}/memory/facts/{2**63}", headers=_bearer(account))
    ).status_code == 422
    assert (
        await client.delete(f"{API}/memory/facts/{mine}", headers=_bearer(account))
    ).status_code == 204
    with world() as session:
        assert session.get(AgentKnowledge, theirs) is not None
        assert session.get(AgentKnowledge, mine) is None


@pytest.mark.asyncio
async def test_forgetting_everything_reaches_only_this_users_notes(client, world):
    account = await _signed_up(client)
    stranger = await _signed_up(client)
    _note(world, account["id"], "a")
    _note(world, account["id"], "b")
    theirs = _note(world, stranger["id"], "theirs")

    response = await client.delete(f"{API}/memory/facts", headers=_bearer(account))
    assert response.status_code == 200
    assert response.json() == {"deleted": 2}
    again = await client.delete(f"{API}/memory/facts", headers=_bearer(account))
    assert again.json() == {"deleted": 0}
    with world() as session:
        assert session.get(AgentKnowledge, theirs) is not None


# -- history -----------------------------------------------------------------


def _thread(world, user_id: int) -> uuid.UUID:
    with world() as session:
        thread = AgentThread(id=uuid.uuid4(), user_id=user_id, title="t")
        session.add(thread)
        session.flush()
        session.add(
            AgentMessage(thread_id=thread.id, seq=1, role="user", content={"text": "hi"})
        )
        session.commit()
        return thread.id


@pytest.mark.asyncio
async def test_deleting_all_threads_cascades_and_spares_other_users(client, world):
    account = await _signed_up(client)
    stranger = await _signed_up(client)
    mine = [_thread(world, account["id"]) for _ in range(3)]
    theirs = _thread(world, stranger["id"])

    response = await client.delete(f"{API}/threads", headers=_bearer(account))
    assert response.status_code == 200
    assert response.json() == {"deleted": 3}
    with world() as session:
        assert session.scalar(
            select(func.count()).select_from(AgentMessage).where(AgentMessage.thread_id.in_(mine))
        ) == 0
        assert session.get(AgentThread, theirs) is not None
        assert session.scalar(
            select(func.count()).select_from(AgentThread).where(
                AgentThread.user_id == account["id"]
            )
        ) == 0


# -- the memory switch -------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_switched_off_refuses_both_note_tools_without_writing(world):
    with world() as session:
        user = User(
            email=f"off-{uuid.uuid4().hex}@example.com",
            hashed_password="x",
            preferences={"memory_enabled": False},
        )
        session.add(user)
        session.commit()
        user_id = user.id
    tools = MemoryTools(session_factory=world)
    context = ToolContext(user_id=user_id)

    remembered = await tools.remember_fact(context, {"title": "t", "body": "b"})
    recalled = await tools.recall_facts(context, {"query": "t"})

    assert remembered["remembered"] is False
    assert remembered["reason"] == MEMORY_DISABLED
    assert recalled["facts"] == [] and recalled["reason"] == MEMORY_DISABLED
    with world() as session:
        assert session.scalar(
            select(func.count()).select_from(AgentKnowledge).where(
                AgentKnowledge.user_id == user_id
            )
        ) == 0


@pytest.mark.asyncio
async def test_memory_left_on_keeps_working(world):
    with world() as session:
        user = User(email=f"on-{uuid.uuid4().hex}@example.com", hashed_password="x")
        session.add(user)
        session.commit()
        user_id = user.id
    tools = MemoryTools(session_factory=world)
    context = ToolContext(user_id=user_id)

    remembered = await tools.remember_fact(context, {"title": "Kỳ hạn", "body": "Dài hạn."})
    recalled = await tools.recall_facts(context, {"query": "ky han"})

    assert remembered["remembered"] is True
    assert recalled["count"] == 1
