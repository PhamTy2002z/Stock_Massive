"""The three endpoints, against a live database and the real app (#85).

Integration rather than unit, for the reason the Watchlist tests give: owner
scoping, the idempotency key and "another user's Turn is never reachable" are
statements about rows and about the join that reads them, and a fake store would
let all three pass while the real one refused.

The model is the only thing stubbed. The loop is scripted so a test can hold a
Turn open, publish into it, and end it on command — none of which a real
provider would let it do.

Requires DATABASE_URL to point at a migrated database
(`docker compose up -d db && alembic upgrade head`).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date, datetime, timezone
from types import MappingProxyType

import pytest
import pytest_asyncio
from fastapi.dependencies.utils import get_dependant
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from src.agent.events import EventType
from src.agent.limits import SubscriptionLimiter, SubscriptionThrottled
from src.agent.loop import (
    SessionSlots,
    ToolCallStatus,
    TurnAdmission,
    TurnOutcome,
    TurnStatus,
    TurnToolCall,
)
from src.agent.persistence import AgentPersistence
from src.agent.router import (
    desk as desk_dependency,
    history_of,
    router as alpha_desk_router,
    streaming_user_id,
    turn_events,
)
from src.agent.service import AlphaDeskService
from src.agent.turns import TurnService
from src.alpha.models import (
    AgentMessage,
    AgentThread,
    AgentToolCall,
    AgentTurn,
    LlmCallUsage,
)
from src.auth.models import RefreshToken, User
from src.core.database import Base, engine, get_db, get_sync_db, sync_engine
from src.core.llm import (
    BudgetLanes,
    BudgetRefusal,
    LLMConfig,
    LLMRoute,
    PricingTable,
    TokenPrices,
    Usage,
    Workload,
)
from src.core.ratelimit import heavy_rate_limit, standard_rate_limit
from src.main import app

API = "/api/v1"


# -- the world the endpoints run in ---------------------------------------


def llm_config(*, enabled: bool = True) -> LLMConfig:
    return LLMConfig(
        enabled=enabled,
        route=LLMRoute(base_url="https://llm.example/v1", api_key="secret"),
        models=MappingProxyType(
            {Workload.BATCH: "batch-model", Workload.SESSION: "session-model"}
        ),
        pricing=PricingTable(
            version="2026-08",
            effective_from=date(2026, 8, 1),
            batch=TokenPrices(input=0.5, cached_input=0.1, cache_write=0.5, output=1.0),
            session=TokenPrices(input=2.0, cached_input=0.2, cache_write=2.0, output=5.0),
        ),
        lanes=BudgetLanes(
            monthly_envelope_usd=50,
            analysis_usd=10,
            turn_usd=30,
            emergency_usd=5,
            eval_usd=5,
        ),
    )


class ScriptedLoop:
    """A Turn the test drives, one step at a time.

    Stands in for :class:`AgentLoop` at the seam :class:`TurnService` already
    has — a factory that is handed a checkpoint and a publisher — so nothing in
    the lifecycle or the transport is bypassed to make a test possible.
    """

    def __init__(self, control: "Control", *, checkpoint, publisher) -> None:
        self._control = control
        self._checkpoint = checkpoint
        self._publisher = publisher

    async def run(self, request, cancelled) -> TurnOutcome:
        self._control.started.set()
        for call in self._control.calls:
            self._publisher.tool_call(call.as_wire())
        for index, piece in enumerate(self._control.pieces):
            # The separator travels inside the delta, exactly as the real loop
            # sends it, so the answer is the concatenation of what was streamed.
            self._publisher.content_delta(piece if index == 0 else f"\n\n{piece}")
        await self._control.release.wait()
        status = TurnStatus.CANCELLED if cancelled() else self._control.status
        return TurnOutcome(
            status=status,
            terminal_reason=(
                "cancelled_by_user"
                if status is TurnStatus.CANCELLED
                else self._control.terminal_reason
            ),
            text=self._control.text or None,
            rounds_used=0,
            rounds_exhausted=False,
            tool_calls=tuple(self._control.calls),
            usage=Usage(),
        )


class Control:
    """What the test says the Turn should do."""

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.pieces: list[str] = []
        self.calls: list[TurnToolCall] = []
        self.status = TurnStatus.COMPLETE
        self.terminal_reason: str | None = None

    @property
    def text(self) -> str:
        return "\n\n".join(self.pieces)

    def finish(self) -> None:
        self.release.set()

    def says(self, *texts: str) -> None:
        self.pieces = list(texts)

    def calls_a_tool(self, name: str = "web_search") -> None:
        self.calls = [
            TurnToolCall(
                id="call_0",
                name=name,
                status=ToolCallStatus.OK,
                summary=f"Tìm trên web: {name}",
            )
        ]


class OpenLedger:
    """A ledger that admits everything, unless a test says otherwise."""

    def __init__(self) -> None:
        self.refusal: BudgetRefusal | None = None
        self.checked: list[int] = []

    def preflight_turn(self, user_id: int, *, output_tokens: int) -> None:
        self.checked.append(user_id)
        if self.refusal is not None:
            raise self.refusal


class Desk:
    """The service under test, plus the handles a test needs on it."""

    def __init__(self, *, enabled: bool = True) -> None:
        self.control = Control()
        self.ledger = OpenLedger()
        self.slots = SessionSlots()
        store = AgentPersistence()

        def loop_factory(*, checkpoint, publisher):
            return ScriptedLoop(self.control, checkpoint=checkpoint, publisher=publisher)

        self.service = AlphaDeskService(
            turns=TurnService(
                store=store,
                loop_factory=loop_factory,
                config=llm_config(enabled=enabled),
            ),
            admission=TurnAdmission(self.ledger, slots=self.slots),
            subscriptions=SubscriptionLimiter(per_user=1000, per_turn=1000, window=60),
            store=store,
            config=llm_config(enabled=enabled),
            client=None,
        )


@pytest.fixture(scope="module", autouse=True)
def alpha_schema():
    Base.metadata.create_all(
        sync_engine,
        tables=[
            AgentThread.__table__,
            AgentMessage.__table__,
            AgentToolCall.__table__,
            AgentTurn.__table__,
            LlmCallUsage.__table__,
        ],
        checkfirst=True,
    )


@pytest_asyncio.fixture
async def desk():
    """Install the service the endpoints read, then drain it.

    The drain is not tidiness. A Turn outlives the request that started it by
    design, so a test that ends while one is still running would have its rows
    deleted underneath a live task — and the failure would surface in whichever
    test ran next.
    """
    built = Desk()
    app.dependency_overrides[desk_dependency] = lambda: built.service
    yield built
    app.dependency_overrides.pop(desk_dependency, None)
    built.control.finish()
    await built.service.turns.shutdown(timeout=5)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    await engine.dispose()


@pytest_asyncio.fixture
async def live_client():
    """A real socket, because ASGI-in-process cannot prove streaming.

    ``httpx.ASGITransport`` runs the application to completion and *then*
    answers, so an open-ended stream over it does not arrive late — it never
    arrives at all. Everything this file asserts about ordering, about a
    subscriber leaving, and about the response starting before the Turn ends is
    a claim about bytes on a socket, so the tests that make it use one.

    Started with ``lifespan="off"``: the application's own startup runs a
    Universe check, Budget Validation and the interrupted-Turn sweep, none of
    which this file is about, and the sweep in particular would freeze Turns
    belonging to whatever else is using the database.
    """
    import uvicorn

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=0,
            lifespan="off",
            log_level="warning",
            timeout_graceful_shutdown=1,
        )
    )
    serving = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.01)
    port = server.servers[0].sockets[0].getsockname()[1]
    async with AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=10) as ac:
        yield ac
    server.should_exit = True
    await serving


@pytest.fixture
def account():
    email = f"transport-{uuid.uuid4().hex[:12]}@example.com"
    yield {"email": email, "password": "sup3r-secret-pw"}
    _purge(email)


@pytest.fixture
def other_account():
    email = f"stranger-{uuid.uuid4().hex[:12]}@example.com"
    yield {"email": email, "password": "sup3r-secret-pw"}
    _purge(email)


def _purge(email: str) -> None:
    with get_sync_db() as session:
        user = session.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()
        if user is None:
            return
        threads = (
            session.execute(select(AgentThread.id).where(AgentThread.user_id == user.id))
            .scalars()
            .all()
        )
        if threads:
            session.execute(delete(AgentTurn).where(AgentTurn.thread_id.in_(threads)))
            session.execute(
                delete(AgentToolCall).where(AgentToolCall.thread_id.in_(threads))
            )
            session.execute(delete(AgentMessage).where(AgentMessage.thread_id.in_(threads)))
            session.execute(delete(AgentThread).where(AgentThread.id.in_(threads)))
        session.execute(delete(LlmCallUsage).where(LlmCallUsage.user_id == user.id))
        session.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
        session.execute(delete(User).where(User.id == user.id))


async def authenticate(client: AsyncClient, account: dict) -> dict:
    response = await client.post(f"{API}/auth/register", json=account)
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest_asyncio.fixture
async def auth(client, account):
    return await authenticate(client, account)


async def open_thread(client: AsyncClient, auth: dict) -> str:
    response = await client.post(f"{API}/threads", json={"title": None}, headers=auth)
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def start_turn(
    client: AsyncClient,
    auth: dict,
    thread_id: str,
    *,
    turn_id: str | None = None,
    text: str = "VCB thế nào?",
    **extra,
):
    return await client.post(
        f"{API}/threads/{thread_id}/turns",
        json={"turn_id": turn_id or str(uuid.uuid4()), "text": text, **extra},
        headers=auth,
    )


def sse_events(body: str) -> list[dict]:
    """Every envelope in a finished SSE body, comments excluded."""
    parsed: list[dict] = []
    for frame in body.split("\n\n"):
        for line in frame.split("\n"):
            if line.startswith("data: "):
                parsed.append(json.loads(line[len("data: ") :]))
    return parsed


def sse_ids(body: str) -> list[str]:
    return [
        line[len("id: ") :]
        for line in body.split("\n")
        if line.startswith("id: ")
    ]


# -- admission -------------------------------------------------------------


class TestAdmission:
    pytestmark = pytest.mark.asyncio

    async def test_a_turn_is_created_and_the_client_chosen_id_is_what_comes_back(
        self, client, auth, desk
    ):
        thread_id = await open_thread(client, auth)
        turn_id = str(uuid.uuid4())

        response = await start_turn(client, auth, thread_id, turn_id=turn_id)

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["id"] == turn_id
        assert body["created"] is True
        assert body["thread_id"] == thread_id
        await asyncio.wait_for(desk.control.started.wait(), 2)
        desk.control.finish()

    async def test_an_exhausted_user_allowance_is_429_with_its_stable_reason(
        self, client, auth, desk
    ):
        thread_id = await open_thread(client, auth)
        desk.ledger.refusal = BudgetRefusal(
            "user_turn_starts_daily",
            "Your daily Turn allowance has been exhausted.",
            reset_at=datetime(2026, 8, 16, tzinfo=timezone.utc),
        )

        response = await start_turn(client, auth, thread_id)

        assert response.status_code == 429
        assert response.json()["detail"]["reason"] == "user_turn_starts_daily"

    async def test_an_exhausted_service_budget_is_503(self, client, auth, desk):
        thread_id = await open_thread(client, auth)
        desk.ledger.refusal = BudgetRefusal(
            "lane_budget_exhausted",
            "This service lane is unavailable until its allowance resets.",
        )

        response = await start_turn(client, auth, thread_id)

        assert response.status_code == 503
        assert response.json()["detail"]["reason"] == "lane_budget_exhausted"

    async def test_an_admission_failure_leaves_no_turn_and_opens_no_stream(
        self, client, auth, desk
    ):
        thread_id = await open_thread(client, auth)
        turn_id = str(uuid.uuid4())
        desk.ledger.refusal = BudgetRefusal(
            "system_active_turns",
            "The service is at its active Turn capacity.",
            state="capacity_exhausted",
        )

        refused = await start_turn(client, auth, thread_id, turn_id=turn_id)
        stream = await client.get(f"{API}/turns/{turn_id}/events", headers=auth)

        assert refused.status_code == 503
        # No row, so no stream: the refusal is the whole of the answer.
        assert stream.status_code == 404
        with get_sync_db() as session:
            assert session.get(AgentTurn, uuid.UUID(turn_id)) is None

    async def test_a_full_semaphore_refuses_before_any_ledger_question(
        self, client, auth, desk
    ):
        thread_id = await open_thread(client, auth)

        async with desk.slots.occupy():
            async with desk.slots.occupy():
                async with desk.slots.occupy():
                    response = await start_turn(client, auth, thread_id)

        assert response.status_code == 503
        assert response.json()["detail"]["reason"] == "system_active_turns"
        assert desk.ledger.checked == []


class TestIdempotency:
    pytestmark = pytest.mark.asyncio

    async def test_the_same_id_and_payload_returns_the_turn_that_exists(
        self, client, auth, desk
    ):
        thread_id = await open_thread(client, auth)
        turn_id = str(uuid.uuid4())

        first = await start_turn(client, auth, thread_id, turn_id=turn_id)
        second = await start_turn(client, auth, thread_id, turn_id=turn_id)

        assert first.status_code == 201
        assert first.json()["created"] is True
        # 200 rather than 201: nothing was created, and nothing was started.
        assert second.status_code == 200
        assert second.json()["created"] is False
        assert second.json()["id"] == turn_id
        with get_sync_db() as session:
            assert (
                session.scalar(
                    select(AgentMessage)
                    .where(AgentMessage.thread_id == uuid.UUID(thread_id))
                    .where(AgentMessage.role == "user")
                    .order_by(AgentMessage.seq.desc())
                ).seq
                == 1
            )
        desk.control.finish()

    async def test_the_same_id_with_a_different_question_is_a_conflict(
        self, client, auth, desk
    ):
        thread_id = await open_thread(client, auth)
        turn_id = str(uuid.uuid4())

        await start_turn(client, auth, thread_id, turn_id=turn_id, text="VCB?")
        clash = await start_turn(client, auth, thread_id, turn_id=turn_id, text="HPG?")

        assert clash.status_code == 409
        assert clash.json()["detail"]["reason"] == "turn_id_reused"
        desk.control.finish()

    async def test_a_symbol_set_is_part_of_the_payload_the_key_protects(
        self, client, auth, desk
    ):
        thread_id = await open_thread(client, auth)
        turn_id = str(uuid.uuid4())

        await start_turn(client, auth, thread_id, turn_id=turn_id, symbols=["VCB"])
        clash = await start_turn(
            client, auth, thread_id, turn_id=turn_id, symbols=["HPG"]
        )

        assert clash.status_code == 409
        desk.control.finish()


class TestOwnership:
    pytestmark = pytest.mark.asyncio

    async def test_a_stranger_reaches_none_of_the_three_endpoints(
        self, client, auth, desk, other_account
    ):
        thread_id = await open_thread(client, auth)
        turn_id = str(uuid.uuid4())
        await start_turn(client, auth, thread_id, turn_id=turn_id)
        stranger = await authenticate(client, other_account)

        created = await start_turn(client, stranger, thread_id)
        subscribed = await client.get(f"{API}/turns/{turn_id}/events", headers=stranger)
        cancelled = await client.post(
            f"{API}/turns/{turn_id}/cancel", headers=stranger
        )
        read = await client.get(f"{API}/turns/{turn_id}", headers=stranger)

        # 404 rather than 403 everywhere: a Turn under another user's Thread is
        # not a Turn this caller may be told exists.
        assert [
            created.status_code,
            subscribed.status_code,
            cancelled.status_code,
            read.status_code,
        ] == [404, 404, 404, 404]
        desk.control.finish()

    async def test_an_unauthenticated_subscribe_is_401_rather_than_a_stream(
        self, client, auth, desk
    ):
        thread_id = await open_thread(client, auth)
        turn_id = str(uuid.uuid4())
        await start_turn(client, auth, thread_id, turn_id=turn_id)

        response = await client.get(f"{API}/turns/{turn_id}/events")

        assert response.status_code == 401
        desk.control.finish()


# -- the stream ------------------------------------------------------------


class TestTheStream:
    pytestmark = pytest.mark.asyncio

    async def test_a_terminal_turn_is_served_as_a_snapshot_and_the_stream_closes(
        self, client, auth, desk
    ):
        # A fast Turn must not look like a dead one.
        thread_id = await open_thread(client, auth)
        turn_id = str(uuid.uuid4())
        desk.control.says("VCB đóng cửa ở 62.0")
        await start_turn(client, auth, thread_id, turn_id=turn_id)
        await asyncio.wait_for(desk.control.started.wait(), 2)
        desk.control.finish()
        await _settle(desk, turn_id)

        response = await client.get(f"{API}/turns/{turn_id}/events", headers=auth)

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-store, no-transform"
        assert response.headers["x-accel-buffering"] == "no"
        # No Content-Length would have been synthesised for a stream, and the
        # body ends by itself rather than waiting for a timeout.
        events = sse_events(response.text)
        assert [event["type"] for event in events] == [EventType.SNAPSHOT.value]
        assert events[0]["data"]["status"] == "complete"

    async def test_every_event_type_reaches_the_wire_with_seq_as_the_sse_id(
        self, client, auth, desk
    ):
        thread_id = await open_thread(client, auth)
        turn_id = str(uuid.uuid4())
        desk.control.says("một", "hai")
        await start_turn(client, auth, thread_id, turn_id=turn_id)
        await asyncio.wait_for(desk.control.started.wait(), 2)
        desk.control.finish()
        await _settle(desk, turn_id)

        response = await client.get(f"{API}/turns/{turn_id}/events", headers=auth)

        # The Turn ended before this subscriber arrived, so the snapshot is the
        # whole of it — and it carries the text the stream would have.
        snapshot = sse_events(response.text)[0]
        assert snapshot["seq"] == snapshot["data"]["through_seq"]
        assert sse_ids(response.text) == [str(snapshot["seq"])]
        assert snapshot["version"] == 2

    async def test_a_live_turn_streams_its_events_before_it_ends(
        self, live_client, auth, desk
    ):
        # The load-bearing assertion is the *first* one: the response head and
        # the snapshot arrive while the Turn is still running. A buffered
        # transport would answer nothing here until `finish()` had been called.
        thread_id = await open_thread(live_client, auth)
        turn_id = str(uuid.uuid4())
        desk.control.says("một")
        await start_turn(live_client, auth, thread_id, turn_id=turn_id)
        await asyncio.wait_for(desk.control.started.wait(), 2)

        received: list[dict] = []
        async with live_client.stream(
            "GET", f"{API}/turns/{turn_id}/events", headers=auth
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            # A stream has no length to declare, and declaring one would make
            # every intermediary wait for that many bytes.
            assert "content-length" not in response.headers
            lines = response.aiter_lines()
            received.append(await _first_event(lines))
            desk.control.finish()
            async for line in lines:
                if line.startswith("data: "):
                    received.append(json.loads(line[len("data: ") :]))

        sequences = [event["seq"] for event in received]
        assert sequences == sorted(sequences)
        assert received[0]["type"] == EventType.SNAPSHOT.value
        assert received[-1]["type"] == EventType.COMPLETED.value

    async def test_the_stream_is_the_snapshot_and_then_only_what_follows_it(
        self, live_client, auth, desk
    ):
        # A reconnect is exactly this: whatever already happened arrives as one
        # snapshot, and the stream resumes past it. No duplicate, and no gap.
        thread_id = await open_thread(live_client, auth)
        turn_id = str(uuid.uuid4())
        desk.control.says("một", "hai")
        await start_turn(live_client, auth, thread_id, turn_id=turn_id)
        await asyncio.wait_for(desk.control.started.wait(), 2)

        async with live_client.stream(
            "GET",
            f"{API}/turns/{turn_id}/events",
            headers={**auth, "Last-Event-ID": "1"},
        ) as response:
            lines = response.aiter_lines()
            snapshot = await _first_event(lines)
            desk.control.finish()
            following = await _first_event(lines)

        assert snapshot["type"] == EventType.SNAPSHOT.value
        assert snapshot["data"]["text"] == "một\n\nhai"
        assert following["seq"] > snapshot["data"]["through_seq"]

    async def test_a_subscriber_that_leaves_does_not_stop_the_turn(
        self, live_client, auth, desk
    ):
        thread_id = await open_thread(live_client, auth)
        turn_id = str(uuid.uuid4())
        await start_turn(live_client, auth, thread_id, turn_id=turn_id)
        await asyncio.wait_for(desk.control.started.wait(), 2)

        async with live_client.stream(
            "GET", f"{API}/turns/{turn_id}/events", headers=auth
        ) as response:
            await _first_event(response.aiter_lines())

        # The connection is gone; the Turn is not.
        assert desk.service.turns.running(turn_id) is not None
        desk.control.finish()
        await _settle(desk, turn_id)
        with get_sync_db() as session:
            assert session.get(AgentTurn, uuid.UUID(turn_id)).status == "complete"


class TestTheSubscriptionLimiter:
    pytestmark = pytest.mark.asyncio

    async def test_reconnecting_is_throttled_on_its_own_counter_not_charged_as_a_start(
        self, client, auth, desk, monkeypatch
    ):
        thread_id = await open_thread(client, auth)
        turn_id = str(uuid.uuid4())
        await start_turn(client, auth, thread_id, turn_id=turn_id)
        await asyncio.wait_for(desk.control.started.wait(), 2)
        desk.control.finish()
        await _settle(desk, turn_id)

        allowed = 0
        refused = 0
        counter = _CountingLimiter(limit=2)
        desk.service.subscriptions = counter
        for _ in range(4):
            response = await client.get(f"{API}/turns/{turn_id}/events", headers=auth)
            if response.status_code == 200:
                allowed += 1
            else:
                refused += 1
                assert response.status_code == 429
                assert (
                    response.json()["detail"]["reason"] == "turn_subscribe_throttled"
                )

        assert (allowed, refused) == (2, 2)
        # Not one further admission question was asked: reattaching to a Turn
        # dispatches nothing, so it is not a Turn start.
        assert len(desk.ledger.checked) == 1

    async def test_a_strangers_turn_never_spends_that_turns_window(
        self, client, auth, desk, other_account
    ):
        # The per-Turn window is keyed by Turn, so counting it before ownership
        # was resolved would let any signed-in account exhaust it by naming
        # somebody else's Turn id — the very failure this limiter exists to
        # prevent, reintroduced through the limiter.
        thread_id = await open_thread(client, auth)
        turn_id = str(uuid.uuid4())
        await start_turn(client, auth, thread_id, turn_id=turn_id)
        await asyncio.wait_for(desk.control.started.wait(), 2)
        desk.control.finish()
        await _settle(desk, turn_id)

        counter = _CountingLimiter(limit=10)
        desk.service.subscriptions = counter
        stranger = await authenticate(client, other_account)
        refused = await client.get(f"{API}/turns/{turn_id}/events", headers=stranger)
        allowed = await client.get(f"{API}/turns/{turn_id}/events", headers=auth)

        assert refused.status_code == 404
        assert allowed.status_code == 200
        # The stranger's attempt was counted against the stranger, and against
        # no Turn at all.
        assert len(counter.users) == 2
        assert counter.turns == [turn_id]


class _CountingLimiter:
    """A limiter with no Redis behind it, so the count is the test's."""

    def __init__(self, *, limit: int) -> None:
        self._limit = limit
        self.users: list[int] = []
        self.turns: list[str] = []

    def check_user(self, user_id: int) -> None:
        self.users.append(user_id)
        if len(self.users) > self._limit:
            raise SubscriptionThrottled("user")

    def check_turn(self, turn_id) -> None:
        self.turns.append(str(turn_id))


