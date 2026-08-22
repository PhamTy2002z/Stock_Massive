"""widen remembered facts and make the transcript searchable

Revision ID: b7d2f5a10c93
Revises: a4c71d9e5b28
Create Date: 2026-08-21 23:55:00.000000

Two additions to memory that only make sense together.

`agent_knowledge` gains what a fact needs to be quoted honestly a week later:
what kind of thing it is, who said it, and when it stops being worth quoting.
`source_url` and `source_name` become nullable because a reader stating their
own risk appetite has no URL, and a required column would have forced either a
refusal to remember or an invented citation. The CHECK keeps the case that does
have a source from losing it.

`agent_message` gains the same generated search vector `agent_knowledge`
already carries, over `content ->> 'text'` — the one key both a user and an
assistant message write. `->>` is immutable, so the column is a legal generated
expression and no trigger can fall behind the row it indexes. The `simple`
configuration with `immutable_unaccent` is deliberate and not the default: a
reader who types *co phieu* means *cổ phiếu*, and the default configuration
answers that with silence rather than an error.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b7d2f5a10c93"
down_revision: Union[str, None] = "a4c71d9e5b28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Server defaults, so the rows written before this revision keep the meaning
    # they were written with: everything remembered so far arrived from a URL.
    op.add_column(
        "agent_knowledge",
        sa.Column(
            "kind",
            sa.String(length=16),
            nullable=False,
            server_default="observation",
        ),
    )
    op.add_column(
        "agent_knowledge",
        sa.Column(
            "origin",
            sa.String(length=16),
            nullable=False,
            server_default="external_source",
        ),
    )
    op.add_column(
        "agent_knowledge",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column(
        "agent_knowledge",
        "source_url",
        existing_type=sa.Text(),
        nullable=True,
    )
    op.alter_column(
        "agent_knowledge",
        "source_name",
        existing_type=sa.Text(),
        nullable=True,
    )
    op.create_check_constraint(
        "ck_agent_knowledge_external_source_url",
        "agent_knowledge",
        "origin <> 'external_source' OR source_url IS NOT NULL",
    )

    op.add_column(
        "agent_message",
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('simple', immutable_unaccent("
                "coalesce(content ->> 'text', '')"
                "))",
                persisted=True,
            ),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_agent_message_tsv",
        "agent_message",
        ["tsv"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_agent_message_tsv", table_name="agent_message")
    op.drop_column("agent_message", "tsv")

    op.drop_constraint(
        "ck_agent_knowledge_external_source_url",
        "agent_knowledge",
        type_="check",
    )
    # A fact with no source is precisely what the older schema could not hold,
    # so it is dropped rather than given a fabricated URL. A placeholder would
    # survive the rollback as a citation that leads nowhere, which is worse than
    # losing the row: the tool layer would then serve it as sourced evidence.
    op.execute("DELETE FROM agent_knowledge WHERE source_url IS NULL")
    op.execute(
        "UPDATE agent_knowledge SET source_name = source_url "
        "WHERE source_name IS NULL"
    )
    op.alter_column(
        "agent_knowledge",
        "source_name",
        existing_type=sa.Text(),
        nullable=False,
    )
    op.alter_column(
        "agent_knowledge",
        "source_url",
        existing_type=sa.Text(),
        nullable=False,
    )
    op.drop_column("agent_knowledge", "expires_at")
    op.drop_column("agent_knowledge", "origin")
    op.drop_column("agent_knowledge", "kind")
