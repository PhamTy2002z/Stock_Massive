"""address a tool call trace by its call id, and note when its result was previewed

Revision ID: a4c71d9e5b28
Revises: c6f8a1d42e70
Create Date: 2026-08-21 22:55:12.104338

Two nullable columns on `agent_tool_call`, both additive, and neither one is
backfillable — which is why they are nullable rather than defaulted.

`tool_call_id` is the route's own identifier for the call, and it is also the id
the model cites in an evidence reference. Without it a citation and the row
holding the result it names can only be joined by guessing from the tool name and
the arguments, which is ambiguous exactly when it matters: one tool asked twice
in a Turn. Rows written before this migration have an id that was never stored
and cannot be recovered, so they keep NULL.

`spilled_bytes` records that the model was shown a preview of this result rather
than the whole of it (`agent/tools/spillover.py`), and how large the whole was.
The column is what makes the spill threshold tunable against measurement instead
of judgement: a Turn that answered worse after a spill is only diagnosable if the
spill left a record. NULL means the model saw the result entire, which is the
ordinary case and every case before this branch.

No index. Both columns are read by an operator asking about one request message,
and `ix_agent_tool_call_request_message` already answers that; an index on a
column that is NULL for almost every row would be paid for on every insert to
serve a query nobody runs yet.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a4c71d9e5b28'
down_revision: Union[str, None] = 'c6f8a1d42e70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'agent_tool_call',
        sa.Column('tool_call_id', sa.String(length=128), nullable=True),
    )
    op.add_column(
        'agent_tool_call',
        sa.Column('spilled_bytes', sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('agent_tool_call', 'spilled_bytes')
    op.drop_column('agent_tool_call', 'tool_call_id')
