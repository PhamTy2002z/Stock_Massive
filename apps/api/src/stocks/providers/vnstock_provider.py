"""vnstock adapters for the reference and fundamental capabilities.

vnstock is the Main Source for both (``docs/adr/0002``): the free FiinQuant
tier returns empty share counts, and answers foreign room with a 403. These two
capabilities had a contract and no implementation until now.

The binding constraint here is quota rather than the gateway — 20 requests a
minute without an API key, 60 with one — so the two adapters read very
differently. Reference comes off one batched price board that covers the whole
Universe in a single request. Statements have no batched form at all, so
fundamental pays two requests per symbol and paces itself to the allowance.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable, Sequence
from datetime import date, datetime, timezone
from time import monotonic, sleep
from typing import Any

import pandas as pd
from pydantic import ValidationError

from src.core.config import get_settings
from src.core.vnstock_client import (
    Finance,
    Trading,
    VnstockUnavailable,
    VnstockUnsupported,
)

from .contracts import (
    FundamentalSnapshot,
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

# The allowances vnstock's own quota layer grants: its guest tier is cut off at
# 20 requests a minute and an API key lifts that to 60.
QUOTA_WITHOUT_API_KEY = 20
QUOTA_WITH_API_KEY = 60

# The same environment variable vnstock's quota layer reads to decide the tier.
# Deliberately not a pydantic setting: settings also load from a .env file
# without reaching the environment, and a key vnstock never sees would triple
# the pace this adapter runs at while the account stayed on the guest tier.
API_KEY_ENV_VAR = "VNSTOCK_API_KEY"

# The flattened VCI price board carries all of reference in one row per symbol.
# ``current_room`` is the room still available, not the holding — measured
# against HPG, FPT and VCB, where total room less current room matches each
# company's published foreign ownership.
REFERENCE_FIELDS = ("symbol", "listed_share", "current_room", "total_room")

# Statement rows are addressed by ``item_id`` rather than by their label: the
# label is free text that arrives in two languages and changes wording, while
# the id is the provider's stable key.
INCOME_ITEM_PARENT_PROFIT = "attributable_to_parent_company"
BALANCE_ITEM_OWNERS_EQUITY = "owners_equity"
BALANCE_ITEM_MINORITY_INTERESTS = "minority_interests"

TRAILING_QUARTERS = 4

# Statement periods arrive as column headers, one per quarter.
PERIOD_PATTERN = re.compile(r"^(\d{4})-Q([1-4])$")
QUARTER_END = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}


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


def quota_per_minute(api_key: str) -> int:
    """Return the request allowance these credentials actually have."""
    return QUOTA_WITH_API_KEY if api_key else QUOTA_WITHOUT_API_KEY


class RequestPacer:
    """Space calls out so a run can never outpace the provider's allowance.

    Discovering the limit by being cut off costs the whole remaining run:
    vnstock answers an exhausted quota by calling ``sys.exit()``, so a collector
    that sprints into it takes the process with it. Waiting is cheaper.
    """

    def __init__(
        self,
        calls_per_minute: int,
        clock: Callable[[], float] = monotonic,
        sleep: Callable[[float], None] = sleep,
    ) -> None:
        if calls_per_minute < 1:
            raise ValueError("the request allowance must be at least one per minute")
        self.min_interval = 60.0 / calls_per_minute
        self._clock = clock
        self._sleep = sleep
        self._last_call: float | None = None

    def wait(self) -> None:
        now = self._clock()
        if self._last_call is not None:
            remaining = self.min_interval - (now - self._last_call)
            if remaining > 0:
                self._sleep(remaining)
                # Advance by what was slept rather than reading the clock
                # again: the two agree, and one reading keeps the pacing
                # honest even when the clock is coarse.
                now += remaining
        self._last_call = now


_process_pacer: RequestPacer | None = None


def process_pacer() -> RequestPacer:
    """Return the one pacer every adapter shares by default.

    The allowance belongs to the account, not to an adapter. Two adapters each
    pacing themselves would run a cycle that reads both capabilities at twice
    the allowance and be cut off halfway through — and vnstock answers an
    exhausted quota by calling ``sys.exit()``, taking the collector with it.

    Built once, from the environment vnstock's own quota layer reads, so the
    pace this adapter keeps and the tier vnstock grants cannot disagree.
    """
    global _process_pacer
    if _process_pacer is None:
        _process_pacer = RequestPacer(
            quota_per_minute(os.environ.get(API_KEY_ENV_VAR, ""))
        )
    return _process_pacer


def _default_trading_factory(source: str) -> Any:
    return Trading(source=source)


def _default_finance_factory(symbol: str, source: str) -> Any:
    return Finance(symbol=symbol, source=source)


class VnstockProviderBase:
    """Symbol handling, pacing and error hygiene shared by both adapters."""

    source = ProviderSource.VNSTOCK

    def __init__(
        self,
        vnstock_source: str | None = None,
        pacer: RequestPacer | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._vnstock_source = vnstock_source or get_settings().vnstock_source
        self._pacer = pacer or process_pacer()
        self._now = now

    def _paced(self, call: Callable[[], Any], message: str) -> Any:
        """Run one upstream read within the allowance, keeping its text out of ours.

        Quota exhaustion and an unimplemented provider carry meanings of their
        own that the rest of the app already handles, so they travel unchanged.
        """
        self._pacer.wait()
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
        pacer: RequestPacer | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        trading_factory: Callable[[str], Any] = _default_trading_factory,
    ) -> None:
        super().__init__(vnstock_source=vnstock_source, pacer=pacer, now=now)
        self._trading_factory = trading_factory

    def fetch_reference(self, symbols: Sequence[str]) -> Sequence[ReferenceSnapshot]:
        normalized = normalized_symbols(symbols)
        if not normalized:
            return ()

        board = self._paced(
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
        snapshots: list[ReferenceSnapshot] = []

        for symbol in requested_symbols:
            row = rows.get(symbol)
            if row is None:
                continue
            snapshot = self._build(symbol, row, observed_at)
            if snapshot is not None:
                snapshots.append(snapshot)

        return tuple(snapshots)

    def _build(
        self,
        symbol: str,
        row: pd.Series,
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
                    # The board describes the position as of the read; it
                    # carries no period of its own to date it by.
                    effective_at=observed_at,
                    observed_at=observed_at,
                ),
                shares=shares,
                current_foreign_room=current_room,
                total_foreign_room=total_room,
            )
        except ValidationError as exc:
            logger.warning("Skipping unusable vnstock reference row for %s: %s", symbol, exc)
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
        pacer: RequestPacer | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        finance_factory: Callable[[str, str], Any] = _default_finance_factory,
    ) -> None:
        super().__init__(vnstock_source=vnstock_source, pacer=pacer, now=now)
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
                snapshot = self._fetch_one(symbol, observed_at)
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
            if snapshot is not None:
                snapshots.append(snapshot)

        return tuple(snapshots)

    def _fetch_one(
        self,
        symbol: str,
        observed_at: datetime,
    ) -> FundamentalSnapshot | None:
        finance = self._finance_factory(symbol, self._vnstock_source)
        income = self._paced(
            lambda: finance.income_statement(period="quarter", lang="en", dropna=True),
            f"vnstock income statement fetch failed for {symbol}",
        )
        balance = self._paced(
            lambda: finance.balance_sheet(period="quarter", lang="en", dropna=True),
            f"vnstock balance sheet fetch failed for {symbol}",
        )

        income_periods = _statement_periods(income, f"{symbol} income statement")
        if not income_periods:
            logger.info("Skipping %s: vnstock reports no income statement", symbol)
            return None

        period_end, latest_column = income_periods[0]
        balance_periods = _statement_periods(balance, f"{symbol} balance sheet")

        try:
            return FundamentalSnapshot(
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
                    income, income_periods
                ),
                parent_equity_vnd=(
                    _parent_equity(balance, latest_column) if balance_periods else None
                ),
            )
        except ValidationError as exc:
            logger.warning("Skipping unusable vnstock statements for %s: %s", symbol, exc)
            return None


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
