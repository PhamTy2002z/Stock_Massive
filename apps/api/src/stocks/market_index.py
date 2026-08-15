"""The benchmark's own session series, and how deep it has to be.

`relative_strength.beta_vs_market_index` is registered and refuses, and until
this module ran it refused because **this system stored no market-index session
series**. The VN-Index existed only as an alias inside the live price path, and
reading it from there is exactly the substitution ``docs/specs/0003`` §13
forbids: a legacy live read used to make a registered field look available. So
the field was honest and useless at the same time, and this is the load that
turns it into something a number can be computed from.

## The market index load is not a Warm-up, and not a Backfill

It borrows a property from each and matches neither, so it is named for itself
rather than dressed as one of them. Like a **Warm-up** (``docs/adr/0005``) it is
repeatable and reads the Main Source only — the run that first fills the series
is the run that tops it up tomorrow and repairs a week the collector was down.
Like a **Backfill** it is deep: a year of sessions rather than the recent signal
window. And unlike both it loads one instrument that is in no Universe, under a
Capability of its own.

Calling it a Warm-up would have been the convenient lie: `CONTEXT.md` defines
that term as recent ``market`` history that makes a *Universe member* evaluable,
and none of those three words is true here.

## Why the depth is the field's own floor, and where that is enforced

``RELATIVE_STRENGTH_MIN_SESSIONS`` is 250, and ``prepare_bars()`` refuses a
window that reaches fewer sessions than the field declares. A benchmark stored
249 sessions deep would therefore leave that field refusing under
``insufficient_history`` — the same unavailability wearing a reason that points
at the wrong fix, and a reader chasing a collection gap that is really a
configuration one.

Spelling the default as ``RELATIVE_STRENGTH_MIN_SESSIONS + a margin`` is not
enough on its own, because production reads the depth from configuration and a
constant nothing checks is a comment. So ``build_market_index_loader`` compares
what was actually configured against the field's floor and refuses to wire a
loader that cannot serve it. Shortening the load below what the only reader of
the series needs is then a refusal an operator sees, rather than a field that
starts refusing for an unrelated-sounding reason weeks later.

The margin on top is a month of sessions: how far behind the daily run may fall
— a long holiday, a broken week — while still leaving the field its full 250 the
moment the load succeeds again.

## One index, and where its identity comes from

The series exists for one declared field, so the field names both what to store
and how deep: ``RELATIVE_STRENGTH_BENCHMARK`` is the benchmark's code and
``RELATIVE_STRENGTH_MIN_SESSIONS`` its floor, both read from the field's own
module rather than restated here. A second index would be a second declaration
there, not a second literal here.

Stored under ``Capability.MARKET_INDEX`` rather than under ``market`` with a
reserved symbol — ``docs/adr/0017`` records why, and the short version is that a
**Trading Day** is derived from the ``market`` Capability, so an index session
stored there would help define the market-wide window every equity is measured
against.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal

from src.core.config import Settings, get_settings

from .providers import (
    Capability,
    MarketIndexHistoryProvider,
    MarketIndexSnapshot,
    SnapshotStore,
    main_source,
)
from .providers.normalize import VN_TZ
from .session_window import newest_sessions, reaches_back_to
from .signals.cross_sectional import (
    RELATIVE_STRENGTH_BENCHMARK,
    RELATIVE_STRENGTH_MIN_SESSIONS,
)

logger = logging.getLogger(__name__)

# The index this system stores a series for, named by the one field that reads
# it. Bound to a storage-side name so a loader, a job and a test can say what
# they are loading without importing a signals module for a string.
MARKET_INDEX_SYMBOL = RELATIVE_STRENGTH_BENCHMARK

# How far behind the daily run may fall and still leave the deepest field its
# full window on the next successful run.
MARKET_INDEX_MARGIN_SESSIONS = 25

MARKET_INDEX_WINDOW_TRADING_DAYS = (
    RELATIVE_STRENGTH_MIN_SESSIONS + MARKET_INDEX_MARGIN_SESSIONS
)

MarketIndexStatus = Literal["completed", "failed"]


class MarketIndexUnavailable(RuntimeError):
    """The benchmark series cannot be loaded as configured.

    Two conditions, both configuration rather than weather. **No Main Source
    account**: the ``market_index`` Capability has one owner and no cover on
    purpose (``docs/adr/0017``), because the Cover Source's quote history is
    ``adjusted_at_source`` while an index is adjusted for nothing — a series
    filled from there would carry a basis asserting a rescaling nobody
    performed. **A depth below what the only reader needs**: see the module
    docstring; a load shortened past the field's floor produces a field refusing
    for a reason that points somewhere else.
    """


@dataclass(frozen=True)
class MarketIndexResult:
    """How one index's load went."""

    index: str
    status: MarketIndexStatus
    sessions_written: int = 0
    reason: str | None = None


@dataclass(frozen=True)
class MarketIndexSummary:
    """What one run did, per index."""

    results: tuple[MarketIndexResult, ...]

    @property
    def sessions_written(self) -> int:
        return sum(result.sessions_written for result in self.results)

    @property
    def completed(self) -> tuple[str, ...]:
        return tuple(
            result.index for result in self.results if result.status == "completed"
        )

    @property
    def failed(self) -> tuple[MarketIndexResult, ...]:
        return tuple(result for result in self.results if result.status == "failed")


