"""pin a thread

Revision ID: a1c5e93f2b64
Revises: d7902ed8cf36
Create Date: 2026-08-16 23:10:00.000000

One nullable column on `agent_thread`. The sidebar's per-Thread menu offers
Pin / Rename / Delete; rename writes `title`, which already exists, and delete
removes the row, so pinning is the only thing that needed storage.

`pinned_at` rather than a boolean, because the pinned group has to keep the
order the user built it in — see the column's own note in
`src/alpha/models.py`.

No index. The predicate is always `user_id = ?` and a user's Threads are a
short list; `ix_agent_thread_user_updated` already narrows to them, and a second
index would be written on every pin toggle to sort a handful of rows.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a1c5e93f2b64"
down_revision: Union[str, None] = "d7902ed8cf36"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_thread",
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_thread", "pinned_at")
