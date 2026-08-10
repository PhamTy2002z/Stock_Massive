"""The one-time history load from the Cover Source.

The Main Source is granted about five years of daily history. Anything deeper
than that is loaded once, from vnstock, and then never again: this is the most
expensive thing the system asks of that provider, and a load that repeated
would spend an account's whole allowance on data already held.

Progress is written to the database as it goes, so a restart resumes where it
stopped and a symbol that leaves the Universe and comes back only fetches what
it is still missing.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.config import Settings, get_settings
from src.stocks.models import SymbolBackfill

from .providers import Capability, MarketSnapshot, SnapshotStore
from .providers.normalize import VN_TZ
from .universe import Universe

logger = logging.getLogger(__name__)

# Measured on the free tier: five years of daily history came back, 1.247
# sessions reaching 2021-08. The load stops where that begins, because past it
# the Main Source answers with a richer session than a quote history carries.
MAIN_SOURCE_HISTORY_DAYS = 5 * 365

# How deep the load goes. Ten years is what a long-term trend needs and what
# VCI answers with; it is a product decision rather than a provider limit.
HISTORY_DEPTH_DAYS = 10 * 365

# One call per year of history. Large enough that a decade is ten calls rather
# than a hundred, small enough that an interrupted load loses little.
CHUNK_DAYS = 365

# How many symbols one run will take on. The allowance is shared with the daily
# cycle, and a load that spent all of it would starve the collection that
# everything else depends on.
SYMBOLS_PER_RUN = 5

BackfillStatus = Literal["in_progress", "completed", "failed"]


class MarketHistoryProvider(Protocol):
    """Read a stretch of one symbol's history from the Cover Source."""

    def fetch_market_history(
        self,
        symbol: str,
        from_date: date,
        to_date: date,
    ) -> Sequence[MarketSnapshot]: ...


@dataclass(frozen=True)
class SymbolProgress:
    """Where one symbol's load stands, and why if it stopped badly."""

    symbol: str
    status: BackfillStatus
    covered_through: date | None = None
    reason: str | None = None


@dataclass(frozen=True)
class BackfillSummary:
    """What one run of the load did, per symbol."""

    snapshots_written: int
    progress: tuple[SymbolProgress, ...]

    def _with_status(self, status: BackfillStatus) -> tuple[SymbolProgress, ...]:
        return tuple(item for item in self.progress if item.status == status)

    @property
    def completed(self) -> tuple[str, ...]:
        return tuple(item.symbol for item in self._with_status("completed"))

    @property
    def in_progress(self) -> tuple[str, ...]:
        return tuple(item.symbol for item in self._with_status("in_progress"))

    @property
    def failed(self) -> tuple[SymbolProgress, ...]:
        return self._with_status("failed")


class BackfillStateStore:
    """How far each symbol's load has got, kept where a restart can find it."""

    def __init__(self, session: Session):
        self.session = session

    def get(self, symbol: str) -> SymbolBackfill | None:
        return self.session.execute(
            select(SymbolBackfill).where(SymbolBackfill.symbol == symbol.upper())
        ).scalar_one_or_none()

    def all(self) -> list[SymbolBackfill]:
        return list(
            self.session.execute(
                select(SymbolBackfill).order_by(SymbolBackfill.symbol)
            ).scalars()
        )

    def record(
        self,
        symbol: str,
        status: BackfillStatus,
        covered_through: date | None = None,
        reason: str | None = None,
    ) -> None:
        """Write this symbol's position, keeping the ground it already covered.

        ``covered_through`` only ever moves forward: a run that failed before
        fetching anything must not erase what an earlier run paid for.
        """
        state = self.get(symbol)
        if state is None:
            state = SymbolBackfill(symbol=symbol.upper())
            self.session.add(state)
        state.status = status
        if covered_through is not None:
            state.covered_through = covered_through
        state.last_error = reason[:500] if reason else None
        self.session.flush()

    def commit(self) -> None:
        """Make everything written so far survive a restart.

        Called between chunks rather than at the end of the run: resuming is
        the whole point of this state, and state that only lands when the run
        finishes is state that never lands on the runs that need it.
        """
        self.session.commit()


