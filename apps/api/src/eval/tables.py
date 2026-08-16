"""Which store tables an Eval Fixture is cut from, and how a row round-trips.

Four tables, named once. Everything else the battery needs is either derived
from them by the real code — the Universe, the bar window, the Signal Registry —
or seated by the loader from the fixture's own manifest, which is a different
thing and is kept a different thing on purpose:

**Captured** is what was read out of the real store at one ``trading_day``.
Public market data, so no anonymisation is needed (``docs/adr/0016``).

**Seated** is what the battery needs in order to have an actor at all: an eval
user and its watchlist. Those are not market data and they are not captured —
a fixture carrying a real account's watchlist would be personal data frozen into
a repository artifact, and it would also make the fixture depend on whoever
happened to be logged in on capture day.

No ``cohort_versions``/``cohort_members`` here, and the omission is deliberate.
The Universe is pinned by the manifest as the declared half, so it is one
written-down list rather than a list plus a ranking that only means something
with all fifty of its members present. Capturing a cohort filtered down to the
fixture's symbols would store a top-fifty that is not a top-fifty.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, Numeric
from sqlalchemy.orm import DeclarativeBase

from src.alpha.models import Analysis
from src.stocks.models import CorporateAction, ListingRoster, ProviderSnapshot


@dataclass(frozen=True)
class CapturedTable:
    """One table the fixture holds, and the column that names its symbol."""

    model: type[DeclarativeBase]
    symbol_column: str
    # Excluded from the seed because the source database assigned it and the
    # eval database will assign its own. Kept out rather than carried and
    # ignored: a seed holding ids from another database invites a loader that
    # trusts them, and the first foreign key added later would silently point at
    # the wrong row.
    surrogate_key: str | None = "id"

    @property
    def name(self) -> str:
        return str(self.model.__tablename__)


# Load order is insert order. No foreign key runs between these four today, and
# the order is still fixed so that a seed file diffs cleanly across captures.
CAPTURED_TABLES: tuple[CapturedTable, ...] = (
    CapturedTable(model=ListingRoster, symbol_column="symbol", surrogate_key=None),
    CapturedTable(model=ProviderSnapshot, symbol_column="symbol"),
    CapturedTable(model=CorporateAction, symbol_column="symbol"),
    CapturedTable(model=Analysis, symbol_column="symbol"),
)

CAPTURED_TABLE_BY_NAME: Mapping[str, CapturedTable] = {
    table.name: table for table in CAPTURED_TABLES
}


def _columns(table: CapturedTable) -> Sequence[Any]:
    return [
        column
        for column in table.model.__table__.columns
        if column.name != table.surrogate_key
    ]


def encode_value(column: Any, value: Any) -> Any:
    """One stored value as JSON, losing neither its type nor its precision.

    ``Numeric`` becomes a string rather than a float. A net income in dong is
    twelve significant digits before the decimal point, and a float would round
    it — quietly, and only for the large companies a Profit Leaders fixture is
    made of.
    """
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(column.type, Numeric) and not isinstance(value, (int, str)):
        return str(value)
    return value


def decode_value(column: Any, value: Any) -> Any:
    """The inverse, driven by the column's declared type and nothing else."""
    if value is None:
        return None
    if isinstance(column.type, DateTime):
        return dt.datetime.fromisoformat(value)
    if isinstance(column.type, Date):
        return dt.date.fromisoformat(value)
    if isinstance(column.type, Numeric):
        return Decimal(str(value))
    return value


def encode_row(table: CapturedTable, row: Any) -> dict[str, Any]:
    """One ORM row as the seed holds it: sorted keys, no surrogate id."""
    return {
        column.name: encode_value(column, getattr(row, column.name))
        for column in sorted(_columns(table), key=lambda item: item.name)
    }


def decode_row(table: CapturedTable, payload: Mapping[str, Any]) -> Any:
    """One seed entry back into an unattached ORM instance."""
    columns = {column.name: column for column in _columns(table)}
    values = {
        name: decode_value(columns[name], value)
        for name, value in payload.items()
        if name in columns
    }
    return table.model(**values)


def store_schema_version() -> str:
    """A short digest of the shape the fixture was frozen against.

    Over the captured tables only. A column added to ``users`` cannot void a
    fixture made of market data, and a column added to ``provider_snapshots``
    must — the whole purpose of this string is that an old fixture read through
    new code fails loud instead of scoring well (``docs/adr/0016``).

    Names and types, not defaults or indexes: what changes the meaning of a
    captured row is what it holds, and an index moving does not.
    """
    digest = hashlib.sha256()
    for table in sorted(CAPTURED_TABLES, key=lambda item: item.name):
        digest.update(table.name.encode("utf-8"))
        for column in sorted(_columns(table), key=lambda item: item.name):
            digest.update(b"\x00")
            digest.update(column.name.encode("utf-8"))
            digest.update(b"\x00")
            digest.update(str(column.type).encode("utf-8"))
        digest.update(b"\x01")
    return digest.hexdigest()[:16]


__all__ = [
    "CAPTURED_TABLES",
    "CAPTURED_TABLE_BY_NAME",
    "CapturedTable",
    "decode_row",
    "decode_value",
    "encode_row",
    "encode_value",
    "store_schema_version",
]
