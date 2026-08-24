"""add realtime ingestion spine

Revision ID: c8f2a6d31e04
Revises: b7f4e9c21a08
Create Date: 2026-08-24 21:29:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8f2a6d31e04"
down_revision: Union[str, None] = "b7f4e9c21a08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "realtime_events",
        sa.Column("evidence_id", sa.String(length=68), nullable=False),
        sa.Column("trading_day", sa.Date(), nullable=False),
        sa.Column("event_family", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("provider_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("normalization_version", sa.Integer(), nullable=False),
        sa.Column("retention_policy_version", sa.Integer(), nullable=False),
        sa.Column("quality_state", sa.String(length=16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("evidence_id"),
    )
    op.create_index(
        "ix_realtime_event_replay",
        "realtime_events",
        [
            "trading_day",
            "event_family",
            "provider_time",
            "observed_time",
            "evidence_id",
        ],
    )
    op.create_index(
        "ix_realtime_event_symbol_latest",
        "realtime_events",
        ["event_family", "symbol", "provider_time"],
    )
    op.create_table(
        "realtime_checkpoints",
        sa.Column("consumer", sa.String(length=64), nullable=False),
        sa.Column("partition_key", sa.String(length=96), nullable=False),
        sa.Column("evidence_id", sa.String(length=68), nullable=False),
        sa.Column("provider_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("consumer", "partition_key"),
    )
    op.create_table(
        "realtime_spills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evidence_id", sa.String(length=68), nullable=False),
        sa.Column("trading_day", sa.Date(), nullable=False),
        sa.Column("event_family", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("recovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evidence_id", name="uq_realtime_spill_evidence"),
    )
    op.create_index(
        "ix_realtime_spill_pending",
        "realtime_spills",
        ["recovered_at", "created_at", "id"],
    )
    op.create_table(
        "realtime_health",
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("scope"),
    )


def downgrade() -> None:
    op.drop_table("realtime_health")
    op.drop_index("ix_realtime_spill_pending", table_name="realtime_spills")
    op.drop_table("realtime_spills")
    op.drop_table("realtime_checkpoints")
    op.drop_index("ix_realtime_event_symbol_latest", table_name="realtime_events")
    op.drop_index("ix_realtime_event_replay", table_name="realtime_events")
    op.drop_table("realtime_events")
