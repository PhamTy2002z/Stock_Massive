"""One composer exposes the stable core plus explicitly enabled capabilities."""

from contextlib import contextmanager

from src.agent.tools.suite import IntelligentQuantCatalog
from src.core.config import Settings
from src.core.news_lane import NewsLane
from src.stocks.universe import Universe
from tests.fake_redis import FakeRedis


class SessionFactory:
    @contextmanager
    def __call__(self):
        yield object()


def test_the_composed_catalog_has_the_stable_core_and_deliberate_memory_tools():
    redis = FakeRedis()
    suite = IntelligentQuantCatalog(
        session_factory=SessionFactory(),
        redis=redis,
        universe_factory=lambda _session: Universe(explicit=("FPT",)),
        news_lane=NewsLane(redis_factory=lambda: redis),
        fetch_news=lambda _symbol: (),
    )

    catalog = suite.catalog(trace_writer=lambda _trace: None)

    assert catalog.names == (
        "get_analysis",
        "get_price_series",
        "get_financials",
        "get_company_profile",
        "search_news",
        "remember_fact",
        "recall_facts",
        "screen_universe",
        "risk_metrics",
        "market_behavior",
        "cross_sectional",
        "foreign_flow",
        "indicator_pack",
        "get_watchlist",
    )
    assert len(catalog.tool_schemas) == 14


def test_web_and_executor_tools_join_only_when_their_lanes_are_enabled():
    redis = FakeRedis()
    suite = IntelligentQuantCatalog(
        session_factory=SessionFactory(),
        redis=redis,
        universe_factory=lambda _session: Universe(explicit=("FPT",)),
        news_lane=NewsLane(redis_factory=lambda: redis),
        fetch_news=lambda _symbol: (),
        settings=Settings(web_tools_enabled=True, executor_enabled=True),
    )

    catalog = suite.catalog(trace_writer=lambda _trace: None)

    assert "web_search" in catalog.names
    assert "fetch_url" in catalog.names
    assert "run_python" in catalog.names
    assert len(catalog.tool_schemas) == 17
