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

from .providers import (
    Capability,
    MarketSnapshot,
    SnapshotStore,
    SymbolSnapshot,
    ValuationSnapshot,
)
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

# How far before a chunk starts the request reaches. The adapter measures a
# session's change against the session before it in the same answer, so without
# this the first session of every chunk would be stored with no reference price
# — and which sessions those were would depend on when a run happened to be
# interrupted. Wide enough to clear a long weekend; it costs no extra call, and
# the sessions it repeats collapse in the store.
CHUNK_OVERLAP_DAYS = 7

# How many symbols one run will take on. The allowance is shared with the daily
# cycle, and a load that spent all of it would starve the collection that
# everything else depends on.
SYMBOLS_PER_RUN = 5

BackfillStatus = Literal["pending", "in_progress", "completed", "failed"]


class MarketHistoryProvider(Protocol):
    """Read a stretch of one symbol's session history."""

    def fetch_market_history(
        self,
        symbol: str,
        from_date: date,
        to_date: date,
    ) -> Sequence[MarketSnapshot]: ...


class ValuationHistoryProvider(Protocol):
    """Read a stretch of the ratio series, which arrives per symbol per session."""

    def fetch_valuation(
        self,
        symbols: Sequence[str],
        from_date: date,
        to_date: date,
    ) -> Sequence[ValuationSnapshot]: ...


@dataclass(frozen=True)
class Segment:
    """One stretch of history and the source that reaches it.

    The load is not one walk from one provider: the deep years come from the
    Cover Source and the Main Source's own granted window comes from the Main
    Source, which is the only reason the daily cycle can be cheap. Segments run
    oldest first so the single per-symbol cursor stays monotonic across both.
    """

    history: MarketHistoryProvider
    ends: date
    valuation: ValuationHistoryProvider | None = None


