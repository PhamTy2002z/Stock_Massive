"""vnstock adapters for the reference and fundamental capabilities.

vnstock is the Main Source for both (``docs/adr/0002``): the free FiinQuant
tier returns empty share counts, and answers foreign room with a 403. These two
capabilities had a contract and no implementation until now.

The binding constraint here is quota rather than the gateway — 20 requests a
minute without an API key, 60 with one — so the two adapters read very
differently. Reference comes off one batched price board that covers the whole
Universe in a single request. Statements have no batched form at all, so
fundamental pays two requests per symbol against that same allowance.

Neither adapter paces itself. The allowance belongs to the account, so it is
spent in one place for every live path (``src/core/quota.py``,
``docs/adr/0014``); an adapter with a pacer of its own was one of the three
copies that together added up to more than the account had.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd
from pydantic import ValidationError

from src.core.config import get_settings
from src.core.vnstock_client import (
    Company,
    Finance,
    Listing,
    Quote,
    Trading,
    VnstockUnavailable,
    VnstockUnsupported,
)
from src.stocks.shared import StockServiceError
from src.stocks.shared.converters import quote_price_vnd

from .contracts import (
    MARKET_SCHEMA_VERSION,
    CorporateActionEvent,
    Exchange,
    FundamentalSnapshot,
    ListingEntry,
    MarketSnapshot,
    PriceBasis,
    ProviderSource,
    ReferenceSnapshot,
    ShareCount,
    ShareType,
    SnapshotMetadata,
)
from .normalize import (
    VN_TZ,
    lower_cased_columns,
    missing_fields,
    normalized_symbols,
    optional_float,
    optional_int,
)

logger = logging.getLogger(__name__)

# The flattened VCI price board carries all of reference in one row per symbol.
# ``current_room`` is the room still available, not the holding — measured
# against HPG, FPT and VCB, where total room less current room matches each
# company's published foreign ownership.
REFERENCE_FIELDS = ("symbol", "listed_share", "current_room", "total_room")

# Statement rows are addressed by ``item_id`` rather than by their label: the
# label is free text that arrives in two languages and changes wording, while
# the id is the provider's stable key. Every id below was read off a live VCI
# response (MSN, 2026-08-17) rather than guessed from a label.
INCOME_ITEM_PARENT_PROFIT = "attributable_to_parent_company"
INCOME_ITEM_NET_SALES = "net_sales"
INCOME_ITEM_GROSS_PROFIT = "gross_profit"
INCOME_ITEM_OPERATING_PROFIT = "operating_profit_loss"
INCOME_ITEM_PRE_TAX_PROFIT = "net_accounting_profit_loss_before_tax"
INCOME_ITEM_NET_PROFIT_AFTER_TAX = "net_profit_loss_after_tax"
BALANCE_ITEM_OWNERS_EQUITY = "owners_equity"
BALANCE_ITEM_MINORITY_INTERESTS = "minority_interests"
BALANCE_ITEM_TOTAL_ASSETS = "total_assets"
BALANCE_ITEM_LIABILITIES = "liabilities"
BALANCE_ITEM_SHORT_TERM_BORROWINGS = "short_term_borrowings"
BALANCE_ITEM_LONG_TERM_BORROWINGS = "long_term_borrowings"
BALANCE_ITEM_CASH_AND_EQUIVALENTS = "cash_and_cash_equivalents"
CASHFLOW_ITEM_CFO = "net_cash_inflows_outflows_from_operating_activities"
CASHFLOW_ITEM_CFI = "net_cash_inflows_outflows_from_investing_activities"
CASHFLOW_ITEM_CFF = "net_cash_inflows_outflows_from_financing_activities"

TRAILING_QUARTERS = 4

# How many reporting periods one collection emits. The community tier answers
# with at most 8 period columns; asking to keep more is free, the columns are
# simply not there.
STATEMENT_QUARTERS = 8

# What a quote history answers with, and the interval that asks for sessions.
HISTORY_FIELDS = ("time", "open", "high", "low", "close", "volume")
HISTORY_INTERVAL = "1D"

# The quote history takes no adjustment flag: VCI rescales it for every
# corporate action up to the moment it answers, and there is no way to ask for
# the numbers the exchange published. So the sessions this adapter writes say
# ``adjusted_at_source``, and a window lying wholly in them is refused rather
# than adjusted — that basis was fixed at ``observed_at`` and cannot be
# recomputed from what is stored (``docs/adr/0006``).
MARKET_PRICE_BASIS = PriceBasis.ADJUSTED_AT_SOURCE

# Statement periods arrive as column headers, one per quarter.
PERIOD_PATTERN = re.compile(r"^(\d{4})-Q([1-4])$")
QUARTER_END = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}

# The register is answered one board at a time. All three are read even though
# only HOSE and HNX are rankable: a symbol has to be *seen* on UPCOM to be
# excluded for being there, and a company that moves down to UPCOM has to stop
# looking like a company that vanished.
ROSTER_EXCHANGES = (Exchange.HOSE, Exchange.HNX, Exchange.UPCOM)

# What a listing row must carry, and the value that marks an ordinary equity.
# The register also lists funds, covered warrants and bonds, none of which have a
# net income to rank.
LISTING_FIELDS = ("symbol", "type")
LISTING_EQUITY_TYPE = "STOCK"
LISTING_NAME_FIELDS = ("organ_short_name", "organ_name")

# What the market-wide ICB list must carry, and the level read out of it. This
# is the VCI shape, which is the source this system configures by default: one
# row per symbol *per level*, so the level is a column to filter on rather than
# something to assume — level 1 puts banks, insurers and developers together,
# and levels 3 and 4 split each of them again. Level 2 is where "a bank" is one
# code, which is the level the Analysis Field Profile's industry blocks are
# keyed on (spec 0003 §8.4).
#
# The other source answers this call with `industry_code` / `industry_name`,
# which its own documentation says are not ICB (see the shape
# `src/stocks/shared/industries.py` was written against). A frame without these
# four columns therefore classifies nobody rather than being read as if it
# carried codes it does not.
ICB_FIELDS = ("symbol", "icb_level", "icb_code", "icb_name")
ICB_LEVEL = 2

# The bounds of the register's columns, mirroring `ListingRoster.icb_code` and
# `icb_name`. A code longer than a supersector code is dropped rather than
# truncated: cutting `83000` down to `8300` would invent a classification the
# provider never gave. A name is descriptive and nothing branches on it, so it
# is bounded rather than dropped.
ICB_CODE_LENGTH = 4
ICB_NAME_LENGTH = 100

# What an event row must carry, and the category that marks a corporate action.
# The same feed answers with AGMs, insider dealings and additional listings; only
# ``DIVIDEND`` rows carry a ratio or a payment, which is what an adjustment is
# made of. The English title is read rather than the Vietnamese one because the
# kind of a share issue is only in the title text, and the English wording is the
# one this system's parsing is measured against.
EVENT_ACTION_CATEGORY = "DIVIDEND"
EVENT_TITLE_FIELD = "event_title_en"
EVENT_FIELDS = (
    "event_code",
    "category",
    "exright_date",
    "public_date",
    # The title is required with the dates rather than with the terms below: it
    # is the only place the kind of a share issue appears, so a feed without it
    # answers with rows whose kind is unreadable, and a table of those reads like
    # a market with no corporate actions in it.
    EVENT_TITLE_FIELD,
)

# The columns carrying an action's terms, which are *not* required. This frame's
# schema follows its contents: a company whose history holds no cash dividend
# comes back without a ``value_per_share`` column at all, and five of the thirty
# symbols in the configured Universe did on the first live run — STB without
# either. Demanding them refuses those companies' share issues, which are
# perfectly readable, over a column their absence of dividends explains.
#
# Absent, the terms read as missing, and an action with missing terms already has
# an honest answer: it is stored and refuses to produce a factor. That is the
# same outcome as a row whose columns are present and empty, which is what it is.
EVENT_TERM_FIELDS = ("exercise_ratio", "value_per_share")


class VnstockProviderError(RuntimeError):
    """A vnstock response this adapter refuses to interpret.

    Raised for failures that are about the response rather than about the
    symbol that provoked it, so they are not worth repeating for every symbol
    left in the batch.
    """


class VnstockReadFailed(VnstockProviderError):
    """One upstream read did not come back.

    Distinct from its parent because it says nothing about the other symbols: a
    delisted ticker fails here while the rest of the batch is fine.
    """


def _default_trading_factory(source: str) -> Any:
    return Trading(source=source)


def _default_quote_factory(symbol: str, source: str) -> Any:
    return Quote(symbol=symbol, source=source)


def _default_finance_factory(symbol: str, source: str) -> Any:
    return Finance(symbol=symbol, source=source)


def _default_listing_factory(source: str) -> Any:
    return Listing(source=source)


def _default_company_factory(symbol: str, source: str) -> Any:
    return Company(symbol=symbol, source=source)


class VnstockProviderBase:
    """Symbol handling and error hygiene shared by both adapters.

    Pacing is no longer here. It belongs to the account rather than to an
    adapter, and this class holding a pacer of its own was one of the three
    uncoordinated copies ``src/core/quota.py`` replaced: the allowance is now
    spent in ``src/core/vnstock_client``, where every live call passes through
    whether it came from an adapter or from a legacy service.
    """

    source = ProviderSource.VNSTOCK

    def __init__(
        self,
        vnstock_source: str | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._vnstock_source = vnstock_source or get_settings().vnstock_source
        self._now = now

    def _read(self, call: Callable[[], Any], message: str) -> Any:
        """Run one upstream read, keeping its error text out of ours.

        Quota exhaustion, an unimplemented provider and a refusal from the
        arbiter all carry meanings of their own that the rest of the app already
        handles, so they travel unchanged.
        """
        try:
            return call()
        except (VnstockUnavailable, VnstockUnsupported, VnstockProviderError):
            raise
        except Exception as exc:
            logger.warning("%s: %s", message, exc)
            raise VnstockReadFailed(f"{message} ({type(exc).__name__})") from None


class VnstockReferenceProvider(VnstockProviderBase):
    """Turn one batched price board into one ReferenceSnapshot per symbol.

    The whole Universe costs a single request here, which is why this capability
    is affordable at all: at 20 requests a minute, reading a hundred symbols one
    at a time would spend five minutes on what one read covers.

    A malformed board is an error. A board that simply has no row for a symbol
    is not — a delisted or freshly listed ticker is normal, and it never costs
    the rest of the batch its snapshots.

    Only a listed count is produced, never an outstanding one. This is a limit
    of the source rather than of the adapter, measured: ``ratio_summary`` still
    answers with 2018 share counts, and ``overview``'s ``issue_share`` is the
    same number the board already gives as ``listed_share``. Since an
    outstanding count differs from a listed one by treasury shares, inferring
    it would put a wrong figure behind a right-looking name — so the gap is
    left visible instead, and ``canonical_shares()`` falls through to listed.
    """

    def __init__(
        self,
        vnstock_source: str | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        trading_factory: Callable[[str], Any] = _default_trading_factory,
    ) -> None:
        super().__init__(vnstock_source=vnstock_source, now=now)
        self._trading_factory = trading_factory

    def fetch_reference(self, symbols: Sequence[str]) -> Sequence[ReferenceSnapshot]:
        normalized = normalized_symbols(symbols)
        if not normalized:
            return ()

        board = self._read(
            lambda: self._trading_factory(self._vnstock_source).price_board(
                symbols_list=list(normalized),
                flatten_columns=True,
                drop_levels=[0],
            ),
            "vnstock reference fetch failed",
        )
        return self._to_snapshots(board, normalized)

    def _to_snapshots(
        self,
        board: pd.DataFrame | None,
        requested_symbols: Sequence[str],
    ) -> tuple[ReferenceSnapshot, ...]:
        if board is None or getattr(board, "empty", True):
            raise VnstockProviderError(
                "vnstock returned no reference data for any requested symbol"
            )

        rows = _rows_by_symbol(board, REFERENCE_FIELDS, requested_symbols)
        observed_at = self._now()
        effective_at = _session_start(observed_at)
        snapshots: list[ReferenceSnapshot] = []

        for symbol in requested_symbols:
            row = rows.get(symbol)
            if row is None:
                continue
            snapshot = self._build(symbol, row, effective_at, observed_at)
            if snapshot is not None:
                snapshots.append(snapshot)

        return tuple(snapshots)

    def _build(
        self,
        symbol: str,
        row: pd.Series,
        effective_at: datetime,
        observed_at: datetime,
    ) -> ReferenceSnapshot | None:
        listed = _optional_int(row.get("listed_share"))
        current_room = _optional_int(row.get("current_room"))
        total_room = _optional_int(row.get("total_room"))

        if listed is None and current_room is None and total_room is None:
            logger.info("Skipping %s: the price board carries no reference data", symbol)
            return None

        if (
            current_room is not None
            and total_room is not None
            and current_room > total_room
        ):
            # A room larger than the room it sits inside is what a unit slip
            # between the two looks like, and the contract refuses it outright —
            # nothing here downgrades that to a figure stored with a caveat.
            #
            # What it is not is a reason to lose the other ninety-nine symbols:
            # the response is well formed and every other row in it is fine, so
            # this one is dropped loudly and the batch carries on.
            logger.error(
                "Dropping %s: vnstock reports a current foreign room (%s) larger "
                "than its total room (%s)",
                symbol,
                current_room,
                total_room,
            )
            return None

        # The count is recorded as listed because that is what VCI publishes.
        # Nothing relabels it as outstanding: the two differ by treasury shares,
        # and every per-share figure computed from the wrong one is off by that
        # gap while looking entirely reasonable.
        shares = (
            (ShareCount(share_type=ShareType.LISTED, value=listed),)
            if listed is not None and listed > 0
            else ()
        )

        try:
            return ReferenceSnapshot(
                symbol=symbol,
                metadata=SnapshotMetadata(
                    source=self.source,
                    # The board carries no period of its own, so it is dated by
                    # the session it was read in. Dating it by the minute would
                    # make each re-run of a cycle a fresh Snapshot of facts that
                    # have not changed — and these facts change over months.
                    effective_at=effective_at,
                    observed_at=observed_at,
                ),
                shares=shares,
                current_foreign_room=current_room,
                total_foreign_room=total_room,
            )
        except ValidationError as exc:
            logger.warning("Skipping unusable vnstock reference row for %s: %s", symbol, exc)
            return None


class VnstockListingRosterProvider(VnstockProviderBase):
    """Read the whole market's listing register, one board per request.

    Four requests for the entire market is the cheapest thing this adapter does,
    which matters because the census that follows it costs two requests per
    symbol across roughly 1,600 of them.

    All three boards or none. A refresh is an "as it stands now" picture of the
    market, and the caller marks whatever is missing from it as delisted — so a
    board that failed to answer would delist every company on it. Failing the
    whole read is recoverable; a roster wrong about who is still trading is not
    noticed until a cohort has already been rebuilt around it.

    The fourth request classifies the market, and it is the opposite kind of
    read: market-wide, best-effort, and never able to fail the refresh. It is
    made here because this is the only pass that reads every listed company at
    once, and because the nightly Analysis pipeline that needs the answer may
    not call a Provider Source at all (spec 0003 §8.1) — an industry it cannot
    read from a stored row is an industry it does not have.
    """

    def __init__(
        self,
        vnstock_source: str | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        listing_factory: Callable[[str], Any] = _default_listing_factory,
    ) -> None:
        super().__init__(vnstock_source=vnstock_source, now=now)
        self._listing_factory = listing_factory

    def fetch_listing_roster(self) -> Sequence[ListingEntry]:
        listing = self._listing_factory(self._vnstock_source)
        boards = [
            (exchange, self._read_board(listing, exchange))
            for exchange in ROSTER_EXCHANGES
        ]
        # Read after the boards and never before. The register is what a refresh
        # has to come back with; spending the allowance on the classification of
        # a market whose boards then failed to answer buys nothing.
        classifications = self._read_classifications(listing)

        entries: list[ListingEntry] = []
        seen: set[str] = set()
        for exchange, frame in boards:
            entries.extend(self._to_entries(frame, exchange, seen, classifications))

        return tuple(entries)

    def _read_board(self, listing: Any, exchange: Exchange) -> pd.DataFrame:
        frame = self._read(
            lambda: listing.symbols_by_exchange(exchange=exchange.value),
            f"vnstock listing roster fetch failed for {exchange.value}",
        )
        if frame is None or getattr(frame, "empty", True):
            raise VnstockProviderError(
                f"vnstock returned no listings for {exchange.value}"
            )
        return frame

    def _read_classifications(self, listing: Any) -> dict[str, tuple[str, str | None]]:
        """The market's ICB level-2 classification, or nothing at all.

        A failed read answers with an empty mapping rather than raising: the
        boards have already been read, and the store leaves a stored
        classification alone when a refresh carries none, so carrying on costs a
        classification that is a week old rather than a register that is.

        An exhausted allowance is the exception, and it travels. It is not a
        fact about the classification at all — it says the account has nothing
        left to spend, and the census that follows this refresh costs two
        requests per symbol across the whole market. Swallowed here, it would be
        met again immediately with no warning that it was already known.

        A frame this adapter does not recognise classifies nobody. The other
        vnstock source answers this call with codes of its own that are
        explicitly not ICB, and reading those as level-2 codes would select an
        industry block off a number that means something else entirely.
        """
        try:
            frame = self._read(
                lambda: listing.symbols_by_industries(),
                "vnstock ICB classification fetch failed",
            )
        except VnstockUnavailable:
            raise
        except (VnstockProviderError, VnstockUnsupported) as exc:
            logger.warning(
                "vnstock ICB classification unavailable, refreshing the register "
                "without it: %s",
                exc,
            )
            return {}

        if frame is None or getattr(frame, "empty", True):
            logger.warning("vnstock returned no ICB classification for the market")
            return {}

        rows = lower_cased_columns(frame)
        missing = missing_fields(rows, ICB_FIELDS)
        if missing:
            logger.warning(
                "vnstock ICB classification is missing fields %s; refreshing the "
                "register without it",
                ", ".join(missing),
            )
            return {}

        level_two = rows[pd.to_numeric(rows["icb_level"], errors="coerce") == ICB_LEVEL]
        classified: dict[str, tuple[str, str | None]] = {}
        for _, row in level_two.iterrows():
            symbol = str(row.get("symbol") or "").strip().upper()
            code = _icb_code(row.get("icb_code"))
            if not symbol or code is None:
                continue
            classified[symbol] = (code, _icb_name(row.get("icb_name")))

        logger.info("ICB level-2 classification read for %d symbols", len(classified))
        return classified

    def _to_entries(
        self,
        frame: pd.DataFrame,
        exchange: Exchange,
        seen: set[str],
        classifications: Mapping[str, tuple[str, str | None]],
    ) -> list[ListingEntry]:
        rows = lower_cased_columns(frame)
        missing = missing_fields(rows, LISTING_FIELDS)
        if missing:
            raise VnstockProviderError(
                f"vnstock listing for {exchange.value} is missing fields: "
                f"{', '.join(missing)}"
            )

        equities = rows[rows["type"].astype(str).str.upper() == LISTING_EQUITY_TYPE]
        entries: list[ListingEntry] = []

        for _, row in equities.iterrows():
            symbol = str(row.get("symbol") or "").strip().upper()
            # A board is read before the ones after it, so the first board a
            # symbol appears on is the one it is recorded against. Dual listing
            # does not happen on these exchanges; a duplicate here is the
            # register repeating itself, and taking the second one would move a
            # HOSE company to UPCOM and drop it out of the ranking.
            if not symbol or symbol in seen:
                continue

            icb_code, icb_name = classifications.get(symbol, (None, None))
            try:
                entries.append(
                    ListingEntry(
                        symbol=symbol,
                        exchange=exchange,
                        # Everything in the register is currently listed. Whoever
                        # is *not* in it is what a delisting looks like, and that
                        # is the caller's comparison to make, not this adapter's.
                        is_listed=True,
                        company_name=_listing_name(row),
                        icb_code=icb_code,
                        icb_name=icb_name,
                    )
                )
            except (ValidationError, StockServiceError) as exc:
                # An index code or a malformed ticker sitting in the register
                # costs itself. The market has ~1,600 rows and the census needs
                # the other 1,599.
                logger.info("Skipping unusable listing row %s: %s", symbol, exc)
                continue
            seen.add(symbol)

        return entries


class VnstockMarketHistoryProvider(VnstockProviderBase):
    """Turn one symbol's quote history into a MarketSnapshot per session.

    This is the Cover Source for `market` (``docs/adr/0002``): the stretch of
    history that reaches back further than the Main Source is granted. It is
    never the daily read — those two disagree on how much of a session they
    describe, and the daily one is richer.

    Prices arrive here in thousands of VND, unlike the price board's plain VND.
    Normalizing at the adapter is what keeps a chart drawn across both sources
    from stepping by a factor of a thousand at the seam.

    Only what a quote history carries is filled in: money traded, the flow
    pairs, the permitted band and market cap are not in this answer, and are
    left empty rather than guessed at.
    """

    def __init__(
        self,
        vnstock_source: str | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        quote_factory: Callable[[str, str], Any] = _default_quote_factory,
    ) -> None:
        super().__init__(vnstock_source=vnstock_source, now=now)
        self._quote_factory = quote_factory

    def fetch_market_history(
        self,
        symbol: str,
        from_date: date,
        to_date: date,
    ) -> Sequence[MarketSnapshot]:
        if from_date > to_date:
            raise ValueError("from_date cannot be later than to_date")
        (normalized,) = normalized_symbols([symbol])

        quote = self._quote_factory(normalized, self._vnstock_source)
        frame = self._read(
            lambda: quote.history(
                start=from_date.strftime("%Y-%m-%d"),
                end=to_date.strftime("%Y-%m-%d"),
                interval=HISTORY_INTERVAL,
            ),
            f"vnstock market history fetch failed for {normalized}",
        )
        return self._to_snapshots(frame, normalized)

    def _to_snapshots(
        self,
        frame: pd.DataFrame | None,
        symbol: str,
    ) -> tuple[MarketSnapshot, ...]:
        """Read a whole window in one pass, oldest session first.

        An empty window is a symbol with no sessions in it, not a failure: a
        backfill walks straight through the years before a company listed.
        This differs from the price board, where an empty answer means the
        request itself did not work.
        """
        if frame is None or getattr(frame, "empty", True):
            return ()

        sessions = lower_cased_columns(frame)
        missing = missing_fields(sessions, HISTORY_FIELDS)
        if missing:
            raise VnstockProviderError(
                f"vnstock history is missing fields: {', '.join(missing)}"
            )

        sessions = sessions.sort_values("time")
        observed_at = self._now()
        snapshots: list[MarketSnapshot] = []
        previous_close: float | None = None

        for _, row in sessions.iterrows():
            close = quote_price_vnd(row.get("close"))
            session_day = pd.to_datetime(row.get("time"), errors="coerce")
            if close is None or pd.isna(session_day):
                # An all-blank row is a gap in the series rather than a session
                # priced at zero, and the contract refuses a zero price anyway.
                continue

            snapshot = self._build(
                symbol=symbol,
                row=row,
                close=close,
                previous_close=previous_close,
                effective_at=datetime.combine(
                    session_day.date(), datetime.min.time(), tzinfo=VN_TZ
                ),
                observed_at=observed_at,
            )
            previous_close = close
            if snapshot is not None:
                snapshots.append(snapshot)

        return tuple(snapshots)

    def _build(
        self,
        symbol: str,
        row: pd.Series,
        close: float,
        previous_close: float | None,
        effective_at: datetime,
        observed_at: datetime,
    ) -> MarketSnapshot | None:
        change_pct = None
        if previous_close:
            change_pct = (close - previous_close) / previous_close * 100

        try:
            return MarketSnapshot(
                symbol=symbol,
                metadata=SnapshotMetadata(
                    source=self.source,
                    effective_at=effective_at,
                    observed_at=observed_at,
                    schema_version=MARKET_SCHEMA_VERSION,
                ),
                # No raw option exists on this endpoint: what comes back has
                # been rescaled for every action up to the moment it answered,
                # and ``observed_at`` is when that was.
                price_basis=MARKET_PRICE_BASIS,
                last_price=close,
                # Only where the previous session is in this same answer. The
                # first row of a window has no predecessor here, and taking the
                # row's own open would report every chunk boundary as flat.
                reference_price=previous_close,
                open_price=quote_price_vnd(row.get("open")),
                high_price=quote_price_vnd(row.get("high")),
                low_price=quote_price_vnd(row.get("low")),
                change_pct=change_pct,
                volume=_optional_int(row.get("volume")),
            )
        except ValidationError as exc:
            logger.warning("Skipping unusable vnstock history row for %s: %s", symbol, exc)
            return None


class VnstockFundamentalProvider(VnstockProviderBase):
    """Turn a symbol's two statements into one snapshot for the latest period.

    Statements have no batched form, so this is two requests per symbol and the
    run leans on the pacer for the whole of its quota safety.

    Figures arrive in whole dong in this layout. The adapter refuses any layout
    it does not recognise rather than reading numbers whose scale it is
    guessing at — the older wide layout labels the same figures in billions,
    and confusing the two is an error of a billion that nothing downstream
    could detect.
    """

    def __init__(
        self,
        vnstock_source: str | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        finance_factory: Callable[[str, str], Any] = _default_finance_factory,
    ) -> None:
        super().__init__(vnstock_source=vnstock_source, now=now)
        self._finance_factory = finance_factory

    def fetch_fundamentals(
        self,
        symbols: Sequence[str],
    ) -> Sequence[FundamentalSnapshot]:
        normalized = normalized_symbols(symbols)
        observed_at = self._now()
        snapshots: list[FundamentalSnapshot] = []

        for symbol in normalized:
            try:
                periods = self._fetch_one(symbol, observed_at)
            except (VnstockUnavailable, VnstockUnsupported):
                # Quota and capability failures are about the account, not this
                # symbol; carrying on would repeat them for every remaining one
                # at the price of a request each.
                raise
            except VnstockReadFailed as exc:
                logger.warning("Skipping %s: %s", symbol, exc)
                continue
            except VnstockProviderError:
                # A layout this adapter cannot read is the same for every
                # symbol. Skipping them one by one would end in an empty result
                # that reads like a quiet market rather than a broken contract.
                raise
            except Exception as exc:
                logger.warning("Skipping %s: vnstock statements unusable (%s)", symbol, exc)
                continue
            snapshots.extend(periods)

        return tuple(snapshots)

    def _fetch_one(
        self,
        symbol: str,
        observed_at: datetime,
    ) -> list[FundamentalSnapshot]:
        """Return one snapshot per reporting period, oldest first.

        Oldest first because the store's current-view cache keeps whichever
        snapshot was saved last, and a writer iterating this list in order must
        leave the newest period there.
        """
        finance = self._finance_factory(symbol, self._vnstock_source)
        income = self._read(
            lambda: finance.income_statement(period="quarter", lang="en", dropna=True),
            f"vnstock income statement fetch failed for {symbol}",
        )
        balance = self._read(
            lambda: finance.balance_sheet(period="quarter", lang="en", dropna=True),
            f"vnstock balance sheet fetch failed for {symbol}",
        )

        income_periods = _statement_periods(income, f"{symbol} income statement")
        if not income_periods:
            logger.info("Skipping %s: vnstock reports no income statement", symbol)
            return []

        balance_periods = _statement_periods(balance, f"{symbol} balance sheet")

        # A missing cash flow statement costs this symbol its three flow lines,
        # not its filing: banks and recent listings file the other two first,
        # and refusing the whole symbol over the youngest statement would blank
        # exactly the companies with the least coverage already.
        try:
            cash_flow = self._read(
                lambda: finance.cash_flow(period="quarter", lang="en", dropna=True),
                f"vnstock cash flow fetch failed for {symbol}",
            )
            cash_flow_periods = _statement_periods(
                cash_flow, f"{symbol} cash flow statement"
            )
        except VnstockReadFailed as exc:
            logger.warning("Keeping %s without cash flow lines: %s", symbol, exc)
            cash_flow, cash_flow_periods = None, []

        snapshots: list[FundamentalSnapshot] = []
        for index, (period_end, column) in enumerate(
            income_periods[:STATEMENT_QUARTERS]
        ):
            balance_column = column if any(column == c for _, c in balance_periods) else None
            cash_flow_column = (
                column if any(column == c for _, c in cash_flow_periods) else None
            )
            try:
                snapshots.append(
                    FundamentalSnapshot(
                        symbol=symbol,
                        metadata=SnapshotMetadata(
                            source=self.source,
                            effective_at=datetime.combine(
                                period_end, datetime.min.time(), tzinfo=VN_TZ
                            ),
                            observed_at=observed_at,
                        ),
                        period_end=period_end,
                        trailing_12_month_net_income_vnd=_trailing_net_income(
                            income, income_periods[index:]
                        ),
                        parent_equity_vnd=(
                            _parent_equity(balance, balance_column)
                            if balance_column is not None
                            else None
                        ),
                        revenue_vnd=_statement_value(
                            income, INCOME_ITEM_NET_SALES, column
                        ),
                        gross_profit_vnd=_statement_value(
                            income, INCOME_ITEM_GROSS_PROFIT, column
                        ),
                        operating_profit_vnd=_statement_value(
                            income, INCOME_ITEM_OPERATING_PROFIT, column
                        ),
                        pre_tax_profit_vnd=_statement_value(
                            income, INCOME_ITEM_PRE_TAX_PROFIT, column
                        ),
                        net_profit_after_tax_vnd=_statement_value(
                            income, INCOME_ITEM_NET_PROFIT_AFTER_TAX, column
                        ),
                        parent_net_profit_vnd=_statement_value(
                            income, INCOME_ITEM_PARENT_PROFIT, column
                        ),
                        **_balance_lines(balance, balance_column),
                        **_cash_flow_lines(cash_flow, cash_flow_column),
                    )
                )
            except ValidationError as exc:
                logger.warning(
                    "Skipping unusable vnstock statements for %s %s: %s",
                    symbol,
                    period_end,
                    exc,
                )

        snapshots.reverse()
        return snapshots


class VnstockCorporateActionProvider(VnstockProviderBase):
    """Read one company's declared corporate actions from its event feed.

    One request per symbol, and the feed answers with the company's whole event
    history in one frame — annual general meetings, insider dealings, additional
    listings and, among them, the handful of rows that actually move a price.
    Only the ``DIVIDEND`` category is kept: an AGM is not an adjustment and a
    director's share purchase is not either, and storing them would put rows into
    a table whose whole purpose is that everything in it may be reasoned about.

    Nothing here decides what an action *means*. The kind of a share issue lives
    in free text and the ratio means different things by event code, both of
    which are read in ``signals.corporate_actions`` — this adapter's job is to
    turn a frame into records without losing or inventing a field.
    """

    def __init__(
        self,
        vnstock_source: str | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        company_factory: Callable[[str, str], Any] = _default_company_factory,
    ) -> None:
        super().__init__(vnstock_source=vnstock_source, now=now)
        self._company_factory = company_factory

    def fetch_corporate_actions(
        self,
        symbol: str,
    ) -> Sequence[CorporateActionEvent]:
        normalized = normalized_symbols([symbol])[0]
        company = self._company_factory(normalized, self._vnstock_source)
        frame = self._read(
            lambda: company.events(),
            f"vnstock corporate action fetch failed for {normalized}",
        )
        if frame is None or getattr(frame, "empty", True):
            # A company with no events is ordinary — a recent listing has none —
            # and it is not the same as a failed read, which raised above.
            return ()
        return self._to_events(frame, normalized)

    def _to_events(
        self,
        frame: pd.DataFrame,
        symbol: str,
    ) -> tuple[CorporateActionEvent, ...]:
        rows = lower_cased_columns(frame)
        missing = missing_fields(rows, EVENT_FIELDS)
        if missing:
            # A feed without these is a layout this adapter cannot read, which is
            # true for every symbol. Skipping symbol by symbol would end in an
            # empty table that reads like a market with no corporate actions.
            raise VnstockProviderError(
                f"vnstock events for {symbol} are missing fields: "
                f"{', '.join(missing)}"
            )

        absent_terms = missing_fields(rows, EVENT_TERM_FIELDS)
        if absent_terms:
            # Not a refusal, and worth a line anyway: every action this company
            # has will be stored without that term and will refuse a factor, so a
            # reader wondering why none of them adjusts anything has the reason
            # here rather than having to re-read the feed to find it.
            logger.info(
                "The %s event feed carries no %s column, so any action needing "
                "it is stored without its terms",
                symbol,
                " or ".join(absent_terms),
            )

        actions = rows[rows["category"].astype(str).str.upper() == EVENT_ACTION_CATEGORY]
        events: list[CorporateActionEvent] = []

        for _, row in actions.iterrows():
            try:
                events.append(
                    CorporateActionEvent(
                        symbol=symbol,
                        event_code=str(row.get("event_code") or ""),
                        title=str(row.get(EVENT_TITLE_FIELD) or "").strip(),
                        ex_date=_event_date(row.get("exright_date")),
                        record_date=_event_date(row.get("record_date")),
                        public_date=_event_date(row.get("public_date")),
                        exercise_ratio=_optional_float(row.get("exercise_ratio")),
                        value_per_share=_optional_float(row.get("value_per_share")),
                    )
                )
            except (ValidationError, StockServiceError) as exc:
                # A row with no dates at all cannot be stored idempotently, and a
                # row with no event code cannot be classified. Either costs
                # itself; the company's other actions are still worth having.
                logger.info(
                    "Skipping unusable %s event row (%s): %s",
                    symbol,
                    row.get("event_code"),
                    exc,
                )
                continue

        return tuple(events)


def _event_date(value: Any) -> date | None:
    """Read an event date, treating every way the feed spells absence as None.

    Dates arrive as ISO strings, as pandas timestamps, and as ``NaN`` — the last
    of which is not a defect but the answer for a real row: TCB's 2026 bonus
    issue carries a ``public_date`` and no ex-date at all.
    """
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        # ``pd.isna`` refuses some containers; a value it cannot judge is a value
        # to try parsing rather than one to drop.
        pass
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        stamp = pd.to_datetime(value)
    except (TypeError, ValueError):
        return None
    if stamp is None or pd.isna(stamp):
        return None
    return stamp.date()


def _icb_code(value: object) -> str | None:
    """The level-2 code, or nothing — never a piece of one.

    A value that does not fit a supersector code is dropped rather than cut:
    a code is an identifier, and half of one identifies a different industry.
    """
    text = _text(value)
    if text is None or len(text) > ICB_CODE_LENGTH:
        return None
    return text


def _icb_name(value: object) -> str | None:
    """The industry's name, bounded by the column that stores it.

    Cut rather than dropped, unlike the code: nothing branches on the name, so
    a long one shortened still says what it said.
    """
    text = _text(value)
    return None if text is None else text[:ICB_NAME_LENGTH]


def _text(value: object) -> str | None:
    """A provider cell as a non-empty string, or None."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value).strip() or None


