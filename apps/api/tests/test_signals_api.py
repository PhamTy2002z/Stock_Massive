"""What the signals route puts on the wire.

The shape is the promise: every answer states the session it is for, how much of
the scope it covers, and how it relates to the newest market data. A thin answer
is a 200 carrying its reasons — the request succeeded, and what it found is the
finding — so these tests assert that the reasons are present rather than that
the list is long.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from src.core.database import get_sync_session
from src.main import app
from src.stocks.models import CohortVersion
from src.stocks.providers import CorporateActionEvent, Exchange, ProviderSource
from src.stocks.signals.corporate_actions import CorporateActionStore
from src.stocks.signals.volume_spike import BASELINE_TRADING_DAYS
from src.stocks.universe import forget_cohort_cache

from .test_volume_spike import (
    list_on,
    open_session,
    seat_cohort,
    steady_market,
    trading_calendar,
    write_sessions,
)

# A whole cohort, because the signal will not resolve to a session it cannot
# evaluate forty-five members on — the floor is the domain's, not the test's.
MEMBERS = [f"C{index:02d}" for index in range(50)]


@pytest.fixture(autouse=True)
def clear_universe_cache():
    forget_cohort_cache()
    yield
    forget_cohort_cache()


def serving(session) -> TestClient:
    app.dependency_overrides[get_sync_session] = lambda: session
    return TestClient(app)


class MemoryCache:
    """The endpoint cache contract, kept local so cache identity is observable."""

    def __init__(self):
        self.values: dict[str, object] = {}

    def get(self, key: str):
        return self.values.get(key)

    def set(self, key: str, value: object):
        self.values[key] = value


@pytest.fixture(autouse=True)
def drop_overrides():
    yield
    app.dependency_overrides.clear()


def a_market_with_a_cohort():
    """Fifty seated companies, all evaluable, one of them trading loudly."""
    session = open_session()
    sessions = trading_calendar(BASELINE_TRADING_DAYS + 1)
    seat_cohort(session, MEMBERS)
    list_on(session, MEMBERS)
    steady_market(session, MEMBERS[1:], sessions)
    volumes = {day: 1_000_000 for day in sessions[:-1]}
    volumes[sessions[-1]] = 3_000_000
    write_sessions(session, MEMBERS[0], volumes)
    return session, sessions


class TestServing:
    def test_the_answer_carries_its_own_provenance(self):
        session, sessions = a_market_with_a_cohort()

        body = serving(session).get(
            "/api/v1/signals/volume-spikes",
            params={"scope": "profit_leaders", "threshold": 1.5},
        ).json()

        assert body["trading_day"] == sessions[-1].isoformat()
        assert body["coverage"] == {"state": "ready", "evaluated": 50, "total": 50}
        assert body["freshness"] in {"fresh", "lagging", "stale"}
        assert body["cohort_version"]["reporting_period"] == "2026-03-31"
        assert body["unevaluable"] == []
        assert [spike["symbol"] for spike in body["spikes"]] == [MEMBERS[0]]
        assert body["spikes"][0]["ratio"] == pytest.approx(3.0)
        assert body["spikes"][0]["baseline_average_volume"] == 1_000_000

    def test_a_volume_basis_break_stays_on_the_spike_item(self):
        session, sessions = a_market_with_a_cohort()
        CorporateActionStore(session).save(
            CorporateActionEvent(
                symbol=MEMBERS[0],
                event_code="ISS",
                title="Share Issue - Stock dividend ratio 10.0%",
                ex_date=sessions[10],
                record_date=sessions[11],
                public_date=sessions[5],
                exercise_ratio=0.10,
                value_per_share=None,
            ),
            ProviderSource.VNSTOCK,
            datetime(2026, 8, 13, tzinfo=timezone.utc),
        )

        body = serving(session).get(
            "/api/v1/signals/volume-spikes",
            params={"scope": "profit_leaders", "threshold": 1.5},
        ).json()

        spike = next(item for item in body["spikes"] if item["symbol"] == MEMBERS[0])
        assert spike["ratio"] == pytest.approx(3.0)
        assert "volume_basis_break" in spike["issues"]

    def test_an_action_write_makes_the_cached_answer_unreachable(self, monkeypatch):
        session, sessions = a_market_with_a_cohort()
        cache = MemoryCache()
        monkeypatch.setattr("src.stocks.signals.router.volume_spikes_cache", cache)

        client = serving(session)
        first = client.get(
            "/api/v1/signals/volume-spikes",
            params={"scope": "profit_leaders", "threshold": 1.5},
        ).json()
        first_spike = next(
            item for item in first["spikes"] if item["symbol"] == MEMBERS[0]
        )
        assert "volume_basis_break" not in first_spike["issues"]

        CorporateActionStore(session).save(
            CorporateActionEvent(
                symbol=MEMBERS[0],
                event_code="ISS",
                title="Share Issue - Stock dividend ratio 10.0%",
                ex_date=sessions[10],
                record_date=sessions[11],
                public_date=sessions[5],
                exercise_ratio=0.10,
                value_per_share=None,
            ),
            ProviderSource.VNSTOCK,
            datetime(2026, 8, 13, 0, 0, 1, tzinfo=timezone.utc),
        )

        second = client.get(
            "/api/v1/signals/volume-spikes",
            params={"scope": "profit_leaders", "threshold": 1.5},
        ).json()
        second_spike = next(
            item for item in second["spikes"] if item["symbol"] == MEMBERS[0]
        )
        assert "volume_basis_break" in second_spike["issues"]
        assert len(cache.values) == 2

    def test_a_symbol_that_could_not_be_evaluated_is_named(self):
        session, sessions = a_market_with_a_cohort()
        # A fifty-first member seated after the others, with no history behind
        # it. The version it replaces has to be retired first: "at most one
        # active" is a database constraint, not a convention.
        write_sessions(session, "NEW", {sessions[-1]: 500_000})
        handover = datetime(2026, 2, 2, 3, 0, tzinfo=timezone.utc)
        session.execute(
            update(CohortVersion)
            .where(CohortVersion.state == "active")
            .values(state="superseded", superseded_at=handover)
        )
        seat_cohort(session, MEMBERS + ["NEW"], activated_at=handover)

        body = serving(session).get(
            "/api/v1/signals/volume-spikes",
            params={"threshold": 1.5},
        ).json()

        assert body["coverage"] == {"state": "partial", "evaluated": 50, "total": 51}
        assert body["unevaluable"] == [
            {"symbol": "NEW", "issues": ["insufficient_history"]}
        ]

    def test_no_ranking_is_an_answer_not_an_error(self):
        session = open_session()
        sessions = trading_calendar(BASELINE_TRADING_DAYS + 1)
        steady_market(session, ["FPT"], sessions)

        response = serving(session).get("/api/v1/signals/volume-spikes")
        body = response.json()

        assert response.status_code == 200
        assert body["coverage"]["state"] == "insufficient_data"
        assert body["issues"] == ["ranking_unavailable"]
        assert body["trading_day"] is None
        assert body["spikes"] == []

    def test_a_historical_query_answers_for_the_day_asked_about(self):
        session, sessions = a_market_with_a_cohort()

        body = serving(session).get(
            "/api/v1/signals/volume-spikes",
            params={"trading_day": sessions[-1].isoformat()},
        ).json()

        assert body["trading_day"] == sessions[-1].isoformat()

    def test_a_day_with_no_cohort_behind_it_says_so(self):
        session, sessions = a_market_with_a_cohort()

        body = serving(session).get(
            "/api/v1/signals/volume-spikes",
            params={"trading_day": (sessions[0] - timedelta(days=400)).isoformat()},
        ).json()

        assert body["issues"] == ["ranking_unavailable"]
        assert body["trading_day"] is None


class TestScopeAndFilters:
    def test_the_universe_scope_carries_no_cohort_version(self):
        session, _ = a_market_with_a_cohort()

        body = serving(session).get(
            "/api/v1/signals/volume-spikes", params={"scope": "universe"}
        ).json()

        assert body["scope"] == "universe"
        assert body["cohort_version"] is None

    def test_an_exchange_filter_on_the_ranking_is_refused(self):
        session, _ = a_market_with_a_cohort()

        response = serving(session).get(
            "/api/v1/signals/volume-spikes",
            params={"scope": "profit_leaders", "exchange": Exchange.HNX.value},
        )

        assert response.status_code == 400

    def test_upcom_is_not_a_board_this_system_serves(self):
        session, _ = a_market_with_a_cohort()

        response = serving(session).get(
            "/api/v1/signals/volume-spikes",
            params={"scope": "universe", "exchange": "UPCOM"},
        )

        assert response.status_code == 400

    def test_a_threshold_below_one_is_refused(self):
        session, _ = a_market_with_a_cohort()

        response = serving(session).get(
            "/api/v1/signals/volume-spikes", params={"threshold": 0.5}
        )

        assert response.status_code == 422

    def test_the_legacy_analytics_route_is_gone(self):
        session, _ = a_market_with_a_cohort()

        response = serving(session).get("/api/v1/stocks/analytics/volume-spikes")

        assert response.status_code == 404


def test_the_signal_never_calls_a_provider(monkeypatch):
    """The serving path reads the store and nothing else (``docs/adr/0001``)."""
    import src.core.vnstock_client as vnstock_client

    def refuse(*args, **kwargs):
        raise AssertionError("the serving path reached a Provider Source")

    monkeypatch.setattr(vnstock_client, "Listing", refuse)
    session, _ = a_market_with_a_cohort()

    response = serving(session).get("/api/v1/signals/volume-spikes")

    assert response.status_code == 200
    assert response.json()["trading_day"] is not None
