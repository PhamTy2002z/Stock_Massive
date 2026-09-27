"""Turns in a table more than one process shares.

A Turn's process says it is alive by touching ``heartbeat_at``. Everything that
decides a Turn is dead — the startup sweep, the periodic reaper, admission's
active counts — reads that one signal, so a second process's Turns survive a
restart here and a row a crash left behind stops locking its user out.

Against the real store, because each rule is a ``WHERE`` clause, an advisory
lock or a row lock, and a fake would only prove the fake.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy import delete, func, select, update

from src.agent import turns as turns_module
from src.agent.compaction import ThreadCompactor
from src.agent.loop import AgentLoop, ContextBudget, TurnRefused
from src.agent.persistence import (
    INTERRUPTED_REASON,
    TURN_INCOMPLETE,
    TURN_RUNNING,
    AgentPersistence,
    TurnPayloadConflict,
)
from src.agent.turns import TurnService, frozen_message, run_turn_housekeeping
from src.alpha.models import TURN_STALE_SECONDS, AgentThread, AgentTurn
from src.auth.models import User
from src.core.database import get_sync_db, sync_session_factory
from src.core.llm.admission import _read_turn_state

from .test_agent_loop import FakeClient, config
from .test_agent_turn_lifecycle import (  # noqa: F401 - fixtures
    _tools,
    answer,
    owner,
    runtime,
    schema,
    service,
    store,
    thread_for,
)

LONG_AGO = timedelta(seconds=TURN_STALE_SECONDS + 60)


async def _active_row(
    owner_id: int,
    *,
    status: str = TURN_RUNNING,
    started_ago: timedelta = timedelta(0),
    beat_ago: timedelta | None = None,
) -> uuid.UUID:
    """An active Turn some process owns, aged by the database's own clock."""
    thread_id = await thread_for(owner_id)
    message = await store().append_message(
        thread_id, role="user", content={"text": "FPT thế nào?"}
    )
    turn_id = uuid.uuid4()
    with get_sync_db() as session:
        session.add(
            AgentTurn(
                id=turn_id,
                thread_id=thread_id,
                request_message_id=message.id,
                status=status,
                started_at=datetime.now(timezone.utc) - started_ago,
                draft_content={"text": "Một phần.", "tool_calls": [], "rounds_used": 1},
            )
        )
    if beat_ago is not None:
        with get_sync_db() as session:
            session.execute(
                update(AgentTurn)
                .where(AgentTurn.id == turn_id)
                .values(heartbeat_at=func.now() - beat_ago)
            )
    return turn_id


def _row(turn_id: uuid.UUID) -> AgentTurn:
    with get_sync_db() as session:
        return session.execute(
            select(AgentTurn).where(AgentTurn.id == turn_id)
        ).scalar_one()


# --- the sweep and the reaper ----------------------------------------------


@pytest.mark.asyncio
async def test_the_sweep_takes_only_turns_whose_process_stopped_beating(owner):
    beating = await _active_row(owner, started_ago=LONG_AGO, beat_ago=timedelta(0))
    just_admitted = await _active_row(owner, status="admitted")
    dead = await _active_row(owner, started_ago=LONG_AGO * 2, beat_ago=LONG_AGO)
    never_beat = await _active_row(owner, started_ago=LONG_AGO)

    frozen = {record.id for record in await service(FakeClient([])).sweep()}

    assert {dead, never_beat} <= frozen
    assert beating not in frozen and just_admitted not in frozen
    assert _row(beating).status == TURN_RUNNING
    assert _row(just_admitted).status == "admitted"
    assert (_row(dead).status, _row(dead).terminal_reason) == (
        TURN_INCOMPLETE,
        INTERRUPTED_REASON,
    )


@pytest.mark.asyncio
async def test_the_reaper_spares_what_this_process_is_running(owner):
    """A heartbeat that failed once must not get a Turn frozen under its own process."""
    mine = await _active_row(owner, started_ago=LONG_AGO, beat_ago=LONG_AGO)

    frozen = await store().freeze_interrupted_turns(frozen_message, exclude=[mine])

    assert mine not in {record.id for record in frozen}
    assert _row(mine).status == TURN_RUNNING


@pytest.mark.asyncio
async def test_running_stamps_a_heartbeat_and_beats_touch_only_active_rows(owner):
    turn_id = await _active_row(owner, status="admitted")
    await store().mark_turn_running(turn_id)
    first = _row(turn_id)
    assert first.status == TURN_RUNNING and first.heartbeat_at is not None

    settled = await _active_row(owner)
    await store().finish_turn(settled, status=TURN_INCOMPLETE, terminal_reason="x")
    await store().heartbeat_turns([turn_id, settled])

    assert _row(turn_id).heartbeat_at >= first.heartbeat_at
    assert _row(settled).heartbeat_at is None


