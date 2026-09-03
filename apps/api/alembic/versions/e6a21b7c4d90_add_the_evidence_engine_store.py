"""add the evidence engine store

Revision ID: e6a21b7c4d90
Revises: d3f6a1c82b47
Create Date: 2026-09-02 10:30:00.000000

Three deliberately different lifetimes are represented by three tables:
public fetched documents may be shared and expire by source policy, private
research trajectories are owner-scoped and expire after thirty days, and the
checked claim ledger lasts with the assistant message it substantiates.

The migration is additive.  Its downgrade removes only Phase 6 data; transcript
messages remain readable because their rendered prose is already canonical.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e6a21b7c4d90"
down_revision: Union[str, None] = "d3f6a1c82b47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_evidence_cache",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("as_of_bucket", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("cache_kind", sa.String(length=32), nullable=False),
        sa.Column("source_class", sa.String(length=32), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("publisher", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("publication", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("char_length(content_sha256) = 64", name="ck_agent_evidence_cache_sha256"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "canonical_url",
            "content_sha256",
            "as_of_bucket",
            "policy_version",
            name="uq_agent_evidence_cache_identity",
        ),
    )
    op.create_index(
        "ix_agent_evidence_cache_lookup",
        "agent_evidence_cache",
        ["canonical_url", "as_of_bucket"],
    )
    op.create_index(
        "ix_agent_evidence_cache_expires", "agent_evidence_cache", ["expires_at"]
    )

    op.create_table(
        "agent_evidence_trajectory",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("turn_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["turn_id"], ["agent_turn.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_evidence_trajectory_owner_turn",
        "agent_evidence_trajectory",
        ["user_id", "turn_id"],
    )
    op.create_index(
        "ix_agent_evidence_trajectory_expires",
        "agent_evidence_trajectory",
        ["expires_at"],
    )

    op.create_table(
        "agent_claim_ledger",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("turn_id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["turn_id"], ["agent_turn.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["thread_id"], ["agent_thread.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["agent_message.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id"),
        sa.UniqueConstraint("turn_id"),
    )
    op.create_index(
        "ix_agent_claim_ledger_owner_message",
        "agent_claim_ledger",
        ["user_id", "message_id"],
    )
    op.create_index(
        "ix_agent_claim_ledger_thread", "agent_claim_ledger", ["thread_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_agent_claim_ledger_thread", table_name="agent_claim_ledger")
    op.drop_index("ix_agent_claim_ledger_owner_message", table_name="agent_claim_ledger")
    op.drop_table("agent_claim_ledger")
    op.drop_index("ix_agent_evidence_trajectory_expires", table_name="agent_evidence_trajectory")
    op.drop_index("ix_agent_evidence_trajectory_owner_turn", table_name="agent_evidence_trajectory")
    op.drop_table("agent_evidence_trajectory")
    op.drop_index("ix_agent_evidence_cache_expires", table_name="agent_evidence_cache")
    op.drop_index("ix_agent_evidence_cache_lookup", table_name="agent_evidence_cache")
    op.drop_table("agent_evidence_cache")
