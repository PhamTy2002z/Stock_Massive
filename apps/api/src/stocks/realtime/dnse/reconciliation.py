"""Reconnect REST backfill that shares identity and dedupe with live delivery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from .. import DataOutcome, NormalizedMarketEvent
from .deduplication import SnapshotDeduplicator
from .parsing import DnseEventParser
from .rest import RestPage
from .validation import EventWindow


class PageSource(Protocol):
    def pages(
        self,
        symbol: str,
        family: str,
        window: EventWindow,
        board: str | None = None,
    ): ...


_REST_EVENT_TYPE = {
    "trades": "te",
    "quotes": "q",
    "foreign-trading": "f",
    "expected-price": "ep",
}


@dataclass(frozen=True, slots=True)
class ReconciliationBatch:
    recovered: tuple[NormalizedMarketEvent, ...]
    outcomes: tuple[DataOutcome, ...]
    duplicate_count: int
    pages_read: int


class ReconnectReconciler:
    """Backfill one trading day after reconnect without replay inflation."""

    def __init__(
        self,
        source: PageSource,
        parser: DnseEventParser,
        deduplicator: SnapshotDeduplicator,
    ) -> None:
        self._source = source
        self._parser = parser
        self._deduplicator = deduplicator

    async def reconcile(
        self,
        *,
        symbol: str,
        family: str,
        trading_day: date,
        board: str | None = None,
    ) -> ReconciliationBatch:
        event_type = _REST_EVENT_TYPE.get(family)
        if event_type is None:
            raise ValueError("unsupported DNSE reconciliation family")
        recovered: list[NormalizedMarketEvent] = []
        outcomes: list[DataOutcome] = []
        duplicate_count = 0
        pages_read = 0
        window = EventWindow(trading_day, trading_day)
        async for page in self._source.pages(symbol, family, window, board):
            if not isinstance(page, RestPage):
                raise TypeError("reconciliation source must yield RestPage")
            pages_read += 1
            for index, row in enumerate(page.items):
                wire = dict(row)
                wire.setdefault("T", event_type)
                parsed = self._parser.parse(
                    wire,
                    request_id=f"reconcile-{family}-{pages_read}-{index}",
                )
                if parsed.outcome is not None:
                    outcomes.append(parsed.outcome)
                    continue
                event = parsed.event
                if event is None:
                    raise RuntimeError("parser returned neither event nor outcome")
                duplicate = self._deduplicator.classify(event)
                if duplicate is not None:
                    outcomes.append(duplicate)
                    duplicate_count += 1
                    continue
                recovered.append(event)
        return ReconciliationBatch(
            recovered=tuple(recovered),
            outcomes=tuple(outcomes),
            duplicate_count=duplicate_count,
            pages_read=pages_read,
        )