def _listing_name(row: pd.Series) -> str | None:
    """Prefer the short trading name, fall back to the legal one, else nothing."""
    for field in LISTING_NAME_FIELDS:
        name = _text(row.get(field))
        if name is not None:
            return name
    return None


def _session_start(observed_at: datetime) -> datetime:
    """Return midnight of the Vietnamese trading day this read happened on."""
    return datetime.combine(
        observed_at.astimezone(VN_TZ).date(),
        datetime.min.time(),
        tzinfo=VN_TZ,
    )


def _rows_by_symbol(
    frame: pd.DataFrame,
    required_fields: Sequence[str],
    requested_symbols: Sequence[str],
) -> dict[str, pd.Series]:
    """Prove the fields arrived, then index the asked-for rows by symbol."""
    columns = {str(column).lower(): column for column in frame.columns}
    missing = set(required_fields) - columns.keys()
    if missing:
        raise VnstockProviderError(
            f"vnstock response is missing fields: {', '.join(sorted(missing))}"
        )

    working = frame.rename(columns={value: key for key, value in columns.items()})
    working = working.loc[:, list(required_fields)].copy()
    working["symbol"] = working["symbol"].astype(str).str.upper()
    wanted = working[working["symbol"].isin(list(requested_symbols))]
    return {str(row["symbol"]): row for _, row in wanted.iterrows()}


