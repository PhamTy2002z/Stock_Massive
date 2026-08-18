"""add the sourced Agent Knowledge Store

Revision ID: c6f8a1d42e70
Revises: a1c5e93f2b64
Create Date: 2026-08-17 00:30:00.000000

Facts remain external claims after persistence. The generated search vector and
the title trigram index both remove Vietnamese diacritics so a query typed
without them finds the same title. PostgreSQL marks `unaccent` as stable, so a
small immutable SQL wrapper is required for generated columns and expression
indexes; its dictionary is schema-qualified and fixed.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c6f8a1d42e70"
down_revision: Union[str, None] = "a1c5e93f2b64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.immutable_unaccent(text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        PARALLEL SAFE
        STRICT
        AS $$ SELECT public.unaccent('public.unaccent', $1) $$
        """
    )
    op.create_table(
        "agent_knowledge",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=True),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("symbol", sa.String(length=20), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('simple', immutable_unaccent("
                "coalesce(title, '') || ' ' || coalesce(body, '')"
                "))",
                persisted=True,
            ),
            nullable=False,
        ),
    )
    op.create_index("ix_agent_knowledge_user", "agent_knowledge", ["user_id"])
    op.create_index(
        "ix_agent_knowledge_tsv",
        "agent_knowledge",
        ["tsv"],
        postgresql_using="gin",
    )
    op.execute(
        """
        CREATE INDEX ix_agent_knowledge_title_trgm
        ON agent_knowledge
        USING gin (immutable_unaccent(lower(title)) gin_trgm_ops)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_agent_knowledge_title_trgm", table_name="agent_knowledge")
    op.drop_index("ix_agent_knowledge_tsv", table_name="agent_knowledge")
    op.drop_index("ix_agent_knowledge_user", table_name="agent_knowledge")
    op.drop_table("agent_knowledge")
    op.execute("DROP FUNCTION IF EXISTS public.immutable_unaccent(text)")
