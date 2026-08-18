"""add the Trading Day index and the backfill retry backoff

Revision ID: c4e8f2a10b73
Revises: b3d71ac90f42
Create Date: 2026-08-13 10:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e8f2a10b73"
down_revision: Union[str, None] = "b3d71ac90f42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Resolving a Trading Day asks which sessions exist across every symbol at
    # once. ix_provider_snapshot_latest leads with the symbol, so it cannot
    # serve that question; without this index the resolver scans the table on
    # every signal request.
    op.create_index(
        "ix_provider_snapshot_capability_effective",
        "provider_snapshots",
        ["capability", sa.text("effective_at DESC")],
    )

    # A run has a handful of slots and the Universe has up to a hundred symbols.
    # Without a backoff the same few permanent failures take every slot every
    # night, and the symbols behind them are never reached.
    op.add_column(
        "symbol_backfills",
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "symbol_backfills",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("symbol_backfills", "next_attempt_at")
    op.drop_column("symbol_backfills", "attempts")
    op.drop_index(
        "ix_provider_snapshot_capability_effective",
        table_name="provider_snapshots",
    )
