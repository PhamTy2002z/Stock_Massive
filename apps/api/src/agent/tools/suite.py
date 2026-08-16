"""Composition root for the fixed twelve-tool model-visible catalog."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from src.core.database import sync_session_factory
from src.core.news_lane import NewsLane
from src.stocks.universe import build_universe

from .catalog import ToolCatalog
from .computations import ComputationTools
from .data import SessionFactory, StoreBackedTools, UniverseFactory
from .news import NewsFetcher, NewsTools, _fetch_vci_news


class IntelligentQuantCatalog:
    """Build the one catalog surface whose ordering is part of its version."""

    def __init__(
        self,
        *,
        session_factory: SessionFactory = sync_session_factory,
        redis: Any | None = None,
        universe_factory: UniverseFactory = build_universe,
        news_lane: NewsLane | None = None,
        fetch_news: NewsFetcher = _fetch_vci_news,
    ) -> None:
        self.data = StoreBackedTools(
            session_factory=session_factory,
            redis=redis,
            universe_factory=universe_factory,
        )
        self.news = NewsTools(
            session_factory=session_factory,
            universe_factory=universe_factory,
            news_lane=news_lane,
            fetch_news=fetch_news,
        )
        self.computations = ComputationTools(
            session_factory=session_factory,
            universe_factory=universe_factory,
        )

    def catalog(self, *, trace_writer) -> ToolCatalog:
        stored = {registration.name: registration for registration in self.data.registrations()}
        news = self.news.registrations()
        computations = self.computations.registrations()
        registrations = (
            stored["get_analysis"],
            stored["get_price_series"],
            stored["get_financials"],
            stored["get_company_profile"],
            *news,
            stored["screen_universe"],
            *computations,
            stored["get_watchlist"],
        )
        return ToolCatalog(registrations, trace_writer=trace_writer)


@lru_cache(maxsize=1)
def tool_catalog_version() -> str:
    """The deployed catalog's version, resolved without running a Turn.

    The version is a hash of the tool *schemas*, which are static — so a caller
    that only needs to record or compare it should not have to build a service
    to find it out.  Two of them need exactly that and neither is a Turn: the
    Eval Fixture pins the catalog it was frozen against (``docs/adr/0016``), and
    the harness refuses to run when the pin and the deployment disagree.

    Cached because the answer cannot change inside a process: the schemas are
    declared at import.  Nothing is dispatched through this catalog — the trace
    writer refuses — so it cannot become a second, untraced route to a tool.
    """

    def _no_dispatch(_trace):  # pragma: no cover - never reached
        raise RuntimeError("this catalog exists to be versioned, not dispatched")

    return IntelligentQuantCatalog().catalog(trace_writer=_no_dispatch).tool_catalog_version


__all__ = ["IntelligentQuantCatalog", "tool_catalog_version"]
