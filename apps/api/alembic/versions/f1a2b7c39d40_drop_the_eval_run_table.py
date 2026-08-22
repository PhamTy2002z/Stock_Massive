"""drop the eval_run table

Revision ID: f1a2b7c39d40
Revises: c4e81f37b6da
Create Date: 2026-08-22 18:40:00.000000

The battery that wrote this table is gone, and a table nothing writes is a
schema claim nobody can honour. Dropped rather than left standing: the next
autogenerate would propose exactly this drop, and a table kept only to postpone
that decision is one more thing a reader has to ask about.

`llm_call_usage` keeps its rows untouched. `owner_type` and `lane` are plain
text there, so any historical row that named an eval run stays readable as the
history it is — the ledger's job is to say what was spent, not to agree with the
code that is running now.

Downgrade recreates the table empty. There is nothing to restore into it: the
rows a battery would have written are produced by a battery, and re-adding the
columns is all a downgrade can honestly promise.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f1a2b7c39d40"
down_revision: Union[str, None] = "c4e81f37b6da"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("eval_run")


def downgrade() -> None:
    op.create_table(
        "eval_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("route", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("tool_catalog_version", sa.String(length=32), nullable=False),
        sa.Column("registry_version", sa.String(length=32), nullable=False),
        sa.Column("fixture_version", sa.String(length=32), nullable=False),
        sa.Column(
            "category_totals",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("report_path", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
