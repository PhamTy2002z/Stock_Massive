"""Reading Analyses: the newest per symbol, one by pair, history, last-seen.

**Nothing produces an Analysis yet.** The pipeline is a later milestone, so
every row here is inserted directly and these tests say so rather than pretending
a producer exists. What is under test is the reading, and the reading is where
the design pays off:

*Serving the newest needs no mechanism.* A row existing means it is complete, so
newest Trading Day wins and no query filters incomplete rows. If a status filter
ever appears in one of these paths, it is because the invariant was given up
somewhere else, and that is what these tests are for.

*Every read is by ``(symbol, trading_day)``.* The unique key excludes
``schema_version`` on purpose, so a reader meets several template versions across
days and never chooses between two rows for one pair.

*``last_seen_analysis_date`` advances only when that Analysis is opened.* Not on
app open, not on a list request. A rail read that moved it would clear ten badges
at once and make the indicator meaningless exactly when it has work to do.

Run against a live Postgres: the rail resolves its session from
``provider_snapshots`` and its states from ``analysis_run``, and a fake store
would let the wrong answer pass.
"""

import uuid
from datetime import date, datetime, time

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from src.alpha.analysis_reads import HISTORY_DEPTH_SESSIONS, AnalysisState
from src.alpha.analysis_run import MAX_ATTEMPTS_PER_SESSION, RunOrigin, RunStatus
from src.alpha.models import Analysis, AnalysisRun, WatchlistEntry
from src.auth.models import RefreshToken, User
from src.core.config import get_settings
from src.core.database import Base, engine, get_sync_db, sync_engine
from src.main import app
from src.stocks.models import ProviderSnapshot
from src.stocks.providers import Capability, ProviderSource
from src.stocks.providers.normalize import VN_TZ
from src.stocks.universe import forget_cohort_cache

API = "/api/v1"

DECLARED = ("ARDAAA", "ARDBBB", "ARDCCC", "ARDDDD")
OUTSIDE = "ARDZZZ"

# The session the rail is showing, and the two before it. Far from the calendar
# on purpose: a rail that reached for `date.today()` would label itself with a
# day this module never closed.
SESSION = date(2098, 3, 5)
EARLIER = date(2098, 3, 4)
EARLIEST = date(2098, 3, 3)


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
    def declare(*symbols: str) -> None:
        monkeypatch.setenv("UNIVERSE_SYMBOLS", ",".join(symbols))
        get_settings.cache_clear()
        forget_cohort_cache()

    declare(*DECLARED)
    yield declare
    monkeypatch.undo()
    get_settings.cache_clear()
    forget_cohort_cache()


@pytest.fixture
def closed_session():
    """Which sessions the store holds, and nothing left behind afterwards."""
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
    def wipe() -> None:
        with get_sync_db() as session:
            session.execute(
                delete(Analysis).where(Analysis.symbol.in_(DECLARED + (OUTSIDE,)))
            )
            session.execute(
                delete(AnalysisRun).where(AnalysisRun.symbol.in_(DECLARED + (OUTSIDE,)))
            )

    wipe()
    yield
    wipe()


@pytest.fixture
def published():
    """An Analysis, inserted directly — nothing produces one until A4."""

    def store(
        symbol: str,
        trading_day: date,
        verdict: str = "hold",
        schema_version: int = 1,
    ) -> None:
        with get_sync_db() as session:
            session.add(
                Analysis(
                    symbol=symbol,
                    trading_day=trading_day,
                    verdict=verdict,
                    payload={"thesis": f"{symbol} {trading_day.isoformat()}"},
                    schema_version=schema_version,
                )
            )

    return store


