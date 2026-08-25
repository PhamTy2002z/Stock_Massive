"""HTTP contracts for independently loadable Market Monitor lenses."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import update

from src.auth.dependencies import get_current_user
from src.stocks.models import ListingRoster
from src.stocks.monitor.router import (
    get_monitor_service,
    get_realtime_service,
    router,
)
from src.stocks.monitor.service import MarketMonitorService
from src.stocks.providers.contracts import Exchange
from src.stocks.realtime.projections import ProjectionUnavailable

from .test_market_monitor_queries import (
    NOW,
    list_symbol,
    open_session,
    trading_calendar,
    write_market,
)


API = "/api/v1/stocks/market-monitor"


class DisconnectedRealtime:
    async def metrics_many(self, *_args, **_kwargs):
        raise ProjectionUnavailable("not configured")


def make_client(*, authenticated: bool = True, partial: bool = False) -> TestClient:
    session = open_session()
    days = trading_calendar(21)
    symbols = ("AAA", "BBB")
    for symbol in symbols:
        list_symbol(session, symbol, Exchange.HOSE)
    write_market(session, "AAA", days)
    write_market(session, "BBB", days[:-1] if partial else days)
    session.flush()

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/stocks")
    app.dependency_overrides[get_monitor_service] = lambda: MarketMonitorService(
        session,
        universe_symbols=symbols,
    )
    app.dependency_overrides[get_realtime_service] = lambda: DisconnectedRealtime()
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    return TestClient(app)


def test_market_monitor_requires_authentication() -> None:
    response = make_client(authenticated=False).get(f"{API}/breadth")

    assert response.status_code == 401


@pytest.mark.parametrize(
    "path",
    ("overview", "breadth", "flows", "sectors", "stocks", "stocks/AAA"),
)
def test_each_lens_loads_as_one_resource(path: str) -> None:
    response = make_client().get(f"{API}/{path}")

    assert response.status_code == 200, response.text
    assert response.json()["meta"]["exchange"] == "ALL"


def test_overview_rejects_an_unsupported_horizon() -> None:
    assert make_client().get(f"{API}/overview?horizon=2").status_code == 422
    assert make_client().get(f"{API}/flows?horizon=2").status_code == 422


@pytest.mark.parametrize(
    "query",
    (
        "exchange=UPCOM",
        "window_days=20",
        "window_days=254",
        "sort_by=provider_magic",
        "limit=51",
        "cursor=not-a-cursor",
        "as_of=2999-01-01",
    ),
)
def test_invalid_filters_and_bounds_fail_clearly(query: str) -> None:
    response = make_client().get(f"{API}/stocks?{query}")

    assert response.status_code == 422


def test_partial_eod_coverage_is_a_successful_typed_finding() -> None:
    response = make_client(partial=True).get(f"{API}/breadth")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["state"] == "partial"
    assert body["meta"]["coverage"] == {
        "eligible": 2,
        "evaluated": 1,
        "missing": 1,
        "state": "partial",
    }
    assert "missing_target_session" in body["meta"]["issues"]


def test_cursor_is_stable_and_bound_to_the_active_filters() -> None:
    client = make_client()
    first = client.get(f"{API}/stocks?limit=1&sort_by=symbol")

    assert first.status_code == 200
    cursor = first.json()["next_cursor"]
    assert cursor
    second = client.get(
        f"{API}/stocks",
        params={"limit": 1, "sort_by": "symbol", "cursor": cursor},
    )
    changed = client.get(
        f"{API}/stocks",
        params={
            "limit": 1,
            "sort_by": "return_1d_pct",
            "cursor": cursor,
        },
    )

    assert [item["symbol"] for item in first.json()["items"]] == ["AAA"]
    assert [item["symbol"] for item in second.json()["items"]] == ["BBB"]
    assert changed.status_code == 422


def test_cursor_refuses_a_new_storage_generation() -> None:
    client = make_client()
    first = client.get(f"{API}/stocks?limit=1&sort_by=symbol")
    cursor = first.json()["next_cursor"]
    service = client.app.dependency_overrides[get_monitor_service]()
    service.session.execute(
        update(ListingRoster).values(observed_at=NOW + timedelta(seconds=1))
    )
    service.session.flush()

    response = client.get(
        f"{API}/stocks",
        params={"limit": 1, "sort_by": "symbol", "cursor": cursor},
    )

    assert response.status_code == 422


def test_flow_keeps_eod_rows_when_realtime_is_disconnected() -> None:
    response = make_client().get(f"{API}/flows")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["state"] == "disconnected"
    assert body["meta"]["coverage"]["evaluated"] == 2
    assert body["meta"]["realtime_coverage"] == {
        "eligible": 2,
        "evaluated": 0,
        "missing": 2,
        "state": "disconnected",
    }
    assert "realtime_projection_unavailable" in body["meta"]["issues"]
