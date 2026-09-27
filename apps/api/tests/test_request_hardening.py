"""Credential and write-path hardening that needs no database.

Every request here is refused, or its database work is faked, before a
connection would be opened, so these hold on a host with no migrated database.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from src.agent.attachments import (
    MAX_ATTACHMENT_BYTES,
    AttachmentStore,
    StoredAttachment,
    StoredBytes,
)
from src.agent.router import attachment_store, desk
from src.auth import router as auth_router
from src.auth import service
from src.auth.dependencies import get_current_user
from src.core import database
from src.core.config import Settings
from src.core.ratelimit import InProcessSlidingWindowLimiter, credential_rate_limit
from src.main import app

API = "/api/v1"
LONG_MULTIBYTE = "é" * 40  # 40 characters, 80 bytes: past bcrypt's 72


@pytest.fixture
def client():
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def signed_in():
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=4242)


# --- bcrypt's 72 bytes --------------------------------------------------------


def test_a_long_multibyte_password_is_refused_at_signup(client):
    response = client.post(
        f"{API}/auth/register", json={"email": "long@example.com", "password": LONG_MULTIBYTE}
    )
    assert response.status_code == 422
    assert "72 bytes" in response.text


def test_a_long_multibyte_password_at_login_is_never_a_500(client):
    response = client.post(
        f"{API}/auth/login", json={"email": "nobody@example.com", "password": LONG_MULTIBYTE}
    )
    assert response.status_code in (401, 422)


def test_a_password_change_to_a_long_password_is_refused(client, signed_in):
    response = client.post(
        f"{API}/auth/password",
        json={"current_password": "old-password", "new_password": LONG_MULTIBYTE},
    )
    assert response.status_code == 422


class _NoRows:
    def scalar_one_or_none(self):
        return None


class _LookupSession:
    """Answers every lookup with no row; ``flush`` is what a test decides."""

    def __init__(self, flush_error: Exception | None = None):
        self.flush_error = flush_error

    async def execute(self, *_args, **_kwargs):
        return _NoRows()

    def add(self, _row):
        return None

    async def flush(self):
        if self.flush_error is not None:
            raise self.flush_error


@pytest.mark.asyncio
async def test_an_unknown_email_with_an_overlong_password_is_invalid_not_an_error():
    # Past the schema, straight at the service: the dummy check must swallow
    # what bcrypt raises, as the real check does for a known email.
    with pytest.raises(service.InvalidCredentials):
        await service.authenticate_user(_LookupSession(), "nobody@example.com", LONG_MULTIBYTE)


@pytest.mark.asyncio
async def test_a_signup_that_loses_the_race_for_its_email_is_a_conflict():
    raced = _LookupSession(IntegrityError("INSERT", {}, Exception("duplicate key")))
    with pytest.raises(service.EmailAlreadyRegistered):
        await service.register_user(raced, "twice@example.com", "sup3r-secret-pw")


# --- per-account login limit --------------------------------------------------


@pytest.fixture
def account_limit(monkeypatch):
    """Limiters on, no Redis, a two-failure account allowance."""
    enabled = Settings(rate_limit_enabled=True)
    monkeypatch.setattr("src.core.ratelimit.get_redis", lambda: None)
    monkeypatch.setattr("src.core.ratelimit.get_settings", lambda: enabled)
    monkeypatch.setattr(auth_router, "get_redis", lambda: None)
    monkeypatch.setattr(auth_router, "get_settings", lambda: enabled)
    monkeypatch.setattr(credential_rate_limit, "_fallback", InProcessSlidingWindowLimiter(50, 60))
    limit = auth_router._FailedLoginLimit(max_failures=2, window=60, prefix="test-account")
    monkeypatch.setattr(auth_router, "_login_account_limit", limit)
    return limit


def _login(client, email: str) -> int:
    return client.post(
        f"{API}/auth/login", json={"email": email, "password": "some-password"}
    ).status_code


def test_failed_logins_are_limited_per_account_as_well_as_per_address(
    account_limit, client, monkeypatch
):
    async def refuse(*_args, **_kwargs):
        raise service.InvalidCredentials("x")

    monkeypatch.setattr(auth_router, "authenticate_user", refuse)

    # Case does not make a second account.
    assert [_login(client, "victim@example.com"), _login(client, "VICTIM@example.com")] == [
        401,
        401,
    ]
    assert _login(client, "victim@example.com") == 429
    assert _login(client, "someone-else@example.com") == 401


def test_successful_logins_never_spend_the_accounts_allowance(
    account_limit, client, monkeypatch
):
    """Signing in as a known email, correctly, cannot lock its owner out."""

    async def accept(*_args, **_kwargs):
        return SimpleNamespace(id=7)

    async def issue(*_args, **_kwargs):
        return "refresh-token"

    monkeypatch.setattr(auth_router, "authenticate_user", accept)
    monkeypatch.setattr(auth_router, "issue_refresh_token", issue)
    monkeypatch.setattr(auth_router, "_token_pair", lambda _user, refresh: {
        "access_token": "a", "refresh_token": refresh, "expires_in": 60
    })

    assert [_login(client, "owner@example.com") for _ in range(5)] == [200] * 5


@pytest.mark.asyncio
async def test_a_redis_failure_count_is_read_without_being_spent(monkeypatch):
    from tests.fake_redis import FakeRedis

    redis = FakeRedis()
    enabled = Settings(rate_limit_enabled=True)
    monkeypatch.setattr(auth_router, "get_redis", lambda: redis)
    monkeypatch.setattr(auth_router, "get_settings", lambda: enabled)
    limit = auth_router._FailedLoginLimit(max_failures=2, window=60, prefix="t")

    for _ in range(5):
        await limit.check("acct")
    await limit.record_failure("acct")
    await limit.check("acct")
    await limit.record_failure("acct")

    with pytest.raises(auth_router.HTTPException) as refused:
        await limit.check("acct")
    assert refused.value.status_code == 429


def test_refresh_is_behind_the_credential_limiter():
    route = next(r for r in auth_router.router.routes if r.path == "/auth/refresh")
    assert any(d.call is credential_rate_limit for d in route.dependant.dependencies)


# --- a write whose commit fails is not a success ------------------------------


class _FailingCommitSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def execute(self, *_args, **_kwargs):
        return None

    async def commit(self):
        raise RuntimeError("commit failed")

    async def rollback(self):
        return None


def test_a_failed_commit_on_logout_all_is_a_500(client, signed_in, monkeypatch):
    monkeypatch.setattr(database, "async_session_factory", _FailingCommitSession)
    response = client.post(f"{API}/auth/logout-all")
    assert response.status_code == 500


# --- /capabilities is behind the session ---------------------------------------


def test_capabilities_needs_a_signed_in_caller(client):
    app.dependency_overrides[desk] = lambda: SimpleNamespace(
        config=SimpleNamespace(route=SimpleNamespace(vision=True))
    )
    assert client.get(f"{API}/capabilities").status_code == 401

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    response = client.get(f"{API}/capabilities")
    assert response.status_code == 200
    assert response.json()["vision"] is True


# --- uploads ------------------------------------------------------------------


def _no_database():
    raise AssertionError("the upload should have been refused before the store")


def _multipart(payload: bytes) -> tuple[bytes, str]:
    boundary = "testboundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="notes.txt"\r\n'
        "Content-Type: text/plain\r\n\r\n"
    ).encode() + payload + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def test_an_upload_without_a_content_length_is_refused(client, signed_in):
    app.dependency_overrides[attachment_store] = lambda: AttachmentStore(_no_database)
    body, content_type = _multipart(b"hello")

    def chunked():
        yield body

    response = client.post(
        f"{API}/attachments", content=chunked(), headers={"content-type": content_type}
    )
    assert response.status_code == 411
    assert response.json()["detail"]["reason"] == "length_required"


def test_a_declared_length_past_the_ceiling_is_refused_early(client, signed_in):
    app.dependency_overrides[attachment_store] = lambda: AttachmentStore(_no_database)
    body, content_type = _multipart(b"x")
    response = client.post(
        f"{API}/attachments",
        content=body,
        headers={"content-type": content_type, "content-length": str(MAX_ATTACHMENT_BYTES * 2)},
    )
    assert response.status_code == 413


def test_a_file_larger_than_its_declared_length_is_read_only_to_the_ceiling(
    client, signed_in
):
    seen: list[int] = []

    class _MeasuringStore(AttachmentStore):
        async def store(self, user_id, *, declared_type, filename, data):
            seen.append(len(data))
            return await super().store(
                user_id, declared_type=declared_type, filename=filename, data=data
            )

    app.dependency_overrides[attachment_store] = lambda: _MeasuringStore(_no_database)
    body, content_type = _multipart(b"x" * (MAX_ATTACHMENT_BYTES + 4096))
    # A lying length: small enough to pass the early check.
    response = client.post(
        f"{API}/attachments",
        content=body,
        headers={"content-type": content_type, "content-length": "100"},
    )
    assert response.status_code == 413
    assert seen == [MAX_ATTACHMENT_BYTES + 1]


def test_a_vietnamese_filename_is_served_without_a_500(client, signed_in):
    meta = StoredAttachment(
        id=uuid.uuid4(),
        media_type="image/png",
        filename="Bảng lợi nhuận.png",
        byte_size=4,
        pixel_width=1,
        pixel_height=1,
    )

    class _OneFile:
        async def read(self, _user_id, _attachment_id):
            return StoredBytes(meta=meta, content=b"\x89PNG")

    app.dependency_overrides[attachment_store] = lambda: _OneFile()
    response = client.get(f"{API}/attachments/{meta.id}")
    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert disposition.startswith('inline; filename="Bang loi nhuan.png"; ')
    assert "filename*=UTF-8''B%E1%BA%A3ng%20l%E1%BB%A3i%20nhu%E1%BA%ADn.png" in disposition