@dataclass(frozen=True)
class HistoryWindow:
    """How deep the load reaches, where it stops, and how it is cut up.

    One type because the three always travel together and only mean anything
    against each other: the depth is measured from the same day the boundary
    is, and a chunk is a slice of the stretch between them.
    """

    depth_days: int = HISTORY_DEPTH_DAYS
    main_source_days: int = MAIN_SOURCE_HISTORY_DAYS
    chunk_days: int = CHUNK_DAYS
    overlap_days: int = CHUNK_OVERLAP_DAYS

    def crossover(self, today: date) -> date:
        """The newest session the Cover Source is asked for.

        Past it the Main Source is granted its own history and answers with a
        richer session than a quote history carries, so the Cover Source stops
        rather than spending the scarcer allowance on data the other reaches.
        """
        return today - timedelta(days=self.main_source_days)

    def earliest(self, today: date) -> date:
        """The oldest session the load reaches back to."""
        return today - timedelta(days=self.depth_days)

    def chunks(self, start: date, boundary: date) -> Iterator[tuple[date, date, date]]:
        """Yield the windows still to fetch, oldest first.

        Each is (asked-for start, covered start, covered end). The asked-for
        start reaches back before the covered one so the adapter can measure the
        first covered session against the one before it; the covered end is what
        progress is recorded at, because that is what this chunk is responsible
        for.

        A start already past the boundary yields nothing, which is how "there
        is no stretch deeper than the Main Source" reads the same as "already
        loaded".
        """
        while start <= boundary:
            end = min(start + timedelta(days=self.chunk_days - 1), boundary)
            yield start - timedelta(days=self.overlap_days), start, end
            start = end + timedelta(days=1)


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
    def pending(self) -> tuple[str, ...]:
        return tuple(item.symbol for item in self._with_status("pending"))

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
        main_history: MarketHistoryProvider | None = None,
        valuation_history: ValuationHistoryProvider | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        window: HistoryWindow = HistoryWindow(),
        symbols_per_run: int = SYMBOLS_PER_RUN,
    ) -> None:
        self._store = store
        self._state = state
        self._universe = universe
        self._history = history
        self._main_history = main_history
        self._valuation_history = valuation_history
        self._now = now
        self._window = window
        self._symbols_per_run = symbols_per_run

    def run(self) -> BackfillSummary:
        today = self._now().astimezone(VN_TZ).date()
        earliest = self._window.earliest(today)
        segments = self._segments(today)
        # What the walk is responsible for reaching. Without a Main Source
        # account there is no second segment, so the load ends where it always
        # did rather than sitting half-finished waiting for a window nothing in
        # this environment can fetch.
        boundary = segments[-1].ends

        # Read once. Asking per symbol per question would be three round trips
        # each and three chances for the answers to disagree.
        recorded = {state.symbol: state for state in self._state.all()}
        owed = self._symbols_to_load(recorded, boundary, self._window.crossover(today))

        written = 0
        progress: list[SymbolProgress] = []

        for symbol in self._universe:
            if symbol not in owed:
                # Already loaded, and still worth reporting: "which symbols are
                # done" is a question about the Universe, not about this run.
                progress.append(self._settled(recorded.get(symbol), symbol))
                continue
            count, item = self._load(
                recorded.get(symbol), symbol, earliest, boundary, segments
            )
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

    @staticmethod
    def _settled(state: SymbolBackfill | None, symbol: str) -> SymbolProgress:
        """Report a symbol this run did not touch, from what is on record.

        A symbol with no record has not started — distinct from one that is
        part-way through, because "waiting its turn behind the per-run cap" and
        "half loaded" call for different reactions from whoever is watching.
        """
        if state is None:
            return SymbolProgress(symbol=symbol, status="pending")
        return SymbolProgress(
            symbol=symbol,
            status=state.status,
            covered_through=state.covered_through,
            reason=state.last_error,
        )

    def _symbols_to_load(
        self,
        recorded: dict[str, SymbolBackfill],
        boundary: date,
        crossover: date,
    ) -> list[str]:
        """Pick the symbols still owed history, up to this run's allowance."""
        owed = [
            symbol
            for symbol in self._universe
            if not self._is_done(recorded.get(symbol), boundary, crossover)
        ]
        if len(owed) > self._symbols_per_run:
            logger.info(
                "Backfill is taking %d of %d symbols this run; the rest wait for "
                "the next one",
                self._symbols_per_run,
                len(owed),
            )
        return owed[: self._symbols_per_run]

    def _is_done(
        self,
        state: SymbolBackfill | None,
        boundary: date,
        crossover: date,
    ) -> bool:
        """Whether this symbol is owed nothing, this run or any later one.

        A completed walk settles the symbol for good. The end of that walk was
        the day it ran, and every session since is the `Collector`'s — asking
        again each day would make a one-time load into a second daily cycle
        writing what the first already wrote.

        With one exception, which is why the status alone will not do: a symbol
        loaded while no FiinQuant account was configured stopped at the
        crossover and never saw the Main Source's own window. Once an account
        appears it is genuinely owed those years, and reading "completed" as
        settled would leave it with a hole nothing would ever fill.

        A symbol that stopped part-way — failed, or interrupted — is judged on
        its cursor instead, so it resumes rather than being written off.
        """
        if state is None or state.covered_through is None:
            return False
        entered_the_main_window = state.covered_through > crossover
        if state.status == "completed":
            return self._main_history is None or entered_the_main_window
        return state.covered_through >= boundary

    def _segments(self, today: date) -> tuple[Segment, ...]:
        """The stretches this load walks, oldest first, each with its source."""
        crossover = self._window.crossover(today)
        segments = [Segment(history=self._history, ends=crossover)]
        if self._main_history is not None:
            segments.append(
                Segment(
                    history=self._main_history,
                    ends=today,
                    valuation=self._valuation_history,
                )
            )
        return tuple(segments)

    def _load(
        self,
        state: SymbolBackfill | None,
        symbol: str,
        earliest: date,
        boundary: date,
        segments: Sequence[Segment],
    ) -> tuple[int, SymbolProgress]:
        """Walk one symbol's missing years, recording progress as it goes."""
        start = (
            state.covered_through + timedelta(days=1)
            if state is not None and state.covered_through is not None
            else earliest
        )

        written = 0
        covered_through = state.covered_through if state is not None else None
        # Why the walk found nothing, if it found nothing. A symbol that never
        # answered is a failure to report; one that answered eventually had a
        # listing date, not a fault.
        nothing_yet: str | None = None

        for segment in segments:
            for asked_from, _covered_from, chunk_end in self._window.chunks(
                start, segment.ends
            ):
                try:
                    written += self._write(
                        symbol,
                        segment.history.fetch_market_history(
                            symbol, asked_from, chunk_end
                        ),
                        Capability.MARKET,
                    )
                    if segment.valuation is not None:
                        written += self._write(
                            symbol,
                            segment.valuation.fetch_valuation(
                                [symbol], asked_from, chunk_end
                            ),
                            Capability.VALUATION,
                        )
                except Exception as exc:
                    reason = f"{type(exc).__name__}: {exc}"
                    if covered_through is None:
                        # Nothing has loaded for this symbol yet, and the most
                        # likely reason a window that old cannot be answered is
                        # that the company had not listed in it — vnstock raises
                        # for such a window rather than answering with no
                        # sessions, so a walk that stopped here would never load
                        # the years the symbol does have.
                        #
                        # The cursor stays where it is, so nothing is skipped
                        # over: if this was an outage rather than a listing
                        # date, the next run asks these years again.
                        logger.info(
                            "Backfill found no history for %s through %s: %s",
                            symbol,
                            chunk_end,
                            reason,
                        )
                        nothing_yet = reason
                        continue
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

                covered_through = chunk_end
                # Recorded and committed per chunk: a restart between two chunks
                # must cost the one chunk, not the whole stretch of history.
                self._state.record(symbol, "in_progress", covered_through=chunk_end)
                self._state.commit()
            # The next segment picks up the day after this one ended, never
            # before: one cursor covers both only because they run in order.
            start = max(start, segment.ends + timedelta(days=1))

        # A walk that asked for every window it could and came away with
        # nothing is a symbol that could not be loaded, whatever the windows
        # said one at a time.
        if covered_through is None and nothing_yet is not None:
            self._state.record(symbol, "failed", reason=nothing_yet)
            self._state.commit()
            return written, SymbolProgress(
                symbol=symbol, status="failed", reason=nothing_yet
            )

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

    def _write(
        self,
        symbol: str,
        snapshots: Sequence[SymbolSnapshot],
        capability: Capability,
    ) -> int:
        written = 0
        for snapshot in snapshots:
            try:
                self._store.save(capability, snapshot)
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

