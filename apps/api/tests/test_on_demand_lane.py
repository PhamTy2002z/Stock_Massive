"""The one lane that may mint an Analysis outside the nightly pass.

Adding a symbol to a Watchlist is the only thing that creates an on-demand
**Analysis Run**, and two rules carry the whole ticket:

*It always targets the latest Trading Day that already has a Snapshot.* Adding a
symbol at 10:00 yields an Analysis for the last session that closed, clearly
labelled. That is not a policy the lane checks — it is a shape: the lane takes a
user and a symbol and nothing else, so there is no argument through which a
session that has not closed could arrive.

*Three new on-demand Analyses per user per Trading Day.* An addition whose
Analysis already exists is free, because the artifact is keyed by
``(symbol, trading_day)`` and shared — a second watcher is a read. Above the
allowance the **addition still succeeds**; only its Analysis waits for the
nightly cohort. A user is not blocked from curating their Watchlist by a
production budget.

Run against a live Postgres. The Trading Day is resolved from
``provider_snapshots``, the allowance is a count over ``analysis_run``, and both
are the point — a fake store would let every one of these pass while the real
one behaved differently.

The nightly cohort, the queue and the backoff schedule are A4's. Nothing here
produces anything: the lane creates a `pending` run and stops.
"""

import uuid
from datetime import date, datetime, time, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from src.alpha.analysis_run import RunOrigin, RunStatus
from src.alpha.models import Analysis, AnalysisRun, WatchlistEntry
from src.alpha.on_demand import (
    ON_DEMAND_ANALYSES_PER_DAY,
    OnDemandOutcome,
    request_on_demand_analysis,
)
from src.auth.models import RefreshToken, User
from src.core.config import get_settings
from src.core.database import Base, engine, get_sync_db, sync_engine, sync_session_factory
from src.main import app
from src.stocks.models import ProviderSnapshot
from src.stocks.providers import Capability, ProviderSource
from src.stocks.providers.normalize import VN_TZ
from src.stocks.universe import forget_cohort_cache

API = "/api/v1"

# Five declared symbols, so the three-per-day allowance can be spent and then
# collided with, twice over.
DECLARED = ("ODAAA", "ODBBB", "ODCCC", "ODDDD", "ODEEE")

# Two sessions the store holds nothing else newer than, so `latest_trading_day`
# is this module's to decide rather than whatever the environment collected.
# Deliberately nowhere near the calendar: a lane that reached for `date.today()`
# would answer with a day these tests never seeded.
SEEDED_DAY = date(2099, 1, 5)
NEXT_SEEDED_DAY = date(2099, 1, 6)


@pytest.fixture(scope="module", autouse=True)
def alpha_schema():
    Base.metadata.create_all(
        sync_engine,
        tables=[
            Analysis.__table__,
            AnalysisRun.__table__,
            WatchlistEntry.__table__,
        ],
        checkfirst=True,
    )


@pytest.fixture(autouse=True)
def declared_universe(monkeypatch):
    monkeypatch.setenv("UNIVERSE_SYMBOLS", ",".join(DECLARED))
    get_settings.cache_clear()
    forget_cohort_cache()
    yield
    monkeypatch.undo()
    get_settings.cache_clear()
    forget_cohort_cache()


@pytest.fixture
def snapshotted_session():
    """Declare which sessions the store holds, and take them away afterwards.

    A market Snapshot dated at midnight in Vietnam is exactly one Trading Day
    (`src/stocks/trading_day.py`), so seeding one row is how a test says "this
    session has closed".
    """
    seeded: list[date] = []

    def close(day: date) -> None:
        stamp = datetime.combine(day, time.min, tzinfo=VN_TZ)
        with get_sync_db() as session:
            session.add(
                ProviderSnapshot(
                    capability=Capability.MARKET.value,
                    symbol=DECLARED[0],
                    source=ProviderSource.FIINQUANT.value,
                    effective_at=stamp,
                    observed_at=stamp,
                    schema_version=1,
                    payload={},
                )
            )
        seeded.append(day)

    yield close

    with get_sync_db() as session:
        for day in seeded:
            session.execute(
                delete(ProviderSnapshot).where(
                    ProviderSnapshot.symbol == DECLARED[0],
                    ProviderSnapshot.effective_at
                    == datetime.combine(day, time.min, tzinfo=VN_TZ),
                )
            )


