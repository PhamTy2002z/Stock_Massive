"""OAuth 2.1 + PKCE against a real authorization server: connect, refresh (once,
however many Turns ask), disconnect."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import text

from src.connectors import crypto, oauth
from src.connectors.models import UserConnector
from src.connectors.service import ConnectorRefused

from .connector_world import connector_world
from .fake_mcp import FakeMCP

DB = "stockmassive_connectors_oauth_test"


@pytest.fixture(scope="module")
def world():
    with connector_world(DB) as built:
        built.oauth_server = FakeMCP(oauth=True).start()
        yield built
        built.oauth_server.stop()


def _browser(authorize_url: str) -> tuple[str, str]:
    """What the user's browser does: sign in, get sent back with a code."""
    answer = httpx.get(authorize_url, follow_redirects=False)
    assert answer.status_code == 302
    back = parse_qs(urlsplit(answer.headers["location"]).query)
    return back["state"][0], back["code"][0]


async def _connect(world, service):
    row = await service.add_custom(world.alice, name="Drive", url=world.oauth_server.url, oauth=True)
    assert row.status == "needs_auth" and row.tools == []
    authorize = await oauth.start(service, world.alice, row.id)
    query = parse_qs(urlsplit(authorize).query)
    assert query["code_challenge_method"] == ["S256"]
    assert query["resource"] == [world.oauth_server.url]
    state, code = _browser(authorize)
    outcome = await oauth.finish(service, state=state, code=code, error=None)
    assert outcome.ok, outcome.reason
    return row.id


async def _expire(service, connector_id):
    async with service.session() as session, session.begin():
        row = await session.get(UserConnector, connector_id)
        secret = crypto.decrypt(row.credentials, keys=service.settings.connectors_encryption_keys)
        secret["tokens"]["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        row.credentials = crypto.encrypt(secret, keys=service.settings.connectors_encryption_keys)


@pytest.mark.asyncio
async def test_connect_with_pkce_then_refresh_once_then_disconnect(world):
    service = world.service()
    connector_id = await _connect(world, service)
    row, _ = await service.get(world.alice, connector_id)
    assert row.status == "connected"
    assert {tool["name"] for tool in row.tools} >= {"get_revenue"}
    first = (await service.target(world.alice, connector_id)).headers["Authorization"]

    await _expire(service, connector_id)
    before = world.oauth_server.refresh_requests
    world.oauth_server.token_delay = 0.3
    try:
        # Two Turns start together; the row lock makes the second wait and then
        # find the token the first one already refreshed.
        targets = await asyncio.gather(
            service.target(world.alice, connector_id),
            world.service().target(world.alice, connector_id),
        )
    finally:
        world.oauth_server.token_delay = 0.0
    assert world.oauth_server.refresh_requests - before == 1
    fresh = {target.headers["Authorization"] for target in targets}
    assert len(fresh) == 1 and first not in fresh
    # And the refreshed token works.
    refreshed = await service.refresh(world.alice, connector_id)
    assert refreshed.status == "connected"

    await service.delete(world.alice, connector_id)
    with world.sync_session() as session:
        assert session.execute(text("SELECT count(*) FROM user_connector WHERE id = :id"), {"id": connector_id}).scalar() == 0
        assert session.execute(text("SELECT count(*) FROM connector_oauth_state WHERE connector_id = :id"), {"id": connector_id}).scalar() == 0


@pytest.mark.asyncio
async def test_a_state_is_spent_once(world):
    service = world.service()
    row = await service.add_custom(world.alice, name="Drive 2", url=world.oauth_server.url, oauth=True)
    state, code = _browser(await oauth.start(service, world.alice, row.id))
    assert (await oauth.finish(service, state=state, code=code, error=None)).ok
    replay = await oauth.finish(service, state=state, code=code, error=None)
    assert not replay.ok and replay.reason == "invalid_state"
    await service.delete(world.alice, row.id)


@pytest.mark.asyncio
async def test_a_wrong_verifier_is_refused_by_the_provider(world):
    service = world.service()
    row = await service.add_custom(world.alice, name="Drive 3", url=world.oauth_server.url, oauth=True)
    authorize = await oauth.start(service, world.alice, row.id)
    state, code = _browser(authorize)
    # A second start replaces nothing about the first code's challenge, so an
    # attacker who injects their own code into this state fails the exchange.
    world.oauth_server.codes[code]["challenge"] = "not-the-challenge"
    outcome = await oauth.finish(service, state=state, code=code, error=None)
    assert not outcome.ok
    row, _ = await service.get(world.alice, row.id)
    assert row.status == "needs_auth"
    await service.delete(world.alice, row.id)


@pytest.mark.asyncio
async def test_a_denied_sign_in_and_a_refused_refresh_leave_the_connector_signed_out(world):
    service = world.service()
    row = await service.add_custom(world.alice, name="Drive 4", url=world.oauth_server.url, oauth=True)
    state, _ = _browser(await oauth.start(service, world.alice, row.id))
    denied = await oauth.finish(service, state=state, code=None, error="access_denied")
    assert not denied.ok and denied.reason == "provider_denied"

    connector_id = await _connect(world, service)
    await _expire(service, connector_id)
    world.oauth_server.refresh_tokens.clear()  # the provider revoked it
    await service.target(world.alice, connector_id)
    row, _ = await service.get(world.alice, connector_id)
    assert row.status == "needs_auth" and row.last_error == "refresh_failed"
    await service.delete(world.alice, connector_id)
    await service.delete(world.alice, (await service.get(world.alice, denied.connector_id))[0].id)


@pytest.mark.asyncio
async def test_oauth_start_is_refused_for_a_key_connector(world):
    service = world.service()
    row = await service.add_custom(world.alice, name="Khoá", url=world.server.url, header_value="Bearer s3cret")
    with pytest.raises(ConnectorRefused):
        await oauth.start(service, world.alice, row.id)
    await service.delete(world.alice, row.id)


def test_the_return_url_says_what_happened():
    settings = type("S", (), {"connectors_web_return_url": "http://localhost:3000/"})()
    url = oauth.return_url(settings, oauth.Outcome(None, False, "invalid_state"))
    assert "connector_status=failed" in url and "connector_reason=invalid_state" in url
