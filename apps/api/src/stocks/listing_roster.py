"""The stored listing register: reading it, and refreshing it from the market.

The read side is what the Signal Field pack and the alpha envelope use to answer
which exchange a symbol sits on. The write side came back for the daily spine,
which needs a name for "every listed company" before any of it is in the
Universe — and a register is the only thing that can notice a company leaving,
because a listing register lists who is *in* it, so a delisting is an absence.

Two rules the refresh keeps, both learned from the collector this replaces:

**A symbol that left is kept, not deleted.** Deleted, a delisted company would
simply stop matching a query and every reader would go on treating its last
stored numbers as current. The absence has to be recorded to be acted on.

**An empty refresh is refused.** A provider answering with nothing looks exactly
like an exchange that closed, and taken at face value it would delist the whole
market in one write.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.stocks.models import ListingRoster

from .providers.contracts import Exchange, ListingEntry, ProviderSource

logger = logging.getLogger(__name__)

#: The provider's own source for the register. One call answers the whole
#: market: 3,586 rows across every instrument type, measured 2026-08-27.
PROVIDER_SOURCE = "VCI"

#: Only shares. The response also carries covered warrants, bonds, futures, ETFs
#: and unit trusts, and none of them is a company a screener ranks.
STOCK_TYPE = "STOCK"

#: What the provider writes in the exchange column for a share that no longer
#: trades on any board. Not a board, so it never reaches ``Exchange``.
DELISTED_EXCHANGE = "DELISTED"

#: The ICB level whose codes ``symbols_by_exchange`` reports in ``icb_code2``.
ICB_LEVEL = 2


@dataclass(frozen=True)
class ListedIdentity:
    """Who a symbol is, as the register last saw it."""

    symbol: str
    exchange: Exchange
    company_name: str | None
    is_listed: bool
    icb_code: str | None = None
    icb_name: str | None = None


@dataclass(frozen=True)
class RosterRefresh:
    """What one refresh of the register changed, in terms a job log can print."""

    listed: int
    newly_listed: tuple[str, ...]
    newly_delisted: tuple[str, ...]
    unclassified: int


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

    def listed_symbols(
        self, exchanges: Iterable[Exchange] | None = None
    ) -> tuple[str, ...]:
        """The symbols currently listed, alphabetically, all boards by default.

        Ordered so a backfill interrupted halfway walks the market in the same
        order next time, which is what makes "already deep enough" a resumable
        answer rather than a guess about which symbols were reached.
        """
        statement = select(ListingRoster.symbol).where(
            ListingRoster.is_listed.is_(True)
        )
        if exchanges is not None:
            wanted = [exchange.value for exchange in exchanges]
            if not wanted:
                return ()
            statement = statement.where(ListingRoster.exchange.in_(wanted))
        rows = self.session.execute(
            statement.order_by(ListingRoster.symbol.asc())
        ).scalars()
        return tuple(rows)

    def write(
        self,
        entries: Sequence[ListingEntry],
        *,
        shares: Iterable[str],
        mentioned: Iterable[str],
        source: ProviderSource = ProviderSource.VNSTOCK,
        observed_at: datetime | None = None,
    ) -> RosterRefresh:
        """Write the register as it stands now and report what moved.

        Three sets, because a stored row missing from ``entries`` has three
        possible reasons and only two of them are a delisting:

        - ``entries`` — the shares the market lists, one per board row;
        - ``shares`` — every symbol the provider typed as a share, board or not,
          so a share it places on no board is a company that left;
        - ``mentioned`` — every symbol the response named at all. A stored row
          the response never named has left too.

        A stored row mentioned only under another instrument type is left exactly
        as it was: a covered warrant is not a company that delisted, and this
        refresh makes no claim about it.
        """
        if not entries:
            raise ValueError(
                "a listing roster refresh cannot be empty: it would delist the "
                "whole market"
            )

        stamped = observed_at or datetime.now(timezone.utc)
        stored = {
            row.symbol: row
            for row in self.session.execute(select(ListingRoster)).scalars()
        }
        incoming = {entry.symbol: entry for entry in entries}
        share_symbols = {symbol.upper() for symbol in shares}
        named = {symbol.upper() for symbol in mentioned}

        newly_listed: list[str] = []
        unclassified = 0
        for symbol, entry in incoming.items():
            if entry.icb_code is None:
                unclassified += 1
            row = stored.get(symbol)
            if row is None:
                self.session.add(
                    ListingRoster(
                        symbol=symbol,
                        exchange=entry.exchange.value,
                        is_listed=True,
                        company_name=entry.company_name,
                        icb_code=entry.icb_code,
                        icb_name=entry.icb_name,
                        source=source.value,
                        observed_at=stamped,
                    )
                )
                newly_listed.append(symbol)
                continue

            if not row.is_listed:
                # Relisted, or moved boards and came back. Newly listed is what
                # it is to every reader downstream: a symbol that was not
                # rankable and now is.
                newly_listed.append(symbol)
            row.exchange = entry.exchange.value
            row.is_listed = True
            row.company_name = entry.company_name
            # Written only when the refresh carried one. The classification read
            # is best-effort, so an entry without a code means it was not
            # answered this time — and writing that absence through would
            # unclassify the market on a read that never disagreed.
            if entry.icb_code is not None:
                row.icb_code = entry.icb_code
                row.icb_name = entry.icb_name
            row.source = source.value
            row.observed_at = stamped

        newly_delisted: list[str] = []
        for symbol, row in stored.items():
            if symbol in incoming or not row.is_listed:
                continue
            if symbol not in share_symbols and symbol in named:
                # Named only as another instrument type. Nothing here says the
                # company left, so nothing here says it did.
                continue
            row.is_listed = False
            row.observed_at = stamped
            newly_delisted.append(symbol)

        self.session.flush()
        logger.info(
            "Listing roster refreshed: %d listed, %d new, %d delisted, "
            "%d unclassified",
            len(incoming),
            len(newly_listed),
            len(newly_delisted),
            unclassified,
        )
        return RosterRefresh(
            listed=len(incoming),
            newly_listed=tuple(sorted(newly_listed)),
            newly_delisted=tuple(sorted(newly_delisted)),
            unclassified=unclassified,
        )


def refresh_roster(
    session: Session,
    *,
    fetch_listings: Callable[[], Any] | None = None,
    fetch_industries: Callable[[], Any] | None = None,
    observed_at: datetime | None = None,
) -> RosterRefresh:
    """Read the market's register from the provider and store it.

    Two calls: the boards, and the industry names the boards' codes point at.
    The second is best-effort — a symbol the market lists and nothing has
    classified is a normal row, so a failed industry read costs the names and
    keeps the register.

    ``fetch_listings`` and ``fetch_industries`` are injectable so the suite can
    prove the board mapping and the join offline; production passes neither.
    """
    fetch_listings = fetch_listings or _fetch_listings
    fetch_industries = fetch_industries or _fetch_industries

    frame = fetch_listings()
    industries = _industry_names(fetch_industries)
    entries, shares, mentioned = _entries_from(frame, industries)
    return ListingRosterStore(session).write(
        entries, shares=shares, mentioned=mentioned, observed_at=observed_at
    )


def _fetch_listings() -> Any:
    """The whole register, every instrument type, in one call.

    vnstock is imported here rather than at module load: this module is on the
    serving path — the alpha envelope reads it to answer which board a symbol
    trades on — and the provider library costs seconds to import that a request
    should not pay for.
    """
    from src.core.vnstock_wrapper import safe_vnstock_call
    from vnstock import Listing

    frame = safe_vnstock_call(Listing(source=PROVIDER_SOURCE).symbols_by_exchange)
    if frame is None:
        raise RuntimeError(
            "vnstock gave up on the listing register after its retries; the "
            "stored roster was left standing"
        )
    return frame


def _fetch_industries() -> Any:
    from src.core.vnstock_wrapper import safe_vnstock_call
    from vnstock import Listing

    return safe_vnstock_call(Listing(source=PROVIDER_SOURCE).industries_icb)


def _industry_names(fetch_industries: Callable[[], Any]) -> dict[str, str]:
    """ICB level-2 code to Vietnamese industry name, or nothing at all."""
    try:
        frame = fetch_industries()
    except Exception:  # noqa: BLE001 - best-effort by contract
        logger.warning("The ICB industry read failed; the register keeps its codes")
        return {}
    if frame is None or getattr(frame, "empty", True):
        return {}
    missing = [
        name for name in ("icb_code", "icb_name", "level") if name not in frame.columns
    ]
    if missing:
        logger.warning(
            "The ICB industry read answered without %s; got %s",
            missing,
            list(frame.columns),
        )
        return {}
    names: dict[str, str] = {}
    for record in frame.itertuples(index=False):
        if _text(record.level) != str(ICB_LEVEL):
            continue
        code = _text(record.icb_code)
        name = _text(record.icb_name)
        if code and name:
            names[code] = name
    return names


def _entries_from(
    frame: Any, industries: dict[str, str]
) -> tuple[tuple[ListingEntry, ...], tuple[str, ...], tuple[str, ...]]:
    """Listed shares, every share named, and every symbol named.

    Three sets rather than one because ``ListingRosterStore.write`` needs all
    three to tell a delisting from an instrument type it does not describe.
    """
    required = ("symbol", "exchange", "type")
    missing = [name for name in required if name not in frame.columns]
    if missing:
        raise RuntimeError(
            f"the listing register answered without {missing}; got "
            f"{list(frame.columns)}"
        )

    has_name = "organ_name" in frame.columns
    has_icb = "icb_code2" in frame.columns

    entries: list[ListingEntry] = []
    shares: list[str] = []
    mentioned: list[str] = []
    for record in frame.itertuples(index=False):
        symbol = _text(record.symbol).upper()
        if not symbol:
            continue
        mentioned.append(symbol)
        if _text(record.type).upper() != STOCK_TYPE:
            continue
        shares.append(symbol)
        board = _text(record.exchange).upper()
        if board == DELISTED_EXCHANGE or not board:
            # A share the provider still names but places on no board. Its
            # stored row, if there is one, is delisted by absence from
            # ``entries``; a symbol with no stored row is skipped rather than
            # invented, because there is no board to record it on and nothing
            # here ever saw it listed.
            continue
        code = _text(record.icb_code2) if has_icb else ""
        entries.append(
            ListingEntry(
                symbol=symbol,
                exchange=Exchange.parse(board),
                is_listed=True,
                company_name=_text(record.organ_name) if has_name else None,
                icb_code=code or None,
                icb_name=industries.get(code),
            )
        )
    return tuple(entries), tuple(shares), tuple(mentioned)


def _text(value: Any) -> str:
    """A provider cell as text, with pandas' spellings of "missing" flattened."""
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "nat", "<na>"}:
        return ""
    return text
