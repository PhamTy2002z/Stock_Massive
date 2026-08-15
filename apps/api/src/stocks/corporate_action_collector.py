"""The slow load that keeps the Corporate Action series alive.

Deliberately not part of the per-session cycle. Corporate actions are annual
events announced weeks ahead, and the evening cycle exists to catch a session
that just closed — putting this inside it would spend one request per symbol
every evening to re-read a feed that changes a handful of times a year, against
an allowance of twenty requests a minute that the census and the backfill are
already competing for.

The whole Universe fits in one run, which is why there is no resume cursor here
and no per-run symbol cap. A hundred symbols at one request each is five minutes
of paced reading; the census needs a cursor because it walks 1,600 symbols at two
requests each, and copying that machinery here would be inventing a problem.

Each run does two things per symbol, and the second is the reason it is a
recurring job rather than a one-off import: it stores what the feed declares, and
then it re-judges every action that is not confirmed yet. An action is announced
before its ex-date and can only be confirmed after the prices around that date
have been collected, so the verdict is reached by a later run than the one that
first wrote the row.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.orm import Session

from src.core.config import Settings, get_settings

from .providers import CorporateActionProvider
from .signals.corporate_actions import CorporateActionStore

logger = logging.getLogger(__name__)

CollectionStatus = Literal["completed", "failed"]


@dataclass(frozen=True)
class SymbolActions:
    """How one symbol's action load went.

    ``stored`` counts rows written or refreshed, not rows added: a run over a
    company with nothing new stores every action it already had, which is what
    idempotent means here and is not the same as having done nothing.
    """

    symbol: str
    status: CollectionStatus
    stored: int = 0
    confirmed: int = 0
    reason: str | None = None


@dataclass(frozen=True)
class CorporateActionSummary:
    """What one run of the action load did, per symbol."""

    results: tuple[SymbolActions, ...]

    @property
    def actions_stored(self) -> int:
        return sum(result.stored for result in self.results)

    @property
    def actions_confirmed(self) -> int:
        return sum(result.confirmed for result in self.results)

    @property
    def completed(self) -> tuple[str, ...]:
        return tuple(
            result.symbol for result in self.results if result.status == "completed"
        )

    @property
    def failed(self) -> tuple[SymbolActions, ...]:
        return tuple(result for result in self.results if result.status == "failed")


class CorporateActionCollector:
    """Load and confirm the declared actions of a set of symbols."""

    def __init__(
        self,
        session: Session,
        provider: CorporateActionProvider,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._session = session
        self._provider = provider
        self._now = now
        self._store = CorporateActionStore(session)

    def run(self, symbols: Sequence[str]) -> CorporateActionSummary:
        """Load each symbol in turn, letting one failure cost only that symbol."""
        results = [self._collect(symbol) for symbol in symbols]
        summary = CorporateActionSummary(results=tuple(results))
        logger.info(
            "Corporate action load stored %d actions and confirmed %d, over %d of "
            "%d symbols",
            summary.actions_stored,
            summary.actions_confirmed,
            len(summary.completed),
            len(results),
        )
        return summary

    def _collect(self, symbol: str) -> SymbolActions:
        try:
            events = self._provider.fetch_corporate_actions(symbol)
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            logger.warning("Could not read the events of %s: %s", symbol, reason)
            return SymbolActions(symbol=symbol, status="failed", reason=reason)

        observed_at = self._now()
        stored = 0
        for event in events:
            try:
                with self._session.begin_nested():
                    self._store.save(event, self._provider.source, observed_at)
            except Exception as exc:
                # One action the database refuses is one event, not this
                # company's whole history. The savepoint is what keeps it that
                # way: a failed flush otherwise leaves the session unusable and
                # takes every symbol after this one with it.
                logger.warning(
                    "Could not store the %s %s action of %s: %s",
                    event.ex_date or event.public_date,
                    event.event_code,
                    symbol,
                    exc,
                )
                continue
            stored += 1

        try:
            confirmed = self._store.confirm_pending(symbol)
        except Exception as exc:
            # Confirmation reads price history, which may be short or missing.
            # The actions are already stored and unconfirmed is their resting
            # state, so a failure here costs the verdict rather than the load.
            logger.warning("Could not confirm the actions of %s: %s", symbol, exc)
            confirmed = 0

        return SymbolActions(
            symbol=symbol,
            status="completed",
            stored=stored,
            confirmed=confirmed,
        )


def build_collector(
    session: Session,
    settings: Settings | None = None,
) -> CorporateActionCollector:
    """Wire the reference provider's event feed for the configured account.

    vnstock is the Main Source for ``reference`` (``docs/adr/0002``) and the only
    source that answers with a corporate action's declared terms at all — the
    FiinQuant free tier has no such feed — so there is no source choice to make
    here and none is offered.
    """
    settings = settings or get_settings()

    from .providers.vnstock_provider import VnstockCorporateActionProvider

    return CorporateActionCollector(
        session=session,
        provider=VnstockCorporateActionProvider(
            vnstock_source=settings.vnstock_source
        ),
    )


def run_corporate_action_load(
    settings: Settings | None = None,
) -> CorporateActionSummary:
    """Load the Universe's corporate actions and commit what was written.

    Synchronous throughout, like every other collector here: the store is, and
    vnstock is, so a caller on an event loop hands this to a thread.

    On the Collector lane: this is collection, one request per symbol, and it is
    scheduled into a window nothing else uses precisely so it does not contend.
    """
    from src.core.database import get_sync_db
    from src.core.quota import QuotaLane, quota_lane

    from .universe import build_universe

    settings = settings or get_settings()
    with quota_lane(QuotaLane.COLLECTOR), get_sync_db() as session:
        universe = build_universe(session, settings)
        if not len(universe):
            logger.info("No symbols in the Universe, so no corporate actions to load")
            return CorporateActionSummary(results=())
        return build_collector(session, settings).run(universe.symbols)
