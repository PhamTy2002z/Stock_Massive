"""stamp Price Basis on every stored market session

Revision ID: d1f4b7c02e93
Revises: e7a2c9b41f58
Create Date: 2026-08-13 18:00:00

Data only: no column is added, because the basis lives in the payload where the
rest of the Snapshot lives.

The repair needs no provider call and no truncation. Every FiinQuant candle
call has carried ``adjusted=False`` since the day it was written, and the
vnstock quote history has no raw option at all — so every stored row already
*is* what it will be stamped. What is missing is only that the rows do not say
so, and saying so is an in-place ``UPDATE``.

It has to be an update rather than a re-collection: ``schema_version`` is part
of ``uq_provider_snapshot_identity``, so re-fetching the same sessions under 2
would write a second row beside the first for every session in the store.
"""

import logging
from typing import Any, NamedTuple, Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1f4b7c02e93"
down_revision: Union[str, None] = "e7a2c9b41f58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


logger = logging.getLogger("alembic.runtime.migration")

MARKET = "market"
UNSTAMPED_SCHEMA_VERSION = 1
STAMPED_SCHEMA_VERSION = 2
PRICE_BASIS_KEY = "price_basis"

# The payload carries its own copy of the schema version inside ``metadata``,
# and the two have to move together. A row whose column says 2 while its payload
# still says 1 would be re-collected under the payload's version and land beside
# itself — the identity constraint reads the column, and the Adapter builds the
# column from the payload it holds.
METADATA_KEY = "metadata"
SCHEMA_VERSION_KEY = "schema_version"

# Which basis each source's rows have always had. Keyed on ``source`` because
# that is what determined it for every row written before this ran, and it stops
# determining it the moment either provider's flag changes — which is why the
# basis is being moved onto the row rather than left to be inferred.
#
# Spelled out rather than imported from ``src.stocks.providers.contracts``: a
# migration is a record of what the data looked like on the day it ran, and
# importing the application would let a later rename silently rewrite that
# record. ``tests/test_price_basis_repair.py`` holds the two spellings in step.
BASIS_BY_SOURCE = {
    "fiinquant": "raw",
    "vnstock": "adjusted_at_source",
}


snapshots = sa.Table(
    "provider_snapshots",
    sa.MetaData(),
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("capability", sa.String(32)),
    sa.Column("symbol", sa.String(20)),
    sa.Column("source", sa.String(32)),
    sa.Column("effective_at", sa.DateTime(timezone=True)),
    sa.Column("schema_version", sa.Integer),
    sa.Column("payload", sa.JSON),
)


def _versioned(payload: dict, schema_version: int) -> dict:
    """The payload with its own copy of the schema version moved with it."""
    metadata = {**payload.get(METADATA_KEY, {}), SCHEMA_VERSION_KEY: schema_version}
    return {**payload, METADATA_KEY: metadata}


class RepairReport(NamedTuple):
    """What the repair did, in rows.

    ``superseded`` is the count of unstamped rows dropped because the same
    session already exists under the stamped version — a session the collector
    re-read after the new code shipped but before this ran. Keeping both would
    be the second row this whole approach exists to avoid, and the stamped one
    is the same session written by an adapter that knows its own basis.
    """

    stamped: int
    superseded: int


def _identities(connection: Any, schema_version: int) -> set[tuple]:
    """Which sessions the store already holds at this schema version."""
    return {
        (row.symbol, row.source, row.effective_at)
        for row in connection.execute(
            sa.select(
                snapshots.c.symbol,
                snapshots.c.source,
                snapshots.c.effective_at,
            ).where(
                snapshots.c.capability == MARKET,
                snapshots.c.schema_version == schema_version,
            )
        )
    }


def _rewrite(connection: Any, updates: list[dict], schema_version: int) -> None:
    """Write the rewritten payloads back, one statement for all of them."""
    if not updates:
        return
    connection.execute(
        snapshots.update()
        .where(snapshots.c.id == sa.bindparam("row_id"))
        .values(
            payload=sa.bindparam("new_payload", type_=sa.JSON),
            schema_version=schema_version,
        ),
        updates,
    )


def stamp_market_price_basis(connection: Any) -> RepairReport:
    """Stamp every unstamped market payload with the basis its source wrote.

    Idempotent: it selects on ``schema_version`` 1, so a second run finds
    nothing and reports zero. Re-runnable for the same reason — nothing here
    depends on having been run exactly once.

    A source with no known basis stops the repair rather than being guessed at.
    An invented basis is worse than an unstamped row: the row would then be read
    as a measurement it never was, by every window that follows.
    """
    already_stamped = _identities(connection, STAMPED_SCHEMA_VERSION)

    updates: list[dict] = []
    superseded: list[int] = []
    for row in connection.execute(
        sa.select(
            snapshots.c.id,
            snapshots.c.symbol,
            snapshots.c.source,
            snapshots.c.effective_at,
            snapshots.c.payload,
        ).where(
            snapshots.c.capability == MARKET,
            snapshots.c.schema_version == UNSTAMPED_SCHEMA_VERSION,
        )
    ):
        basis = BASIS_BY_SOURCE.get(row.source)
        if basis is None:
            raise RuntimeError(
                f"no Price Basis is known for market rows from {row.source!r}; "
                "add it to BASIS_BY_SOURCE before running this repair"
            )
        if (row.symbol, row.source, row.effective_at) in already_stamped:
            superseded.append(row.id)
            continue
        updates.append(
            {
                "row_id": row.id,
                "new_payload": _versioned(
                    {**row.payload, PRICE_BASIS_KEY: basis},
                    STAMPED_SCHEMA_VERSION,
                ),
            }
        )

    if superseded:
        connection.execute(snapshots.delete().where(snapshots.c.id.in_(superseded)))
    _rewrite(connection, updates, STAMPED_SCHEMA_VERSION)
    return RepairReport(stamped=len(updates), superseded=len(superseded))


def unstamp_market_price_basis(connection: Any) -> int:
    """Put the market payloads back the way version 1 held them, and count them.

    The mirror image, and it makes the same assumption in reverse: after an
    upgrade no market row is left at version 1, so nothing collides. A store
    holding both versions at once is a repair that was interrupted, and there
    the identity constraint refuses rather than this quietly choosing a winner.

    It returns a plain count rather than a ``RepairReport``: a downgrade stamps
    nothing and supersedes nothing, so both of that type's fields would be
    answering a question this never asks. What it cannot undo is the rows the
    upgrade dropped as superseded — those were re-collected copies, and the
    session each of them held is still in the store.
    """
    updates = [
        {
            "row_id": row.id,
            "new_payload": _versioned(
                {
                    key: value
                    for key, value in row.payload.items()
                    if key != PRICE_BASIS_KEY
                },
                UNSTAMPED_SCHEMA_VERSION,
            ),
        }
        for row in connection.execute(
            sa.select(snapshots.c.id, snapshots.c.payload).where(
                snapshots.c.capability == MARKET,
                snapshots.c.schema_version == STAMPED_SCHEMA_VERSION,
            )
        )
    ]
    _rewrite(connection, updates, UNSTAMPED_SCHEMA_VERSION)
    return len(updates)


def upgrade() -> None:
    report = stamp_market_price_basis(op.get_bind())
    logger.info(
        "Price Basis: stamped %s market session(s); dropped %s already re-collected "
        "under schema version %s",
        report.stamped,
        report.superseded,
        STAMPED_SCHEMA_VERSION,
    )


def downgrade() -> None:
    logger.info(
        "Price Basis: unstamped %s market session(s)",
        unstamp_market_price_basis(op.get_bind()),
    )