def _statement_periods(
    frame: pd.DataFrame | None,
    label: str,
) -> list[tuple[date, str]]:
    """Read the reporting periods off the column headers, newest first.

    An empty frame is a company the provider has no statements for and comes
    back as no periods. A frame with rows but no recognisable layout is a
    different thing entirely, and is refused: reading it would mean guessing
    both which figure is which and what scale it is in.
    """
    if frame is None or getattr(frame, "empty", True):
        return []

    if "item_id" not in frame.columns:
        raise VnstockProviderError(
            f"vnstock returned an unrecognised statement layout for {label}: "
            "no item_id column"
        )

    periods: list[tuple[date, str]] = []
    for column in frame.columns:
        match = PERIOD_PATTERN.match(str(column))
        if match is None:
            continue
        year, quarter = int(match.group(1)), int(match.group(2))
        month, day = QUARTER_END[quarter]
        periods.append((date(year, month, day), str(column)))

    if not periods:
        raise VnstockProviderError(
            f"vnstock returned an unrecognised statement layout for {label}: "
            "no quarterly period columns"
        )

    # Sorted rather than taken in column order: the provider happens to answer
    # newest first, but nothing in the response promises it.
    return sorted(periods, reverse=True)


def _statement_value(frame: pd.DataFrame, item_id: str, column: str) -> float | None:
    """Read one statement line for one period, or None if it is not there."""
    rows = frame[frame["item_id"].astype(str) == item_id]
    if rows.empty or column not in frame.columns:
        return None
    return _optional_float(rows.iloc[0][column])


