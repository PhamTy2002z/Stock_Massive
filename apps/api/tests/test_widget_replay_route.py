"""Reading a Widget's fixed slice back through the message that stores it (#89).

The route's shape is its security property: a caller names a message and a
descriptor id, never a descriptor. This file is about what that rules out.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from src.agent.persistence import AgentPersistence
from src.alpha.models import AgentThread
from src.alpha.widget_router import get_resolver, get_store
from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.core.database import Base, get_sync_db, sync_engine, sync_session_factory
from src.main import app

DESCRIPTOR = {
    "kind": "cross_symbol",
    "field": "momentum_rank.percentile_12_2",
    "symbols": ["FPT"],
    "as_of": "2026-08-14",
}
DESCRIPTOR_ID = "slice-of-2026-08-14"


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture
def users():
    made: list[int] = []
    with get_sync_db() as session:
        for _ in range(2):
            user = User(email=f"widget-{uuid.uuid4().hex}@example.com", hashed_password="x")
            session.add(user)
            session.flush()
            made.append(user.id)

    yield made

    with get_sync_db() as session:
        for user_id in made:
            session.execute(delete(AgentThread).where(AgentThread.user_id == user_id))
            session.execute(delete(User).where(User.id == user_id))


class _Resolver:
    """Stands in for the store, and records the descriptor it was handed."""

    def __init__(self) -> None:
        self.seen: list[dict] = []

    async def resolve(self, descriptor):
        self.seen.append(dict(descriptor))
        return {"kind": descriptor.get("kind"), "as_of": descriptor.get("as_of"), "available": True}


@pytest.fixture
def api(users):
    store = AgentPersistence(session_factory=sync_session_factory)
    resolver = _Resolver()
    with get_sync_db() as session:
        owner = session.get(User, users[0])
        stranger = session.get(User, users[1])
        session.expunge(owner)
        session.expunge(stranger)

    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_resolver] = lambda: resolver
    app.dependency_overrides[get_current_user] = lambda: owner
    yield TestClient(app), store, resolver, stranger
    app.dependency_overrides.clear()


async def _message_with_widget(store: AgentPersistence, user_id: int) -> int:
    thread = await store.create_thread(user_id, title="Widgets")
    message = await store.append_message(
        thread.id,
        role="assistant",
        content={
            "text": "FPT dẫn đầu.",
            "widgets": [
                {
                    "name": "metric_comparison",
                    "version": 1,
                    "descriptor_id": DESCRIPTOR_ID,
                    "descriptor": DESCRIPTOR,
                }
            ],
        },
    )
    return message.id


@pytest.mark.asyncio
async def test_the_slice_resolved_is_the_one_the_message_stored(api, users):
    client, store, resolver, _stranger = api
    message_id = await _message_with_widget(store, users[0])

    response = client.get(f"/api/v1/widgets/{message_id}/{DESCRIPTOR_ID}")

    assert response.status_code == 200
    assert response.json()["as_of"] == "2026-08-14"
    # The descriptor came off the message. There is no request parameter through
    # which a different day could have been asked for.
    assert resolver.seen == [DESCRIPTOR]


@pytest.mark.asyncio
async def test_another_users_message_is_not_found_rather_than_forbidden(api, users):
    client, store, resolver, stranger = api
    message_id = await _message_with_widget(store, users[1])

    response = client.get(f"/api/v1/widgets/{message_id}/{DESCRIPTOR_ID}")

    assert response.status_code == 404
    assert resolver.seen == []
    assert stranger.id == users[1]


@pytest.mark.asyncio
async def test_a_descriptor_id_that_is_not_on_the_message_resolves_nothing(api, users):
    client, store, resolver, _stranger = api
    message_id = await _message_with_widget(store, users[0])

    response = client.get(f"/api/v1/widgets/{message_id}/some-other-slice")

    assert response.status_code == 404
    assert resolver.seen == []