class MarketIndexLoader:
    """Load the benchmark's trailing session window, from the Main Source."""

    def __init__(
        self,
        store: SnapshotStore,
        history: MarketIndexHistoryProvider,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        window_trading_days: int = MARKET_INDEX_WINDOW_TRADING_DAYS,
    ) -> None:
        expected = main_source(Capability.MARKET_INDEX)
        if getattr(history, "source", None) is not expected:
            # Checked here rather than trusted from the caller, exactly as the
            # Warm-up checks it: another adapter could implement the same
            # protocol, and the mistake would otherwise surface as a wrong beta
            # months later rather than as an error now.
            raise MarketIndexUnavailable(
                f"The market index series is written from {expected.value} only, "
                f"not {getattr(history, 'source', None)}"
            )
        self._store = store
        self._history = history
        self._now = now
        self._window = window_trading_days

    def run(
        self,
        indices: Sequence[str] = (MARKET_INDEX_SYMBOL,),
    ) -> MarketIndexSummary:
        """Load each index in turn, letting one failure cost only that index."""
        today = self._now().astimezone(VN_TZ).date()
        from_date = reaches_back_to(today, self._window)

        results = [self._load(index, from_date, today) for index in indices]
        summary = MarketIndexSummary(results=tuple(results))
        logger.info(
            "The market index load wrote %d sessions for %d of %d indices",
            summary.sessions_written,
            len(summary.completed),
            len(results),
        )
        return summary

    def _load(self, index: str, from_date: date, to_date: date) -> MarketIndexResult:
        try:
            sessions = self._history.fetch_index_history(index, from_date, to_date)
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            logger.warning("The market index load could not read %s: %s", index, reason)
            return MarketIndexResult(index=index, status="failed", reason=reason)

        written = 0
        refused = 0
        for snapshot in newest_sessions(sessions, self._window):
            try:
                self._store.save(Capability.MARKET_INDEX, snapshot)
            except Exception as exc:
                # One refused session is one day of the series, not a reason to
                # abandon the rest of it.
                refused += 1
                logger.warning(
                    "The market index load could not store the %s session for %s: %s",
                    snapshot.metadata.effective_at.date(),
                    index,
                    exc,
                )
                continue
            written += 1

        if written == 0:
            # A run that stored nothing is a failed run, whatever the reason.
            # The index publishes a level on every session the exchange opens,
            # and re-storing one already held still counts — so an empty answer
            # or a store refusing every row are both the silent-empty failure
            # this codebase refuses elsewhere, and reporting them as success is
            # how a benchmark quietly stops advancing.
            reason = (
                f"the store refused all {refused} sessions"
                if refused
                else "the provider returned no sessions"
            )
            logger.warning("The market index load wrote nothing for %s: %s", index, reason)
            return MarketIndexResult(index=index, status="failed", reason=reason)

        return MarketIndexResult(
            index=index, status="completed", sessions_written=written
        )


def build_market_index_loader(
    store: SnapshotStore,
    settings: Settings | None = None,
) -> MarketIndexLoader:
    """Wire the Main Source index adapter, or refuse the configuration.

    The depth check is here rather than on the constant, because the constant is
    not what production runs on: the configured value is. A depth below the
    field's own floor is refused with both numbers named, so an operator sees a
    misconfiguration rather than a field that starts refusing under
    ``insufficient_history`` some weeks later.
    """
    settings = settings or get_settings()
    if not (settings.fiinquant_username and settings.fiinquant_password):
        raise MarketIndexUnavailable(
            "The market index series needs a FiinQuant account: it is the one "
            "source that owns the market_index Capability, and no other may "
            "fill it"
        )

    window = settings.market_index_window_trading_days
    if window < RELATIVE_STRENGTH_MIN_SESSIONS:
        raise MarketIndexUnavailable(
            f"The market index window is configured at {window} sessions, below "
            f"the {RELATIVE_STRENGTH_MIN_SESSIONS} that "
            f"relative_strength.beta_vs_market_index declares. A series that "
            f"short leaves the only field reading it refusing under "
            f"insufficient_history"
        )

    from .providers.fiinquant import (
        FiinQuantMarketIndexProvider,
        ProviderCircuitBreaker,
        shared_session_factory,
    )

    return MarketIndexLoader(
        store=store,
        history=FiinQuantMarketIndexProvider(
            username=settings.fiinquant_username,
            password=settings.fiinquant_password,
            session_factory=shared_session_factory(),
            circuit_breaker=ProviderCircuitBreaker(),
        ),
        window_trading_days=window,
    )


def run_market_index_load(
    indices: Sequence[str] = (MARKET_INDEX_SYMBOL,),
    settings: Settings | None = None,
) -> MarketIndexSummary:
    """Load the benchmark series and commit what was written.

    Synchronous throughout, like the Collector and the Warm-up: the store is,
    and FiinQuantX is, so a caller on an event loop hands this to a thread.
    """
    from src.core.database import get_sync_db

    with get_sync_db() as session:
        return build_market_index_loader(
            SnapshotStore(session), settings=settings
        ).run(indices)
