"""One composer exposes exactly the twelve tools fixed by ADR-0009."""

from contextlib import contextmanager

from src.agent.tools.suite import AgentTools
from src.core.news_lane import NewsLane
from src.stocks.universe import Universe
from tests.fake_redis import FakeRedis


class SessionFactory:
    @contextmanager
    def __call__(self):
        yield object()


def test_the_composed_catalog_has_exactly_the_twelve_semantic_tools():
    redis = FakeRedis()
    suite = AgentTools(
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
        "screen_universe",
        "risk_metrics",
        "market_behavior",
        "cross_sectional",
        "foreign_flow",
        "indicator_pack",
        "get_watchlist",
    )
    assert len(catalog.tool_schemas) == 12

