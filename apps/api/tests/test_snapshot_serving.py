"""Tests for the serving path — endpoints read the store, never a provider.

Everything here runs against SQLite in memory with Redis handed in explicitly,
so the suite proves the request path needs no Postgres, no Redis and no network
to answer.
"""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.core.database import get_sync_session
from src.main import app
from src.stocks.models import ProviderSnapshot
from src.stocks.providers import (
    Capability,
    FundamentalSnapshot,
    MarketSnapshot,
    ProviderSource,
    ReferenceSnapshot,
    ShareCount,
    ShareType,
    SnapshotMetadata,
    SnapshotStore,
    ValuationSnapshot,
)
from src.stocks.schemas.snapshot import (
    FundamentalData,
    MarketData,
    ReferenceData,
    ValuationData,
)
from src.stocks.providers.normalize import VN_TZ
from src.stocks.universe import Universe

OBSERVED_AT = datetime(2026, 8, 10, 8, 30, tzinfo=timezone.utc)
SECTIONS = ("market", "valuation", "reference", "fundamental")


class FailedRedis:
    """A Redis that is down in the only way that matters here: every call."""

    def get(self, key):
        raise ConnectionError("redis unavailable")

    def set(self, key, value, **kwargs):
        raise ConnectionError("redis unavailable")


