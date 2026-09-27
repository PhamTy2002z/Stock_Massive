"""Connector rows: attach, snapshot, permissions, failures, and what a Turn gets.

Every read and write is scoped by ``user_id`` in the query itself, so a
connector id from another account is simply not found — the same answer as an
id that never existed.

Three rules live here because this is where rows change:

**A snapshot is accepted once, and every later change is proposed.** The first
snapshot of a connector becomes its tools. A later one whose fingerprint
differs is stored as ``pending`` and the connector moves to
``needs_reconsent``; until the user accepts, only tools that are byte-identical
in both snapshots stay callable. A server cannot add a tool, or reword one, and
have the model see it without the user looking first.

**Failures open a breaker; a refused credential parks.** Three consecutive
transient failures open the breaker for a minute, doubling to fifteen. A 401 or
403 sets ``needs_auth`` at once and is not retried, because repeating a request
the server has already refused only repeats the refusal.

**Deleting a connector deletes its credentials** — they are a column of the row.
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.config import Settings, get_settings

from . import crypto, mcp_client, netguard, policy, snapshot
from .models import (
    ConnectorCatalog,
    UserConnector,
    UserConnectorPreference,
)

logger = logging.getLogger(__name__)

INTERNAL_PROFILE = "personal_internal"
BREAKER_THRESHOLD = 3
BREAKER_BASE = timedelta(seconds=60)
BREAKER_MAX = timedelta(minutes=15)
_HEADER_NAME = re.compile(r"^[A-Za-z0-9-]{1,64}$")
_FORBIDDEN_HEADERS = frozenset(
    {"host", "content-length", "transfer-encoding", "connection", "cookie", "mcp-session-id", "mcp-protocol-version"}
)

SessionFactory = Callable[[], AsyncSession]
Lister = Callable[[mcp_client.Target], Awaitable[list[Any]]]


class ConnectorNotFound(LookupError):
    """No connector with that id belongs to this user."""


class ConnectorRefused(ValueError):
    """The request is understood and not permitted; ``code`` says which rule."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _factory() -> SessionFactory:
    from src.core.database import async_session_factory

    return async_session_factory


@dataclass(frozen=True)
class ActiveConnector:
    """One connector a Turn may call, with everything its tools need."""

    id: uuid.UUID
    slug: str
    name: str
    trusted_data: bool
    catalog_effects: Mapping[str, str] | None
    tools: tuple[Mapping[str, Any], ...]
    policies: Mapping[str, str]


