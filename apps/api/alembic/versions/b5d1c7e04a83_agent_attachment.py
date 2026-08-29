"""hold what a reader attached

Revision ID: b5d1c7e04a83
Revises: a3f7e21b8d54
Create Date: 2026-08-29 01:30:00.000000

A Turn may now carry files. They are held here rather than on disk for three
reasons that hold: ownership is a column read through the same owner-scoped join
as every other row in this schema; ``pg_dump`` is already the backup procedure;
and a Turn and the attachments it names commit or roll back together.

``attached_turn_id`` is nullable on purpose. It is ``NULL`` for an upload still
in flight, and that is exactly what the sweep in ``agent/attachments.py`` keys
on: a row past the grace period that never became a Turn is the only thing here
nothing will ever read again.

The parent was read from ``alembic heads`` at build time, not copied from a
plan. ``a3f7e21b8d54`` was already applied when this was written, so nothing
here re-runs its row-count-gated deletion.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b5d1c7e04a83"
down_revision: Union[str, None] = "a3f7e21b8d54"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_attachment",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # ``users.id`` is an integer sequence, not a UUID — every other
        # user-scoped table here says Integer for the same reason.
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("attached_turn_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("media_type", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("pixel_width", sa.Integer(), nullable=True),
        sa.Column("pixel_height", sa.Integer(), nullable=True),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["attached_turn_id"], ["agent_turn.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_agent_attachment_user_created",
        "agent_attachment",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_agent_attachment_orphans",
        "agent_attachment",
        ["attached_turn_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_attachment_orphans", table_name="agent_attachment")
    op.drop_index("ix_agent_attachment_user_created", table_name="agent_attachment")
    op.drop_table("agent_attachment")