# -- cancel ----------------------------------------------------------------


class TestCancel:
    pytestmark = pytest.mark.asyncio

    async def test_cancel_is_idempotent_and_dispatches_nothing(
        self, client, auth, desk
    ):
        thread_id = await open_thread(client, auth)
        turn_id = str(uuid.uuid4())
        await start_turn(client, auth, thread_id, turn_id=turn_id)
        await asyncio.wait_for(desk.control.started.wait(), 2)

        first = await client.post(f"{API}/turns/{turn_id}/cancel", headers=auth)
        second = await client.post(f"{API}/turns/{turn_id}/cancel", headers=auth)

        assert first.status_code == 200
        assert first.json()["cancel_requested"] is True
        assert second.json() == first.json()

        desk.control.finish()
        record = await _settle(desk, turn_id)
        assert record.status == "cancelled"
        assert record.terminal_reason == "cancelled_by_user"

        # A cancel after the Turn is terminal changes nothing at all.
        third = await client.post(f"{API}/turns/{turn_id}/cancel", headers=auth)
        assert third.status_code == 200
        assert third.json()["status"] == "cancelled"
        assert third.json()["terminal_reason"] == "cancelled_by_user"

    async def test_cancelling_keeps_what_the_turn_already_produced(
        self, client, auth, desk
    ):
        thread_id = await open_thread(client, auth)
        turn_id = str(uuid.uuid4())
        desk.control.says("VCB đóng cửa ở 62.0")
        await start_turn(client, auth, thread_id, turn_id=turn_id)
        await asyncio.wait_for(desk.control.started.wait(), 2)

        await client.post(f"{API}/turns/{turn_id}/cancel", headers=auth)
        desk.control.finish()
        await _settle(desk, turn_id)

        stream = await client.get(f"{API}/turns/{turn_id}/events", headers=auth)
        snapshot = sse_events(stream.text)[0]
        assert snapshot["data"]["status"] == "cancelled"
        assert snapshot["data"]["text"] == "VCB đóng cửa ở 62.0"


