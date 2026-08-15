"""What a user may put on their Watchlist, and what removing one means.

Integration tests against a live database, for the same reason the auth tests
are: the cap, the Universe restriction and the "removing deletes nothing"
promise are all statements about rows, and a fake store would let all three pass
while the real one refused.

Requires DATABASE_URL to point at a database migrated to head
(`docker compose up -d db && alembic upgrade head`).

Driven through an ASGI transport rather than TestClient: the async engine's pool
binds to whichever event loop first used it, and TestClient opens a fresh loop
per request, which strands pooled connections after the first call.
"""

import uuid
from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from src.alpha.models import (
    AgentMessage,
    AgentThread,
    Analysis,
    WatchlistEntry,
)
from src.alpha.watchlist import WATCHLIST_MAX_SYMBOLS
from src.auth.models import RefreshToken, User
from src.core.config import get_settings
from src.core.database import Base, engine, get_sync_db, sync_engine
from src.main import app
from src.stocks.universe import forget_cohort_cache

API = "/api/v1"

# Twelve declared symbols, so the ten-symbol cap can be reached with two to
# spare and "outside the Universe" can be a symbol that really is outside it.
DECLARED = ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH", "III", "JJJ", "KKK", "LLL")
OUTSIDE = "ZZZ"

TRADING_DAY = date(2026, 8, 14)


@pytest.fixture(scope="module", autouse=True)
def alpha_schema():
    """Make sure the tables this file reads exist, whatever shaped the database.

    Restricted to the Alpha Desk tables: this file has no business creating the
    market store, and `checkfirst` keeps it a no-op on a migrated database.
    """
    Base.metadata.create_all(
        sync_engine,
        tables=[
            AgentThread.__table__,
            AgentMessage.__table__,
            Analysis.__table__,
            WatchlistEntry.__table__,
        ],
        checkfirst=True,
    )


@pytest.fixture(autouse=True)
def declared_universe(monkeypatch):
    """Declare a Universe the way an operator does, through the environment.

    Yields the declaration itself, so a test can trim the Universe mid-flight —
    which is one of the two ways a watched symbol becomes `unsupported`, and the
    only one an operator can cause on purpose.

    The settings are cached for the life of the process and the cohort half is
    memoized per version, so both are cleared on every declaration and again on
    the way out; leaving a test's Universe behind would silently reconfigure
    every test after it.
    """

    def declare(*symbols: str) -> None:
        monkeypatch.setenv("UNIVERSE_SYMBOLS", ",".join(symbols))
        get_settings.cache_clear()
        forget_cohort_cache()

    declare(*DECLARED)
    yield declare
    monkeypatch.undo()
    get_settings.cache_clear()
    forget_cohort_cache()


