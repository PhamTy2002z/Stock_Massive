"""add append-only realtime reconciliation audit

Revision ID: e2c4a7d19b63
Revises: c8f2a6d31e04
Create Date: 2026-08-24 23:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2c4a7d19b63"
down_revision: Union[str, None] = "c8f2a6d31e04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "realtime_reconciliation_audits",
        sa.Column("audit_id", sa.String(length=68), nullable=False),
        sa.Column("trading_day", sa.Date(), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("quality_state", sa.String(length=16), nullable=False),
        sa.Column("left_evidence_id", sa.String(length=68), nullable=False),
        sa.Column("right_evidence_id", sa.String(length=68), nullable=False),
        sa.Column("left_source", sa.String(length=32), nullable=False),
        sa.Column("right_source", sa.String(length=32), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("enforcement_mode", sa.String(length=16), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("audit_id"),
    )
    op.create_index(
        "ix_realtime_reconciliation_session",
        "realtime_reconciliation_audits",
        ["trading_day", "symbol", "scope", "checked_at"],
    )
    op.create_index(
        "ix_realtime_reconciliation_status",
        "realtime_reconciliation_audits",
        ["status", "quality_state", "checked_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_realtime_reconciliation_status",
        table_name="realtime_reconciliation_audits",
    )
    op.drop_index(
        "ix_realtime_reconciliation_session",
        table_name="realtime_reconciliation_audits",
    )
    op.drop_table("realtime_reconciliation_audits")
