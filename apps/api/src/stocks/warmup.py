"""The repeatable, recent load that makes a symbol evaluable.

A Volume Spike needs the target session and the twenty before it — twenty-one
days in all. Waiting for the daily Collector to accumulate them takes a month of
sessions, and the deep Backfill walks years to get there through the Cover
Source. Neither is the right instrument for "this symbol joined the cohort on
Tuesday and has to produce a signal".

So this is a third thing, and ``docs/adr/0005`` keeps it separate on purpose:
bounded to the recent signal window, Main Source only, and repeatable. Being
repeatable is what lets it double as the repair for a collection cycle that was
missed — the Backfill cannot do that, because a completed Backfill is finished
for good and never looks at recent sessions again.
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
    MarketHistoryProvider,
    MarketSnapshot,
    SnapshotStore,
    main_source,
)
from .providers.normalize import VN_TZ

logger = logging.getLogger(__name__)

# Twenty preceding sessions plus the target one is twenty-one. The window asks
# for a few more so a session the provider has not appended yet costs nothing:
# FiinQuant publishes the session that just closed late in the evening, and a
# Warm-up run before it lands would otherwise come away one session short of
# evaluable.
WARMUP_WINDOW_TRADING_DAYS = 25

# Sessions are asked for by calendar date, so the window has to be translated.
# Five sessions a week is seven calendar days, and the slack absorbs the public
# holidays — including a Tet that shuts the exchange for nine days — without
# reaching so far back that the load stops being bounded.
_CALENDAR_DAYS_PER_TRADING_DAY = 7 / 5
_CALENDAR_SLACK_DAYS = 14

WarmupStatus = Literal["completed", "failed"]


class WarmupUnavailable(RuntimeError):
    """No Main Source account is configured, so a Warm-up cannot be run.

    Raised rather than quietly degrading to the Cover Source. The two disagree
    on units (``docs/adr/0002``), and a baseline averaged across both would
    produce a ratio that looks measured and is not.
    """


@dataclass(frozen=True)
class WarmupResult:
    """How one symbol's Warm-up went."""

    symbol: str
    status: WarmupStatus
    sessions_written: int = 0
    reason: str | None = None


@dataclass(frozen=True)
class WarmupSummary:
    """What one Warm-up run did, per symbol."""

    results: tuple[WarmupResult, ...]

    @property
    def sessions_written(self) -> int:
        return sum(result.sessions_written for result in self.results)

    @property
    def completed(self) -> tuple[str, ...]:
        return tuple(
            result.symbol for result in self.results if result.status == "completed"
        )

    @property
    def failed(self) -> tuple[WarmupResult, ...]:
        return tuple(result for result in self.results if result.status == "failed")


class Warmup:
    """Load the recent signal window for named symbols, from the Main Source."""

    def __init__(
        self,
        store: SnapshotStore,
        history: MarketHistoryProvider,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        window_trading_days: int = WARMUP_WINDOW_TRADING_DAYS,
    ) -> None:
        expected = main_source(Capability.MARKET)
        if getattr(history, "source", None) is not expected:
            # Checked here rather than trusted from the caller: the Cover Source
            # implements the same protocol, so passing the wrong one is an
            # ordinary mistake that would otherwise show up as a wrong ratio
            # weeks later rather than as an error now.
            raise WarmupUnavailable(
                f"Warm-up reads the {expected.value} market history only, "
                f"not {getattr(history, 'source', None)}"
            )
        self._store = store
        self._history = history
        self._now = now
        self._window = window_trading_days

    def run(self, symbols: Sequence[str]) -> WarmupSummary:
        """Warm each symbol in turn, letting one failure cost only that symbol."""
        today = self._now().astimezone(VN_TZ).date()
        from_date = self._reaches_back_to(today)

        results = [self._warm(symbol, from_date, today) for symbol in symbols]
        summary = WarmupSummary(results=tuple(results))
        logger.info(
            "Warm-up wrote %d sessions for %d of %d symbols",
            summary.sessions_written,
            len(summary.completed),
            len(results),
        )
        return summary

    def _reaches_back_to(self, today: date) -> date:
        span = round(self._window * _CALENDAR_DAYS_PER_TRADING_DAY)
        return today - timedelta(days=span + _CALENDAR_SLACK_DAYS)

    def _warm(self, symbol: str, from_date: date, to_date: date) -> WarmupResult:
        try:
            sessions = self._history.fetch_market_history(symbol, from_date, to_date)
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            logger.warning("Warm-up could not read %s: %s", symbol, reason)
            return WarmupResult(symbol=symbol, status="failed", reason=reason)

        written = 0
        for snapshot in self._bounded(sessions):
            try:
                self._store.save(Capability.MARKET, snapshot)
            except Exception as exc:
                # One refused session is one day of the window, not a reason to
                # abandon the rest of it.
                logger.warning(
                    "Warm-up could not store the %s session for %s: %s",
                    snapshot.metadata.effective_at.date(),
                    symbol,
                    exc,
                )
                continue
            written += 1

        return WarmupResult(symbol=symbol, status="completed", sessions_written=written)

    def _bounded(self, sessions: Sequence[MarketSnapshot]) -> tuple[MarketSnapshot, ...]:
        """Keep the newest sessions in the window and drop the rest.

        The calendar span reaches back further than the window to survive the
        holidays, so a quiet stretch comes back with more sessions than were
        asked for. Trimming keeps "bounded to the recent signal window" a
        property of what is written, not only of what was requested.
        """
        newest_first = sorted(
            sessions, key=lambda item: item.metadata.effective_at, reverse=True
        )
        return tuple(newest_first[: self._window])


def build_warmup(
    store: SnapshotStore,
    settings: Settings | None = None,
) -> Warmup:
    """Wire the Main Source market adapter for the configured account."""
    settings = settings or get_settings()
    if not (settings.fiinquant_username and settings.fiinquant_password):
        raise WarmupUnavailable(
            "Warm-up needs a FiinQuant account: it is the Main Source for market "
            "history, and no other source may fill the signal window"
        )

    from .providers.fiinquant import (
        FiinQuantMarketProvider,
        ProviderCircuitBreaker,
        shared_session_factory,
    )

    return Warmup(
        store=store,
        history=FiinQuantMarketProvider(
            username=settings.fiinquant_username,
            password=settings.fiinquant_password,
            session_factory=shared_session_factory(),
            circuit_breaker=ProviderCircuitBreaker(),
        ),
        window_trading_days=settings.warmup_window_trading_days,
    )


def run_warmup(
    symbols: Sequence[str],
    settings: Settings | None = None,
) -> WarmupSummary:
    """Warm the named symbols and commit what was written.

    Synchronous throughout, like the Collector: the store is, and FiinQuantX is,
    so a caller on an event loop hands this to a thread.
    """
    from src.core.database import get_sync_db

    with get_sync_db() as session:
        return build_warmup(SnapshotStore(session), settings=settings).run(symbols)