class ConnectorService:
    """The one owner of ``user_connector`` rows."""

    def __init__(
        self,
        *,
        session_factory: SessionFactory | None = None,
        settings: Settings | None = None,
        lister: Lister | None = None,
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._sessions = session_factory
        self._settings = settings
        self._lister = lister or (lambda target: mcp_client.list_tools(target))
        self._clock = clock
        # Set by ``oauth.py`` when it is imported, so a Turn can refresh an
        # expiring token without this module importing the OAuth flow.
        self.token_refresher: Callable[[uuid.UUID], Awaitable[None]] | None = None

    @property
    def settings(self) -> Settings:
        return self._settings or get_settings()

    def session(self) -> AsyncSession:
        return (self._sessions or _factory())()

    # -- rules ------------------------------------------------------------

    def enabled(self) -> bool:
        return bool(self.settings.connectors_enabled and self.settings.connectors_encryption_keys.strip())

    def custom_url_allowed(self, user_id: int) -> bool:
        settings = self.settings
        allowlist = {item.strip() for item in settings.connectors_custom_url_users.split(",") if item.strip()}
        return bool(
            self.enabled()
            and settings.connectors_custom_url
            and settings.deployment_profile == INTERNAL_PROFILE
            and str(user_id) in allowlist
        )

    def require_enabled(self) -> None:
        if not self.enabled():
            raise ConnectorRefused("connectors_disabled", "connectors are not enabled here")

    def _keys(self) -> str:
        return self.settings.connectors_encryption_keys

    # -- reads ------------------------------------------------------------

    async def catalog(self) -> list[ConnectorCatalog]:
        async with self.session() as session:
            rows = await session.scalars(
                select(ConnectorCatalog).where(ConnectorCatalog.enabled.is_(True)).order_by(ConnectorCatalog.name)
            )
            return list(rows)

    async def mine(self, user_id: int) -> list[tuple[UserConnector, ConnectorCatalog | None]]:
        async with self.session() as session:
            rows = await session.execute(
                select(UserConnector, ConnectorCatalog)
                .outerjoin(ConnectorCatalog, UserConnector.catalog_id == ConnectorCatalog.id)
                .where(UserConnector.user_id == user_id)
                .order_by(UserConnector.created_at)
            )
            return [(row[0], row[1]) for row in rows]

    async def get(self, user_id: int, connector_id: uuid.UUID) -> tuple[UserConnector, ConnectorCatalog | None]:
        async with self.session() as session:
            return await self._get(session, user_id, connector_id)

    async def _get(
        self, session: AsyncSession, user_id: int, connector_id: uuid.UUID, *, lock: bool = False
    ) -> tuple[UserConnector, ConnectorCatalog | None]:
        query = select(UserConnector).where(
            UserConnector.id == connector_id, UserConnector.user_id == user_id
        )
        if lock:
            query = query.with_for_update()
        row = await session.scalar(query)
        if row is None:
            raise ConnectorNotFound(str(connector_id))
        catalog = (
            await session.get(ConnectorCatalog, row.catalog_id) if row.catalog_id is not None else None
        )
        return row, catalog

    async def tool_access(self, user_id: int) -> str:
        async with self.session() as session:
            row = await session.get(UserConnectorPreference, user_id)
            return row.tool_access if row is not None else "on_demand"

    async def set_tool_access(self, user_id: int, mode: str) -> str:
        if mode not in ("on_demand", "preloaded"):
            raise ConnectorRefused("invalid_mode", "tool access is on_demand or preloaded")
        async with self.session() as session, session.begin():
            row = await session.get(UserConnectorPreference, user_id)
            if row is None:
                session.add(UserConnectorPreference(user_id=user_id, tool_access=mode))
            else:
                row.tool_access = mode
        return mode

    async def active(self, user_id: int) -> list[ActiveConnector]:
        """What a Turn starting now may call. Read once, at Turn creation."""
        if not self.enabled() or user_id is None:
            return []
        now = self._clock()
        active: list[ActiveConnector] = []
        for row, catalog in await self.mine(user_id):
            if not row.enabled or row.status not in ("connected", "needs_reconsent"):
                continue
            if row.breaker_until is not None and row.breaker_until > now:
                continue
            if catalog is not None and not catalog.enabled:
                continue
            tools = tuple(row.tools or ())
            if row.pending:
                # Until the user accepts a changed tool list, only what is
                # byte-identical in both stays callable.
                proposed = {self._identity(tool) for tool in row.pending["tools"]}
                tools = tuple(tool for tool in tools if self._identity(tool) in proposed)
            active.append(
                ActiveConnector(
                    id=row.id,
                    slug=row.slug,
                    name=row.name,
                    trusted_data=bool(catalog is not None and catalog.trusted_data),
                    catalog_effects=(dict(catalog.tool_effects or {}) if catalog is not None else None),
                    tools=tools,
                    policies=dict(row.policies or {}),
                )
            )
        return active

    # -- attach -----------------------------------------------------------

    async def add_from_catalog(
        self, user_id: int, catalog_id: int, *, header_value: str | None = None
    ) -> UserConnector:
        self.require_enabled()
        async with self.session() as session:
            catalog = await session.get(ConnectorCatalog, catalog_id)
            if catalog is None or not catalog.enabled:
                raise ConnectorNotFound(str(catalog_id))
        credentials: dict[str, Any] = {}
        if catalog.auth_type == "header":
            if not header_value:
                raise ConnectorRefused("credential_required", "this connector needs a key")
            credentials = {"header": {"name": "Authorization", "value": header_value}}
        return await self._create(
            user_id,
            name=catalog.name,
            slug_source=catalog.slug,
            url=catalog.url,
            auth_type=catalog.auth_type,
            catalog_id=catalog.id,
            credentials=credentials,
        )

    async def add_custom(
        self,
        user_id: int,
        *,
        name: str,
        url: str,
        header_name: str | None = None,
        header_value: str | None = None,
        oauth: bool = False,
    ) -> UserConnector:
        self.require_enabled()
        if not self.custom_url_allowed(user_id):
            raise ConnectorRefused("custom_url_not_allowed", "custom connector URLs are not enabled for this account")
        name = (name or "").strip()[:120]
        if not name:
            raise ConnectorRefused("name_required", "a connector needs a name")
        try:
            url = netguard.validate_connector_url(url)
        except netguard.ConnectorURLRefused as exc:
            raise ConnectorRefused("url_refused", str(exc)) from exc
        credentials: dict[str, Any] = {}
        auth_type = "oauth" if oauth else "none"
        if header_value:
            header_name = (header_name or "Authorization").strip()
            if not _HEADER_NAME.match(header_name) or header_name.lower() in _FORBIDDEN_HEADERS:
                raise ConnectorRefused("header_refused", "that header name cannot carry a credential")
            credentials = {"header": {"name": header_name, "value": header_value}}
            auth_type = "header"
        return await self._create(
            user_id,
            name=name,
            slug_source=name,
            url=url,
            auth_type=auth_type,
            catalog_id=None,
            credentials=credentials,
        )

    async def _create(
        self,
        user_id: int,
        *,
        name: str,
        slug_source: str,
        url: str,
        auth_type: str,
        catalog_id: int | None,
        credentials: Mapping[str, Any],
    ) -> UserConnector:
        base = snapshot.clean_slug(slug_source)
        async with self.session() as session, session.begin():
            taken = set(
                await session.scalars(select(UserConnector.slug).where(UserConnector.user_id == user_id))
            )
            slug, counter = base, 2
            while slug in taken:
                slug = f"{base[:17]}_{counter}"
                counter += 1
            row = UserConnector(
                id=uuid.uuid4(),
                user_id=user_id,
                catalog_id=catalog_id,
                slug=slug,
                name=name,
                url=url,
                auth_type=auth_type,
                credentials=crypto.encrypt(credentials, keys=self._keys()) if credentials else None,
                status="needs_auth" if auth_type == "oauth" else "connected",
                enabled=True,
                tools=[],
                dropped=[],
                policies={},
            )
            session.add(row)
        if auth_type != "oauth":
            await self.refresh(user_id, row.id)
        return (await self.get(user_id, row.id))[0]

    # -- snapshot ---------------------------------------------------------

    async def target(self, user_id: int, connector_id: uuid.UUID) -> mcp_client.Target:
        row, _ = await self.get(user_id, connector_id)
        if row.auth_type == "oauth" and self.token_refresher is not None:
            await self.token_refresher(connector_id)
            row, _ = await self.get(user_id, connector_id)
        return self._target(row)

    def _target(self, row: UserConnector) -> mcp_client.Target:
        secret = crypto.decrypt(row.credentials, keys=self._keys())
        headers: dict[str, str] = {}
        if row.auth_type == "header" and secret.get("header"):
            headers[secret["header"]["name"]] = secret["header"]["value"]
        elif row.auth_type == "oauth" and secret.get("tokens", {}).get("access_token"):
            headers["Authorization"] = f"Bearer {secret['tokens']['access_token']}"
        return mcp_client.Target(
            url=row.url, headers=headers, timeout=self.settings.connectors_call_timeout_seconds
        )

    async def refresh(self, user_id: int, connector_id: uuid.UUID) -> UserConnector:
        """List the server's tools now and accept or propose the snapshot."""
        target = await self.target(user_id, connector_id)
        row, _ = await self.get(user_id, connector_id)
        try:
            listed = await self._lister(target)
        except mcp_client.ConnectorError as exc:
            await self.record_failure(connector_id, exc)
            return (await self.get(user_id, connector_id))[0]
        built = snapshot.build(row.slug, snapshot.from_mcp(listed) if listed and not isinstance(listed[0], Mapping) else listed)
        async with self.session() as session, session.begin():
            row, _ = await self._get(session, user_id, connector_id, lock=True)
            row.snapshot_at = self._clock()
            row.failures = 0
            row.breaker_until = None
            row.last_error = None
            dropped = [*built.dropped]
            if not row.fingerprint or built.fingerprint == row.fingerprint:
                # First snapshot, or the server is back to what was accepted.
                row.tools = list(built.tools)
                row.fingerprint = built.fingerprint
                row.dropped = dropped
                row.pending = None
                row.status = "connected"
            elif built.fingerprint != (row.pending or {}).get("fingerprint"):
                # ``tools`` keeps the accepted list; :meth:`active` serves only
                # the part of it that is identical in the proposal.
                row.pending = {
                    "tools": list(built.tools),
                    "dropped": dropped,
                    "fingerprint": built.fingerprint,
                    "detected_at": self._clock().isoformat(),
                }
                row.status = "needs_reconsent"
        return (await self.get(user_id, connector_id))[0]

    @staticmethod
    def _identity(tool: Mapping[str, Any]) -> str:
        return snapshot.fingerprint([tool])

    async def accept_pending(self, user_id: int, connector_id: uuid.UUID) -> UserConnector:
        async with self.session() as session, session.begin():
            row, _ = await self._get(session, user_id, connector_id, lock=True)
            if row.pending:
                previous = {tool["name"]: self._identity(tool) for tool in row.tools or ()}
                policies = dict(row.policies or {})
                for tool in row.pending["tools"]:
                    if previous.get(tool["name"]) != self._identity(tool):
                        # New or changed: back to its default, never a grant
                        # carried over from the tool it replaced.
                        policies.pop(tool["name"], None)
                row.tools = row.pending["tools"]
                row.dropped = row.pending.get("dropped", [])
                row.fingerprint = row.pending["fingerprint"]
                row.policies = policies
                row.pending = None
                row.status = "connected"
        return (await self.get(user_id, connector_id))[0]

    # -- edits ------------------------------------------------------------

    async def set_enabled(self, user_id: int, connector_id: uuid.UUID, enabled: bool) -> UserConnector:
        async with self.session() as session, session.begin():
            row, _ = await self._get(session, user_id, connector_id, lock=True)
            row.enabled = bool(enabled)
        if not enabled:
            from .approvals import hub

            hub.deny_connector(connector_id)
        return (await self.get(user_id, connector_id))[0]

    async def set_policy(
        self, user_id: int, connector_id: uuid.UUID, tool_name: str, action: str
    ) -> UserConnector:
        if action not in policy.ACTIONS:
            raise ConnectorRefused("invalid_action", "the action is allow, ask or deny")
        async with self.session() as session, session.begin():
            row, catalog = await self._get(session, user_id, connector_id, lock=True)
            tool = next((item for item in row.tools or () if item["name"] == tool_name), None)
            if tool is None:
                raise ConnectorNotFound(tool_name)
            try:
                policy.validate(tool, action, catalog_effects=self.catalog_effects(catalog))
            except policy.PolicyRefused as exc:
                raise ConnectorRefused("write_needs_approval", str(exc)) from exc
            row.policies = {**(row.policies or {}), tool_name: action}
        return (await self.get(user_id, connector_id))[0]

    async def set_header(self, user_id: int, connector_id: uuid.UUID, value: str) -> UserConnector:
        async with self.session() as session, session.begin():
            row, _ = await self._get(session, user_id, connector_id, lock=True)
            if row.auth_type != "header":
                raise ConnectorRefused("not_header_auth", "this connector does not use a key")
            secret = crypto.decrypt(row.credentials, keys=self._keys())
            secret["header"] = {**secret.get("header", {"name": "Authorization"}), "value": value}
            row.credentials = crypto.encrypt(secret, keys=self._keys())
            row.status = "connected"
            row.failures = 0
            row.breaker_until = None
        return await self.refresh(user_id, connector_id)

    async def delete(self, user_id: int, connector_id: uuid.UUID) -> None:
        async with self.session() as session, session.begin():
            result = await session.execute(
                delete(UserConnector).where(
                    UserConnector.id == connector_id, UserConnector.user_id == user_id
                )
            )
            if result.rowcount == 0:
                raise ConnectorNotFound(str(connector_id))
        from .approvals import hub

        hub.deny_connector(connector_id)

    @staticmethod
    def catalog_effects(catalog: ConnectorCatalog | None) -> Mapping[str, str] | None:
        return dict(catalog.tool_effects or {}) if catalog is not None else None

    # -- health -----------------------------------------------------------

    async def record_failure(self, connector_id: uuid.UUID, error: mcp_client.ConnectorError) -> None:
        async with self.session() as session, session.begin():
            row = await session.get(UserConnector, connector_id, with_for_update=True)
            if row is None:
                return
            row.last_error = error.code
            if isinstance(error, mcp_client.ConnectorAuthError):
                row.status = "needs_auth"
                return
            row.failures = (row.failures or 0) + 1
            if row.failures >= BREAKER_THRESHOLD:
                opened = BREAKER_BASE * (2 ** (row.failures - BREAKER_THRESHOLD))
                row.breaker_until = self._clock() + min(opened, BREAKER_MAX)
                row.status = "error"

    async def record_success(self, connector_id: uuid.UUID) -> None:
        async with self.session() as session, session.begin():
            row = await session.get(UserConnector, connector_id, with_for_update=True)
            if row is None or (row.failures == 0 and row.status != "error"):
                return
            row.failures = 0
            row.breaker_until = None
            row.last_error = None
            if row.status == "error":
                row.status = "needs_reconsent" if row.pending else "connected"


def describe(row: UserConnector, catalog: ConnectorCatalog | None, *, now: datetime | None = None) -> dict[str, Any]:
    """The settings page's view of one connector. Never carries a secret."""
    effects = ConnectorService.catalog_effects(catalog)
    stored = row.policies or {}
    tools = []
    for tool in row.tools or ():
        tool_effect = policy.effect(tool, catalog_effects=effects)
        tools.append(
            {
                "name": tool["name"],
                "wire": tool["wire"],
                "title": tool.get("title") or "",
                "description": tool.get("description") or "",
                "effect": tool_effect,
                "action": policy.action(tool, stored, catalog_effects=effects),
                "allowed_actions": list(policy.allowed_actions(tool_effect)),
                # A read on a custom connector is the server's word for it.
                "read_only_claimed_by_server": effects is None and tool_effect == policy.READ,
            }
        )
    pending = None
    if row.pending:
        before = {tool["name"]: ConnectorService._identity(tool) for tool in row.tools or ()}
        after = {tool["name"]: ConnectorService._identity(tool) for tool in row.pending["tools"]}
        pending = {
            "added": sorted(set(after) - set(before)),
            "removed": sorted(set(before) - set(after)),
            "changed": sorted(name for name in set(after) & set(before) if after[name] != before[name]),
            "detected_at": row.pending.get("detected_at"),
        }
    moment = now or _now()
    return {
        "id": str(row.id),
        "slug": row.slug,
        "name": row.name,
        "source": "catalog" if catalog is not None else "custom",
        "catalog_id": catalog.id if catalog is not None else None,
        "url": row.url,
        "auth_type": row.auth_type,
        "status": row.status,
        "enabled": row.enabled,
        "last_error": row.last_error,
        "breaker_open": bool(row.breaker_until and row.breaker_until > moment),
        "trusted_data": bool(catalog is not None and catalog.trusted_data),
        "tools": tools,
        "dropped": list(row.dropped or ()),
        "truncated": sum(1 for item in row.dropped or () if item.get("reason") == "over_tool_limit"),
        "pending": pending,
        "snapshot_at": row.snapshot_at.isoformat() if row.snapshot_at else None,
    }


def describe_catalog(entry: ConnectorCatalog) -> dict[str, Any]:
    return {
        "id": entry.id,
        "slug": entry.slug,
        "name": entry.name,
        "description": entry.description,
        "auth_type": entry.auth_type,
        "trusted_data": entry.trusted_data,
    }


_service: ConnectorService | None = None


def connectors() -> ConnectorService:
    global _service
    if _service is None:
        _service = ConnectorService()
    return _service


def set_connectors(service: ConnectorService | None) -> ConnectorService | None:
    global _service
    previous, _service = _service, service
    return previous


__all__ = [
    "ActiveConnector",
    "ConnectorNotFound",
    "ConnectorRefused",
    "ConnectorService",
    "connectors",
    "describe",
    "describe_catalog",
    "set_connectors",
]
