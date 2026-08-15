"""The one way an async request reaches synchronous store code.

Half the codebase is synchronous because the store is, and the request path is
not. Every route needing both has the same problem, and the reason it is
answered once is that the wrong answer is invisible: calling sync SQLAlchemy
straight from a coroutine works perfectly in a test and blocks every other
request in production.

So the property under test is not "it returns the right value" — it is "it did
not run on the event loop's thread".
"""

import asyncio
import threading

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.database import in_sync_session, sync_engine
from src.stocks.universe import build_universe


@pytest.mark.asyncio
async def test_returns_what_the_work_returned():
    assert await in_sync_session(lambda _: "đọc xong") == "đọc xong"


@pytest.mark.asyncio
async def test_runs_off_the_event_loop_thread():
    """The whole point. On the loop's thread, a slow query stalls the process."""
    loop_thread = threading.get_ident()

    where = await in_sync_session(lambda _: threading.get_ident())

    assert where != loop_thread


@pytest.mark.asyncio
async def test_hands_over_a_usable_sync_session():
    kind, answer = await in_sync_session(
        lambda session: (type(session), session.execute(select(1)).scalar_one())
    )

    assert issubclass(kind, Session)
    assert answer == 1


@pytest.mark.asyncio
async def test_returns_its_connection_to_the_pool():
    """Its own session, closed on the way out. A crossing that leaked a
    connection would look fine until the pool ran dry under load."""
    before = sync_engine.pool.checkedout()

    await in_sync_session(lambda session: session.execute(select(1)).scalar_one())

    assert sync_engine.pool.checkedout() == before


@pytest.mark.asyncio
async def test_carries_the_universe_check_this_ticket_needs():
    """The seam's first caller: the Watchlist asking whether a symbol is in the
    Universe, which is a synchronous read from an async handler."""
    universe = await in_sync_session(build_universe)

    assert universe is not None


@pytest.mark.asyncio
async def test_several_crossings_may_be_awaited_together():
    """Each gets its own session, so gathering them is safe — which is what a
    handler doing two sync reads at once will do."""
    results = await asyncio.gather(*(in_sync_session(lambda _, n=n: n) for n in range(4)))

    assert results == [0, 1, 2, 3]
