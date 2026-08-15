"""One end-of-day collection cycle over the Universe.

The Collector is the only place in this system that calls out to a Provider
Source. It runs one cycle for the whole Universe, writes what comes back into
the SnapshotStore, and hands the operator a summary of how the cycle went.

Providers and the store arrive through the constructor, so a test can run a
whole cycle without a network, a Postgres or a Redis.
"""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.core.config import Settings, get_settings

from .providers import (
    BatchTooLarge,
    Capability,
    FundamentalDataProvider,
    MarketDataProvider,
    ReferenceDataProvider,
    SnapshotStore,
    SymbolSnapshot,
    ValuationDataProvider,
)
from .providers.normalize import VN_TZ
from .universe import Universe, build_universe

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 50

# Halving stops here. A single symbol the gateway still will not answer for is
# that symbol's failure; there is nothing smaller left to try.
MIN_BATCH_SIZE = 1

# How far back the valuation read reaches. The ratio series is dated by session,
# so a cycle that only asked for today would come back empty whenever it ran on
# a day the exchange was shut, and never go back for the session it missed. A
# week of sessions is still one call, and repeats collapse in the store.
VALUATION_LOOKBACK_DAYS = 7


@dataclass(frozen=True)
class SymbolFailure:
    """One symbol whose read or write went wrong for one capability, and why."""

    symbol: str
    capability: Capability
    reason: str


@dataclass(frozen=True)
class MissingSnapshot:
    """One symbol a well-formed answer simply carried no data for.

    Kept apart from a failure on purpose: a company with no financial report
    filed yet, or a symbol the provider publishes no ratios for, is a normal
    state of this market. Counting it as a failure would leave a healthy cycle
    reporting failures every day, which is how an operator learns to ignore
    the number.
    """

    symbol: str
    capability: Capability


@dataclass(frozen=True)
class CollectionSummary:
    """What one cycle did, in the terms an operator judges it by.

    ``succeeded`` holds the symbols that came away with at least one snapshot,
    ``failures`` the reads and writes that went wrong, and ``missing`` the
    capabilities a symbol simply had no data for. A symbol can appear in more
    than one of the three: that is the half-collected state worth seeing rather
    than rounding to healthy or broken.
    """

    snapshots_written: int
    succeeded: tuple[str, ...]
    failures: tuple[SymbolFailure, ...]
    missing: tuple[MissingSnapshot, ...] = ()


