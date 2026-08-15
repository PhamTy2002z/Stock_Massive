"""record who asked for an Analysis Run

The on-demand allowance is three new Analyses per user per Trading Day, and
there was nowhere to count them from. ``analysis`` is keyed by
``(symbol, trading_day)`` precisely so it belongs to no user, and ``analysis_run``
carried *what* asked for a run (``origin``) but not *who*.

Nullable, and null is the common case: the nightly cohort is nobody's in
particular. ``ON DELETE SET NULL`` rather than CASCADE because an Analysis is
shared system-wide and outlives whoever triggered it — deleting an account must
not delete a session's production record.

Revision ID: f3b0d7c15a92
Revises: dbd106456567
Create Date: 2026-08-15 17:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f3b0d7c15a92'
down_revision: Union[str, None] = 'dbd106456567'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'analysis_run',
        sa.Column('requested_by_user_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_analysis_run_requested_by_user',
        'analysis_run',
        'users',
        ['requested_by_user_id'],
        ['id'],
        ondelete='SET NULL',
    )
    # The allowance is a count of one user's runs for one session, asked on
    # every Watchlist addition.
    op.create_index(
        'ix_analysis_run_requester_day',
        'analysis_run',
        ['requested_by_user_id', 'trading_day'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_analysis_run_requester_day', table_name='analysis_run')
    op.drop_constraint(
        'fk_analysis_run_requested_by_user', 'analysis_run', type_='foreignkey'
    )
    op.drop_column('analysis_run', 'requested_by_user_id')