@pytest.mark.asyncio
async def test_housekeeping_beats_for_running_turns_and_reaps_on_its_own_tick(
    monkeypatch,
):
    beats: list[tuple[uuid.UUID, ...]] = []
    reaps: list[tuple[uuid.UUID, ...]] = []
    running = (uuid.uuid4(),)

    class Recording:
        async def heartbeat_turns(self, ids):
            beats.append(tuple(ids))
            raise RuntimeError("a failed beat is logged, not fatal")

        async def freeze_interrupted_turns(self, _builder, *, exclude=()):
            reaps.append(tuple(exclude))
            return ()

    monkeypatch.setattr(turns_module, "running_turn_ids", lambda: running)
    task = asyncio.create_task(
        run_turn_housekeeping(Recording(), heartbeat_seconds=0.01, reap_seconds=0.03)
    )
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(beats) >= 3 and all(ids == running for ids in beats)
    assert 1 <= len(reaps) < len(beats)
    assert all(ids == running for ids in reaps)


# --- admission's active counts ---------------------------------------------


@pytest.mark.asyncio
async def test_a_stale_row_stops_counting_before_anyone_reaps_it(owner):
    await _active_row(owner, started_ago=LONG_AGO * 2, beat_ago=LONG_AGO)
    with get_sync_db() as session:
        stale_only = _read_turn_state(session, owner, datetime.now(timezone.utc), "")
    await _active_row(owner, status="admitted")
    with get_sync_db() as session:
        with_live = _read_turn_state(session, owner, datetime.now(timezone.utc), "")

    assert stale_only.active_for_user == 0
    assert with_live.active_for_user == 1


# --- creation ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_second_create_while_one_is_active_is_refused_like_preflight(owner):
    """The re-count under the admission locks; the second create commits nothing."""
    thread_id = await thread_for(owner)
    await _active_row(owner, status="admitted")
    turns = service(FakeClient([answer("Không tới đây.")]))
    turn_id = uuid.uuid4()

    with pytest.raises(TurnRefused) as refused:
        await turns.create(
            user_id=owner,
            thread_id=thread_id,
            turn_id=turn_id,
            user_text="FPT thế nào?",
            runtime=runtime(owner),
        )

    assert (refused.value.reason, refused.value.status_code) == ("user_active_turn", 429)
    assert await store().read_turn(owner, turn_id) is None
    assert turns.running_ids == ()


@pytest.mark.asyncio
async def test_two_creates_racing_past_preflight_admit_exactly_one(owner):
    """Both run at once, in two threads; the advisory lock makes one wait and lose."""
    turns = TurnService(
        store=store(),
        loop_factory=lambda **_: _Hangs(asyncio.Event()),
        config=config(),
        shutdown_seconds=0.05,
    )
    threads = [await thread_for(owner), await thread_for(owner)]

    results = await asyncio.gather(
        *(
            turns.create(
                user_id=owner,
                thread_id=thread_id,
                turn_id=uuid.uuid4(),
                user_text="FPT thế nào?",
                runtime=runtime(owner),
            )
            for thread_id in threads
        ),
        return_exceptions=True,
    )
    await turns.shutdown()

    refused = [result for result in results if isinstance(result, TurnRefused)]
    created = [result for result in results if not isinstance(result, BaseException)]
    assert len(created) == 1 and len(refused) == 1
    assert refused[0].reason == "user_active_turn"


@pytest.mark.asyncio
async def test_a_turn_id_another_user_holds_is_a_conflict_at_once(owner):
    other = await _active_row(owner)
    thread_id = await thread_for(owner)
    with get_sync_db() as session:
        user = User(email=f"stranger-{uuid.uuid4().hex}@example.com", hashed_password="x")
        session.add(user)
        session.flush()
        stranger = user.id
    try:
        stranger_thread = await thread_for(stranger)
        # Not a twenty-fold retry of the primary key ending in a 500.
        with pytest.raises(TurnPayloadConflict):
            await store().create_turn(
                user_id=stranger,
                thread_id=stranger_thread,
                turn_id=other,
                user_text="Của tôi?",
            )
        # A retry names a Turn of the same Thread, or nothing.
        with pytest.raises(LookupError):
            await store().create_turn(
                user_id=owner,
                thread_id=thread_id,
                turn_id=uuid.uuid4(),
                user_text="Thử lại.",
                retry_of_turn_id=other,
            )
    finally:
        with get_sync_db() as session:
            session.execute(delete(AgentThread).where(AgentThread.user_id == stranger))
            session.execute(delete(User).where(User.id == stranger))


