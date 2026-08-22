"""mark a message helpful

Revision ID: c4e81f37b6da
Revises: b7d2f5a10c93
Create Date: 2026-08-22 18:20:11.402318

One nullable timestamp on `agent_message`, and the shape is the point.

The flag is a pair — a reason and a stamp — because a dispute is only readable
if it says what went wrong. The positive mark has nothing to categorise, so it
is one column: set means the reader marked this answer helpful, null means they
did not. No vocabulary, no second column that could disagree with the first.

Nullable with no default and no backfill: every message written before this
revision is *unmarked*, which is exactly true, and a default of `now()` would
have invented a verdict for the whole transcript.

No index. The flag's index exists because the ops query counts flags by reason
over a date range; nothing counts helpful marks yet, and an index nothing reads
is a write-path cost on every message insert.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4e81f37b6da'
down_revision: Union[str, None] = 'b7d2f5a10c93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'agent_message',
        sa.Column('helpful_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('agent_message', 'helpful_at')
