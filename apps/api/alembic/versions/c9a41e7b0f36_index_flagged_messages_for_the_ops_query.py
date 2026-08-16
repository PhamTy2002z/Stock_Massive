"""index flagged messages for the ops query

Revision ID: c9a41e7b0f36
Revises: b7e4c1d9a208
Create Date: 2026-08-16 12:00:00

No column and no table. `flagged_reason` and `flagged_at` already exist on
`agent_message` from the Alpha Desk migration, and ADR-0016 forbids a new table
for observability — so the flag action of §A7 adds exactly one index and
nothing else.

Partial, on `flagged_reason IS NOT NULL`. The ops query counts flags by reason
over a date range against a table that holds every message ever written, and a
flag is rare: a full index would be the size of the transcript to answer a
question about a handful of rows, and would be touched by every message insert
rather than by the few that are flagged.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c9a41e7b0f36"
down_revision: Union[str, None] = "b7e4c1d9a208"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_agent_message_flagged",
        "agent_message",
        ["flagged_reason", "flagged_at"],
        postgresql_where="flagged_reason IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("ix_agent_message_flagged", table_name="agent_message")