@pytest.fixture(autouse=True)
def clean_rows():
    """Every row this module's symbols can leave behind, removed either side."""

    def wipe() -> None:
        with get_sync_db() as session:
            session.execute(delete(Analysis).where(Analysis.symbol.in_(DECLARED)))
            session.execute(delete(AnalysisRun).where(AnalysisRun.symbol.in_(DECLARED)))

    wipe()
    yield
    wipe()


@pytest.fixture
def session():
    session = sync_session_factory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def watcher():
    """A user id, with the account and its Watchlist removed afterwards."""
    created: list[int] = []

    def make(*symbols: str) -> int:
        with get_sync_db() as inner:
            user = User(
                email=f"ondemand-{uuid.uuid4().hex[:12]}@example.com",
                hashed_password="x",
            )
            inner.add(user)
            inner.flush()
            for symbol in symbols:
                inner.add(WatchlistEntry(user_id=user.id, symbol=symbol))
            created.append(user.id)
            return user.id

    yield make

    with get_sync_db() as inner:
        for user_id in created:
            inner.execute(delete(WatchlistEntry).where(WatchlistEntry.user_id == user_id))
            inner.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
            inner.execute(delete(User).where(User.id == user_id))


@pytest.fixture
def published():
    """An Analysis that already exists, so a second watcher is a free read."""

    def store(symbol: str, trading_day: date) -> None:
        with get_sync_db() as session:
            session.add(
                Analysis(
                    symbol=symbol,
                    trading_day=trading_day,
                    verdict="hold",
                    payload={"note": "published before the test"},
                    schema_version=1,
                )
            )

    return store


def _runs(session, symbol: str) -> list[AnalysisRun]:
    session.expire_all()
    return list(
        session.execute(
            select(AnalysisRun).where(AnalysisRun.symbol == symbol)
        ).scalars()
    )


def _spend_allowance(session, user_id: int) -> None:
    """Use up the whole allowance on distinct symbols."""
    for symbol in DECLARED[:ON_DEMAND_ANALYSES_PER_DAY]:
        outcome = request_on_demand_analysis(session, user_id, symbol)
        assert outcome.outcome is OnDemandOutcome.CREATED, outcome


