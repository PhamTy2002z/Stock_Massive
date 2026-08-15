"""The benchmark's own session series, and how deep it has to be.

`relative_strength.beta_vs_market_index` is registered and refuses, and until
this module ran it refused because **this system stored no market-index session
series at all**. The VN-Index existed only as an alias inside the live price
path, and reading it from there is exactly the substitution
``docs/specs/0003`` §13 forbids: a legacy live read used to make a registered
field look available. So the field was honest and useless at the same time, and
this is the load that turns it into something a number can be computed from.

## What it is, in ADR-0005's vocabulary

A **Warm-up**, and not a Backfill. Every property ``docs/adr/0005`` puts on one
holds: it is bounded, it reads the Main Source only, and it is repeatable — the
same run that first fills the series is the run that tops it up tomorrow and the
run that repairs a week the collector was down. What differs is only the bound.
The Volume Spike's Warm-up is bounded by a month because that is the window a
Volume Spike reads; this one is bounded by the deepest field that reads the
index, which is a year.

## Why the depth is written as the field's own floor

``RELATIVE_STRENGTH_MIN_SESSIONS`` is 250, and ``prepare_bars()`` refuses a
window that reaches fewer sessions than the field declares. A benchmark stored
249 sessions deep would therefore leave that field refusing under
``insufficient_history`` — the same unavailability wearing a reason that points
at the wrong fix, and a reader chasing a collection gap that is really a
configuration one. The depth is spelled as the field's floor plus a margin so
the two cannot be edited apart: deepen the field, and the load follows it.

The margin is a month of sessions. It is how far behind the daily run may fall —
a long holiday, a broken week — while still leaving the field its full 250 the
moment the load succeeds again.

## One index, and where its identity comes from

The series exists for one declared field, so the field names both what to store
and how deep: ``RELATIVE_STRENGTH_BENCHMARK`` is the benchmark's code and
``RELATIVE_STRENGTH_MIN_SESSIONS`` its depth, both read from the field's own
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
from datetime import date, datetime, timedelta, timezone
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
from .signals.cross_sectional import (
    RELATIVE_STRENGTH_BENCHMARK,
    RELATIVE_STRENGTH_MIN_SESSIONS,
)

logger = logging.getLogger(__name__)

# The index this system stores a series for, named by the one field that reads
# it. Re-exported under a storage-side name so a loader, a job and a test can say
# what they are loading without importing a signals module for a string.
MARKET_INDEX_SYMBOL = RELATIVE_STRENGTH_BENCHMARK

# How far behind the daily run may fall and still leave the deepest field its
# full window on the next successful run.
MARKET_INDEX_MARGIN_SESSIONS = 25

MARKET_INDEX_WINDOW_TRADING_DAYS = (
    RELATIVE_STRENGTH_MIN_SESSIONS + MARKET_INDEX_MARGIN_SESSIONS
)

# Sessions are asked for by calendar date, so the window has to be translated.
# Five sessions a week is seven calendar days; on top of that Vietnam closes for
# roughly eleven public holidays a year, nine of them running at Tet. The holiday
# term is per session rather than a fixed fortnight on the end: over a window
# this deep a fortnight is less than half of what the holidays actually take, and
# a reach-back that fell short would silently store fewer sessions than asked
# for.
_CALENDAR_DAYS_PER_TRADING_DAY = 7 / 5
_HOLIDAY_DAYS_PER_TRADING_DAY = 11 / 250

# A fortnight on top of the proportional terms, for the ordinary case of a run
# made on a Monday after a long weekend. Reaching further back costs nothing: it
# is one provider call either way, and sessions already held collapse in the
# store.
_CALENDAR_SLACK_DAYS = 14

MarketIndexStatus = Literal["completed", "failed"]


class MarketIndexUnavailable(RuntimeError):
    """No Main Source account is configured, so the benchmark cannot be loaded.

    Raised rather than quietly degrading to another source. The
    ``market_index`` Capability has one owner and no cover on purpose
    (``docs/adr/0017``): the Cover Source's quote history is
    ``adjusted_at_source``, and an index is adjusted for nothing — so a series
    filled from there would carry a basis asserting a rescaling nobody
    performed, and a window mixing the two would be refused for a seam that does
    not exist in the market.
    """


@dataclass(frozen=True)
class MarketIndexLoad:
    """How one index's load went."""

    index: str
    status: MarketIndexStatus
    sessions_written: int = 0
    reason: str | None = None