# -- Threads ---------------------------------------------------------------


class TestThreads:
    pytestmark = pytest.mark.asyncio

    async def test_a_thread_carries_its_transcript_and_only_its_owners(
        self, client, auth, desk, other_account
    ):
        thread_id = await open_thread(client, auth)
        turn_id = str(uuid.uuid4())
        desk.control.says("VCB đóng cửa ở 62.0")
        await start_turn(client, auth, thread_id, turn_id=turn_id, text="VCB?")
        await asyncio.wait_for(desk.control.started.wait(), 2)
        desk.control.finish()
        await _settle(desk, turn_id)
        stranger = await authenticate(client, other_account)

        mine = await client.get(f"{API}/threads/{thread_id}", headers=auth)
        theirs = await client.get(f"{API}/threads/{thread_id}", headers=stranger)

        assert mine.status_code == 200
        roles = [message["role"] for message in mine.json()["messages"]]
        assert roles == ["user", "assistant"]
        assert theirs.status_code == 404

    async def test_the_canonical_message_says_whether_the_answer_finished(
        self, client, auth, desk
    ):
        """A reopened Thread renders the transcript and nothing else.

        Without ``status`` on the content, a reader could not tell an answer that
        finished from one a deadline cut off — every truncated answer in the
        transcript would read as complete.
        """
        thread_id = await open_thread(client, auth)
        turn_id = str(uuid.uuid4())
        desk.control.says("một phần")
        desk.control.calls_a_tool()
        desk.control.status = TurnStatus.INCOMPLETE
        desk.control.terminal_reason = "turn_deadline"
        await start_turn(client, auth, thread_id, turn_id=turn_id)
        await asyncio.wait_for(desk.control.started.wait(), 2)
        desk.control.finish()
        await _settle(desk, turn_id)

        thread = await client.get(f"{API}/threads/{thread_id}", headers=auth)
        answer = thread.json()["messages"][-1]

        assert answer["role"] == "assistant"
        assert answer["content"]["text"] == "một phần"
        assert answer["content"]["status"] == "incomplete"
        assert [call["id"] for call in answer["content"]["tool_calls"]] == ["call_0"]
        # Four fields and no arguments: what a page said is trace material, not
        # transcript material.
        assert set(answer["content"]["tool_calls"][0]) == {
            "id",
            "name",
            "status",
            "summary",
        }

    async def test_a_tool_call_reaches_the_wire_and_rides_the_snapshot(
        self, client, auth, desk
    ):
        thread_id = await open_thread(client, auth)
        turn_id = str(uuid.uuid4())
        desk.control.says("xong")
        desk.control.calls_a_tool()
        await start_turn(client, auth, thread_id, turn_id=turn_id)
        await asyncio.wait_for(desk.control.started.wait(), 2)
        desk.control.finish()
        await _settle(desk, turn_id)

        stream = await client.get(f"{API}/turns/{turn_id}/events", headers=auth)
        snapshot = sse_events(stream.text)[0]

        assert snapshot["data"]["tool_calls"] == [
            {
                "id": "call_0",
                "name": "web_search",
                "status": "ok",
                "summary": "Tìm trên web: web_search",
            }
        ]

    async def test_a_second_question_reuses_the_thread(self, client, auth, desk):
        thread_id = await open_thread(client, auth)

        first = await start_turn(client, auth, thread_id, text="VCB?")
        desk.control.finish()
        await _settle(desk, first.json()["id"])
        desk.control = Control()
        second = await start_turn(client, auth, thread_id, text="HPG?")
        desk.control.finish()
        await _settle(desk, second.json()["id"])

        assert first.json()["thread_id"] == second.json()["thread_id"] == thread_id


