"""Composition root for the fixed twelve-tool model-visible catalog."""

from __future__ import annotations

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


__all__ = ["IntelligentQuantCatalog"]
