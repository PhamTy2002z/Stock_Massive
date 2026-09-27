"""join the connectors and turn heartbeat heads

Revision ID: 9c1e7a4b2d58
Revises: f2b8c4d61a37, c4e9a2f71b35
Create Date: 2026-09-27 17:00:00.000000

No schema change. The user connectors table and the reader-preferences /
turn-heartbeat chain were both written on top of ``e6a21b7c4d90`` on separate
branches; this revision gives alembic one head again. Either branch may already
be applied to a database, so neither is re-parented.
"""

from typing import Sequence, Union

revision: str = "9c1e7a4b2d58"
down_revision: Union[str, Sequence[str], None] = ("f2b8c4d61a37", "c4e9a2f71b35")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