class TestTheThreadMenu:
    """Rename, pin and delete — the three writes the sidebar's menu makes.

    Integration for the same reason the rest of this module is: all three are
    statements about owner-scoped rows, and the interesting half of rename is
    what it does *not* write.
    """

    pytestmark = pytest.mark.asyncio

    async def test_rename_writes_the_title_and_leaves_the_order_alone(
        self, client, auth, desk
    ):
        older = await open_thread(client, auth)
        newer = await open_thread(client, auth)

        renamed = await client.patch(
            f"{API}/threads/{older}", json={"title": "  Xu hướng STB  "}, headers=auth
        )

        assert renamed.status_code == 200
        # Trimmed on the way in: a name is what the user typed, without the
        # whitespace their paste brought with it.
        assert renamed.json()["title"] == "Xu hướng STB"
        listed = await client.get(f"{API}/threads", headers=auth)
        # `updated_at` is when the conversation was last worked in. Renaming is
        # not working in it, so the Thread stays where it was.
        assert [row["id"] for row in listed.json()["threads"]][:2] == [newer, older]

    async def test_an_empty_title_clears_it_rather_than_storing_blank(
        self, client, auth, desk
    ):
        thread_id = await open_thread(client, auth)
        await client.patch(f"{API}/threads/{thread_id}", json={"title": "Tạm"}, headers=auth)

        cleared = await client.patch(
            f"{API}/threads/{thread_id}", json={"title": "   "}, headers=auth
        )

        assert cleared.status_code == 200
        assert cleared.json()["title"] is None

    async def test_pinning_lifts_a_thread_above_newer_ones_and_unpinning_drops_it(
        self, client, auth, desk
    ):
        older = await open_thread(client, auth)
        newer = await open_thread(client, auth)

        pinned = await client.patch(
            f"{API}/threads/{older}", json={"pinned": True}, headers=auth
        )
        after_pin = await client.get(f"{API}/threads", headers=auth)

        assert pinned.status_code == 200
        assert pinned.json()["pinned_at"] is not None
        assert [row["id"] for row in after_pin.json()["threads"]][:2] == [older, newer]

        await client.patch(f"{API}/threads/{older}", json={"pinned": False}, headers=auth)
        after_unpin = await client.get(f"{API}/threads", headers=auth)

        assert [row["id"] for row in after_unpin.json()["threads"]][:2] == [newer, older]

    async def test_a_pin_carries_no_title_and_a_rename_does_not_unpin(
        self, client, auth, desk
    ):
        thread_id = await open_thread(client, auth)
        await client.patch(
            f"{API}/threads/{thread_id}", json={"title": "Giữ tên"}, headers=auth
        )

        pinned = await client.patch(
            f"{API}/threads/{thread_id}", json={"pinned": True}, headers=auth
        )
        renamed = await client.patch(
            f"{API}/threads/{thread_id}", json={"title": "Tên mới"}, headers=auth
        )

        assert pinned.json()["title"] == "Giữ tên"
        assert renamed.json()["pinned_at"] == pinned.json()["pinned_at"]

    async def test_delete_takes_the_transcript_with_it(self, client, auth, desk):
        thread_id = await open_thread(client, auth)
        turn_id = str(uuid.uuid4())
        desk.control.says("VCB đóng cửa ở 62.0")
        await start_turn(client, auth, thread_id, turn_id=turn_id, text="VCB?")
        await asyncio.wait_for(desk.control.started.wait(), 2)
        desk.control.finish()
        await _settle(desk, turn_id)

        removed = await client.delete(f"{API}/threads/{thread_id}", headers=auth)

        assert removed.status_code == 204
        assert (await client.get(f"{API}/threads/{thread_id}", headers=auth)).status_code == 404
        with get_sync_db() as session:
            left = session.execute(
                select(AgentMessage).where(AgentMessage.thread_id == uuid.UUID(thread_id))
            ).scalars().all()
        assert left == []

    async def test_a_stranger_can_neither_rename_nor_delete(
        self, client, auth, desk, other_account
    ):
        thread_id = await open_thread(client, auth)
        stranger = await authenticate(client, other_account)

        renamed = await client.patch(
            f"{API}/threads/{thread_id}", json={"title": "của tôi"}, headers=stranger
        )
        removed = await client.delete(f"{API}/threads/{thread_id}", headers=stranger)

        # 404 rather than 403, for the reason the read route gives.
        assert renamed.status_code == 404
        assert removed.status_code == 404
        assert (await client.get(f"{API}/threads/{thread_id}", headers=auth)).status_code == 200


