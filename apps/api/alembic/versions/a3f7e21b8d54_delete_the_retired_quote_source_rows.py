"""delete the retired quote source rows

Revision ID: a3f7e21b8d54
Revises: f8c2d4a96e17
Create Date: 2026-08-29 00:20:11.000000

Data rather than schema: the table stays and one source's rows leave it.

Packaged as a revision instead of run as a one-off statement so that the
deletion is replayable and reviewable. A one-off `DELETE` against one machine's
database is a change no other environment can reproduce and no reviewer can read
as a diff, which for a permanent removal is the wrong record to leave.

The rows belong to a quote source whose licence does not permit redistributing
what it served. Nothing reads them: sessions come off the daily spine, and the
valuation rows never had a reader at all. What is removed here cannot be
collected again, so `downgrade` refuses rather than pretending otherwise.

The guard below is the point of the whole revision. A count that does not match
means this database is not the one the removal was measured against, and the
transaction is abandoned instead of removing whatever it happens to find.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f7e21b8d54'
down_revision: Union[str, None] = 'f8c2d4a96e17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: The source being retired, as it is spelled in the column.
RETIRED_SOURCE = "fiinquant"

#: What this database held when the removal was measured, per capability. An
#: equality rather than a floor: a database holding more rows than this under the
#: same source is one whose contents this revision has not been checked against.
EXPECTED_BY_CAPABILITY = {
    "market": 36_528,
    "valuation": 35_245,
}
EXPECTED_TOTAL = sum(EXPECTED_BY_CAPABILITY.values())


def upgrade() -> None:
    """Remove the retired source's rows, or abandon the transaction."""
    bind = op.get_bind()

    measured = dict(
        bind.execute(
            sa.text(
                "SELECT capability, count(*) FROM provider_snapshots "
                "WHERE source = :source GROUP BY capability"
            ),
            {"source": RETIRED_SOURCE},
        ).all()
    )

    # Nothing to do rather than a failure: a database that has already had this
    # applied — or never held the source at all — is in the state this revision
    # exists to produce, and re-running a migration must not be an error.
    if not measured:
        return

    if measured != EXPECTED_BY_CAPABILITY:
        raise RuntimeError(
            "refusing to delete: this database does not hold the row counts "
            f"this removal was measured against. expected "
            f"{EXPECTED_BY_CAPABILITY}, found {measured}. Restore is "
            "backups/pre-retire-fiinquant-provider-snapshots-260829.sql.gz; "
            "re-measure before changing the numbers above."
        )

    removed = bind.execute(
        sa.text("DELETE FROM provider_snapshots WHERE source = :source"),
        {"source": RETIRED_SOURCE},
    ).rowcount

    if removed != EXPECTED_TOTAL:
        raise RuntimeError(
            f"refusing to commit: deleted {removed} rows, expected "
            f"{EXPECTED_TOTAL}. The transaction is being abandoned."
        )


def downgrade() -> None:
    raise NotImplementedError(
        "The rows cannot be collected again: the source's licence does not "
        "permit redistributing them. Load "
        "backups/pre-retire-fiinquant-provider-snapshots-260829.sql.gz into the "
        "running database instead — a whole-database restore would also discard "
        "every Turn, artifact and daily bar written since the dump."
    )
