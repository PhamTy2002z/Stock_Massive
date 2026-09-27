"""heartbeat active turns and index their counts

Revision ID: f2b8c4d61a37
Revises: ce858b22360a
Create Date: 2026-09-27 16:00:00.000000

Additive only: one nullable column and three indexes on `agent_turn`.

`heartbeat_at` is touched every 20 seconds by the process running a Turn. The
startup sweep and the periodic reaper settle only active rows whose heartbeat
(or, before the first one, `started_at`) is older than 90 seconds, so a second
process sharing the table — a rolling deploy, the strict stack on 8001 — keeps
its Turns instead of having them frozen underneath it. Nullable with no default:
every existing row reads as "never beat", which is exactly true, and a terminal
row never needs one.

`ix_agent_turn_active` is partial on the two active statuses. Admission counts
active Turns while holding a system-wide advisory lock, and without it that
count scans every Turn ever asked. `thread_id` is the column the per-user count
joins on.

The two message FKs get plain indexes so deleting a Thread's messages does not
scan `agent_turn` for the rows the CASCADE and the SET NULL have to touch.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2b8c4d61a37"
down_revision: Union[str, None] = "ce858b22360a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACTIVE = sa.text("status IN ('admitted', 'running')")


def upgrade() -> None:
    op.add_column(
        "agent_turn",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_agent_turn_active",
        "agent_turn",
        ["thread_id"],
        unique=False,
        postgresql_where=_ACTIVE,
    )
    op.create_index(
        "ix_agent_turn_request_message_id",
        "agent_turn",
        ["request_message_id"],
        unique=False,
    )
    op.create_index(
        "ix_agent_turn_response_message_id",
        "agent_turn",
        ["response_message_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_turn_response_message_id", table_name="agent_turn")
    op.drop_index("ix_agent_turn_request_message_id", table_name="agent_turn")
    op.drop_index(
        "ix_agent_turn_active",
        table_name="agent_turn",
        postgresql_where=_ACTIVE,
    )
    op.drop_column("agent_turn", "heartbeat_at")