class TestWhatTheSubscribeEndpointDependsOn:
    """``docs/specs/0003`` §10.5, and the limiter ``docs/adr/0013`` forbids.

    Both are properties of what the endpoint *declares* rather than of what one
    request happens to do, and a declaration is what drifts: a later hand adding
    ``CurrentUser`` here for symmetry with the other routes would reintroduce a
    session whose scope is the response, and the response is the Turn.
    """

    def test_subscribing_holds_no_session_and_no_ip_based_limiter(self):
        # Behind the Next proxy every user shares one IP, so the first reconnect
        # burst on the `heavy` limiter would rate-limit everybody at once. The
        # per-user and per-Turn counter in `src.agent.limits` is what stands
        # here instead, and it is asked inside the endpoint rather than as a
        # dependency — which is why this asserts an absence.
        calls = _dependency_calls(turn_events)

        assert heavy_rate_limit not in calls
        assert standard_rate_limit not in calls
        # `get_db` is the other thing that must not be here: its scope ends when
        # the *response* does, which for this route is when the Turn does. The
        # caller is resolved by `streaming_user_id`, which opens and closes its
        # own session before anything streams.
        assert get_db not in calls
        assert streaming_user_id in calls
        # Nothing is smuggled in at the router either, which would apply to
        # every endpoint mounted on it including this one.
        assert alpha_desk_router.dependencies == []