def build_backfill(
    store: SnapshotStore,
    state: BackfillStateStore,
    settings: Settings | None = None,
    universe: Universe | None = None,
) -> Backfill:
    """Wire one adapter per stretch of history the load has to cover.

    The Cover Source is always there; the Main Source only when an account is
    configured, which is why a development environment loads the deep years and
    stops. Both FiinQuant adapters share one login and one breaker: the free
    tier grants a single concurrent connection, and the health being tracked
    belongs to the account rather than to either capability.
    """
    from .providers.vnstock_provider import VnstockMarketHistoryProvider

    settings = settings or get_settings()
    main_history = valuation_history = None

    if settings.fiinquant_username and settings.fiinquant_password:
        from .providers.fiinquant import (
            FiinQuantMarketProvider,
            FiinQuantValuationProvider,
            ProviderCircuitBreaker,
            shared_session_factory,
        )

        account = {
            "username": settings.fiinquant_username,
            "password": settings.fiinquant_password,
            "session_factory": shared_session_factory(),
            "circuit_breaker": ProviderCircuitBreaker(),
        }
        main_history = FiinQuantMarketProvider(**account)
        valuation_history = FiinQuantValuationProvider(**account)

    return Backfill(
        store=store,
        state=state,
        universe=universe or Universe.from_settings(settings),
        history=VnstockMarketHistoryProvider(vnstock_source=settings.vnstock_source),
        main_history=main_history,
        valuation_history=valuation_history,
        window=HistoryWindow(
            depth_days=settings.backfill_depth_days,
            main_source_days=settings.backfill_main_source_days,
        ),
        symbols_per_run=settings.backfill_symbols_per_run,
    )


def run_backfill(settings: Settings | None = None) -> BackfillSummary:
    """Run one pass of the history load and commit what it wrote."""
    from src.core.database import get_sync_db

    with get_sync_db() as session:
        return build_backfill(
            SnapshotStore(session), BackfillStateStore(session), settings=settings
        ).run()
