"""Rows for connectors: the reviewed catalog and what each user attached.

Four tables, and the split follows who writes them. The catalog is the
operator's; a user connector, its OAuth handshake and the user's one preference
are the user's. Tool permissions and the tool snapshot live as JSONB on the
connector row because they are read and written with it and never queried on
their own.

Secrets never sit in a column in the clear: ``credentials`` holds a MultiFernet
token (``crypto.py``), and the OAuth verifier is stored the same way.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func, text

from src.core.database import Base

AUTH_TYPES = ("none", "header", "oauth")
#: ``connected`` is the only status the overlay reads tools from.
STATUSES = ("connected", "needs_auth", "needs_reconsent", "error")
TOOL_ACCESS_MODES = ("on_demand", "preloaded")


class ConnectorCatalog(Base):
    """One operator-reviewed connector every user may attach."""

    __tablename__ = "connector_catalog"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(40), nullable=False, unique=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=False, server_default="")
    url = Column(Text, nullable=False)
    auth_type = Column(String(16), nullable=False, server_default="none")
    #: A client id registered with the provider in advance. Empty means dynamic
    #: client registration at connect time.
    oauth_client_id = Column(Text, nullable=True)
    oauth_scopes = Column(Text, nullable=True)
    #: Whether figures from this connector count as verified evidence. Only the
    #: operator sets it, and only after reviewing the provider.
    trusted_data = Column(Boolean, nullable=False, server_default=text("false"))
    #: The operator's read/write classification per tool name. A tool missing
    #: from it is treated as a write.
    tool_effects = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    enabled = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(f"auth_type IN {AUTH_TYPES}", name="ck_connector_catalog_auth_type"),
    )


class UserConnector(Base):
    """One connector a user attached, from the catalog or by URL."""

    __tablename__ = "user_connector"

    id = Column(Uuid, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    catalog_id = Column(
        Integer, ForeignKey("connector_catalog.id", ondelete="CASCADE"), nullable=True
    )
    #: The ``<connector>`` part of every wire name. Unique per user.
    slug = Column(String(40), nullable=False)
    name = Column(String(120), nullable=False)
    url = Column(Text, nullable=False)
    auth_type = Column(String(16), nullable=False)
    #: MultiFernet token over a JSON object: header secret, OAuth tokens,
    #: dynamically registered client. ``None`` when there is nothing secret.
    credentials = Column(Text, nullable=True)
    status = Column(String(24), nullable=False, server_default="connected")
    enabled = Column(Boolean, nullable=False, server_default=text("true"))
    #: The accepted tool list (``snapshot.py``), and the fingerprint over it.
    tools = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    fingerprint = Column(String(64), nullable=False, server_default="")
    #: Tools the server offered but that were not kept, with the reason.
    dropped = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    #: A newer snapshot waiting for the user to accept it.
    pending = Column(JSONB, nullable=True)
    #: ``{tool name: allow|ask|deny}`` as the user set it.
    policies = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    snapshot_at = Column(DateTime(timezone=True), nullable=True)
    failures = Column(Integer, nullable=False, server_default="0")
    breaker_until = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(String(40), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "slug", name="uq_user_connector_slug"),
        CheckConstraint(f"auth_type IN {AUTH_TYPES}", name="ck_user_connector_auth_type"),
        CheckConstraint(f"status IN {STATUSES}", name="ck_user_connector_status"),
    )


class ConnectorOAuthState(Base):
    """One OAuth authorization in flight, keyed by its ``state``."""

    __tablename__ = "connector_oauth_state"

    state = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    connector_id = Column(
        Uuid, ForeignKey("user_connector.id", ondelete="CASCADE"), nullable=False
    )
    #: Encrypted: the PKCE verifier and the token endpoint it is spent at.
    secret = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class UserConnectorPreference(Base):
    """How a user wants connector tools offered to the model."""

    __tablename__ = "user_connector_preference"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    tool_access = Column(String(16), nullable=False, server_default="on_demand")

    __table_args__ = (
        CheckConstraint(
            f"tool_access IN {TOOL_ACCESS_MODES}", name="ck_user_connector_preference_mode"
        ),
    )


__all__ = [
    "AUTH_TYPES",
    "ConnectorCatalog",
    "ConnectorOAuthState",
    "STATUSES",
    "TOOL_ACCESS_MODES",
    "UserConnector",
    "UserConnectorPreference",
]
