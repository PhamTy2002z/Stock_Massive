"""add LLM spend admission dimensions

Revision ID: a365676b9d01
Revises: f3b0d7c15a92
Create Date: 2026-08-15 22:10:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a365676b9d01"
down_revision: Union[str, None] = "f3b0d7c15a92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("llm_call_usage", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column("llm_call_usage", sa.Column("lane", sa.String(16), nullable=True))
    op.add_column(
        "llm_call_usage",
        sa.Column(
            "reserved_input_tokens",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "llm_call_usage",
        sa.Column(
            "reserved_output_tokens",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "llm_call_usage",
        sa.Column("provider_called_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(
        """
        UPDATE llm_call_usage
        SET lane = CASE owner_type
            WHEN 'analysis_run' THEN 'analysis'
            WHEN 'turn_request_message' THEN 'turn'
            WHEN 'capability_probe' THEN 'emergency'
            WHEN 'eval_run' THEN 'eval'
            ELSE 'emergency'
        END,
        provider_called_at = created_at
        """
    )
    op.alter_column("llm_call_usage", "lane", nullable=False)
    op.alter_column("llm_call_usage", "provider_called_at", nullable=False)
    op.create_index(
        "ix_llm_call_usage_lane_called",
        "llm_call_usage",
        ["lane", "provider_called_at"],
        unique=False,
    )
    op.create_index(
        "ix_llm_call_usage_user_called",
        "llm_call_usage",
        ["user_id", "provider_called_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_llm_call_usage_user_called", table_name="llm_call_usage")
    op.drop_index("ix_llm_call_usage_lane_called", table_name="llm_call_usage")
    op.drop_column("llm_call_usage", "provider_called_at")
    op.drop_column("llm_call_usage", "reserved_output_tokens")
    op.drop_column("llm_call_usage", "reserved_input_tokens")
    op.drop_column("llm_call_usage", "lane")
    op.drop_column("llm_call_usage", "user_id")