class Backfill:
    """Load each Universe symbol's deep history once, and remember that it did."""

    def __init__(
        self,
        store: SnapshotStore,
        state: BackfillStateStore,
        universe: Universe,
        history: MarketHistoryProvider,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        depth_days: int = HISTORY_DEPTH_DAYS,
        main_source_days: int = MAIN_SOURCE_HISTORY_DAYS,
        chunk_days: int = CHUNK_DAYS,
        symbols_per_run: int = SYMBOLS_PER_RUN,
        chunk_limit: int | None = None,
    ) -> None:
        self._store = store
        self._state = state
        self._universe = universe
        self._history = history
        self._now = now
        self._depth_days = depth_days
        self._main_source_days = main_source_days
        self._chunk_days = chunk_days
        self._symbols_per_run = symbols_per_run
        # Bounds the chunks one symbol gets in one run. Left off by default;
        # it exists so a run can be stopped part-way and proven to resume.
        self._chunk_limit = chunk_limit

    def run(self) -> BackfillSummary:
        today = self._now().astimezone(VN_TZ).date()
        boundary = today - timedelta(days=self._main_source_days)
        earliest = today - timedelta(days=self._depth_days)

        written = 0
        progress: list[SymbolProgress] = []
        owed = self._symbols_to_load(boundary)

        for symbol in self._universe:
            if symbol not in owed:
                # Already loaded, and still worth reporting: "which symbols are
                # done" is a question about the Universe, not about this run.
                progress.append(self._settled(symbol))
                continue
            count, item = self._load(symbol, earliest, boundary)
            written += count
            progress.append(item)

        logger.info(
            "Backfill run wrote %d snapshots across %d symbols",
            written,
            len(progress),
        )
        return BackfillSummary(
            snapshots_written=written, progress=tuple(progress)
        )

    def _settled(self, symbol: str) -> SymbolProgress:
        """Report a symbol this run did not touch, from what is on record.

        A symbol left waiting for the next run reads as in progress rather than
        as done: nothing about it has finished.
        """
        state = self._state.get(symbol)
        if state is None:
            return SymbolProgress(symbol=symbol, status="in_progress")
        return SymbolProgress(
            symbol=symbol,
            status=state.status,
            covered_through=state.covered_through,
            reason=state.last_error,
        )

    def _symbols_to_load(self, boundary: date) -> list[str]:
        """Pick the symbols still owed history, up to this run's allowance."""
        owed = [
            symbol
            for symbol in self._universe
            if not self._is_done(self._state.get(symbol), boundary)
        ]
        if len(owed) > self._symbols_per_run:
            logger.info(
                "Backfill is taking %d of %d symbols this run; the rest wait for "
                "the next one",
                self._symbols_per_run,
                len(owed),
            )
        return owed[: self._symbols_per_run]

    @staticmethod
    def _is_done(state: SymbolBackfill | None, boundary: date) -> bool:
        if state is None:
            return False
        if state.status == "completed":
            return True
        # A failed or half-finished symbol that nonetheless reached the
        # boundary is done: there is nothing left to ask for.
        return state.covered_through is not None and state.covered_through >= boundary

    def _load(
        self,
        symbol: str,
        earliest: date,
        boundary: date,
    ) -> tuple[int, SymbolProgress]:
        """Walk one symbol's missing years, recording progress as it goes."""
        state = self._state.get(symbol)
        start = (
            state.covered_through + timedelta(days=1)
            if state is not None and state.covered_through is not None
            else earliest
        )

        written = 0
        covered_through = state.covered_through if state is not None else None

        for chunk_start, chunk_end in self._chunks(start, boundary):
            try:
                snapshots = self._history.fetch_market_history(
                    symbol, chunk_start, chunk_end
                )
            except Exception as exc:
                reason = f"{type(exc).__name__}: {exc}"
                logger.warning("Backfill for %s stopped: %s", symbol, reason)
                self._state.record(
                    symbol, "failed", covered_through=covered_through, reason=reason
                )
                self._state.commit()
                return written, SymbolProgress(
                    symbol=symbol,
                    status="failed",
                    covered_through=covered_through,
                    reason=reason,
                )

            written += self._write(symbol, snapshots)
            covered_through = chunk_end
            # Recorded and committed per chunk: a restart between two chunks
            # must cost the one chunk, not the whole stretch of history.
            self._state.record(symbol, "in_progress", covered_through=chunk_end)
            self._state.commit()

        # Nothing left to ask for, either because the walk reached the boundary
        # or because it never had a stretch to walk: a symbol whose history is
        # all within the Main Source's reach is loaded by having nothing to load.
        done = start > boundary or (
            covered_through is not None and covered_through >= boundary
        )
        status: BackfillStatus = "completed" if done else "in_progress"
        self._state.record(symbol, status, covered_through=covered_through)
        self._state.commit()
        return written, SymbolProgress(
            symbol=symbol, status=status, covered_through=covered_through
        )

    def _write(self, symbol: str, snapshots: Sequence[MarketSnapshot]) -> int:
        written = 0
        for snapshot in snapshots:
            try:
                self._store.save(Capability.MARKET, snapshot)
            except Exception as exc:
                # One refused session is one day of history, not a reason to
                # abandon the decade around it.
                logger.warning(
                    "Backfill could not store a %s session for %s: %s",
                    snapshot.metadata.effective_at.date(),
                    symbol,
                    exc,
                )
                continue
            written += 1
        return written

    def _chunks(self, start: date, boundary: date) -> Iterator[tuple[date, date]]:
        """Yield the windows still to fetch, oldest first.

        A symbol whose history already reaches the boundary yields nothing,
        which is how "there is no stretch deeper than the Main Source" reads
        the same as "already loaded".
        """
        produced = 0
        while start <= boundary:
            if self._chunk_limit is not None and produced >= self._chunk_limit:
                return
            end = min(start + timedelta(days=self._chunk_days - 1), boundary)
            yield start, end
            produced += 1
            start = end + timedelta(days=1)


def build_backfill(
    store: SnapshotStore,
    state: BackfillStateStore,
    settings: Settings | None = None,
    universe: Universe | None = None,
) -> Backfill:
    """Wire the Cover Source adapter for the configured account."""
    from .providers.vnstock_provider import VnstockMarketHistoryProvider

    settings = settings or get_settings()
    return Backfill(
        store=store,
        state=state,
        universe=universe or Universe.from_settings(settings),
        history=VnstockMarketHistoryProvider(vnstock_source=settings.vnstock_source),
        symbols_per_run=settings.backfill_symbols_per_run,
    )


def run_backfill(settings: Settings | None = None) -> BackfillSummary:
    """Run one pass of the history load and commit what it wrote."""
    from src.core.database import get_sync_db

    with get_sync_db() as session:
        return build_backfill(
            SnapshotStore(session), BackfillStateStore(session), settings=settings
        ).run()