class Collector:
    """Run one cycle for the Universe against every wired Provider Source."""

    def __init__(
        self,
        store: SnapshotStore,
        universe: Universe,
        market: MarketDataProvider | None = None,
        valuation: ValuationDataProvider | None = None,
        reference: ReferenceDataProvider | None = None,
        fundamental: FundamentalDataProvider | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._store = store
        self._universe = universe
        self._market = market
        self._valuation = valuation
        self._reference = reference
        self._fundamental = fundamental
        self._batch_size = batch_size
        self._now = now

    @property
    def capabilities(self) -> tuple[Capability, ...]:
        """The capabilities this cycle will read, in the order it reads them.

        An operator running a cycle by hand needs to know what it is about to
        cover, and a cycle with no FiinQuant account configured covers less.
        """
        return tuple(capability for capability, _ in self._readers())

    def run(self) -> CollectionSummary:
        symbols = tuple(self._universe)
        written = 0
        succeeded: set[str] = set()
        failures: list[SymbolFailure] = []
        missing: list[MissingSnapshot] = []

        for capability, fetch in self._readers():
            snapshots, accounted = self._read(capability, fetch, symbols, failures)

            for snapshot in snapshots:
                accounted.add(snapshot.symbol)
                try:
                    self._store.save(capability, snapshot)
                except Exception as exc:
                    # One refused snapshot is one symbol's problem. Letting it
                    # out would end the cycle for every capability still to come.
                    self._blame(failures, (snapshot.symbol,), capability, exc)
                    continue
                written += 1
                succeeded.add(snapshot.symbol)

            # Silence is the state an operator cannot see on their own: the
            # cycle looks healthy while one symbol quietly stops being collected.
            missing.extend(
                MissingSnapshot(symbol=symbol, capability=capability)
                for symbol in symbols
                if symbol not in accounted
            )

        summary = CollectionSummary(
            snapshots_written=written,
            succeeded=tuple(symbol for symbol in symbols if symbol in succeeded),
            failures=tuple(failures),
            missing=tuple(missing),
        )
        logger.info(
            "Collector cycle wrote %d snapshots for %d of %d symbols, "
            "%d failures, %d capabilities with no data",
            summary.snapshots_written,
            len(summary.succeeded),
            len(symbols),
            len(summary.failures),
            len(summary.missing),
        )
        return summary

    def _read(
        self,
        capability: Capability,
        fetch: Callable[[Sequence[str]], Sequence[SymbolSnapshot]],
        symbols: Sequence[str],
        failures: list[SymbolFailure],
    ) -> tuple[list[SymbolSnapshot], set[str]]:
        """Read one capability for the whole Universe, batch by batch.

        Returns what came back and the symbols already accounted for by a call
        that failed, so those are not reported a second time as symbols the
        provider simply had nothing for.

        A batch the gateway gives up on is halved and put back at the front of
        the queue, so its symbols are still tried in the order the Universe
        declared them rather than drifting to the end of the cycle.
        """
        collected: list[SymbolSnapshot] = []
        accounted: set[str] = set()
        pending = deque(self._batches(symbols))

        while pending:
            batch = pending.popleft()
            try:
                collected.extend(fetch(batch))
            except Exception as exc:
                if isinstance(exc, BatchTooLarge) and len(batch) > MIN_BATCH_SIZE:
                    middle = len(batch) // 2
                    pending.appendleft(batch[middle:])
                    pending.appendleft(batch[:middle])
                    continue
                # One source failing is not the other sources failing: each
                # capability has an owner of its own (docs/adr/0002), and losing
                # valuation must not also lose price.
                self._blame(failures, batch, capability, exc)
                accounted.update(batch)

        return collected, accounted

    def _blame(
        self,
        failures: list[SymbolFailure],
        symbols: Sequence[str],
        capability: Capability,
        exc: Exception,
    ) -> None:
        """Attribute one failed call to every symbol that call was for."""
        reason = str(exc)
        logger.warning(
            "Collector could not collect %s for %s: %s",
            capability.value,
            ", ".join(symbols),
            reason,
        )
        failures.extend(
            SymbolFailure(symbol=symbol, capability=capability, reason=reason)
            for symbol in symbols
        )

    def _readers(
        self,
    ) -> Iterator[tuple[Capability, Callable[[Sequence[str]], Sequence[SymbolSnapshot]]]]:
        """Yield one read per capability that has an adapter wired to it."""
        if self._market is not None:
            yield Capability.MARKET, self._market.fetch_market
        if self._valuation is not None:
            yield Capability.VALUATION, self._fetch_valuation
        if self._reference is not None:
            yield Capability.REFERENCE, self._reference.fetch_reference
        if self._fundamental is not None:
            yield Capability.FUNDAMENTAL, self._fundamental.fetch_fundamentals

    def _fetch_valuation(self, batch: Sequence[str]) -> Sequence[SymbolSnapshot]:
        """Ask for the sessions that have closed since a cycle last succeeded.

        The contract has the collector asking for the session that just closed
        while a backfill asks for a stretch of history, and this stays on the
        collector's side of that line: it reaches back a week only because a
        cycle cannot assume it ran yesterday. The window is one call either way,
        and sessions already held collapse in the store.
        """
        session_date = self._now().astimezone(VN_TZ).date()
        return self._valuation.fetch_valuation(
            batch,
            session_date - timedelta(days=VALUATION_LOOKBACK_DAYS),
            session_date,
        )

    def _batches(self, symbols: Sequence[str]) -> Iterator[tuple[str, ...]]:
        for start in range(0, len(symbols), self._batch_size):
            yield tuple(symbols[start : start + self._batch_size])


def build_collector(
    store: SnapshotStore,
    settings: Settings | None = None,
    universe: Universe | None = None,
) -> Collector:
    """Wire the real adapters for the configured account.

    Adapters are imported here rather than at module scope, the way the
    providers package asks: importing one pulls in its provider library.

    A missing FiinQuant account is a configured state, not an error. A
    development environment runs without one and still collects the two
    capabilities vnstock owns, rather than refusing to start.

    The caller owns the transaction. Nothing here commits, so a run reaches
    PostgreSQL when the session it was handed does.
    """
    from .providers.fiinquant import (
        FiinQuantMarketProvider,
        FiinQuantValuationProvider,
        ProviderCircuitBreaker,
        shared_session_factory,
    )
    from .providers.vnstock_provider import (
        VnstockFundamentalProvider,
        VnstockReferenceProvider,
    )

    settings = settings or get_settings()
    market = valuation = None

    if settings.fiinquant_username and settings.fiinquant_password:
        # One login and one breaker across both adapters: the free tier grants a
        # single concurrent connection, and the health being tracked belongs to
        # the account rather than to either capability.
        session_factory = shared_session_factory()
        breaker = ProviderCircuitBreaker()
        market = FiinQuantMarketProvider(
            username=settings.fiinquant_username,
            password=settings.fiinquant_password,
            session_factory=session_factory,
            circuit_breaker=breaker,
        )
        valuation = FiinQuantValuationProvider(
            username=settings.fiinquant_username,
            password=settings.fiinquant_password,
            session_factory=session_factory,
            circuit_breaker=breaker,
        )
    else:
        logger.warning(
            "No FiinQuant account configured: this cycle collects reference and "
            "fundamental data only"
        )

    return Collector(
        store=store,
        # Both halves of the Universe: the cohort the census seated is collected
        # by exactly the same cycle as the declared symbols, which is what makes
        # a cohort member evaluable the day after it is activated.
        universe=universe or build_universe(store.session, settings),
        market=market,
        valuation=valuation,
        reference=VnstockReferenceProvider(vnstock_source=settings.vnstock_source),
        fundamental=VnstockFundamentalProvider(vnstock_source=settings.vnstock_source),
    )


def run_cycle(
    settings: Settings | None = None,
    universe: Universe | None = None,
) -> CollectionSummary:
    """Run one cycle against the configured account and commit what it wrote.

    This is the whole pipeline in one call: an operator running it by hand ends
    up with Snapshots in PostgreSQL for the Universe, which is the only proof
    that the collection path is alive end to end.

    Synchronous throughout. The store is synchronous and FiinQuantX is a
    synchronous library, so a caller on an event loop hands this to a thread
    rather than the other way round.

    It holds the Collector lease for the whole cycle (``docs/adr/0014``). That
    lease is what makes ADR-0001's rule real rather than a convention: while it
    is held, news, Backfill and the frozen legacy routes are refused outright
    instead of quietly sharing an allowance the cycle is already spending. It is
    released when the cycle ends, however it ends, and expires on its own if the
    process dies holding it.
    """
    from src.core.database import get_sync_db
    from src.core.quota import QuotaLane, quota_arbiter, quota_lane

    with quota_arbiter().collector_lease(), quota_lane(QuotaLane.COLLECTOR):
        with get_sync_db() as session:
            return build_collector(
                SnapshotStore(session), settings=settings, universe=universe
            ).run()


if __name__ == "__main__":  # pragma: no cover - the manual entry point
    logging.basicConfig(level=logging.INFO)
    summary = run_cycle()
    print(
        f"{summary.snapshots_written} snapshots, "
        f"{len(summary.succeeded)} symbols collected, "
        f"{len(summary.failures)} failures, "
        f"{len(summary.missing)} capabilities with no data"
    )
    for failure in summary.failures:
        print(f"  {failure.symbol} {failure.capability.value}: {failure.reason}")
