"""OAuth 2.1 with PKCE for connectors that need a user's sign-in.

The flow is the MCP authorization spec's, server-side:

1. **Discover.** Ask the MCP endpoint without a token; its 401 names the
   protected-resource metadata (RFC 9728), which names the authorization server,
   whose metadata (RFC 8414) names the endpoints. Every one of these URLs is
   typed by somebody else, so every request goes through ``netguard``.
2. **Identify.** The catalog's pre-registered ``oauth_client_id`` if it has one,
   otherwise dynamic registration (RFC 7591) as a public client.
3. **Authorize.** A PKCE S256 verifier and a random ``state`` are stored
   encrypted for ten minutes; the browser goes to the authorization endpoint.
4. **Exchange.** The callback spends the ``state`` once (it is deleted in the
   same transaction that reads it), exchanges the code with the verifier, and
   stores the tokens with an *absolute* expiry.
5. **Refresh.** :func:`ensure_fresh` takes the connector row ``FOR UPDATE``,
   re-reads it, and refreshes only if the token it now sees is still expiring —
   so two Turns starting together never spend a rotating refresh token twice.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx2
from sqlalchemy import delete, select

from src.core.config import Settings

from . import crypto, netguard
from .models import ConnectorCatalog, ConnectorOAuthState, UserConnector
from .service import ConnectorNotFound, ConnectorRefused, ConnectorService

logger = logging.getLogger(__name__)

STATE_TTL = timedelta(minutes=10)
#: Refresh this long before the stated expiry, so a token does not lapse
#: between the check and the call.
REFRESH_MARGIN = timedelta(seconds=60)
CLIENT_NAME = "VisgniteAI"
_RESOURCE_METADATA = re.compile(r'resource_metadata="([^"]+)"')


class OAuthFailed(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Outcome:
    connector_id: uuid.UUID | None
    ok: bool
    reason: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


async def _checked(url: str) -> str:
    return await asyncio.to_thread(netguard.validate_connector_url, url)


async def _json(client: httpx2.AsyncClient, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
    await _checked(url)
    response = await client.request(method, url, **kwargs)
    if response.status_code >= 400:
        raise OAuthFailed("provider_refused", f"{urlsplit(url).path} answered {response.status_code}")
    try:
        body = response.json()
    except ValueError as exc:
        raise OAuthFailed("provider_invalid", "the provider did not answer JSON") from exc
    if not isinstance(body, dict):
        raise OAuthFailed("provider_invalid", "the provider did not answer an object")
    return body


async def discover(client: httpx2.AsyncClient, resource: str) -> dict[str, Any]:
    """The authorization server's metadata for one MCP endpoint."""
    await _checked(resource)
    probe = await client.post(
        resource,
        json={"jsonrpc": "2.0", "id": 0, "method": "ping"},
        headers={"Accept": "application/json, text/event-stream"},
    )
    candidates = []
    match = _RESOURCE_METADATA.search(probe.headers.get("www-authenticate", ""))
    if match:
        candidates.append(match.group(1))
    path = urlsplit(resource).path.rstrip("/")
    candidates += [
        f"{_origin(resource)}/.well-known/oauth-protected-resource{path}",
        f"{_origin(resource)}/.well-known/oauth-protected-resource",
    ]
    issuer = None
    for candidate in candidates:
        try:
            servers = (await _json(client, "GET", candidate)).get("authorization_servers") or []
        except (OAuthFailed, netguard.ConnectorURLRefused, httpx2.HTTPError):
            continue
        if servers:
            issuer = str(servers[0]).rstrip("/")
            break
    if issuer is None:
        # An older server with the authorization endpoints on its own origin.
        issuer = _origin(resource)
    issuer_path = urlsplit(issuer).path.rstrip("/")
    for candidate in (
        f"{_origin(issuer)}/.well-known/oauth-authorization-server{issuer_path}",
        f"{_origin(issuer)}/.well-known/openid-configuration{issuer_path}",
    ):
        try:
            metadata = await _json(client, "GET", candidate)
        except (OAuthFailed, httpx2.HTTPError):
            continue
        methods = metadata.get("code_challenge_methods_supported")
        if methods is not None and "S256" not in methods:
            raise OAuthFailed("pkce_unsupported", "the provider does not support PKCE S256")
        if not metadata.get("authorization_endpoint") or not metadata.get("token_endpoint"):
            continue
        return metadata
    raise OAuthFailed("discovery_failed", "the provider's authorization metadata was not found")


