"""carry the ICB classification on the listing register

Revision ID: b7e4c1d9a208
Revises: a365676b9d01
Create Date: 2026-08-16 09:00:00

Two columns rather than a table. The classification is reference data about a
listed company — the same kind of fact as the board it trades on, arriving from
the same market-wide register read, one row per company — so it belongs beside
`exchange` and not in `provider_snapshots`, which holds per-symbol observations
for the symbols the Universe has promised to follow.

Which narrows one sentence of ADR-0004: "Company name, exchange, listing status,
and ICB Level 2 remain reference data and are persisted for Universe members
through `ReferenceSnapshot`". That path covers Universe members, and this
classification is needed for every listed company — by the census before any of
them is in the Universe, and by the nightly Analysis pipeline for a symbol whose
Reference Snapshot may be months old. It is the same reason company name and
listing status already sit on this table rather than on a Snapshot; the ADR's
own `ReferenceSnapshot` never carried either of them, or an ICB code.

Nullable, because the register's classification read is best-effort. A refresh
that answered with a board and no industry list leaves the stored classification
alone rather than blanking it, so an existing row surviving this migration with
NULL is a symbol nobody has classified yet — which is exactly what the nightly
Analysis pipeline reports as `unclassified`.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7e4c1d9a208"
down_revision: Union[str, None] = "a365676b9d01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ICB level 2 — four characters, which is the whole of a supersector code.
    op.add_column(
        "listing_roster",
        sa.Column("icb_code", sa.String(length=4), nullable=True),
    )
    op.add_column(
        "listing_roster",
        sa.Column("icb_name", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("listing_roster", "icb_name")
    op.drop_column("listing_roster", "icb_code")