class TestWhichSessionItTargets:
    """Always the latest Trading Day that already has a Snapshot."""

    def test_an_addition_creates_one_run_marked_with_its_origin(
        self, session, watcher, snapshotted_session
    ):
        snapshotted_session(SEEDED_DAY)
        user_id = watcher()

        outcome = request_on_demand_analysis(session, user_id, DECLARED[0])

        assert outcome.outcome is OnDemandOutcome.CREATED
        runs = _runs(session, DECLARED[0])
        assert len(runs) == 1
        assert runs[0].origin == RunOrigin.ON_DEMAND.value
        assert runs[0].status == RunStatus.PENDING.value
        assert runs[0].trading_day == SEEDED_DAY

    def test_the_session_comes_from_the_store_and_never_from_the_clock(
        self, session, watcher, snapshotted_session
    ):
        """The seeded session is years from today. A lane reaching for
        `date.today()` — or for "the session that is open now" — would answer
        with a day nothing in this module ever closed."""
        snapshotted_session(SEEDED_DAY)
        user_id = watcher()

        request_on_demand_analysis(session, user_id, DECLARED[0])

        assert _runs(session, DECLARED[0])[0].trading_day == SEEDED_DAY
        assert _runs(session, DECLARED[0])[0].trading_day != date.today()

    def test_the_newest_snapshotted_session_wins(
        self, session, watcher, snapshotted_session
    ):
        snapshotted_session(SEEDED_DAY)
        snapshotted_session(NEXT_SEEDED_DAY)
        user_id = watcher()

        request_on_demand_analysis(session, user_id, DECLARED[0])

        assert _runs(session, DECLARED[0])[0].trading_day == NEXT_SEEDED_DAY

    def test_no_caller_can_choose_the_session(self):
        """The guarantee is structural rather than checked. The lane takes a
        user and a symbol; there is no parameter through which a session that
        has not closed could be requested, which is why no test can construct
        that case."""
        import inspect

        parameters = set(inspect.signature(request_on_demand_analysis).parameters)

        assert parameters == {"session", "user_id", "symbol"}

    def test_a_store_holding_no_session_creates_nothing_and_says_so(
        self, session, watcher, monkeypatch
    ):
        """A fresh environment has collected nothing. Substituting today would
        mint an artifact labelled with a session that never happened."""
        monkeypatch.setattr(
            "src.alpha.on_demand.latest_trading_day", lambda _session: None
        )
        user_id = watcher()

        outcome = request_on_demand_analysis(session, user_id, DECLARED[0])

        assert outcome.outcome is OnDemandOutcome.NO_SNAPSHOTTED_SESSION
        assert outcome.trading_day is None
        assert outcome.message
        assert _runs(session, DECLARED[0]) == []


class TestWhatIsFree:
    """A shared artifact means a second watcher costs nothing."""

    def test_a_symbol_already_analysed_creates_no_run(
        self, session, watcher, snapshotted_session, published
    ):
        snapshotted_session(SEEDED_DAY)
        published(DECLARED[0], SEEDED_DAY)
        user_id = watcher()

        outcome = request_on_demand_analysis(session, user_id, DECLARED[0])

        assert outcome.outcome is OnDemandOutcome.ALREADY_ANALYSED
        assert _runs(session, DECLARED[0]) == []

    def test_a_free_addition_does_not_consume_the_allowance(
        self, session, watcher, snapshotted_session, published
    ):
        """Ten watchers of one analysed symbol must not exhaust ten
        allowances between them."""
        snapshotted_session(SEEDED_DAY)
        published(DECLARED[4], SEEDED_DAY)
        user_id = watcher()

        free = request_on_demand_analysis(session, user_id, DECLARED[4])

        assert free.remaining == ON_DEMAND_ANALYSES_PER_DAY
        _spend_allowance(session, user_id)

    def test_a_symbol_someone_else_already_queued_creates_no_second_run(
        self, session, watcher, snapshotted_session
    ):
        snapshotted_session(SEEDED_DAY)
        first = watcher()
        second = watcher()
        request_on_demand_analysis(session, first, DECLARED[0])

        outcome = request_on_demand_analysis(session, second, DECLARED[0])

        assert outcome.outcome is OnDemandOutcome.ALREADY_QUEUED
        assert len(_runs(session, DECLARED[0])) == 1

    def test_joining_a_queued_symbol_costs_the_joiner_nothing(
        self, session, watcher, snapshotted_session
    ):
        snapshotted_session(SEEDED_DAY)
        first = watcher()
        second = watcher()
        request_on_demand_analysis(session, first, DECLARED[4])

        joined = request_on_demand_analysis(session, second, DECLARED[4])

        assert joined.remaining == ON_DEMAND_ANALYSES_PER_DAY
        _spend_allowance(session, second)

    def test_two_users_adding_the_same_symbol_yield_one_run_and_one_analysis(
        self, session, watcher, snapshotted_session
    ):
        snapshotted_session(SEEDED_DAY)
        first = watcher()
        second = watcher()

        request_on_demand_analysis(session, first, DECLARED[0])
        request_on_demand_analysis(session, second, DECLARED[0])

        runs = _runs(session, DECLARED[0])
        assert len(runs) == 1
        assert runs[0].trading_day == SEEDED_DAY