def _trailing_net_income(
    income: pd.DataFrame,
    periods: list[tuple[date, str]],
) -> float | None:
    """Sum four quarters of parent profit, or report nothing at all.

    Anything shorter is not a trailing twelve months. Returning a partial sum
    under that name would understate earnings for exactly the symbols with the
    least history, which is where it would be hardest to notice.
    """
    if len(periods) < TRAILING_QUARTERS:
        return None

    quarters = [
        _statement_value(income, INCOME_ITEM_PARENT_PROFIT, column)
        for _, column in periods[:TRAILING_QUARTERS]
    ]
    if any(value is None for value in quarters):
        return None
    return sum(quarters)


def _balance_lines(
    balance: pd.DataFrame | None,
    column: str | None,
) -> dict[str, float | None]:
    """Read the balance-sheet lines one period's snapshot stores."""
    if balance is None or column is None:
        return {}
    return {
        "total_assets_vnd": _statement_value(balance, BALANCE_ITEM_TOTAL_ASSETS, column),
        "total_liabilities_vnd": _statement_value(
            balance, BALANCE_ITEM_LIABILITIES, column
        ),
        "short_term_borrowings_vnd": _statement_value(
            balance, BALANCE_ITEM_SHORT_TERM_BORROWINGS, column
        ),
        "long_term_borrowings_vnd": _statement_value(
            balance, BALANCE_ITEM_LONG_TERM_BORROWINGS, column
        ),
        "cash_and_equivalents_vnd": _statement_value(
            balance, BALANCE_ITEM_CASH_AND_EQUIVALENTS, column
        ),
    }


def _cash_flow_lines(
    cash_flow: pd.DataFrame | None,
    column: str | None,
) -> dict[str, float | None]:
    """Read the three net cash-flow lines one period's snapshot stores."""
    if cash_flow is None or column is None:
        return {}
    return {
        "cfo_vnd": _statement_value(cash_flow, CASHFLOW_ITEM_CFO, column),
        "cfi_vnd": _statement_value(cash_flow, CASHFLOW_ITEM_CFI, column),
        "cff_vnd": _statement_value(cash_flow, CASHFLOW_ITEM_CFF, column),
    }


def _parent_equity(balance: pd.DataFrame, column: str) -> float | None:
    """Return owner's equity less the minority interest sitting inside it.

    Under Circular 200 the minority interest is a line within owner's equity
    rather than a sibling of it — measured on HPG, liabilities plus owner's
    equity equals total assets exactly while the minority line is reported
    separately. Left in, this would credit the parent with equity it does not
    own.
    """
    equity = _statement_value(balance, BALANCE_ITEM_OWNERS_EQUITY, column)
    if equity is None:
        return None
    minority = _statement_value(balance, BALANCE_ITEM_MINORITY_INTERESTS, column)
    return equity - minority if minority is not None else equity


def _optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)