# --- the terminal path ---------------------------------------------------------


class _Hangs:
    """A loop that starts and never finishes, until it is cancelled."""

    def __init__(self, started: asyncio.Event) -> None:
        self._started = started

    async def run(self, *_args: Any, **_kwargs: Any):
        self._started.set()
        await asyncio.Event().wait()


class _FinishFails(AgentPersistence):
    def __init__(self) -> None:
        super().__init__(session_factory=sync_session_factory)
        self.finishes = 0

    async def finish_turn(self, *_args: Any, **_kwargs: Any):
        self.finishes += 1
        raise RuntimeError("the database went away")


@pytest.mark.asyncio
async def test_a_turn_that_cannot_write_its_end_still_closes_every_stream(
    owner, monkeypatch
):
    monkeypatch.setattr(turns_module, "FINISH_BACKOFF_SECONDS", 0.0)
    failing = _FinishFails()

    def loop_factory(*, checkpoint, publisher, lane, toolsets):
        return AgentLoop(
            client=FakeClient([answer("Xong.")]),
            config=config(),
            budget=ContextBudget(max_tokens=30_000),
            lane=lane,
            checkpoint=checkpoint,
            publisher=publisher,
        )

    turns = TurnService(store=failing, loop_factory=loop_factory, config=config())
    thread_id = await thread_for(owner)
    turn_id = uuid.uuid4()
    handle = await turns.create(
        user_id=owner,
        thread_id=thread_id,
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    subscriber = handle.publisher.subscribe()

    assert await turns.running(turn_id).task is None

    assert failing.finishes == turns_module.FINISH_ATTEMPTS
    events = [event async for event in subscriber.events()]
    assert events[-1].data["status"] == TURN_INCOMPLETE
    assert events[-1].data["terminal_reason"] == INTERRUPTED_REASON
    # Out of the registry, so it stops beating and the reaper can have it.
    assert turns.running(turn_id) is None
    assert _row(turn_id).status == TURN_RUNNING


@pytest.mark.asyncio
async def test_shutdown_freezes_the_turns_it_had_to_cancel(owner):
    """Its Turns were beating a moment ago, so no sweep would take them soon."""
    started = asyncio.Event()
    turns = TurnService(
        store=store(),
        loop_factory=lambda **_: _Hangs(started),
        config=config(),
        shutdown_seconds=0.05,
    )
    turn_id = uuid.uuid4()
    await turns.create(
        user_id=owner,
        thread_id=await thread_for(owner),
        turn_id=turn_id,
        user_text="FPT thế nào?",
        runtime=runtime(owner),
    )
    await started.wait()

    await turns.shutdown()

    row = _row(turn_id)
    assert (row.status, row.terminal_reason) == (TURN_INCOMPLETE, INTERRUPTED_REASON)


# --- compaction ----------------------------------------------------------------


class _GatedStore:
    def __init__(self) -> None:
        self.reads = 0
        self.release = asyncio.Event()

    async def read_thread(self, _user_id: int, _thread_id: Any):
        self.reads += 1
        await self.release.wait()
        raise RuntimeError("nothing to summarise here")


@pytest.mark.asyncio
async def test_one_thread_is_compacted_once_at_a_time_and_cooldowns_are_pruned():
    now = {"value": 0.0}
    gated = _GatedStore()
    compactor = ThreadCompactor(
        client=FakeClient([]),
        config=config(),
        store=gated,  # type: ignore[arg-type] - only read_thread is reached
        cooldown_seconds=10.0,
        clock=lambda: now["value"],
    )
    thread = uuid.uuid4()

    first = asyncio.create_task(compactor.compact(thread_id=thread, user_id=1))
    await asyncio.sleep(0)
    assert await compactor.compact(thread_id=thread, user_id=1) is None
    gated.release.set()
    assert await first is None
    assert gated.reads == 1

    # The failure cooled the thread; once that cooldown has ended, the next
    # failure anywhere drops it rather than letting the map grow.
    now["value"] = 11.0
    await compactor.compact(thread_id=uuid.uuid4(), user_id=1)
    assert str(thread) not in compactor._cooling
    assert len(compactor._cooling) == 1