class TestTheAllowance:
    """Three per user per Trading Day, and it resets with the session."""

    def test_the_fourth_new_analysis_in_one_session_is_not_produced(
        self, session, watcher, snapshotted_session
    ):
        snapshotted_session(SEEDED_DAY)
        user_id = watcher()
        _spend_allowance(session, user_id)

        fourth = request_on_demand_analysis(session, user_id, DECLARED[3])

        assert fourth.outcome is OnDemandOutcome.ALLOWANCE_EXHAUSTED
        assert fourth.remaining == 0
        assert fourth.message
        assert _runs(session, DECLARED[3]) == []

    def test_the_allowance_is_counted_per_user(
        self, session, watcher, snapshotted_session
    ):
        """One heavy user must not spend everyone else's evening."""
        snapshotted_session(SEEDED_DAY)
        spent = watcher()
        fresh = watcher()
        _spend_allowance(session, spent)

        outcome = request_on_demand_analysis(session, fresh, DECLARED[3])

        assert outcome.outcome is OnDemandOutcome.CREATED
        assert outcome.remaining == ON_DEMAND_ANALYSES_PER_DAY - 1

    def test_the_allowance_resets_with_the_trading_day_not_a_rolling_clock(
        self, session, watcher, snapshotted_session
    ):
        """Nothing here waits for a clock to tick over. The count is keyed by
        the session it was spent on, so a new session is a new allowance by
        construction."""
        snapshotted_session(SEEDED_DAY)
        user_id = watcher()
        _spend_allowance(session, user_id)
        assert (
            request_on_demand_analysis(session, user_id, DECLARED[3]).outcome
            is OnDemandOutcome.ALLOWANCE_EXHAUSTED
        )

        snapshotted_session(NEXT_SEEDED_DAY)

        outcome = request_on_demand_analysis(session, user_id, DECLARED[3])
        assert outcome.outcome is OnDemandOutcome.CREATED
        assert outcome.remaining == ON_DEMAND_ANALYSES_PER_DAY - 1
        assert _runs(session, DECLARED[3])[0].trading_day == NEXT_SEEDED_DAY

    def test_a_nightly_run_is_not_charged_to_anyone(
        self, session, watcher, snapshotted_session
    ):
        """The nightly cohort produces for everybody. Counting its runs against
        whoever happens to watch the symbol would empty allowances nobody
        spent."""
        snapshotted_session(SEEDED_DAY)
        user_id = watcher()
        with get_sync_db() as inner:
            inner.add(
                AnalysisRun(
                    symbol=DECLARED[0],
                    trading_day=SEEDED_DAY,
                    status=RunStatus.PENDING.value,
                    origin=RunOrigin.NIGHTLY.value,
                    attempts=0,
                )
            )

        outcome = request_on_demand_analysis(session, user_id, DECLARED[1])

        assert outcome.remaining == ON_DEMAND_ANALYSES_PER_DAY - 1


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    await engine.dispose()


@pytest.fixture
def account():
    email = f"ondemand-api-{uuid.uuid4().hex[:12]}@example.com"
    yield {"email": email, "password": "sup3r-secret-pw"}

    with get_sync_db() as session:
        user = session.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()
        if user is not None:
            session.execute(delete(WatchlistEntry).where(WatchlistEntry.user_id == user.id))
            session.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
            session.execute(delete(User).where(User.id == user.id))


