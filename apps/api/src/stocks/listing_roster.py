"""Reading the stored listing register — just enough for the surviving code.

The collector logic that filled this table (RosterRefresh, ListingRosterStore
mutation methods) was ripped out with the rest of the market-data plane. Only
the read side stays, because the Signal Field pack and the alpha envelope still
answer questions about which exchange a symbol sits on.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.stocks.models import ListingRoster

from .providers.contracts import Exchange


@dataclass(frozen=True)
class ListedIdentity:
    """Who a symbol is, as the register last saw it."""

    symbol: str
    exchange: Exchange
    company_name: str | None
    is_listed: bool
    icb_code: str | None = None
    icb_name: str | None = None


class ListingRosterStore:
    """Read the stored listing register."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def identity_of(self, symbol: str) -> ListedIdentity | None:
        row = self.session.execute(
            select(ListingRoster).where(ListingRoster.symbol == symbol.upper())
        ).scalar_one_or_none()
        if row is None:
            return None
        return ListedIdentity(
            symbol=row.symbol,
            exchange=Exchange(row.exchange),
            company_name=row.company_name,
            is_listed=bool(row.is_listed),
            icb_code=row.icb_code,
            icb_name=row.icb_name,
        )
