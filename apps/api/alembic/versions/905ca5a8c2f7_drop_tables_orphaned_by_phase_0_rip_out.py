"""drop tables orphaned by Phase 0 rip-out

Revision ID: 905ca5a8c2f7
Revises: e2c4a7d19b63
Create Date: 2026-08-26 19:42:53.320521

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '905ca5a8c2f7'
down_revision: Union[str, None] = 'e2c4a7d19b63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove storage whose owning runtime features were ripped in Phase 0."""
    op.drop_table("analysis_tool_call")
    op.drop_table("analysis_run")
    op.drop_table("watchlist_entries")
    op.drop_table("analysis")
    op.drop_table("cohort_members")
    op.drop_table("cohort_versions")
    op.drop_table("profit_ranking_census_runs")
    op.drop_table("symbol_backfills")
    op.drop_table("stock_intraday_bars")
    op.drop_table("stock_daily_ohlcv")


def downgrade() -> None:
    raise NotImplementedError(
        "restore from backups/pre-rip-out-260825.sql.gz"
    )