async def start(service: ConnectorService, user_id: int, connector_id: uuid.UUID) -> str:
    """Prepare one authorization and return where to send the browser."""
    service.require_enabled()
    row, catalog = await service.get(user_id, connector_id)
    if row.auth_type != "oauth":
        raise ConnectorRefused("not_oauth", "this connector does not sign in with OAuth")
    settings = service.settings
    keys = settings.connectors_encryption_keys
    async with netguard.pinned_client(timeout=settings.connectors_call_timeout_seconds) as client:
        try:
            metadata = await discover(client, row.url)
            secret = crypto.decrypt(row.credentials, keys=keys)
            registered = secret.get("client") or {}
            if catalog is not None and catalog.oauth_client_id:
                registered = {"client_id": catalog.oauth_client_id}
            elif not registered.get("client_id") or registered.get("redirect_uri") != settings.connectors_oauth_redirect_url:
                endpoint = metadata.get("registration_endpoint")
                if not endpoint:
                    raise OAuthFailed("registration_unavailable", "the provider needs a pre-registered client")
                body = await _json(
                    client,
                    "POST",
                    endpoint,
                    json={
                        "client_name": CLIENT_NAME,
                        "redirect_uris": [settings.connectors_oauth_redirect_url],
                        "grant_types": ["authorization_code", "refresh_token"],
                        "response_types": ["code"],
                        "token_endpoint_auth_method": "none",
                    },
                )
                registered = {
                    "client_id": body.get("client_id"),
                    "client_secret": body.get("client_secret"),
                    "redirect_uri": settings.connectors_oauth_redirect_url,
                }
                if not registered["client_id"]:
                    raise OAuthFailed("registration_failed", "the provider registered no client id")
        except (OAuthFailed, netguard.ConnectorURLRefused, httpx2.HTTPError) as exc:
            code = getattr(exc, "code", "provider_unreachable")
            raise ConnectorRefused(code, f"sign-in could not start: {exc}") from exc
    verifier = secrets.token_urlsafe(64)
    state = secrets.token_urlsafe(32)
    secret["client"] = registered
    secret["provider"] = {
        "issuer": metadata.get("issuer"),
        "token_endpoint": metadata["token_endpoint"],
        "authorization_endpoint": metadata["authorization_endpoint"],
    }
    scopes = (catalog.oauth_scopes if catalog is not None else None) or " ".join(
        metadata.get("scopes_supported") or []
    )
    async with service.session() as session, session.begin():
        locked = await session.scalar(
            select(UserConnector).where(UserConnector.id == row.id, UserConnector.user_id == user_id).with_for_update()
        )
        if locked is None:
            raise ConnectorNotFound(str(connector_id))
        locked.credentials = crypto.encrypt(secret, keys=keys)
        session.add(
            ConnectorOAuthState(
                state=state,
                user_id=user_id,
                connector_id=row.id,
                secret=crypto.encrypt({"verifier": verifier}, keys=keys),
                expires_at=_now() + STATE_TTL,
            )
        )
    query = {
        "response_type": "code",
        "client_id": registered["client_id"],
        "redirect_uri": settings.connectors_oauth_redirect_url,
        "code_challenge": _challenge(verifier),
        "code_challenge_method": "S256",
        "state": state,
        "resource": row.url,
    }
    if scopes:
        query["scope"] = scopes
    return f"{metadata['authorization_endpoint']}?{urlencode(query)}"


def _token_form(secret: dict[str, Any], **fields: str) -> dict[str, str]:
    form = {**fields, "client_id": secret["client"]["client_id"]}
    if secret["client"].get("client_secret"):
        form["client_secret"] = secret["client"]["client_secret"]
    return form


def _store_tokens(secret: dict[str, Any], body: dict[str, Any], *, previous: dict[str, Any] | None = None) -> None:
    access = body.get("access_token")
    if not access:
        raise OAuthFailed("token_missing", "the provider returned no access token")
    expires_in = body.get("expires_in")
    secret["tokens"] = {
        "access_token": access,
        # Rotating providers send a new one; others expect the old one reused.
        "refresh_token": body.get("refresh_token") or (previous or {}).get("refresh_token"),
        "expires_at": (
            (_now() + timedelta(seconds=float(expires_in))).isoformat() if expires_in else None
        ),
    }