def database():
    """One in-memory database shared across threads.

    A synchronous handler runs in FastAPI's threadpool, so the default
    per-thread SQLite connection would hand the request a second, empty
    database and the test would read nothing back.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ProviderSnapshot.__table__.create(engine)
    return engine


def market_snapshot(
    observed_at: datetime = OBSERVED_AT,
    effective_at: datetime | None = None,
) -> MarketSnapshot:
    return MarketSnapshot(
        symbol="VCB",
        metadata=SnapshotMetadata(
            source=ProviderSource.FIINQUANT,
            effective_at=effective_at or observed_at - timedelta(minutes=30),
            observed_at=observed_at,
        ),
        last_price=59_700,
        volume=1_000,
    )


def valuation_snapshot(observed_at: datetime = OBSERVED_AT) -> ValuationSnapshot:
    return ValuationSnapshot(
        symbol="VCB",
        metadata=SnapshotMetadata(
            source=ProviderSource.FIINQUANT,
            effective_at=observed_at,
            observed_at=observed_at,
        ),
        provider_pe=12.5,
        provider_pb=1.8,
    )


def reference_snapshot(observed_at: datetime = OBSERVED_AT) -> ReferenceSnapshot:
    return ReferenceSnapshot(
        symbol="VCB",
        metadata=SnapshotMetadata(
            source=ProviderSource.VNSTOCK,
            effective_at=observed_at,
            observed_at=observed_at,
        ),
        shares=(ShareCount(share_type=ShareType.OUTSTANDING, value=5_589_000_000),),
        current_foreign_room=1_000_000,
        total_foreign_room=6_000_000,
    )


def fundamental_snapshot(
    observed_at: datetime = OBSERVED_AT,
    period_end: date | None = None,
) -> FundamentalSnapshot:
    # effective_at follows the period end, the way the vnstock adapter dates a
    # statement: the data speaks about the quarter, not about the day it was
    # fetched.
    closed = period_end or observed_at.date()
    return FundamentalSnapshot(
        symbol="VCB",
        metadata=SnapshotMetadata(
            source=ProviderSource.VNSTOCK,
            effective_at=datetime.combine(closed, datetime.min.time(), tzinfo=timezone.utc),
            observed_at=observed_at,
        ),
        period_end=closed,
        trailing_12_month_net_income_vnd=33_000_000_000_000,
        parent_equity_vnd=190_000_000_000_000,
    )


def write(engine, capability: Capability, snapshot) -> None:
    with Session(engine) as session:
        SnapshotStore(session, redis=None).save(capability, snapshot)
        session.commit()


def ask(engine, path: str, universe=("VCB",), redis=None):
    """Ask one store-backed endpoint, with nothing else wired up."""
    session = Session(engine)
    app.dependency_overrides[get_sync_session] = lambda: session
    try:
        with patch(
            "src.stocks.snapshot_router.get_universe",
            return_value=Universe(symbols=universe),
        ), patch("src.stocks.providers.store.get_redis", return_value=redis):
            return TestClient(app).get(f"/api/v1/stocks/{path}")
    finally:
        app.dependency_overrides.clear()
        session.close()


def serve(engine, symbol: str, universe=("VCB",), redis=None):
    """Ask the serving endpoint for one symbol, with nothing else wired up."""
    return ask(engine, f"{symbol}/snapshot", universe=universe, redis=redis)


def session_snapshot(session_day: date, close: float, source=ProviderSource.FIINQUANT):
    return MarketSnapshot(
        symbol="VCB",
        metadata=SnapshotMetadata(
            source=source,
            effective_at=datetime.combine(session_day, datetime.min.time(), tzinfo=VN_TZ),
            observed_at=OBSERVED_AT,
        ),
        open_price=close - 300,
        high_price=close + 200,
        low_price=close - 500,
        last_price=close,
        volume=1_000_000,
        total_value_vnd=60_000_000_000,
    )


class TestASymbolTheSystemWatches:
    def test_the_session_that_just_closed_is_served_from_the_store(self):
        """The numbers a user opens the app for, and where each one came from.

        Every figure in this system has an age, and a response that hides it
        would be telling the user the market is where it was hours ago.
        """
        engine = database()
        write(engine, Capability.MARKET, market_snapshot())

        body = serve(engine, "VCB").json()

        assert body["symbol"] == "VCB"
        assert body["market"]["data"]["last_price"] == 59_700
        assert body["market"]["data"]["volume"] == 1_000
        assert body["market"]["source"] == "fiinquant"
        assert datetime.fromisoformat(body["market"]["observed_at"]) == OBSERVED_AT
        assert body["market"]["age_seconds"] >= 0

    def test_each_part_names_the_provider_source_behind_it(self):
        """Two providers answer one symbol, and the split is visible.

        Market and valuation come from one source, ownership and the accounts
        from another (``docs/adr/0002``). A reader judging how much to trust a
        figure needs to know which of them produced it.
        """
        engine = database()
        write(engine, Capability.MARKET, market_snapshot())
        write(engine, Capability.VALUATION, valuation_snapshot())
        write(engine, Capability.REFERENCE, reference_snapshot())
        write(
            engine,
            Capability.FUNDAMENTAL,
            fundamental_snapshot(period_end=date(2026, 6, 30)),
        )

        body = serve(engine, "VCB").json()

        assert body["market"]["source"] == "fiinquant"
        assert body["valuation"]["source"] == "fiinquant"
        assert body["valuation"]["data"]["provider_pe"] == 12.5
        assert body["reference"]["source"] == "vnstock"
        assert body["reference"]["data"]["shares"] == [
            {"share_type": "outstanding", "value": 5_589_000_000}
        ]
        assert body["fundamental"]["source"] == "vnstock"
        assert body["fundamental"]["data"]["period_end"] == "2026-06-30"

    def test_a_broken_redis_still_answers_out_of_postgresql(self):
        """The cache is an accelerator, never the thing holding the data.

        A Redis outage that emptied the app would turn a speed layer into a
        second way to lose the day's numbers.
        """
        engine = database()
        write(engine, Capability.MARKET, market_snapshot())

        response = serve(engine, "VCB", redis=FailedRedis())

        assert response.status_code == 200
        assert response.json()["market"]["data"]["last_price"] == 59_700

    def test_answering_a_request_opens_no_connection_of_its_own(self):
        """The whole point of Snapshot-first, asserted at the only place it can
        be: a socket. Named provider entry points would let a new one slip in
        unnoticed, so this refuses the network itself.
        """
        engine = database()
        write(engine, Capability.MARKET, market_snapshot())

        def refuse(*args, **kwargs):
            raise AssertionError("the serving path reached for the network")

        with patch("socket.socket.connect", refuse), patch(
            "socket.create_connection", refuse
        ), patch("src.core.ratelimit.get_redis", return_value=None):
            response = serve(engine, "VCB")

        assert response.status_code == 200
        assert response.json()["market"]["data"]["last_price"] == 59_700


class TestTheWireShapeAgainstWhatIsCollected:
    def test_every_collected_field_has_somewhere_to_land(self):
        """A field added upstream and forgotten here would 500 every request.

        The response models forbid unknown fields on purpose — a number that
        silently disappeared from the wire is worse than a loud failure — so
        the drift is caught here rather than in production.
        """
        pairs = (
            (MarketSnapshot, MarketData),
            (ValuationSnapshot, ValuationData),
            (ReferenceSnapshot, ReferenceData),
            (FundamentalSnapshot, FundamentalData),
        )

        for collected, served in pairs:
            assert set(collected.model_fields) - {"symbol", "metadata"} == set(
                served.model_fields
            ), f"{collected.__name__} and {served.__name__} have drifted apart"


class TestHowOldTheDataIs:
    def test_a_long_weekend_does_not_make_the_last_session_stale(self):
        """Friday's close is still the latest close on Monday morning.

        The collector runs on trading days, so a threshold tuned for an
        intraday feed would raise the stale flag every weekend and on every
        holiday — and a warning that is always on is one nobody reads.
        """
        engine = database()
        observed_at = datetime.now(timezone.utc) - timedelta(days=3)
        write(engine, Capability.MARKET, market_snapshot(observed_at=observed_at))
        write(engine, Capability.VALUATION, valuation_snapshot(observed_at))
        write(engine, Capability.REFERENCE, reference_snapshot(observed_at))
        write(engine, Capability.FUNDAMENTAL, fundamental_snapshot(observed_at))

        body = serve(engine, "VCB").json()

        assert [body[part]["stale"] for part in SECTIONS] == [False] * len(SECTIONS)
        assert body["market"]["age_seconds"] >= 3 * 24 * 60 * 60

    def test_sessions_missed_on_end_do_raise_the_flag(self):
        """Once the collector has been down through several sessions, the
        number on screen is no longer the market and says so."""
        engine = database()
        observed_at = datetime.now(timezone.utc) - timedelta(days=10)
        write(engine, Capability.MARKET, market_snapshot(observed_at=observed_at))
        write(engine, Capability.VALUATION, valuation_snapshot(observed_at))
        write(engine, Capability.REFERENCE, reference_snapshot(observed_at))

        body = serve(engine, "VCB").json()

        # Statements are deliberately absent here: they run on a quarterly
        # clock and are judged by their own threshold, two tests below.
        assert body["market"]["stale"] is True
        assert body["valuation"]["stale"] is True
        assert body["reference"]["stale"] is True

    def test_the_latest_quarter_is_not_old_news_six_weeks_after_it_closed(self):
        """Statements are dated by the period they close, not by collection.

        A company reporting on time still leaves its most recent statement
        weeks old — that is the fastest this data can ever be. Judging it by
        the session cadence marks every healthy symbol stale.
        """
        engine = database()
        now = datetime.now(timezone.utc)
        write(
            engine,
            Capability.FUNDAMENTAL,
            fundamental_snapshot(observed_at=now, period_end=(now - timedelta(days=42)).date()),
        )

        body = serve(engine, "VCB").json()

        assert body["fundamental"]["stale"] is False

    def test_a_company_that_has_not_reported_in_a_year_is_flagged(self):
        """Two quarters past due is a real gap, and it says so."""
        engine = database()
        now = datetime.now(timezone.utc)
        write(
            engine,
            Capability.FUNDAMENTAL,
            fundamental_snapshot(observed_at=now, period_end=(now - timedelta(days=400)).date()),
        )

        body = serve(engine, "VCB").json()

        assert body["fundamental"]["stale"] is True

    def test_age_counts_from_the_session_not_from_the_run_that_fetched_it(self):
        """Re-reading an old session must not make it look like today's.

        Age is a property of the data, not of the job. Measured from the run,
        a collector re-fetching a week-old session would reset the age to zero
        and switch the warning off on exactly the day it is needed.
        """
        engine = database()
        now = datetime.now(timezone.utc)
        write(
            engine,
            Capability.MARKET,
            market_snapshot(observed_at=now, effective_at=now - timedelta(days=10)),
        )

        body = serve(engine, "VCB").json()

        assert body["market"]["age_seconds"] >= 10 * 24 * 60 * 60
        assert body["market"]["stale"] is True


class TestASymbolTheSystemDoesNotWatch:
    def test_a_symbol_outside_the_universe_is_refused_in_so_many_words(self):
        """Silence would read as a broken app.

        A real symbol this system simply has not been asked to follow is not a
        missing page and not a fault — so it says which of the two it is.
        """
        response = serve(database(), "SSI", universe=("VCB",))

        assert response.status_code == 404
        assert "SSI" in response.json()["detail"]
        assert "chưa thu thập" in response.json()["detail"]

    def test_text_that_is_not_a_symbol_is_told_apart_from_one_we_skip(self):
        """A typo and an untracked company are different problems.

        Rolling them together would send someone hunting for a symbol they
        never asked for, or waiting for a collection that will never cover a
        string that is not a symbol at all.
        """
        response = serve(database(), "NOT-A-SYMBOL", universe=("VCB",))

        assert response.status_code == 422
        assert "không hợp lệ" in response.json()["detail"]


class TestTheMarketWideEndpoints:
    def test_they_still_answer_from_where_they_always_did(self):
        """Frozen, deliberately: they are not part of the Universe promise.

        Adding a symbol-shaped route to this router is exactly how a listing
        endpoint gets swallowed by a path parameter, so one of them is asked
        for here and has to come back from its own service.
        """
        with patch("src.stocks.market.router.get_market_service") as service:
            service.return_value.list_symbols.return_value = []
            response = TestClient(app).get("/api/v1/stocks/symbols")

        assert response.status_code == 200
        assert response.json() == []


class TestASymbolWaitingOnItsFirstCollection:
    def test_nothing_collected_yet_is_an_answer_rather_than_a_failure(self):
        """A watched symbol before its first cycle is a state, not a fault.

        The symbol is ours and the collection is coming, so the response says
        so — a 404 here would read as "we do not follow this symbol" and a 500
        as "we are broken".
        """
        response = serve(database(), "VCB", universe=("VCB",))

        assert response.status_code == 200
        assert response.json() == {
            "symbol": "VCB",
            "market": None,
            "valuation": None,
            "reference": None,
            "fundamental": None,
        }


class TestASeriesOfSessions:
    """Stories 4 and 7 of #6: years of price, and valuation read against itself."""

    def test_the_sessions_come_back_oldest_first_with_their_sources(self):
        engine = database()
        write(engine, Capability.MARKET, session_snapshot(date(2019, 3, 1), 30_000,
                                                          ProviderSource.VNSTOCK))
        write(engine, Capability.MARKET, session_snapshot(date(2026, 8, 7), 59_700))
        write(engine, Capability.MARKET, session_snapshot(date(2026, 8, 10), 60_300))

        body = ask(engine, "VCB/series/market?start=2010-01-01&end=2026-08-10").json()

        assert [point["close_price"] for point in body["points"]] == [
            30_000,
            59_700,
            60_300,
        ]
        # The seam between the two providers is on the wire, not hidden by it.
        assert [point["source"] for point in body["points"]] == [
            "vnstock",
            "fiinquant",
            "fiinquant",
        ]

    def test_a_weekly_bar_spans_its_sessions_rather_than_sampling_one(self):
        engine = database()
        for day, close in ((6, 59_000), (7, 59_700), (10, 60_300)):
            write(engine, Capability.MARKET, session_snapshot(date(2026, 8, day), close))

        body = ask(
            engine,
            "VCB/series/market?start=2026-08-01&end=2026-08-10&interval=1W",
        ).json()

        # Two weeks: 3–9 August closing at Friday's 59_700, then 10 August.
        assert [point["close_price"] for point in body["points"]] == [59_700, 60_300]
        assert body["points"][0]["open_price"] == 58_700
        assert body["points"][0]["volume"] == 2_000_000
        # Dated by the week, not by the session that opened it: a symbol that
        # took Monday off has to land on the same bar as one that did not.
        assert body["points"][0]["effective_at"].startswith("2026-08-03")

    def test_a_bar_missing_part_of_its_period_reports_no_total_at_all(self):
        """The Cover Source's history carries volume but no traded value.

        Summing what is there would report a few days' turnover as the week's —
        a smaller number that looks like a total, with nothing on the wire to
        say part of the period was left out.
        """
        engine = database()
        deep = session_snapshot(date(2026, 8, 6), 59_000, ProviderSource.VNSTOCK)
        write(engine, Capability.MARKET, deep.model_copy(update={"total_value_vnd": None}))
        write(engine, Capability.MARKET, session_snapshot(date(2026, 8, 7), 59_700))

        body = ask(
            engine,
            "VCB/series/market?start=2026-08-01&end=2026-08-09&interval=1W",
        ).json()

        assert body["points"][0]["total_value_vnd"] is None
        assert body["points"][0]["volume"] == 2_000_000

    def test_only_the_newest_session_decides_whether_the_series_is_stale(self):
        engine = database()
        write(engine, Capability.MARKET, session_snapshot(date(2019, 3, 1), 30_000))
        write(engine, Capability.MARKET, session_snapshot(date(2026, 8, 10), 60_300))

        with patch(
            "src.stocks.providers.store.datetime",
            wraps=datetime,
        ) as clock:
            clock.now.return_value = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)
            body = ask(engine, "VCB/series/market").json()

        assert body["stale"] is False
        assert body["age_seconds"] is not None

    def test_a_window_the_store_holds_nothing_for_is_empty_not_missing(self):
        engine = database()
        write(engine, Capability.MARKET, session_snapshot(date(2026, 8, 10), 60_300))

        body = ask(engine, "VCB/series/market?start=2026-01-01&end=2026-01-05").json()

        assert body["points"] == []
        assert body["age_seconds"] is None
        assert body["stale"] is False

    def test_the_ratio_series_carries_one_point_per_session(self):
        engine = database()
        write(engine, Capability.VALUATION, valuation_snapshot())

        body = ask(engine, "VCB/series/valuation").json()

        assert body["points"] == [
            {
                "effective_at": body["points"][0]["effective_at"],
                "source": "fiinquant",
                "provider_pe": 12.5,
                "provider_pb": 1.8,
            }
        ]

    def test_an_interval_finer_than_a_session_is_refused_by_name(self):
        """The store holds one bar a day. Answering 5m with a daily bar would
        be a lie the caller cannot see; #6 leaves in-session data frozen."""
        engine = database()

        response = ask(engine, "VCB/series/market?interval=5m")

        assert response.status_code == 400
        assert "1D" in response.json()["detail"]

    def test_a_backwards_window_is_refused_before_the_store_is_read(self):
        engine = database()

        response = ask(engine, "VCB/series/market?start=2026-08-10&end=2026-08-01")

        assert response.status_code == 400

    def test_a_symbol_outside_the_universe_is_refused_the_same_way_everywhere(self):
        engine = database()

        for path in ("VCB/snapshot", "VCB/series/market", "VCB/series/valuation"):
            response = ask(engine, path, universe=("HPG",))
            assert response.status_code == 404
            assert "chưa thu thập" in response.json()["detail"]

    def test_the_series_paths_open_no_socket(self):
        """The promise the whole pipeline exists for, asserted rather than argued.

        Every outbound connection in this process goes through socket.connect,
        so a connect that raises turns any provider call in the request path
        into a failed test instead of a slow one.
        """
        import socket

        engine = database()
        write(engine, Capability.MARKET, session_snapshot(date(2026, 8, 10), 60_300))
        write(engine, Capability.VALUATION, valuation_snapshot())

        def refuse(*args, **kwargs):
            raise AssertionError("the serving path reached for the network")

        with patch.object(socket.socket, "connect", refuse), patch.object(
            socket.socket, "connect_ex", refuse
        ):
            for path in ("VCB/snapshot", "VCB/series/market", "VCB/series/valuation"):
                assert ask(engine, path).status_code == 200
