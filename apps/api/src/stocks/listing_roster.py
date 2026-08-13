"""What the exchanges currently list, held so a census has something to rank.

The Profit Ranking Census needs a market to census: which companies are listed,
on which board, and whether they still are. No adapter answered that before —
every provider contract in this system is keyed on a symbol the Universe already
names, and the whole point here is the symbols it does not.

This is reference data about the market rather than a Snapshot about a company,
so it lives in its own table (``docs/adr/0004``). It is also the only place that
can notice a company leaving: a listing register lists who is *in* it, so a
delisting is an absence, and an absence is only visible against what was there
before.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.stocks.models import ListingRoster

from .providers import Exchange, ListingEntry, ListingRosterProvider, ProviderSource

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RosterRefresh:
    """What one refresh of the register changed.

    ``newly_delisted`` is the answer ADR-0003 asks for: it names the symbols that
    were listed the last time we looked and are not now, which is what has to
    trigger a replacement in an active Profit Leaders Cohort. It is deliberately
    only the *newly* delisted — a company that left months ago has already been
    replaced, and re-reporting it every week would ask the cohort to rebuild
    itself over nothing.
    """

    listed: int
    newly_listed: tuple[str, ...]
    newly_delisted: tuple[str, ...]

    def as_result(self) -> dict:
        return {
            "listed": self.listed,
            "newly_listed": list(self.newly_listed),
            "newly_delisted": list(self.newly_delisted),
        }


class ListingRosterStore:
    """Read and replace the stored listing register."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def refresh(
        self,
        entries: Sequence[ListingEntry],
        source: ProviderSource,
        observed_at: datetime | None = None,
    ) -> RosterRefresh:
        """Write the register as it stands now and report what moved.

        A symbol the register no longer carries is marked delisted rather than
        deleted. Deleted, a cohort member that left the exchange would simply
        stop matching a query and the cohort would go on serving a company that
        no longer trades — the absence has to be recorded to be acted on.

        Refusing an empty refresh is the one hard rule here: an adapter that
        answered with nothing looks exactly like an exchange that closed, and
        taking it at face value would delist the entire market in one write.
        """
        if not entries:
            raise ValueError(
                "a listing roster refresh cannot be empty: it would delist the "
                "whole market"
            )

        stamped = observed_at or datetime.now(timezone.utc)
        stored = {row.symbol: row for row in self._all()}
        incoming = {entry.symbol: entry for entry in entries}

        newly_listed: list[str] = []
        for symbol, entry in incoming.items():
            row = stored.get(symbol)
            if row is None:
                self.session.add(
                    ListingRoster(
                        symbol=symbol,
                        exchange=entry.exchange.value,
                        is_listed=True,
                        company_name=entry.company_name,
                        source=source.value,
                        observed_at=stamped,
                    )
                )
                newly_listed.append(symbol)
                continue

            if not row.is_listed:
                # A company that relisted, or one that moved boards and came
                # back. Recorded as newly listed because that is what it is to
                # every reader downstream: a symbol that was not rankable and
                # now is.
                newly_listed.append(symbol)
            row.exchange = entry.exchange.value
            row.is_listed = True
            row.company_name = entry.company_name
            row.source = source.value
            row.observed_at = stamped

        newly_delisted: list[str] = []
        for symbol, row in stored.items():
            if symbol in incoming or not row.is_listed:
                continue
            row.is_listed = False
            row.observed_at = stamped
            newly_delisted.append(symbol)

        self.session.flush()
        logger.info(
            "Listing roster refreshed: %d listed, %d new, %d delisted",
            len(incoming),
            len(newly_listed),
            len(newly_delisted),
        )
        return RosterRefresh(
            listed=len(incoming),
            newly_listed=tuple(sorted(newly_listed)),
            newly_delisted=tuple(sorted(newly_delisted)),
        )

    def listed_symbols(self, exchanges: Iterable[Exchange]) -> tuple[str, ...]:
        """The symbols currently listed on these boards, alphabetically.

        Ordered so a census resuming after an interruption walks the market in
        the same order it walked before, and ``covered_symbols`` therefore means
        "the first N of this list" rather than "N symbols, we no longer know
        which".
        """
        wanted = [exchange.value for exchange in exchanges]
        if not wanted:
            return ()
        rows = self.session.execute(
            select(ListingRoster.symbol)
            .where(
                ListingRoster.exchange.in_(wanted),
                ListingRoster.is_listed.is_(True),
            )
            .order_by(ListingRoster.symbol.asc())
        ).scalars()
        return tuple(rows)

    def exchange_of(self, symbol: str) -> Exchange | None:
        """Which board this symbol is listed on, or None if it is not listed."""
        row = self.session.execute(
            select(ListingRoster).where(ListingRoster.symbol == symbol.upper())
        ).scalar_one_or_none()
        if row is None or not row.is_listed:
            return None
        return Exchange(row.exchange)

    def delisted_among(self, symbols: Iterable[str]) -> tuple[str, ...]:
        """Which of these symbols the register no longer lists.

        A symbol the register has never carried is not reported: this answers
        "who left", and nothing can be said to have left a register it was never
        in. That is what keeps a roster refresh that failed for one board from
        reading as a mass delisting downstream.
        """
        wanted = [symbol.upper() for symbol in symbols]
        if not wanted:
            return ()
        rows = self.session.execute(
            select(ListingRoster.symbol).where(
                ListingRoster.symbol.in_(wanted),
                ListingRoster.is_listed.is_(False),
            )
        ).scalars()
        return tuple(sorted(rows))

    def _all(self) -> Sequence[ListingRoster]:
        return tuple(
            self.session.execute(select(ListingRoster)).scalars()
        )


def refresh_listing_roster(
    session: Session,
    provider: ListingRosterProvider,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> RosterRefresh:
    """Read the register from a provider and store it in one step."""
    entries = provider.fetch_listing_roster()
    return ListingRosterStore(session).refresh(
        entries,
        source=provider.source,
        observed_at=now(),
    )
