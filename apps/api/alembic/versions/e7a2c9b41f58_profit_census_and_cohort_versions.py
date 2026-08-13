"""add the listing roster, the profit census and Cohort Versions; drop financial_statements

Revision ID: e7a2c9b41f58
Revises: c4e8f2a10b73
Create Date: 2026-08-13 12:00:00

The drop is in the same revision as the creates on purpose. `financial_statements`
ranked quarterly profit across HOSE and HNX, which is the question the census now
answers from a different shape of data. Kept alongside, the two would answer "the
most profitable listed companies" differently — one from a single quarter, one from
trailing twelve months at a period the market has actually reported — and both
would look authoritative.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7a2c9b41f58"
down_revision: Union[str, None] = "c4e8f2a10b73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The market's listing register. Its own table rather than provider_snapshots:
    # that table holds per-symbol observations for symbols the Universe names, and
    # this is every listed company on the market — which is what the census has to
    # know before it can choose fifty of them.
    op.create_table(
        "listing_roster",
        sa.Column("symbol", sa.String(length=20), primary_key=True),
        sa.Column("exchange", sa.String(length=10), nullable=False),
        sa.Column("is_listed", sa.Boolean(), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_listing_roster_exchange_listed",
        "listing_roster",
        ["exchange", "is_listed"],
    )

    # One row per census pass. Durable because a pass is quota-bound and long:
    # a later run resumes against these figures rather than reading the market
    # again from the top.
    op.create_table(
        "profit_ranking_census_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("target_period", sa.Date(), nullable=True),
        sa.Column(
            "eligible_symbols",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "covered_symbols",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("last_error", sa.String(length=500), nullable=True),
    )

    op.create_table(
        "cohort_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("reporting_period", sa.Date(), nullable=False),
        sa.Column(
            "census_run_id",
            sa.Integer(),
            sa.ForeignKey("profit_ranking_census_runs.id"),
            nullable=False,
        ),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("coverage_at_activation", sa.Integer(), nullable=True),
    )
    # At most one active version, enforced here rather than in the activation
    # code: two concurrent activations would both believe they were promoting the
    # newest ranking, and the loser has to fail rather than leave two cohorts
    # being served at once.
    op.create_index(
        "uq_cohort_version_single_active",
        "cohort_versions",
        ["state"],
        unique=True,
        postgresql_where=sa.text("state = 'active'"),
        sqlite_where=sa.text("state = 'active'"),
    )
    # Resolving which version was active on a past day scans the activation
    # window; it never wants the newest row.
    op.create_index(
        "ix_cohort_version_activation_window",
        "cohort_versions",
        ["activated_at", "superseded_at"],
    )

    op.create_table(
        "cohort_members",
        sa.Column(
            "cohort_version_id",
            sa.Integer(),
            sa.ForeignKey("cohort_versions.id"),
            primary_key=True,
        ),
        sa.Column("symbol", sa.String(length=20), primary_key=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("net_income_vnd", sa.Numeric(24, 2), nullable=False),
        sa.Column("exchange", sa.String(length=10), nullable=False),
        sa.UniqueConstraint(
            "cohort_version_id",
            "rank",
            name="uq_cohort_member_rank",
        ),
    )

    # Superseded by the census. See the module docstring above.
    op.drop_table("financial_statements")


def downgrade() -> None:
    # Recreated as it was, indexes included. The rows are not recoverable: the
    # ranking they held was quarterly single-quarter profit, which nothing in the
    # new tables stores.
    op.create_table(
        "financial_statements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(length=10), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("exchange", sa.String(length=10), nullable=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("quarter", sa.Integer(), nullable=False),
        sa.Column("net_profit", sa.BigInteger(), nullable=True),
        sa.Column("revenue", sa.BigInteger(), nullable=True),
        sa.Column("profit_margin", sa.Float(), nullable=True),
        sa.Column("eps", sa.Float(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "symbol",
            "year",
            "quarter",
            name="uq_financial_statements_symbol_period",
        ),
    )
    op.create_index("ix_financial_statements_symbol", "financial_statements", ["symbol"])
    op.create_index("ix_financial_statements_rank", "financial_statements", ["rank"])
    op.create_index(
        "ix_financial_statements_period",
        "financial_statements",
        ["year", "quarter"],
    )
    op.create_index(
        "ix_financial_statements_exchange",
        "financial_statements",
        ["exchange"],
    )

    op.drop_table("cohort_members")
    op.drop_index("ix_cohort_version_activation_window", table_name="cohort_versions")
    op.drop_index("uq_cohort_version_single_active", table_name="cohort_versions")
    op.drop_table("cohort_versions")
    op.drop_table("profit_ranking_census_runs")
    op.drop_index("ix_listing_roster_exchange_listed", table_name="listing_roster")
    op.drop_table("listing_roster")