@pytest_asyncio.fixture
async def client():
    """ASGI client sharing the test's event loop."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    await engine.dispose()


@pytest.fixture
def account():
    """An account, with every row it touches deleted afterwards."""
    email = f"watchlist-{uuid.uuid4().hex[:12]}@example.com"
    yield {"email": email, "password": "sup3r-secret-pw"}

    with get_sync_db() as session:
        user = session.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()
        if user is not None:
            session.execute(delete(WatchlistEntry).where(WatchlistEntry.user_id == user.id))
            threads = session.execute(
                select(AgentThread.id).where(AgentThread.user_id == user.id)
            ).scalars().all()
            if threads:
                session.execute(delete(AgentMessage).where(AgentMessage.thread_id.in_(threads)))
                session.execute(delete(AgentThread).where(AgentThread.id.in_(threads)))
            session.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
            session.execute(delete(User).where(User.id == user.id))


@pytest.fixture
def stored_analysis():
    """An Analysis that exists before the test and must survive it."""
    created: list[tuple[str, date]] = []

    def store(symbol: str, trading_day: date = TRADING_DAY) -> None:
        with get_sync_db() as session:
            session.add(
                Analysis(
                    symbol=symbol,
                    trading_day=trading_day,
                    verdict="hold",
                    payload={"thesis": "stored before the test"},
                    schema_version=1,
                )
            )
        created.append((symbol, trading_day))

    yield store

    with get_sync_db() as session:
        for symbol, trading_day in created:
            session.execute(
                delete(Analysis).where(
                    Analysis.symbol == symbol,
                    Analysis.trading_day == trading_day,
                )
            )


async def _authenticate(client: AsyncClient, account: dict) -> dict:
    response = await client.post(f"{API}/auth/register", json=account)
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest_asyncio.fixture
async def auth(client, account):
    return await _authenticate(client, account)


def _symbols(body: dict) -> list[str]:
    return [entry["symbol"] for entry in body["entries"]]


def _state(body: dict, symbol: str) -> str:
    return next(entry["state"] for entry in body["entries"] if entry["symbol"] == symbol)


class TestListing:
    """GET /watchlist."""

    @pytest.mark.asyncio
    async def test_a_new_users_watchlist_is_empty(self, client, auth):
        """Nothing is seeded. Every seeded symbol would be an Analysis produced
        that night for a holding nobody chose."""
        response = await client.get(f"{API}/watchlist", headers=auth)

        assert response.status_code == 200, response.text
        assert response.json()["entries"] == []
        assert response.json()["count"] == 0

    @pytest.mark.asyncio
    async def test_the_count_is_there_from_the_first_symbol(self, client, auth):
        """The cap is shown permanently, not sprung on the eleventh add."""
        body = (await client.get(f"{API}/watchlist", headers=auth)).json()
        assert body["cap"] == WATCHLIST_MAX_SYMBOLS
        assert body["count"] == 0

        await client.post(f"{API}/watchlist", json={"symbol": "AAA"}, headers=auth)

        body = (await client.get(f"{API}/watchlist", headers=auth)).json()
        assert body["count"] == 1
        assert body["cap"] == WATCHLIST_MAX_SYMBOLS

    @pytest.mark.asyncio
    async def test_requires_authentication(self, client):
        assert (await client.get(f"{API}/watchlist")).status_code == 401


class TestAdding:
    """POST /watchlist."""

    @pytest.mark.asyncio
    async def test_adds_a_universe_symbol(self, client, auth):
        response = await client.post(
            f"{API}/watchlist", json={"symbol": "AAA"}, headers=auth
        )

        assert response.status_code == 201, response.text
        assert _symbols(response.json()) == ["AAA"]
        assert response.json()["count"] == 1

    @pytest.mark.asyncio
    async def test_normalizes_the_symbol(self, client, auth):
        response = await client.post(
            f"{API}/watchlist", json={"symbol": " aaa "}, headers=auth
        )

        assert response.status_code == 201, response.text
        assert _symbols(response.json()) == ["AAA"]

    @pytest.mark.asyncio
    async def test_refuses_a_symbol_outside_the_universe_and_names_the_reason(
        self, client, auth
    ):
        response = await client.post(
            f"{API}/watchlist", json={"symbol": OUTSIDE}, headers=auth
        )

        assert response.status_code == 422, response.text
        assert response.json()["detail"]["reason"] == "symbol_not_in_universe"

    @pytest.mark.asyncio
    async def test_refuses_a_malformed_symbol_the_same_way(self, client, auth):
        """A symbol that could not be in any Universe is refused by the same
        rule, not by a validation error escaping as an upstream failure."""
        response = await client.post(
            f"{API}/watchlist", json={"symbol": "not a symbol!"}, headers=auth
        )

        assert response.status_code == 422, response.text
        assert response.json()["detail"]["reason"] == "symbol_not_in_universe"

    @pytest.mark.asyncio
    async def test_refuses_the_eleventh_symbol_with_a_stable_reason(self, client, auth):
        for symbol in DECLARED[:WATCHLIST_MAX_SYMBOLS]:
            accepted = await client.post(
                f"{API}/watchlist", json={"symbol": symbol}, headers=auth
            )
            assert accepted.status_code == 201, accepted.text

        response = await client.post(
            f"{API}/watchlist",
            json={"symbol": DECLARED[WATCHLIST_MAX_SYMBOLS]},
            headers=auth,
        )

        assert response.status_code == 409, response.text
        assert response.json()["detail"]["reason"] == "watchlist_full"

    @pytest.mark.asyncio
    async def test_adding_a_symbol_already_watched_is_a_no_op(self, client, auth):
        """Not an error: the request describes a state the Watchlist is already
        in, and refusing it would make a retried add look like a lost slot."""
        await client.post(f"{API}/watchlist", json={"symbol": "AAA"}, headers=auth)

        response = await client.post(
            f"{API}/watchlist", json={"symbol": "AAA"}, headers=auth
        )

        assert response.status_code == 201, response.text
        assert _symbols(response.json()) == ["AAA"]
        assert response.json()["count"] == 1


class TestRemoving:
    """DELETE /watchlist/{symbol}."""

    @pytest.mark.asyncio
    async def test_removes_the_entry_and_frees_the_slot(self, client, auth):
        await client.post(f"{API}/watchlist", json={"symbol": "AAA"}, headers=auth)

        response = await client.delete(f"{API}/watchlist/AAA", headers=auth)

        assert response.status_code == 200, response.text
        assert response.json()["entries"] == []
        assert response.json()["count"] == 0

    @pytest.mark.asyncio
    async def test_removing_a_symbol_not_watched_is_a_404(self, client, auth):
        response = await client.delete(f"{API}/watchlist/AAA", headers=auth)

        assert response.status_code == 404, response.text

    @pytest.mark.asyncio
    async def test_removing_deletes_no_analysis_and_no_thread(
        self, client, auth, stored_analysis
    ):
        """Removal is a statement about what keeps being analysed, not about
        history: old Threads and links stay alive and past Analyses stay
        readable."""
        stored_analysis("AAA")
        await client.post(f"{API}/watchlist", json={"symbol": "AAA"}, headers=auth)

        with get_sync_db() as session:
            user_id = session.execute(
                select(WatchlistEntry.user_id).where(WatchlistEntry.symbol == "AAA")
            ).scalars().first()
            thread_id = uuid.uuid4()
            session.add(
                AgentThread(id=thread_id, user_id=user_id, title="AAA", symbols=["AAA"])
            )
            session.flush()
            session.add(
                AgentMessage(
                    thread_id=thread_id, seq=1, role="user", content={"text": "AAA?"}
                )
            )

        await client.delete(f"{API}/watchlist/AAA", headers=auth)

        with get_sync_db() as session:
            analysis = session.execute(
                select(Analysis).where(
                    Analysis.symbol == "AAA", Analysis.trading_day == TRADING_DAY
                )
            ).scalar_one()
            assert analysis.verdict == "hold"
            assert session.execute(
                select(AgentThread).where(AgentThread.id == thread_id)
            ).scalar_one() is not None
            assert session.execute(
                select(AgentMessage).where(AgentMessage.thread_id == thread_id)
            ).scalar_one() is not None

    @pytest.mark.asyncio
    async def test_a_freed_slot_is_reusable_the_same_day_with_no_rate_limit(
        self, client, auth, stored_analysis
    ):
        """An Analysis is keyed by `(symbol, trading_day)` and shared
        system-wide, so re-adding re-reads the existing one at zero cost. No
        mutation rate limit stands between the two calls, and no second Analysis
        appears."""
        stored_analysis("AAA")
        with get_sync_db() as session:
            before = session.execute(
                select(Analysis.id).where(
                    Analysis.symbol == "AAA", Analysis.trading_day == TRADING_DAY
                )
            ).scalar_one()

        await client.post(f"{API}/watchlist", json={"symbol": "AAA"}, headers=auth)
        for _ in range(5):
            assert (
                await client.delete(f"{API}/watchlist/AAA", headers=auth)
            ).status_code == 200
            readded = await client.post(
                f"{API}/watchlist", json={"symbol": "AAA"}, headers=auth
            )
            assert readded.status_code == 201, readded.text

        with get_sync_db() as session:
            rows = session.execute(
                select(Analysis.id).where(
                    Analysis.symbol == "AAA", Analysis.trading_day == TRADING_DAY
                )
            ).scalars().all()
        assert rows == [before]


class TestUnsupported:
    """A watched symbol that has left the Universe.

    One state covers both a real delisting and an operator trimming the
    configured Universe, because v1 cannot tell them apart and does not pretend
    to. The symbol stays, its history stays readable, nothing new is produced
    for it, and it costs the user no slot.

    Auto-removal was rejected and these tests are where that stays rejected: it
    destroys a user's choice because of an operator's config change, turning a
    reversible change into data loss.
    """

    @pytest.mark.asyncio
    async def test_a_symbol_leaving_the_universe_stays_on_the_list(
        self, client, auth, declared_universe
    ):
        await client.post(f"{API}/watchlist", json={"symbol": "AAA"}, headers=auth)

        declared_universe(*[s for s in DECLARED if s != "AAA"])

        body = (await client.get(f"{API}/watchlist", headers=auth)).json()
        assert _symbols(body) == ["AAA"]
        assert _state(body, "AAA") == "unsupported"

    @pytest.mark.asyncio
    async def test_its_stored_analyses_stay_readable(
        self, client, auth, declared_universe, stored_analysis
    ):
        stored_analysis("AAA")
        await client.post(f"{API}/watchlist", json={"symbol": "AAA"}, headers=auth)

        declared_universe(*[s for s in DECLARED if s != "AAA"])
        await client.get(f"{API}/watchlist", headers=auth)

        with get_sync_db() as session:
            stored = session.execute(
                select(Analysis).where(
                    Analysis.symbol == "AAA", Analysis.trading_day == TRADING_DAY
                )
            ).scalar_one()
        assert stored.verdict == "hold"

    @pytest.mark.asyncio
    async def test_nothing_removes_it_automatically(
        self, client, auth, declared_universe
    ):
        """Reading the rail is not an opportunity to tidy up. A dozen polls must
        leave the row exactly where the user put it."""
        await client.post(f"{API}/watchlist", json={"symbol": "AAA"}, headers=auth)
        declared_universe(*[s for s in DECLARED if s != "AAA"])

        for _ in range(12):
            await client.get(f"{API}/watchlist", headers=auth)

        with get_sync_db() as session:
            assert session.execute(
                select(WatchlistEntry).where(WatchlistEntry.symbol == "AAA")
            ).scalar_one() is not None

    @pytest.mark.asyncio
    async def test_it_can_still_be_removed_deliberately(
        self, client, auth, declared_universe
    ):
        """The remove button is the whole point of keeping the row: the user
        clears it, not the system."""
        await client.post(f"{API}/watchlist", json={"symbol": "AAA"}, headers=auth)
        declared_universe(*[s for s in DECLARED if s != "AAA"])

        response = await client.delete(f"{API}/watchlist/AAA", headers=auth)

        assert response.status_code == 200, response.text
        assert response.json()["entries"] == []

    @pytest.mark.asyncio
    async def test_it_does_not_consume_a_slot(self, client, auth, declared_universe):
        """The cap counts active entries only, so trimming the Universe hands
        the user back a slot they did not ask to lose."""
        for symbol in DECLARED[:WATCHLIST_MAX_SYMBOLS]:
            await client.post(f"{API}/watchlist", json={"symbol": symbol}, headers=auth)

        declared_universe(*[s for s in DECLARED if s != "AAA"])

        body = (await client.get(f"{API}/watchlist", headers=auth)).json()
        assert body["count"] == WATCHLIST_MAX_SYMBOLS - 1
        assert len(body["entries"]) == WATCHLIST_MAX_SYMBOLS

        added = await client.post(
            f"{API}/watchlist",
            json={"symbol": DECLARED[WATCHLIST_MAX_SYMBOLS]},
            headers=auth,
        )
        assert added.status_code == 201, added.text
        assert added.json()["count"] == WATCHLIST_MAX_SYMBOLS

    @pytest.mark.asyncio
    async def test_a_symbol_returning_to_the_universe_revives_by_itself(
        self, client, auth, declared_universe
    ):
        await client.post(f"{API}/watchlist", json={"symbol": "AAA"}, headers=auth)
        declared_universe(*[s for s in DECLARED if s != "AAA"])
        assert (
            _state((await client.get(f"{API}/watchlist", headers=auth)).json(), "AAA")
            == "unsupported"
        )

        declared_universe(*DECLARED)

        body = (await client.get(f"{API}/watchlist", headers=auth)).json()
        assert _state(body, "AAA") == "active"
        assert body["count"] == 1

    @pytest.mark.asyncio
    async def test_a_revival_over_the_cap_stands_and_evicts_nobody(
        self, client, auth, declared_universe
    ):
        """The system never picks which symbol to evict. The overflow stands and
        adding is what gets blocked, until the user trims."""
        trimmed = [s for s in DECLARED if s != "AAA"]
        await client.post(f"{API}/watchlist", json={"symbol": "AAA"}, headers=auth)
        declared_universe(*trimmed)
        for symbol in trimmed[:WATCHLIST_MAX_SYMBOLS]:
            accepted = await client.post(
                f"{API}/watchlist", json={"symbol": symbol}, headers=auth
            )
            assert accepted.status_code == 201, accepted.text

        declared_universe(*DECLARED)

        body = (await client.get(f"{API}/watchlist", headers=auth)).json()
        assert body["count"] == WATCHLIST_MAX_SYMBOLS + 1
        assert len(body["entries"]) == WATCHLIST_MAX_SYMBOLS + 1
        assert all(entry["state"] == "active" for entry in body["entries"])

        refused = await client.post(
            f"{API}/watchlist",
            json={"symbol": trimmed[WATCHLIST_MAX_SYMBOLS]},
            headers=auth,
        )
        assert refused.status_code == 409, refused.text
        assert refused.json()["detail"]["reason"] == "watchlist_full"

        after = (await client.get(f"{API}/watchlist", headers=auth)).json()
        assert len(after["entries"]) == WATCHLIST_MAX_SYMBOLS + 1

    @pytest.mark.asyncio
    async def test_an_unsupported_symbol_cannot_be_added_again(
        self, client, auth, declared_universe
    ):
        """Adding is still Universe-restricted, so re-adding a symbol the
        Universe has dropped is refused with the reason named — not silently
        accepted into a state that produces nothing."""
        declared_universe(*[s for s in DECLARED if s != "AAA"])

        response = await client.post(
            f"{API}/watchlist", json={"symbol": "AAA"}, headers=auth
        )

        assert response.status_code == 422, response.text
        assert response.json()["detail"]["reason"] == "symbol_not_in_universe"
