"""add the agent artifact table

Revision ID: b1d38f2c70a5
Revises: 905ca5a8c2f7
Create Date: 2026-08-26 22:35:00.000000

A Study run is persisted so the canvas can be re-opened instead of recomputed:
the numbers are frozen beside the as-of they were read at. Additive, so the
downgrade drops the table rather than raising — nothing existed here before.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b1d38f2c70a5"
down_revision: Union[str, None] = "905ca5a8c2f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_artifact",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("turn_id", sa.Uuid(), nullable=True),
        sa.Column("thread_id", sa.Uuid(), nullable=True),
        sa.Column("study_name", sa.String(length=64), nullable=False),
        sa.Column("study_version", sa.Integer(), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("frames", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "canvas_spec", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"], ["agent_thread.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["turn_id"], ["agent_turn.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_artifact_thread_created",
        "agent_artifact",
        ["thread_id", sa.text("created_at DESC")],
    )
    op.create_index("ix_agent_artifact_turn", "agent_artifact", ["turn_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_artifact_turn", table_name="agent_artifact")
    op.drop_index("ix_agent_artifact_thread_created", table_name="agent_artifact")
    op.drop_table("agent_artifact")
