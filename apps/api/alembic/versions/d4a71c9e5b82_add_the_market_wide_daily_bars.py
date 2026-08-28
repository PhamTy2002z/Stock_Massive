"""add the market wide daily bars

Revision ID: d4a71c9e5b82
Revises: c2e94a7b1f30
Create Date: 2026-08-27 21:50:00.000000

A typed table rather than more rows in ``provider_snapshots``: the daily spine
is 1,523 symbols by hundreds of sessions, and every read of the snapshot table
goes through the RAW-only Price Basis rule the market plane was built around.
``price_basis`` is a column here so a window can be asked what its numbers mean
instead of a caller assuming.

Additive, and nothing reads it yet, so the downgrade drops rather than raises.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d4a71c9e5b82"
down_revision: Union[str, None] = "c2e94a7b1f30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bar_daily",
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("trading_day", sa.Date(), nullable=False),
        sa.Column("series", sa.String(length=8), nullable=False),
        sa.Column("open", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("high", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("low", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("close", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("price_basis", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("symbol", "trading_day"),
    )
    op.create_index(
        "ix_bar_daily_symbol_day",
        "bar_daily",
        ["symbol", sa.text("trading_day DESC")],
    )
    op.create_index(
        "ix_bar_daily_day_series",
        "bar_daily",
        ["trading_day", "series"],
    )


def downgrade() -> None:
    op.drop_index("ix_bar_daily_day_series", table_name="bar_daily")
    op.drop_index("ix_bar_daily_symbol_day", table_name="bar_daily")
    op.drop_table("bar_daily")
