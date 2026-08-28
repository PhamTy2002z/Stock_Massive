"""add the quarterly financial store

Revision ID: e6b3d90c41af
Revises: d4a71c9e5b82
Create Date: 2026-08-27 22:55:00.000000

Two long-format tables rather than a wide one per template. The three templates
this market reports under (bank, securities, non-financial) share almost no line
items — 26, 79 and 25 lines measured on 2026-08-27 — so a typed column per item
would be mostly nulls and would need a migration whenever the provider adds a
line.

``item_seq`` is part of both primary keys because the provider's own response
holds one ``item_id`` twice with different numbers under it: SSI's income
statement answers two ``business_income_tax_deferred`` rows for 2026-Q2
(4,585,945,424 and 758,786,600, the second one being the minority interest line
arriving under the wrong id), and its balance sheet answers
``accumulated_depreciation`` four times. Without the occurrence index the
response is unstorable, and resolving it by "last row wins" drops numbers.

Additive, and nothing outside the new module reads either table, so the
downgrade drops rather than raises.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e6b3d90c41af"
down_revision: Union[str, None] = "d4a71c9e5b82"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "financial_statement_line",
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("statement", sa.String(length=8), nullable=False),
        sa.Column("item_id", sa.String(length=128), nullable=False),
        sa.Column("item_seq", sa.SmallInteger(), nullable=False),
        sa.Column("value", sa.Numeric(precision=28, scale=4), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("symbol", "period", "statement", "item_id", "item_seq"),
    )
    # One line across the market for one quarter: the earnings screener's read.
    # The primary key leads with the symbol and cannot answer it.
    op.create_index(
        "ix_financial_statement_line_period_item",
        "financial_statement_line",
        ["period", "statement", "item_id"],
    )

    op.create_table(
        "financial_ratio_snapshot",
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("item_id", sa.String(length=128), nullable=False),
        sa.Column("item_seq", sa.SmallInteger(), nullable=False),
        sa.Column("value", sa.Numeric(precision=28, scale=4), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("symbol", "period", "item_id", "item_seq"),
    )
    op.create_index(
        "ix_financial_ratio_snapshot_period_item",
        "financial_ratio_snapshot",
        ["period", "item_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_financial_ratio_snapshot_period_item",
        table_name="financial_ratio_snapshot",
    )
    op.drop_table("financial_ratio_snapshot")
    op.drop_index(
        "ix_financial_statement_line_period_item",
        table_name="financial_statement_line",
    )
    op.drop_table("financial_statement_line")
