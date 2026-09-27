"""add user connectors

Four new tables and nothing else: no existing table or row is touched, so the
downgrade drops exactly what the upgrade created.

Revision ID: c4e9a2f71b35
Revises: e6a21b7c4d90
Create Date: 2026-09-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4e9a2f71b35"
down_revision: str | None = "e6a21b7c4d90"
branch_labels = None
depends_on = None

_JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "connector_catalog",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(40), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("auth_type", sa.String(16), nullable=False, server_default="none"),
        sa.Column("oauth_client_id", sa.Text(), nullable=True),
        sa.Column("oauth_scopes", sa.Text(), nullable=True),
        sa.Column("trusted_data", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("tool_effects", _JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "auth_type IN ('none', 'header', 'oauth')", name="ck_connector_catalog_auth_type"
        ),
    )
    op.create_table(
        "user_connector",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "catalog_id",
            sa.Integer(),
            sa.ForeignKey("connector_catalog.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("slug", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("auth_type", sa.String(16), nullable=False),
        sa.Column("credentials", sa.Text(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="connected"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("tools", _JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("fingerprint", sa.String(64), nullable=False, server_default=""),
        sa.Column("dropped", _JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("pending", _JSONB, nullable=True),
        sa.Column("policies", _JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("breaker_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "slug", name="uq_user_connector_slug"),
        sa.CheckConstraint(
            "auth_type IN ('none', 'header', 'oauth')", name="ck_user_connector_auth_type"
        ),
        sa.CheckConstraint(
            "status IN ('connected', 'needs_auth', 'needs_reconsent', 'error')",
            name="ck_user_connector_status",
        ),
    )
    op.create_index("ix_user_connector_user_id", "user_connector", ["user_id"])
    op.create_table(
        "connector_oauth_state",
        sa.Column("state", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "connector_id",
            sa.Uuid(),
            sa.ForeignKey("user_connector.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("secret", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "user_connector_preference",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("tool_access", sa.String(16), nullable=False, server_default="on_demand"),
        sa.CheckConstraint(
            "tool_access IN ('on_demand', 'preloaded')", name="ck_user_connector_preference_mode"
        ),
    )


def downgrade() -> None:
    op.drop_table("user_connector_preference")
    op.drop_table("connector_oauth_state")
    op.drop_index("ix_user_connector_user_id", table_name="user_connector")
    op.drop_table("user_connector")
    op.drop_table("connector_catalog")
