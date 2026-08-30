"""name a statement line in the language a reader asked in

Revision ID: c4e8a1f70b62
Revises: b5d1c7e04a83
Create Date: 2026-08-29 23:52:00.000000

``financial_statement_line`` stores the provider's ``item_id`` raw and no label.
That is right for meaning and wrong for display: every frame handed to the
browser labels its columns in Vietnamese, and a column headed
``business_income_tax_deferred`` is a column nobody asked about a company can
read.

The label is a table rather than a column on the line. The same
``(statement, item_id)`` repeats across 1.235 symbols and 34 quarters, so a
label on the line would be one sentence stored three hundred thousand times, and
fixing a typo would mean re-fetching the market.

Keyed without ``item_seq``: the occurrence index is in the line's key because
the provider answers two different numbers under one id, but both arrive under
the *same* id, and an id is what this table names.

Additive only. Nothing existing is read, rewritten or dropped, so ``downgrade``
is a plain drop rather than the ``NotImplementedError`` the destructive
revisions in this tree raise.

The parent was read from ``alembic heads`` at build time (one head,
``b5d1c7e04a83``), not copied from a plan.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c4e8a1f70b62"
down_revision: Union[str, None] = "b5d1c7e04a83"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "financial_statement_item",
        # Same widths as ``financial_statement_line``: 8 for the statement name
        # and 128 for the id, which is the longest measured across the three
        # reporting templates with room to spare.
        sa.Column("statement", sa.String(length=8), primary_key=True),
        sa.Column("item_id", sa.String(length=128), primary_key=True),
        sa.Column("label_vi", sa.String(length=512), nullable=False),
        sa.Column("label_en", sa.String(length=512), nullable=True),
        # Which symbol's response the label was read from. The three templates
        # disagree about what a line means, so a label seeded from a bank
        # sitting on a securities house's id is a mistake this column makes
        # visible.
        sa.Column("seeded_from", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("financial_statement_item")
