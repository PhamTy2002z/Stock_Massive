"""add top_performers table

Revision ID: 6948fc67
Revises: d945d0cac5ec
Create Date: 2025-12-22 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6948fc67'
down_revision: Union[str, None] = 'd945d0cac5ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('top_performers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('symbol', sa.String(length=10), nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=True),
        sa.Column('exchange', sa.String(length=10), nullable=True),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('quarter', sa.Integer(), nullable=False),
        sa.Column('net_profit', sa.BigInteger(), nullable=True),
        sa.Column('revenue', sa.BigInteger(), nullable=True),
        sa.Column('profit_margin', sa.Float(), nullable=True),
        sa.Column('eps', sa.Float(), nullable=True),
        sa.Column('rank', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('symbol', 'year', 'quarter', name='uq_top_performers_symbol_period')
    )
    op.create_index(op.f('ix_top_performers_symbol'), 'top_performers', ['symbol'], unique=False)
    op.create_index(op.f('ix_top_performers_rank'), 'top_performers', ['rank'], unique=False)
    op.create_index('ix_top_performers_period', 'top_performers', ['year', 'quarter'], unique=False)
    op.create_index('ix_top_performers_exchange', 'top_performers', ['exchange'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_top_performers_exchange', table_name='top_performers')
    op.drop_index('ix_top_performers_period', table_name='top_performers')
    op.drop_index(op.f('ix_top_performers_rank'), table_name='top_performers')
    op.drop_index(op.f('ix_top_performers_symbol'), table_name='top_performers')
    op.drop_table('top_performers')
