"""add provider snapshots

Revision ID: 7f1c8a6e2d90
Revises: 0399ab15140e
Create Date: 2026-08-09 16:28:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7f1c8a6e2d90"
down_revision: Union[str, None] = "0399ab15140e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("capability", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "capability",
            "symbol",
            "source",
            "effective_at",
            "schema_version",
            name="uq_provider_snapshot_identity",
        ),
    )
    op.create_index(
        "ix_provider_snapshot_latest",
        "provider_snapshots",
        ["capability", "symbol", "source", "observed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_provider_snapshot_latest", table_name="provider_snapshots")
    op.drop_table("provider_snapshots")