async def finish(service: ConnectorService, *, state: str, code: str | None, error: str | None) -> Outcome:
    """Spend one ``state``: exchange its code, store the tokens, list the tools."""
    settings = service.settings
    keys = settings.connectors_encryption_keys
    async with service.session() as session, session.begin():
        pending = await session.scalar(
            select(ConnectorOAuthState).where(ConnectorOAuthState.state == state).with_for_update()
        )
        if pending is not None:
            await session.execute(delete(ConnectorOAuthState).where(ConnectorOAuthState.state == state))
    if pending is None or pending.expires_at <= _now():
        return Outcome(None if pending is None else pending.connector_id, False, "invalid_state")
    if error or not code:
        return Outcome(pending.connector_id, False, "provider_denied")
    verifier = crypto.decrypt(pending.secret, keys=keys)["verifier"]
    try:
        row, _ = await service.get(pending.user_id, pending.connector_id)
    except ConnectorNotFound:
        return Outcome(pending.connector_id, False, "connector_removed")
    secret = crypto.decrypt(row.credentials, keys=keys)
    try:
        async with netguard.pinned_client(timeout=settings.connectors_call_timeout_seconds) as client:
            body = await _json(
                client,
                "POST",
                secret["provider"]["token_endpoint"],
                data=_token_form(
                    secret,
                    grant_type="authorization_code",
                    code=code,
                    redirect_uri=settings.connectors_oauth_redirect_url,
                    code_verifier=verifier,
                    resource=row.url,
                ),
            )
        _store_tokens(secret, body)
    except (OAuthFailed, netguard.ConnectorURLRefused, httpx2.HTTPError, KeyError) as exc:
        logger.warning("OAuth exchange for connector %s failed: %s", pending.connector_id, exc)
        return Outcome(pending.connector_id, False, getattr(exc, "code", "exchange_failed"))
    async with service.session() as session, session.begin():
        locked = await session.get(UserConnector, row.id, with_for_update=True)
        if locked is None:
            return Outcome(pending.connector_id, False, "connector_removed")
        locked.credentials = crypto.encrypt(secret, keys=keys)
        locked.status = "connected"
        locked.failures = 0
        locked.breaker_until = None
        locked.last_error = None
    await service.refresh(pending.user_id, row.id)
    return Outcome(row.id, True)


async def ensure_fresh(service: ConnectorService, connector_id: uuid.UUID) -> None:
    """Refresh the access token if it is about to expire. One refresh, ever, per expiry."""
    settings = service.settings
    keys = settings.connectors_encryption_keys
    async with service.session() as session, session.begin():
        row = await session.get(UserConnector, connector_id, with_for_update=True)
        if row is None or row.auth_type != "oauth":
            return
        secret = crypto.decrypt(row.credentials, keys=keys)
        tokens = secret.get("tokens") or {}
        expires_at = tokens.get("expires_at")
        if not tokens.get("access_token"):
            row.status = "needs_auth"
            return
        if expires_at is None or datetime.fromisoformat(expires_at) - REFRESH_MARGIN > _now():
            return
        if not tokens.get("refresh_token"):
            row.status = "needs_auth"
            row.last_error = "token_expired"
            return
        try:
            async with netguard.pinned_client(timeout=settings.connectors_call_timeout_seconds) as client:
                body = await _json(
                    client,
                    "POST",
                    secret["provider"]["token_endpoint"],
                    data=_token_form(
                        secret,
                        grant_type="refresh_token",
                        refresh_token=tokens["refresh_token"],
                        resource=row.url,
                    ),
                )
            _store_tokens(secret, body, previous=tokens)
        except (OAuthFailed, netguard.ConnectorURLRefused, httpx2.HTTPError, KeyError) as exc:
            logger.warning("OAuth refresh for connector %s failed: %s", connector_id, exc)
            row.status = "needs_auth"
            row.last_error = "refresh_failed"
            return
        row.credentials = crypto.encrypt(secret, keys=keys)


def return_url(settings: Settings, outcome: Outcome) -> str:
    query = urlencode(
        {
            "connector": str(outcome.connector_id or ""),
            "connector_status": "connected" if outcome.ok else "failed",
            **({"connector_reason": outcome.reason} if outcome.reason else {}),
        }
    )
    base = settings.connectors_web_return_url
    return f"{base}{'&' if '?' in base else '?'}{query}"


__all__ = ["OAuthFailed", "Outcome", "discover", "ensure_fresh", "finish", "return_url", "start"]
