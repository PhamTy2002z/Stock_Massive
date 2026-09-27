"""The settings page's routes: the owner's rows only, and never a secret."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.auth.dependencies import get_current_user
from src.connectors.service import set_connectors
from src.main import app

from .connector_world import connector_world

DB = "stockmassive_connectors_router_test"


@pytest.fixture(scope="module")
def world():
    with connector_world(DB) as built:
        yield built


@pytest.fixture
def as_user(world):
    previous = set_connectors(world.service())
    current = {"id": world.alice}
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=current["id"], is_active=True)
    try:
        yield current
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        set_connectors(previous)


def test_add_list_edit_and_remove_without_ever_returning_the_key(world, as_user):
    client = TestClient(app)
    secret = "Bearer s3cret"
    added = client.post(
        "/api/v1/connectors",
        json={"name": "Sổ tay", "url": world.server.url, "header_value": secret},
    )
    assert added.status_code == 201, added.text
    body = added.json()
    connector_id = body["id"]
    assert body["status"] == "connected"
    tools = {tool["name"]: tool for tool in body["tools"]}
    assert tools["save_note"]["allowed_actions"] == ["ask", "deny"]
    assert tools["get_revenue"]["read_only_claimed_by_server"] is True

    listing = client.get("/api/v1/connectors")
    assert listing.status_code == 200
    assert listing.json()["custom_url_allowed"] is True
    assert "s3cret" not in json.dumps(listing.json())

    refused = client.put(f"/api/v1/connectors/{connector_id}/tools/save_note", json={"action": "allow"})
    assert refused.status_code == 422 and refused.json()["detail"]["reason"] == "write_needs_approval"
    allowed = client.put(f"/api/v1/connectors/{connector_id}/tools/get_revenue", json={"action": "allow"})
    assert allowed.status_code == 200
    assert next(t for t in allowed.json()["tools"] if t["name"] == "get_revenue")["action"] == "allow"

    assert client.patch(f"/api/v1/connectors/{connector_id}", json={"enabled": False}).json()["enabled"] is False
    assert client.put("/api/v1/connectors/preferences", json={"tool_access": "preloaded"}).json() == {"tool_access": "preloaded"}

    as_user["id"] = world.bob
    assert client.get(f"/api/v1/connectors/{connector_id}").status_code == 404
    assert client.delete(f"/api/v1/connectors/{connector_id}").status_code == 404
    assert client.get("/api/v1/connectors").json()["connectors"] == []

    as_user["id"] = world.alice
    assert client.delete(f"/api/v1/connectors/{connector_id}").status_code == 204
    assert client.get(f"/api/v1/connectors/{connector_id}").status_code == 404


def test_a_custom_url_is_refused_for_an_account_off_the_allowlist(world, as_user):
    set_connectors(world.service(connectors_custom_url_users=str(world.bob)))
    answer = TestClient(app).post("/api/v1/connectors", json={"name": "X", "url": world.server.url})
    assert answer.status_code == 403
    assert answer.json()["detail"]["reason"] == "custom_url_not_allowed"


def test_connectors_off_answers_an_empty_page(world, as_user):
    set_connectors(world.service(connectors_enabled=False))
    body = TestClient(app).get("/api/v1/connectors").json()
    assert body["enabled"] is False and body["connectors"] == []


def test_an_approval_answer_for_nothing_waiting_is_404(world, as_user):
    answer = TestClient(app).post(
        f"/api/v1/turns/{uuid.uuid4()}/approvals/call_1", json={"decision": "allow_once"}
    )
    assert answer.status_code == 404
    bad = TestClient(app).post(f"/api/v1/turns/{uuid.uuid4()}/approvals/call_1", json={"decision": "yes"})
    assert bad.status_code == 422


def test_the_turn_body_declares_what_the_client_can_draw():
    from pydantic import ValidationError

    from src.agent.schemas import CreateTurnRequest

    body = CreateTurnRequest(turn_id=uuid.uuid4(), text="x", client_capabilities=["approvals"])
    assert body.client_capabilities == ["approvals"]
    assert CreateTurnRequest(turn_id=uuid.uuid4(), text="x").client_capabilities == []
    with pytest.raises(ValidationError):
        CreateTurnRequest(turn_id=uuid.uuid4(), text="x", client_capabilities=["everything"])


def test_a_reconnecting_reader_is_shown_the_card_still_waiting():
    from src.agent.events import TurnPublisher

    publisher = TurnPublisher(uuid.uuid4())
    publisher.approval_requested({"call_id": "a", "connector": "Sổ tay", "tool": "t", "secret": "x"})
    publisher.approval_requested({"call_id": "b", "connector": "Sổ tay", "tool": "u"})
    publisher.approval_resolved("a", "deny")
    snapshot = publisher.subscribe().snapshot.data
    assert [card["call_id"] for card in snapshot["approvals"]] == ["b"]
    assert "secret" not in snapshot["approvals"][0]