@pytest_asyncio.fixture
async def auth(client, account):
    response = await client.post(f"{API}/auth/register", json=account)
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class TestThroughTheApi:
    """What the rail learns from an addition."""

    @pytest.mark.asyncio
    async def test_an_addition_reports_the_session_it_produced_for(
        self, client, auth, snapshotted_session
    ):
        snapshotted_session(SEEDED_DAY)

        response = await client.post(
            f"{API}/watchlist", json={"symbol": DECLARED[0]}, headers=auth
        )

        assert response.status_code == 201, response.text
        lane = response.json()["on_demand"]
        assert lane["outcome"] == OnDemandOutcome.CREATED.value
        assert lane["trading_day"] == SEEDED_DAY.isoformat()
        assert lane["remaining"] == ON_DEMAND_ANALYSES_PER_DAY - 1

    @pytest.mark.asyncio
    async def test_the_fourth_addition_still_succeeds_with_the_reason_surfaced(
        self, client, auth, snapshotted_session
    ):
        """The Watchlist is the user's to curate. A production budget refuses
        the Analysis, never the addition."""
        snapshotted_session(SEEDED_DAY)
        for symbol in DECLARED[:ON_DEMAND_ANALYSES_PER_DAY]:
            accepted = await client.post(
                f"{API}/watchlist", json={"symbol": symbol}, headers=auth
            )
            assert accepted.status_code == 201, accepted.text

        response = await client.post(
            f"{API}/watchlist", json={"symbol": DECLARED[3]}, headers=auth
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert DECLARED[3] in [entry["symbol"] for entry in body["entries"]]
        assert body["count"] == ON_DEMAND_ANALYSES_PER_DAY + 1
        assert body["on_demand"]["outcome"] == OnDemandOutcome.ALLOWANCE_EXHAUSTED.value
        assert body["on_demand"]["message"]

    @pytest.mark.asyncio
    async def test_re_adding_a_symbol_already_watched_spends_nothing_more(
        self, client, auth, snapshotted_session
    ):
        """A re-add describes a state the Watchlist is already in. The lane runs
        anyway and finds the run it made a moment ago, which is why it needs no
        "was this row new" flag threaded through the addition to stay honest."""
        snapshotted_session(SEEDED_DAY)
        await client.post(f"{API}/watchlist", json={"symbol": DECLARED[0]}, headers=auth)

        response = await client.post(
            f"{API}/watchlist", json={"symbol": DECLARED[0]}, headers=auth
        )

        assert response.status_code == 201, response.text
        assert response.json()["on_demand"]["remaining"] == ON_DEMAND_ANALYSES_PER_DAY - 1
        with get_sync_db() as inner:
            runs = inner.execute(
                select(AnalysisRun).where(AnalysisRun.symbol == DECLARED[0])
            ).scalars().all()
        assert len(runs) == 1

    @pytest.mark.asyncio
    async def test_a_removed_symbol_re_added_the_same_session_is_free(
        self, client, auth, snapshotted_session
    ):
        """The run outlives the Watchlist row: it is keyed by the pair and
        shared, so churning a symbol cannot drain the allowance."""
        snapshotted_session(SEEDED_DAY)
        await client.post(f"{API}/watchlist", json={"symbol": DECLARED[0]}, headers=auth)

        for _ in range(3):
            assert (
                await client.delete(f"{API}/watchlist/{DECLARED[0]}", headers=auth)
            ).status_code == 200
            readded = await client.post(
                f"{API}/watchlist", json={"symbol": DECLARED[0]}, headers=auth
            )
            assert readded.status_code == 201, readded.text

        assert readded.json()["on_demand"]["outcome"] == OnDemandOutcome.ALREADY_QUEUED.value
        assert readded.json()["on_demand"]["remaining"] == ON_DEMAND_ANALYSES_PER_DAY - 1

    @pytest.mark.asyncio
    async def test_a_refused_addition_never_reaches_the_lane(self, client, auth):
        """A symbol outside the Universe is refused before anything is seated,
        so there is no run to make and no allowance to spend."""
        response = await client.post(
            f"{API}/watchlist", json={"symbol": "NOPE"}, headers=auth
        )

        assert response.status_code == 422, response.text
        with get_sync_db() as inner:
            assert (
                inner.execute(
                    select(AnalysisRun).where(AnalysisRun.symbol == "NOPE")
                ).scalar_one_or_none()
                is None
            )
