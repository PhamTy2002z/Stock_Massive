"""add market context tables

Revision ID: 20251221150022
Revises: 60811b8fd9e3
Create Date: 2025-12-21 15:00:22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251221150022'
down_revision: Union[str, None] = '60811b8fd9e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create stock_daily_returns table
    op.create_table(
        'stock_daily_returns',
        sa.Column('symbol', sa.String(10), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('close_price', sa.Numeric(12, 2), nullable=False),
        sa.Column('return_1d', sa.Numeric(10, 6), nullable=True),
        sa.Column('return_1d_log', sa.Numeric(10, 6), nullable=True),
        sa.PrimaryKeyConstraint('symbol', 'date')
    )
    op.create_index('ix_stock_daily_returns_symbol', 'stock_daily_returns', ['symbol'])
    op.create_index('ix_stock_daily_returns_date', 'stock_daily_returns', ['date'])
    op.create_index('ix_stock_daily_returns_symbol_date', 'stock_daily_returns', ['symbol', 'date'])

    # Create stock_market_metrics table
    op.create_table(
        'stock_market_metrics',
        sa.Column('symbol', sa.String(10), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('corr_5d', sa.Numeric(6, 4), nullable=True),
        sa.Column('corr_20d', sa.Numeric(6, 4), nullable=True),
        sa.Column('corr_60d', sa.Numeric(6, 4), nullable=True),
        sa.Column('beta_20d', sa.Numeric(8, 4), nullable=True),
        sa.Column('beta_60d', sa.Numeric(8, 4), nullable=True),
        sa.Column('rs_market_20d', sa.Numeric(8, 4), nullable=True),
        sa.Column('corr_sector_20d', sa.Numeric(6, 4), nullable=True),
        sa.Column('rs_sector_20d', sa.Numeric(8, 4), nullable=True),
        sa.Column('sector_rank', sa.Integer(), nullable=True),
        sa.Column('sector_total', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('symbol', 'date')
    )
    op.create_index('ix_stock_market_metrics_symbol', 'stock_market_metrics', ['symbol'])
    op.create_index('ix_stock_market_metrics_date', 'stock_market_metrics', ['date'])
    op.create_index('ix_stock_market_metrics_symbol_date', 'stock_market_metrics', ['symbol', 'date'])

    # Create sector_daily_benchmark table
    op.create_table(
        'sector_daily_benchmark',
        sa.Column('icb_code', sa.String(10), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('mcap_weighted_return', sa.Numeric(10, 6), nullable=False),
        sa.Column('total_mcap', sa.BigInteger(), nullable=False),
        sa.Column('stock_count', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('icb_code', 'date')
    )
    op.create_index('ix_sector_daily_benchmark_icb_code', 'sector_daily_benchmark', ['icb_code'])
    op.create_index('ix_sector_daily_benchmark_date', 'sector_daily_benchmark', ['date'])
    op.create_index('ix_sector_daily_benchmark_icb_date', 'sector_daily_benchmark', ['icb_code', 'date'])


def downgrade() -> None:
    # Drop sector_daily_benchmark table
    op.drop_index('ix_sector_daily_benchmark_icb_date', table_name='sector_daily_benchmark')
    op.drop_index('ix_sector_daily_benchmark_date', table_name='sector_daily_benchmark')
    op.drop_index('ix_sector_daily_benchmark_icb_code', table_name='sector_daily_benchmark')
    op.drop_table('sector_daily_benchmark')

    # Drop stock_market_metrics table
    op.drop_index('ix_stock_market_metrics_symbol_date', table_name='stock_market_metrics')
    op.drop_index('ix_stock_market_metrics_date', table_name='stock_market_metrics')
    op.drop_index('ix_stock_market_metrics_symbol', table_name='stock_market_metrics')
    op.drop_table('stock_market_metrics')

    # Drop stock_daily_returns table
    op.drop_index('ix_stock_daily_returns_symbol_date', table_name='stock_daily_returns')
    op.drop_index('ix_stock_daily_returns_date', table_name='stock_daily_returns')
    op.drop_index('ix_stock_daily_returns_symbol', table_name='stock_daily_returns')
    op.drop_table('stock_daily_returns')
