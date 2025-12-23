"""rename top_performers to financial_statements

Revision ID: a1b2c3d4
Revises: 6948fc67
Create Date: 2025-12-23 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4'
down_revision: Union[str, None] = '6948fc67'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old indexes first
    op.drop_index('ix_top_performers_exchange', table_name='top_performers')
    op.drop_index('ix_top_performers_period', table_name='top_performers')
    op.drop_index(op.f('ix_top_performers_rank'), table_name='top_performers')
    op.drop_index(op.f('ix_top_performers_symbol'), table_name='top_performers')

    # Drop old constraint
    op.drop_constraint('uq_top_performers_symbol_period', 'top_performers', type_='unique')

    # Rename table
    op.rename_table('top_performers', 'financial_statements')

    # Recreate indexes with new names
    op.create_index(op.f('ix_financial_statements_symbol'), 'financial_statements', ['symbol'], unique=False)
    op.create_index(op.f('ix_financial_statements_rank'), 'financial_statements', ['rank'], unique=False)
    op.create_index('ix_financial_statements_period', 'financial_statements', ['year', 'quarter'], unique=False)
    op.create_index('ix_financial_statements_exchange', 'financial_statements', ['exchange'], unique=False)

    # Recreate unique constraint with new name
    op.create_unique_constraint('uq_financial_statements_symbol_period', 'financial_statements', ['symbol', 'year', 'quarter'])


def downgrade() -> None:
    # Drop new indexes
    op.drop_index('ix_financial_statements_exchange', table_name='financial_statements')
    op.drop_index('ix_financial_statements_period', table_name='financial_statements')
    op.drop_index(op.f('ix_financial_statements_rank'), table_name='financial_statements')
    op.drop_index(op.f('ix_financial_statements_symbol'), table_name='financial_statements')

    # Drop new constraint
    op.drop_constraint('uq_financial_statements_symbol_period', 'financial_statements', type_='unique')

    # Rename table back
    op.rename_table('financial_statements', 'top_performers')

    # Recreate old indexes
    op.create_index(op.f('ix_top_performers_symbol'), 'top_performers', ['symbol'], unique=False)
    op.create_index(op.f('ix_top_performers_rank'), 'top_performers', ['rank'], unique=False)
    op.create_index('ix_top_performers_period', 'top_performers', ['year', 'quarter'], unique=False)
    op.create_index('ix_top_performers_exchange', 'top_performers', ['exchange'], unique=False)

    # Recreate old unique constraint
    op.create_unique_constraint('uq_top_performers_symbol_period', 'top_performers', ['symbol', 'year', 'quarter'])