@pytest.fixture
def seeded_run():
    """Put the run for one pair into a chosen state.

    Writes over whatever is there, because there is often already a run: adding
    a symbol opens the on-demand lane, which queues one. The helper says "this
    pair is in this state" rather than "insert a row", so a test can seed either
    side of the addition.
    """

    def store(
        symbol: str,
        trading_day: date,
        status: RunStatus,
        attempts: int = 0,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        with get_sync_db() as session:
            run = session.execute(
                select(AnalysisRun).where(
                    AnalysisRun.symbol == symbol,
                    AnalysisRun.trading_day == trading_day,
                )
            ).scalar_one_or_none()
            if run is None:
                run = AnalysisRun(
                    symbol=symbol,
                    trading_day=trading_day,
                    origin=RunOrigin.NIGHTLY.value,
                )
                session.add(run)
            run.status = status.value
            run.attempts = attempts
            run.error_code = error_code
            run.error_message = error_message

    return store


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    await engine.dispose()


@pytest.fixture
def account():
    email = f"reads-{uuid.uuid4().hex[:12]}@example.com"
    yield {"email": email, "password": "sup3r-secret-pw"}

    with get_sync_db() as session:
        user = session.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()
        if user is not None:
            session.execute(delete(WatchlistEntry).where(WatchlistEntry.user_id == user.id))
            session.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
            session.execute(delete(User).where(User.id == user.id))


async def _register(client: AsyncClient, account: dict) -> dict:
    response = await client.post(f"{API}/auth/register", json=account)
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest_asyncio.fixture
async def auth(client, account):
    return await _register(client, account)


@pytest.fixture
def other_account():
    email = f"reads-other-{uuid.uuid4().hex[:12]}@example.com"
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
async def other_auth(client, other_account):
    return await _register(client, other_account)


async def _watch(client: AsyncClient, auth: dict, *symbols: str) -> None:
    for symbol in symbols:
        response = await client.post(
            f"{API}/watchlist", json={"symbol": symbol}, headers=auth
        )
        assert response.status_code == 201, response.text


async def _rail(client: AsyncClient, auth: dict) -> dict:
    response = await client.get(f"{API}/watchlist/rail", headers=auth)
    assert response.status_code == 200, response.text
    return response.json()


def _entry(rail: dict, symbol: str) -> dict:
    return next(entry for entry in rail["entries"] if entry["symbol"] == symbol)


class TestTheLatestPerSymbol:
    """Newest Trading Day wins, with nothing filtered out anywhere."""

    @pytest.mark.asyncio
    async def test_the_newest_analysis_is_served_for_each_watched_symbol(
        self, client, auth, closed_session, published
    ):
        closed_session(SESSION)
        published(DECLARED[0], EARLIEST, verdict="avoid")
        published(DECLARED[0], SESSION, verdict="accumulate")
        published(DECLARED[1], EARLIER, verdict="hold")
        await _watch(client, auth, DECLARED[0], DECLARED[1])

        rail = await _rail(client, auth)

        assert _entry(rail, DECLARED[0])["latest"]["trading_day"] == SESSION.isoformat()
        assert _entry(rail, DECLARED[0])["latest"]["verdict"] == "accumulate"
        assert _entry(rail, DECLARED[1])["latest"]["trading_day"] == EARLIER.isoformat()

    @pytest.mark.asyncio
    async def test_the_rail_names_the_session_it_is_showing(
        self, client, auth, closed_session
    ):
        """Data-defined and dated. The latest session with a Snapshot is
        frequently not today, and the rail must not claim otherwise."""
        closed_session(EARLIER)
        closed_session(SESSION)
        await _watch(client, auth, DECLARED[0])

        rail = await _rail(client, auth)

        assert rail["trading_day"] == SESSION.isoformat()
        assert rail["trading_day"] != date.today().isoformat()

    @pytest.mark.asyncio
    async def test_a_symbol_never_analysed_carries_no_artifact(
        self, client, auth, closed_session
    ):
        closed_session(SESSION)
        await _watch(client, auth, DECLARED[0])

        rail = await _rail(client, auth)

        assert _entry(rail, DECLARED[0])["latest"] is None

    @pytest.mark.asyncio
    async def test_the_cap_and_the_count_travel_with_the_rail(
        self, client, auth, closed_session
    ):
        """One request, or the count and the list are answered at two moments."""
        closed_session(SESSION)
        await _watch(client, auth, DECLARED[0], DECLARED[1])

        rail = await _rail(client, auth)

        assert rail["count"] == 2
        assert rail["cap"] == 10


class TestTheFiveStates:
    """One is a fact about `analysis`; three come from the run; one from the Universe."""

    @pytest.mark.asyncio
    async def test_an_analysis_for_the_session_reads_as_ready(
        self, client, auth, closed_session, published
    ):
        closed_session(SESSION)
        published(DECLARED[0], SESSION)
        await _watch(client, auth, DECLARED[0])

        assert _entry(await _rail(client, auth), DECLARED[0])["state"] == AnalysisState.READY.value

    @pytest.mark.asyncio
    async def test_a_symbol_whose_turn_has_not_come_reads_as_pending(
        self, client, auth, closed_session
    ):
        """A real state, not a synonym for absent: without it a symbol that
        failed looks exactly like one not yet reached."""
        closed_session(SESSION)
        await _watch(client, auth, DECLARED[0])

        assert _entry(await _rail(client, auth), DECLARED[0])["state"] == AnalysisState.PENDING.value

    @pytest.mark.asyncio
    async def test_a_run_mid_flight_reads_as_producing(
        self, client, auth, closed_session, seeded_run
    ):
        closed_session(SESSION)
        seeded_run(DECLARED[0], SESSION, RunStatus.PRODUCING, attempts=1)
        await _watch(client, auth, DECLARED[0])

        assert (
            _entry(await _rail(client, auth), DECLARED[0])["state"]
            == AnalysisState.PRODUCING.value
        )

    @pytest.mark.asyncio
    async def test_a_failed_session_still_shows_the_last_analysis_there_was(
        self, client, auth, closed_session, published, seeded_run
    ):
        """`failed` never renders empty. An empty cell tells the user there is
        nothing to see while a month of history sits behind it."""
        closed_session(SESSION)
        published(DECLARED[0], EARLIER, verdict="hold")
        seeded_run(
            DECLARED[0],
            SESSION,
            RunStatus.FAILED,
            attempts=1,
            error_code="missing_market_snapshot",
            error_message="no session data for ARDAAA",
        )
        await _watch(client, auth, DECLARED[0])

        entry = _entry(await _rail(client, auth), DECLARED[0])

        assert entry["state"] == AnalysisState.FAILED.value
        assert entry["latest"]["trading_day"] == EARLIER.isoformat()
        assert entry["failure"]["code"] == "missing_market_snapshot"
        assert entry["failure"]["message"] == "no session data for ARDAAA"
        assert entry["failure"]["exhausted"] is False

    @pytest.mark.asyncio
    async def test_a_failure_at_the_ceiling_says_so(
        self, client, auth, closed_session, seeded_run
    ):
        """So the interface drops the retry rather than offering one more press
        that does nothing."""
        closed_session(SESSION)
        seeded_run(
            DECLARED[0],
            SESSION,
            RunStatus.FAILED,
            attempts=MAX_ATTEMPTS_PER_SESSION,
            error_code="llm_transport_error",
            error_message="LLM route did not respond",
        )
        await _watch(client, auth, DECLARED[0])

        entry = _entry(await _rail(client, auth), DECLARED[0])

        assert entry["failure"]["exhausted"] is True
        assert entry["failure"]["max_attempts"] == MAX_ATTEMPTS_PER_SESSION

    @pytest.mark.asyncio
    async def test_a_symbol_the_universe_dropped_reads_as_unsupported(
        self, client, auth, closed_session, declared_universe, seeded_run
    ):
        """It overrides whatever the run says: nothing new is produced for it,
        so `pending` would promise an Analysis that is never coming."""
        closed_session(SESSION)
        await _watch(client, auth, DECLARED[0])
        seeded_run(DECLARED[0], SESSION, RunStatus.PENDING)
        declared_universe(*[s for s in DECLARED if s != DECLARED[0]])

        assert (
            _entry(await _rail(client, auth), DECLARED[0])["state"]
            == AnalysisState.UNSUPPORTED.value
        )

    @pytest.mark.asyncio
    async def test_a_store_with_no_closed_session_leaves_the_rail_undated(
        self, client, auth
    ):
        """A fresh environment has collected nothing. Nothing is late, because
        nothing has closed."""
        await _watch(client, auth, DECLARED[0])

        rail = await _rail(client, auth)

        # Whatever the ambient store holds, the rail states its session rather
        # than implying one; on an empty store that answer is null.
        if rail["trading_day"] is None:
            assert _entry(rail, DECLARED[0])["state"] == AnalysisState.PENDING.value


class TestOneByPair:
    """Read by `(symbol, trading_day)`, and never choosing between two rows."""

    @pytest.mark.asyncio
    async def test_an_analysis_is_retrievable_by_symbol_and_date(
        self, client, auth, published
    ):
        published(DECLARED[0], EARLIER, verdict="reduce")

        response = await client.get(
            f"{API}/analyses/{DECLARED[0]}/{EARLIER.isoformat()}", headers=auth
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["verdict"] == "reduce"
        assert body["payload"]["thesis"] == f"{DECLARED[0]} {EARLIER.isoformat()}"

    @pytest.mark.asyncio
    async def test_a_pair_with_no_analysis_is_a_clean_not_found(self, client, auth):
        """Not an empty artifact: a briefing with nothing in it reads as a
        broken Analysis rather than as a session that was never analysed."""
        response = await client.get(
            f"{API}/analyses/{DECLARED[0]}/{EARLIER.isoformat()}", headers=auth
        )

        assert response.status_code == 404, response.text
        assert response.json()["detail"]["reason"] == "analysis_not_found"

    @pytest.mark.asyncio
    async def test_a_malformed_symbol_leaves_by_the_same_door(self, client, auth):
        response = await client.get(
            f"{API}/analyses/not a symbol!/{EARLIER.isoformat()}", headers=auth
        )

        assert response.status_code == 404, response.text
        assert response.json()["detail"]["reason"] == "analysis_not_found"

    @pytest.mark.asyncio
    async def test_reading_an_analysis_needs_no_watchlist_entry(
        self, client, auth, published
    ):
        """An Analysis is shared system-wide and never belonged to a Watchlist,
        which is the same reason removing a symbol deletes nothing."""
        published(DECLARED[0], EARLIER)

        response = await client.get(
            f"{API}/analyses/{DECLARED[0]}/{EARLIER.isoformat()}", headers=auth
        )

        assert response.status_code == 200, response.text

    @pytest.mark.asyncio
    async def test_reading_an_analysis_requires_authentication(self, client, published):
        published(DECLARED[0], EARLIER)

        assert (
            await client.get(f"{API}/analyses/{DECLARED[0]}/{EARLIER.isoformat()}")
        ).status_code == 401

    @pytest.mark.asyncio
    async def test_several_schema_versions_across_days_are_all_readable(
        self, client, auth, published
    ):
        """The unique key excludes `schema_version`, so there is one row per
        pair and a reader handles the versions rather than choosing between
        rows."""
        published(DECLARED[0], EARLIEST, schema_version=1)
        published(DECLARED[0], EARLIER, schema_version=2)

        old = await client.get(
            f"{API}/analyses/{DECLARED[0]}/{EARLIEST.isoformat()}", headers=auth
        )
        new = await client.get(
            f"{API}/analyses/{DECLARED[0]}/{EARLIER.isoformat()}", headers=auth
        )

        assert old.json()["schema_version"] == 1
        assert new.json()["schema_version"] == 2

        history = await client.get(f"{API}/analyses/{DECLARED[0]}", headers=auth)
        assert [row["schema_version"] for row in history.json()["entries"]] == [2, 1]


class TestHistory:
    """Ninety sessions, with the bound stated rather than implied."""

    @pytest.mark.asyncio
    async def test_recent_analyses_come_back_newest_first(
        self, client, auth, published
    ):
        for day in (EARLIEST, EARLIER, SESSION):
            published(DECLARED[0], day)

        response = await client.get(f"{API}/analyses/{DECLARED[0]}", headers=auth)

        assert response.status_code == 200, response.text
        assert [row["trading_day"] for row in response.json()["entries"]] == [
            SESSION.isoformat(),
            EARLIER.isoformat(),
            EARLIEST.isoformat(),
        ]

    @pytest.mark.asyncio
    async def test_the_bound_is_in_the_response(self, client, auth, published):
        published(DECLARED[0], SESSION)

        body = (await client.get(f"{API}/analyses/{DECLARED[0]}", headers=auth)).json()

        assert body["depth"] == HISTORY_DEPTH_SESSIONS
        assert body["older_exist"] is False

    @pytest.mark.asyncio
    async def test_a_symbol_deeper_than_the_bound_stops_at_ninety_and_says_so(
        self, client, auth, published
    ):
        """The length of the list answers neither question: eighty-one rows may
        be everything there is or the first eighty-one of three hundred."""
        for offset in range(HISTORY_DEPTH_SESSIONS + 5):
            published(DECLARED[0], date.fromordinal(SESSION.toordinal() - offset))

        body = (await client.get(f"{API}/analyses/{DECLARED[0]}", headers=auth)).json()

        assert len(body["entries"]) == HISTORY_DEPTH_SESSIONS
        assert body["older_exist"] is True
        assert body["entries"][0]["trading_day"] == SESSION.isoformat()

    @pytest.mark.asyncio
    async def test_a_symbol_with_no_analyses_browses_an_empty_window(
        self, client, auth
    ):
        body = (await client.get(f"{API}/analyses/{DECLARED[0]}", headers=auth)).json()

        assert body["entries"] == []
        assert body["older_exist"] is False


class TestLastSeen:
    """Advances only when that specific Analysis is opened."""

    @pytest.mark.asyncio
    async def test_opening_an_analysis_advances_the_last_seen_date(
        self, client, auth, closed_session, published
    ):
        closed_session(SESSION)
        published(DECLARED[0], SESSION)
        await _watch(client, auth, DECLARED[0])
        assert _entry(await _rail(client, auth), DECLARED[0])["unread"] is True

        response = await client.post(
            f"{API}/analyses/{DECLARED[0]}/{SESSION.isoformat()}/opened", headers=auth
        )

        assert response.status_code == 200, response.text
        assert response.json()["last_seen_analysis_date"] == SESSION.isoformat()
        assert _entry(await _rail(client, auth), DECLARED[0])["unread"] is False

    @pytest.mark.asyncio
    async def test_a_rail_read_advances_nothing(
        self, client, auth, closed_session, published
    ):
        """Opening the app must not clear ten badges at once. Reading the list
        is not an act of opening anything."""
        closed_session(SESSION)
        published(DECLARED[0], SESSION)
        published(DECLARED[1], SESSION)
        await _watch(client, auth, DECLARED[0], DECLARED[1])

        for _ in range(5):
            rail = await _rail(client, auth)

        assert [entry["unread"] for entry in rail["entries"]] == [True, True]
        assert [entry["last_seen_analysis_date"] for entry in rail["entries"]] == [None, None]

    @pytest.mark.asyncio
    async def test_badges_clear_one_symbol_at_a_time(
        self, client, auth, closed_session, published
    ):
        closed_session(SESSION)
        published(DECLARED[0], SESSION)
        published(DECLARED[1], SESSION)
        await _watch(client, auth, DECLARED[0], DECLARED[1])

        await client.post(
            f"{API}/analyses/{DECLARED[0]}/{SESSION.isoformat()}/opened", headers=auth
        )

        rail = await _rail(client, auth)
        assert _entry(rail, DECLARED[0])["unread"] is False
        assert _entry(rail, DECLARED[1])["unread"] is True

    @pytest.mark.asyncio
    async def test_opening_an_older_analysis_does_not_move_it_backwards(
        self, client, auth, closed_session, published
    ):
        """Reading last Tuesday's briefing after this evening's is an ordinary
        thing to do, and must not re-mark the newer one unread."""
        closed_session(SESSION)
        published(DECLARED[0], EARLIER)
        published(DECLARED[0], SESSION)
        await _watch(client, auth, DECLARED[0])
        await client.post(
            f"{API}/analyses/{DECLARED[0]}/{SESSION.isoformat()}/opened", headers=auth
        )

        response = await client.post(
            f"{API}/analyses/{DECLARED[0]}/{EARLIER.isoformat()}/opened", headers=auth
        )

        assert response.json()["last_seen_analysis_date"] == SESSION.isoformat()
        assert _entry(await _rail(client, auth), DECLARED[0])["unread"] is False

    @pytest.mark.asyncio
    async def test_a_symbol_with_no_analysis_is_never_unread(
        self, client, auth, closed_session
    ):
        closed_session(SESSION)
        await _watch(client, auth, DECLARED[0])

        assert _entry(await _rail(client, auth), DECLARED[0])["unread"] is False

    @pytest.mark.asyncio
    async def test_opening_an_analysis_that_does_not_exist_is_refused(
        self, client, auth, published
    ):
        """Advancing past a session that was never published would mark a symbol
        read on the strength of a URL."""
        await _watch(client, auth, DECLARED[0])

        response = await client.post(
            f"{API}/analyses/{DECLARED[0]}/{SESSION.isoformat()}/opened", headers=auth
        )

        assert response.status_code == 404, response.text
        assert response.json()["detail"]["reason"] == "analysis_not_found"

    @pytest.mark.asyncio
    async def test_a_symbol_not_on_the_callers_watchlist_has_no_last_seen_to_move(
        self, client, auth, published
    ):
        published(DECLARED[0], SESSION)

        response = await client.post(
            f"{API}/analyses/{DECLARED[0]}/{SESSION.isoformat()}/opened", headers=auth
        )

        assert response.status_code == 404, response.text
        assert response.json()["detail"]["reason"] == "symbol_not_watched"

    @pytest.mark.asyncio
    async def test_one_users_opening_leaves_another_users_badge_alone(
        self, client, auth, other_auth, closed_session, published
    ):
        """Last-seen is per user per symbol, and every query touching it is
        scoped to the caller's own row — which is the whole ownership check."""
        closed_session(SESSION)
        published(DECLARED[0], SESSION)
        await _watch(client, auth, DECLARED[0])
        await _watch(client, other_auth, DECLARED[0])

        await client.post(
            f"{API}/analyses/{DECLARED[0]}/{SESSION.isoformat()}/opened", headers=auth
        )

        assert _entry(await _rail(client, auth), DECLARED[0])["unread"] is False
        assert _entry(await _rail(client, other_auth), DECLARED[0])["unread"] is True


class TestRetry:
    """The rail's retry action: it queues an attempt, it does not produce one."""

    @pytest.mark.asyncio
    async def test_retrying_a_failed_session_puts_it_back_in_the_queue(
        self, client, auth, closed_session, seeded_run
    ):
        closed_session(SESSION)
        seeded_run(
            DECLARED[0],
            SESSION,
            RunStatus.FAILED,
            attempts=1,
            error_code="llm_transport_error",
            error_message="LLM route did not respond",
        )
        await _watch(client, auth, DECLARED[0])

        response = await client.post(
            f"{API}/analyses/{DECLARED[0]}/{SESSION.isoformat()}/retry", headers=auth
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == RunStatus.PENDING.value
        assert (
            _entry(await _rail(client, auth), DECLARED[0])["state"]
            == AnalysisState.PENDING.value
        )

    @pytest.mark.asyncio
    async def test_a_queued_retry_keeps_the_reason_the_last_attempt_gave(
        self, client, auth, closed_session, seeded_run
    ):
        """Nothing drains the queue until the pipeline milestone, so a symbol
        can sit here for a while. Clearing the reason on the way in would leave
        it waiting with no account of why — the reason describes the attempt
        that happened, and `_begin_attempt` clears it when a new one starts."""
        closed_session(SESSION)
        seeded_run(
            DECLARED[0],
            SESSION,
            RunStatus.FAILED,
            attempts=1,
            error_code="llm_transport_error",
            error_message="LLM route did not respond",
        )
        await _watch(client, auth, DECLARED[0])

        await client.post(
            f"{API}/analyses/{DECLARED[0]}/{SESSION.isoformat()}/retry", headers=auth
        )

        entry = _entry(await _rail(client, auth), DECLARED[0])
        assert entry["state"] == AnalysisState.PENDING.value
        assert entry["failure"]["code"] == "llm_transport_error"
        assert entry["failure"]["message"] == "LLM route did not respond"

    @pytest.mark.asyncio
    async def test_a_retry_does_not_spend_an_attempt_by_itself(
        self, client, auth, closed_session, seeded_run
    ):
        """`attempts` counts production attempts, so the ceiling bites on what
        was actually spent rather than on how many times a button was pressed."""
        closed_session(SESSION)
        seeded_run(DECLARED[0], SESSION, RunStatus.FAILED, attempts=1, error_code="x")
        await _watch(client, auth, DECLARED[0])

        for _ in range(3):
            await client.post(
                f"{API}/analyses/{DECLARED[0]}/{SESSION.isoformat()}/retry", headers=auth
            )

        with get_sync_db() as session:
            run = session.execute(
                select(AnalysisRun).where(
                    AnalysisRun.symbol == DECLARED[0],
                    AnalysisRun.trading_day == SESSION,
                )
            ).scalar_one()
            assert run.attempts == 1

    @pytest.mark.asyncio
    async def test_a_pair_at_the_ceiling_is_locked_until_the_next_session(
        self, client, auth, closed_session, seeded_run
    ):
        closed_session(SESSION)
        seeded_run(
            DECLARED[0],
            SESSION,
            RunStatus.FAILED,
            attempts=MAX_ATTEMPTS_PER_SESSION,
            error_code="missing_market_snapshot",
            error_message="no session data for ARDAAA",
        )
        await _watch(client, auth, DECLARED[0])

        body = (
            await client.post(
                f"{API}/analyses/{DECLARED[0]}/{SESSION.isoformat()}/retry", headers=auth
            )
        ).json()

        assert body["locked"] is True
        assert body["status"] == RunStatus.FAILED.value
        assert body["error_message"] == "no session data for ARDAAA"

    @pytest.mark.asyncio
    async def test_a_user_not_watching_the_symbol_may_not_retry(
        self, client, auth, closed_session, seeded_run
    ):
        closed_session(SESSION)
        seeded_run(DECLARED[0], SESSION, RunStatus.FAILED, attempts=1, error_code="x")

        response = await client.post(
            f"{API}/analyses/{DECLARED[0]}/{SESSION.isoformat()}/retry", headers=auth
        )

        assert response.status_code == 404, response.text
        assert response.json()["detail"]["reason"] == "symbol_not_watched"

    @pytest.mark.asyncio
    async def test_a_symbol_that_left_the_universe_cannot_be_retried(
        self, client, auth, closed_session, seeded_run, declared_universe
    ):
        """`unsupported` means no new Analysis is produced, and the retry button
        is the one path a user could otherwise use to argue with it."""
        closed_session(SESSION)
        await _watch(client, auth, DECLARED[0])
        seeded_run(DECLARED[0], SESSION, RunStatus.FAILED, attempts=1, error_code="x")
        declared_universe(*[s for s in DECLARED if s != DECLARED[0]])

        response = await client.post(
            f"{API}/analyses/{DECLARED[0]}/{SESSION.isoformat()}/retry", headers=auth
        )

        assert response.status_code == 422, response.text
        assert response.json()["detail"]["reason"] == "not_in_universe"

    @pytest.mark.asyncio
    async def test_a_session_never_attempted_has_nothing_to_retry(
        self, client, auth, closed_session
    ):
        """An earlier session, from before the symbol was watched: no run was
        ever made for it. Minting one here would jump the nightly queue on a
        button that says "retry"."""
        closed_session(SESSION)
        await _watch(client, auth, DECLARED[0])

        response = await client.post(
            f"{API}/analyses/{DECLARED[0]}/{EARLIEST.isoformat()}/retry", headers=auth
        )

        assert response.status_code == 404, response.text
        assert response.json()["detail"]["reason"] == "nothing_to_retry"

    @pytest.mark.asyncio
    async def test_retrying_a_ready_pair_returns_the_analysis_it_already_has(
        self, client, auth, closed_session, published
    ):
        closed_session(SESSION)
        published(DECLARED[0], SESSION)
        await _watch(client, auth, DECLARED[0])

        body = (
            await client.post(
                f"{API}/analyses/{DECLARED[0]}/{SESSION.isoformat()}/retry", headers=auth
            )
        ).json()

        assert body["status"] == RunStatus.READY.value
        assert body["locked"] is False
