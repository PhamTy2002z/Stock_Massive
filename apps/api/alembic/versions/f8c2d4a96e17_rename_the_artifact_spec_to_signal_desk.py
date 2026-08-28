"""rename the artifact spec to signal desk

Revision ID: f8c2d4a96e17
Revises: e6b3d90c41af
Create Date: 2026-08-28 18:50:00.000000

The surface a Study draws on is the Signal Desk; the column that holds its
layout takes the same name. A column rename is a catalog change only — no row
is rewritten — and it reverses cleanly.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f8c2d4a96e17"
down_revision: Union[str, None] = "e6b3d90c41af"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("agent_artifact", "canvas_spec", new_column_name="signal_desk_spec")


def downgrade() -> None:
    op.alter_column("agent_artifact", "signal_desk_spec", new_column_name="canvas_spec")
