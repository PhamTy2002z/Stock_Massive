"""keep a reader's own preferences

Revision ID: ce858b22360a
Revises: e6a21b7c4d90
Create Date: 2026-09-27 13:30:00.000000

One JSONB column on `users`, holding what the Settings screen writes: a
nickname, an investing style, free-text instructions about presentation, and
whether the memory tools may run for this account.

A document rather than four columns because every key is optional, read as a
whole and written as a merge, and the shape is owned by one pydantic model
(`auth.schemas.UserPreferences`) that parses it leniently — an unknown key is
ignored and a missing one takes its default, so adding a preference later needs
no migration and a row written before it still reads.

NOT NULL with `'{}'` as the server default: every existing account reads as
"no preferences set", which is exactly true, and there is no third state where
the column is null and the parser has to guess what that meant.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "ce858b22360a"
down_revision: Union[str, None] = "e6a21b7c4d90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "preferences",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "preferences")
