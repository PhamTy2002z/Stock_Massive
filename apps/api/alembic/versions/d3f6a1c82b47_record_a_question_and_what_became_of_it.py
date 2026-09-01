"""record a question and what became of it

Revision ID: d3f6a1c82b47
Revises: c4e8a1f70b62
Create Date: 2026-09-01 15:40:00.000000

A question the harness asks a reader ends the Turn that asked it, so the asking
itself is written into the assistant message like every other typed part. What
cannot live there is the outcome: `agent_message` is immutable and this state
changes afterwards — the reader chooses, declines, or types a new question and
makes the card moot. That is the same split `agent_turn` exists for, so it gets
the same answer: a row of its own.

`user_id` is a column rather than a join because the endpoints that resolve a
question are reached by question id alone, with no Thread in the path to scope
them. The index carries the only two reads there are — the pending question of a
Thread, and the supersede the next Turn's transaction runs over exactly that set.

Additive: nothing existed here before, so the downgrade drops the table rather
than raising. No production path publishes a question yet, so a downgrade taken
now drops an empty table.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d3f6a1c82b47"
down_revision: Union[str, None] = "c4e8a1f70b62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_question",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("turn_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column(
            "selected_option_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["thread_id"], ["agent_thread.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["turn_id"], ["agent_turn.id"], ondelete="CASCADE"),
        # SET NULL, not CASCADE: what a reader answered is a fact about the
        # conversation and outlives the message it was drawn on.
        sa.ForeignKeyConstraint(
            ["message_id"], ["agent_message.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_question_thread_state", "agent_question", ["thread_id", "state"]
    )


def downgrade() -> None:
    op.drop_index("ix_agent_question_thread_state", table_name="agent_question")
    op.drop_table("agent_question")
