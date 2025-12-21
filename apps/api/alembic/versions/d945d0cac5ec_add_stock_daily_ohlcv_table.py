"""add stock_daily_ohlcv table

Revision ID: d945d0cac5ec
Revises: 60811b8fd9e3
Create Date: 2025-12-21 20:23:48.182685

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd945d0cac5ec'
down_revision: Union[str, None] = '60811b8fd9e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Only create the new table, keep existing tables
    op.create_table('stock_daily_ohlcv',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('symbol', sa.String(length=10), nullable=False),
    sa.Column('trade_date', sa.Date(), nullable=False),
    sa.Column('open_price', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('high_price', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('low_price', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('close_price', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('volume', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('symbol', 'trade_date', name='uq_daily_symbol_date')
    )
    op.create_index('idx_daily_symbol_date', 'stock_daily_ohlcv', ['symbol', 'trade_date'], unique=False)
    op.create_index(op.f('ix_stock_daily_ohlcv_symbol'), 'stock_daily_ohlcv', ['symbol'], unique=False)


def downgrade() -> None:
    # Drop the new table only
    op.drop_index(op.f('ix_stock_daily_ohlcv_symbol'), table_name='stock_daily_ohlcv')
    op.drop_index('idx_daily_symbol_date', table_name='stock_daily_ohlcv')
    op.drop_table('stock_daily_ohlcv')