@dataclass(frozen=True)
class MarketIndexSummary:
    """What one run did, per index."""

    results: tuple[MarketIndexLoad, ...]

    @property
    def sessions_written(self) -> int:
        return sum(result.sessions_written for result in self.results)

    @property
    def completed(self) -> tuple[str, ...]:
        return tuple(
            result.index for result in self.results if result.status == "completed"
        )

    @property
    def failed(self) -> tuple[MarketIndexLoad, ...]:
        return tuple(result for result in self.results if result.status == "failed")


class MarketIndexWarmup:
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
            # equity Warm-up checks it: another adapter could implement the same
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
        from_date = self._reaches_back_to(today)

        results = [self._load(index, from_date, today) for index in indices]
        summary = MarketIndexSummary(results=tuple(results))
        logger.info(
            "The market index load wrote %d sessions for %d of %d indices",
            summary.sessions_written,
            len(summary.completed),
            len(results),
        )
        return summary

    def _reaches_back_to(self, today: date) -> date:
        span = round(
            self._window
            * (_CALENDAR_DAYS_PER_TRADING_DAY + _HOLIDAY_DAYS_PER_TRADING_DAY)
        )
        return today - timedelta(days=span + _CALENDAR_SLACK_DAYS)

    def _load(self, index: str, from_date: date, to_date: date) -> MarketIndexLoad:
        try:
            sessions = self._history.fetch_index_history(index, from_date, to_date)
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            logger.warning("The market index load could not read %s: %s", index, reason)
            return MarketIndexLoad(index=index, status="failed", reason=reason)

        written = 0
        for snapshot in self._bounded(sessions):
            try:
                self._store.save(Capability.MARKET_INDEX, snapshot)
            except Exception as exc:
                # One refused session is one day of the series, not a reason to
                # abandon the rest of it.
                logger.warning(
                    "The market index load could not store the %s session for %s: %s",
                    snapshot.metadata.effective_at.date(),
                    index,
                    exc,
                )
                continue
            written += 1

        return MarketIndexLoad(
            index=index, status="completed", sessions_written=written
        )

    def _bounded(
        self,
        sessions: Sequence[MarketIndexSnapshot],
    ) -> tuple[MarketIndexSnapshot, ...]:
        """Keep the newest sessions in the window and drop the rest.

        The calendar span reaches back further than the window so the holidays
        cannot make it fall short, which means a quiet stretch comes back with
        more sessions than were asked for. Trimming keeps "bounded" a property of
        what is written rather than only of what was requested — and it is what
        stops a repeatable load from turning into an ever-deepening one.
        """
        newest_first = sorted(
            sessions, key=lambda item: item.metadata.effective_at, reverse=True
        )
        return tuple(newest_first[: self._window])


def build_market_index_warmup(
    store: SnapshotStore,
    settings: Settings | None = None,
) -> MarketIndexWarmup:
    """Wire the Main Source index adapter for the configured account."""
    settings = settings or get_settings()
    if not (settings.fiinquant_username and settings.fiinquant_password):
        raise MarketIndexUnavailable(
            "The market index series needs a FiinQuant account: it is the one "
            "source that owns the market_index Capability, and no other may "
            "fill it"
        )

    from .providers.fiinquant import (
        FiinQuantMarketIndexProvider,
        ProviderCircuitBreaker,
        shared_session_factory,
    )

    return MarketIndexWarmup(
        store=store,
        history=FiinQuantMarketIndexProvider(
            username=settings.fiinquant_username,
            password=settings.fiinquant_password,
            session_factory=shared_session_factory(),
            circuit_breaker=ProviderCircuitBreaker(),
        ),
        window_trading_days=settings.market_index_window_trading_days,
    )


def run_market_index_warmup(
    indices: Sequence[str] = (MARKET_INDEX_SYMBOL,),
    settings: Settings | None = None,
) -> MarketIndexSummary:
    """Load the benchmark series and commit what was written.

    Synchronous throughout, like the Collector and the equity Warm-up: the store
    is, and FiinQuantX is, so a caller on an event loop hands this to a thread.
    """
    from src.core.database import get_sync_db

    with get_sync_db() as session:
        return build_market_index_warmup(
            SnapshotStore(session), settings=settings
        ).run(indices)
