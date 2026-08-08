"""Integration tests for the auth endpoints against a live database.

Requires DATABASE_URL to point at a database migrated to head
(`docker compose up -d db && alembic upgrade head`).

These drive the app through an ASGI transport rather than TestClient: the async
engine's pool binds to whichever event loop first used it, and TestClient opens
a fresh loop per request, which strands pooled connections after the first call.
"""
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from src.auth.models import RefreshToken, User
from src.core.database import engine, get_sync_db
from src.main import app

API = "/api/v1/auth"


def _unique_email() -> str:
    return f"test-{uuid.uuid4().hex[:12]}@example.com"


@pytest_asyncio.fixture
async def client():
    """ASGI client sharing the test's event loop.

    Disposing the engine afterwards drops connections bound to this loop, so the
    next test does not inherit a pool pointing at a closed one.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    await engine.dispose()


@pytest.fixture
def account():
    """An email/password pair, with any rows it creates deleted afterwards."""
    email = _unique_email()
    yield {"email": email, "password": "sup3r-secret-pw"}

    with get_sync_db() as session:
        user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is not None:
            session.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
            session.execute(delete(User).where(User.id == user.id))


async def _register(client, account) -> dict:
    response = await client.post(f"{API}/register", json=account)
    assert response.status_code == 201, response.text
    return response.json()


class TestRegister:
    """POST /auth/register."""

    @pytest.mark.asyncio
    async def test_returns_token_pair(self, client, account):
        body = await _register(client, account)
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0

    @pytest.mark.asyncio
    async def test_duplicate_email_conflicts(self, client, account):
        await _register(client, account)
        response = await client.post(f"{API}/register", json=account)
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_email_is_case_insensitive(self, client, account):
        """Signing up again with different casing must not create a second account."""
        await _register(client, account)
        shouty = {**account, "email": account["email"].upper()}
        response = await client.post(f"{API}/register", json=shouty)
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_rejects_short_password(self, client):
        response = await client.post(
            f"{API}/register", json={"email": _unique_email(), "password": "short"}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_rejects_malformed_email(self, client):
        response = await client.post(
            f"{API}/register", json={"email": "not-an-email", "password": "sup3r-secret-pw"}
        )
        assert response.status_code == 422


class TestLogin:
    """POST /auth/login."""

    @pytest.mark.asyncio
    async def test_correct_credentials_return_tokens(self, client, account):
        await _register(client, account)
        response = await client.post(f"{API}/login", json=account)
        assert response.status_code == 200
        assert response.json()["access_token"]

    @pytest.mark.asyncio
    async def test_wrong_password_is_401(self, client, account):
        await _register(client, account)
        response = await client.post(
            f"{API}/login", json={**account, "password": "definitely-wrong"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unknown_email_is_401(self, client):
        response = await client.post(
            f"{API}/login", json={"email": _unique_email(), "password": "sup3r-secret-pw"}
        )
        assert response.status_code == 401


class TestMe:
    """GET /auth/me."""

    @pytest.mark.asyncio
    async def test_returns_current_user(self, client, account):
        tokens = await _register(client, account)
        response = await client.get(
            f"{API}/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )
        assert response.status_code == 200

        body = response.json()
        assert body["email"] == account["email"]
        assert body["is_active"] is True
        assert "hashed_password" not in body

    @pytest.mark.asyncio
    async def test_without_token_is_401(self, client):
        response = await client.get(f"{API}/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_with_garbage_token_is_401(self, client):
        response = await client.get(f"{API}/me", headers={"Authorization": "Bearer nonsense"})
        assert response.status_code == 401


class TestRefresh:
    """POST /auth/refresh."""

    @pytest.mark.asyncio
    async def test_rotation_returns_new_tokens(self, client, account):
        tokens = await _register(client, account)
        response = await client.post(
            f"{API}/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert response.status_code == 200
        assert response.json()["refresh_token"] != tokens["refresh_token"]

    @pytest.mark.asyncio
    async def test_old_token_stops_working_after_rotation(self, client, account):
        tokens = await _register(client, account)
        await client.post(f"{API}/refresh", json={"refresh_token": tokens["refresh_token"]})

        replay = await client.post(
            f"{API}/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert replay.status_code == 401

    @pytest.mark.asyncio
    async def test_reuse_revokes_every_session(self, client, account):
        """Replaying a spent token means it leaked, so all sessions must die."""
        first = await _register(client, account)
        second = (
            await client.post(f"{API}/refresh", json={"refresh_token": first["refresh_token"]})
        ).json()

        # Replay the already-spent token to trip reuse detection.
        await client.post(f"{API}/refresh", json={"refresh_token": first["refresh_token"]})

        # The token issued by the legitimate rotation must now be dead too.
        response = await client.post(
            f"{API}/refresh", json={"refresh_token": second["refresh_token"]}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unknown_token_is_401(self, client):
        response = await client.post(f"{API}/refresh", json={"refresh_token": "no-such-token"})
        assert response.status_code == 401


class TestLogout:
    """POST /auth/logout."""

    @pytest.mark.asyncio
    async def test_revokes_refresh_token(self, client, account):
        tokens = await _register(client, account)
        logout = await client.post(
            f"{API}/logout", json={"refresh_token": tokens["refresh_token"]}
        )
        assert logout.status_code == 204

        response = await client.post(
            f"{API}/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unknown_token_is_still_204(self, client):
        """Logout is idempotent and must not leak whether a token existed."""
        response = await client.post(f"{API}/logout", json={"refresh_token": "no-such-token"})
        assert response.status_code == 204