class TestTheHistoryHandedToTheLoop:
    def test_a_turn_that_never_answered_still_reads_as_a_question(self):
        from src.agent.persistence import MessageRecord

        moment = datetime(2026, 8, 15, tzinfo=timezone.utc)
        thread = uuid.uuid4()
        messages = (
            MessageRecord(1, thread, 1, "user", {"text": "VCB?"}, moment),
            MessageRecord(2, thread, 2, "assistant", {"text": "62.0"}, moment),
            MessageRecord(3, thread, 3, "user", {"text": "HPG?"}, moment),
        )

        history = history_of(messages)

        assert [turn.user_text for turn in history] == ["VCB?", "HPG?"]
        assert [turn.assistant_text for turn in history] == ["62.0", None]


# -- helpers ---------------------------------------------------------------


async def _first_event(lines) -> dict:
    async for line in lines:
        if line.startswith("data: "):
            return json.loads(line[len("data: ") :])
    raise AssertionError("the stream ended before it carried an event")


def _dependency_calls(endpoint) -> set:
    """Every callable FastAPI resolves before it enters this endpoint.

    Taken from the endpoint's own signature rather than from a mounted route,
    because that is where the property lives: a dependency declared here is
    resolved for every request and torn down only when the response ends.
    """
    found: set = set()
    pending = list(get_dependant(path="/", call=endpoint).dependencies)
    while pending:
        dependant = pending.pop()
        if dependant.call is not None:
            found.add(dependant.call)
        pending.extend(dependant.dependencies)
    return found


async def _settle(desk: Desk, turn_id: str):
    """Wait for the Turn's own task to reach its terminal transaction."""
    running = desk.service.turns.running(turn_id)
    if running is not None and running.task is not None:
        await asyncio.wait_for(running.task, 5)
    with get_sync_db() as session:
        return session.get(AgentTurn, uuid.UUID(str(turn_id)))
