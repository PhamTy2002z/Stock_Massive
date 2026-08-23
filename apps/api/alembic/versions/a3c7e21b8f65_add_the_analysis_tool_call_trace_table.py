"""add the analysis_tool_call trace table

An Analysis produced by a loop is no longer rebuildable from the store. That
property is stated in ``src/alpha/envelope.py`` — *"an Analysis rebuilt tomorrow
from the same store has to say the same thing, and a live call is a number
nobody can rebuild"* — and giving it up with nothing in return is a pure
downgrade. What is bought back is audit: what the loop asked for, what came
back, in what order. So this table lands before the loop does, not after.

Anchored to ``analysis_run``, not to ``analysis``. A run exists before an
Analysis does, so ``analysis.id`` is not available when the first tool call is
made; anchoring there would orphan the trace exactly when a run dies mid-flight
and the trace is the most valuable thing left. ``ON DELETE CASCADE`` follows
from that: the run is the owner.

Order is ``UNIQUE(run_id, round_index, seq)`` rather than a timestamp, for the
same reason ``agent_message`` orders by ``seq``: two calls dispatched together
in one round share a millisecond, and a timestamp cannot express inserting
between two rows. That constraint's index also serves the only query this table
has — one run's whole trace, in order — so there is no second index, and none on
``started_at``: nothing sweeps this table by age.

A separate table rather than two nullable columns on ``agent_tool_call``. That
table's anchors are NOT NULL foreign keys to a Thread and a message and an
Analysis Run has neither; widening it would teach every existing reader that two
columns it relies on can now be null, and would leave two retention policies —
the chat trace swept at 90 days, an Analysis trace living as long as its
Analysis — competing over one ``started_at``.

Additive: one CREATE TABLE, no existing table touched, no backfill.

Revision ID: a3c7e21b8f65
Revises: f1a2b7c39d40
Create Date: 2026-08-22 21:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a3c7e21b8f65'
down_revision: Union[str, None] = 'f1a2b7c39d40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'analysis_tool_call',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.BigInteger(), nullable=False),
        # Does not reset between the three attempts of one pair: one run row
        # serves all of them, so the counter keeps climbing across attempts.
        sa.Column('round_index', sa.Integer(), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('tool_name', sa.String(length=64), nullable=False),
        sa.Column('tool_call_id', sa.String(length=128), nullable=True),
        sa.Column('arguments', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        # ok | tool_error | timeout | unknown_tool | blocked
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('error', sa.String(length=500), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column(
            'started_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['run_id'], ['analysis_run.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'run_id',
            'round_index',
            'seq',
            name='uq_analysis_tool_call_run_round_seq',
        ),
    )


def downgrade() -> None:
    op.drop_table('analysis_tool_call')
