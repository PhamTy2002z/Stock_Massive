"""add the fifteen minute intraday bars

Revision ID: c2e94a7b1f30
Revises: b1d38f2c70a5
Create Date: 2026-08-26 22:50:00.000000

Session-hours buckets only: the provider answers on a 24-hour grid and the
padding is dropped before anything reaches this table. Additive — the old
``stock_intraday_bars`` was dropped in the Phase 0 rip-out and nothing was left
to reconnect, so the downgrade drops rather than raises.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c2e94a7b1f30"
down_revision: Union[str, None] = "b1d38f2c70a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bar_intraday_15m",
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trading_day", sa.Date(), nullable=False),
        sa.Column("phase", sa.String(length=4), nullable=False),
        sa.Column("open", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("high", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("low", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("close", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("symbol", "bucket_start"),
    )
    op.create_index(
        "ix_bar_intraday_15m_symbol_day",
        "bar_intraday_15m",
        ["symbol", sa.text("trading_day DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_bar_intraday_15m_symbol_day", table_name="bar_intraday_15m")
    op.drop_table("bar_intraday_15m")
