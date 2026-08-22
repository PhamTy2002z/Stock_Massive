"""The real application, with the model replaced by a Turn the test drives.

This is the FastAPI end of the end-to-end streaming acceptance (ADR-0013,
ADR-0026, spec 0003 §7). Unit tests on either side of the proxy prove the two
halves; they cannot prove that an intermediary streams, because both halves are
in the same process and there is no intermediary. So the browser drives Next,
Next proxies FastAPI, and *this* is the FastAPI — ``src.main:app`` itself, with
its routers, its middleware, its lifespan and its shutdown path.

**One thing is replaced and it is named here: the model.** ``AlphaDeskService``
is built with a scripted loop rather than :class:`AgentLoop`, at the seam
:class:`TurnService` already has, so the lifecycle, the event publisher, the
snapshot, the bounded subscriber queue, the checkpoints, the terminal
transaction and every byte of framing are the production ones. A real provider
would not let a test hold a Turn open for twenty seconds, publish on command,
and end it at a chosen moment — which is exactly what the four properties under
test require.

**The control endpoints live in this module and nowhere else.** They are
mounted on the app object *here*, at import time of a file under ``tests/``, so
nothing in ``src/`` knows they exist and no production process can serve them.

Run it with::

    .venv/bin/python -m uvicorn tests.e2e.server:app --port 8010

which is what ``apps/web/playwright.config.ts`` does.
"""

from __future__ import annotations

import asyncio
from datetime import date
from types import MappingProxyType
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select

from src.agent.limits import SubscriptionLimiter
from src.agent.loop import (
    SessionSlots,
    ToolCallStatus,
    TurnAdmission,
    TurnOutcome,
    TurnStatus,
    TurnToolCall,
)
from src.agent.persistence import AgentPersistence
from src.agent.service import AlphaDeskService, set_alpha_desk
from src.agent.turns import TurnService
from src.alpha.models import (
    AgentKnowledge,
    AgentMessage,
    AgentThread,
    AgentToolCall,
    AgentTurn,
    LlmCallUsage,
)
from src.auth.models import RefreshToken, User
from src.core.database import Base, get_sync_db, sync_engine
from src.core.llm import (
    BudgetLanes,
    LLMConfig,
    LLMRoute,
    PricingTable,
    TokenPrices,
    Usage,
    Workload,
)
from src.main import app

#: The one tool call the churn endpoint republishes. A single id on purpose: the
#: browser upserts a ``tool.call`` by id, so republishing one consumes sequence
#: numbers — which is what fills a slow subscriber's queue — while leaving the
#: answer and the list on screen exactly as they were.
CHURN_CALL_ID = "churn-1"


def _config() -> LLMConfig:
    """A route the admission arithmetic can fund, pointing at nothing.

    No call is ever made through it — the scripted loop below is what runs — but
    the configuration is read by Budget Validation, which would otherwise be
    answering about a route that did not exist.
    """
    return LLMConfig(
        enabled=True,
        route=LLMRoute(base_url="https://llm.invalid/v1", api_key="not-used"),
        models=MappingProxyType(
            {Workload.BATCH: "batch-model", Workload.SESSION: "session-model"}
        ),
        pricing=PricingTable(
            version="e2e",
            effective_from=date(2026, 1, 1),
            batch=TokenPrices(input=0.5, cached_input=0.1, cache_write=0.5, output=1.0),
            session=TokenPrices(input=2.0, cached_input=0.2, cache_write=2.0, output=5.0),
        ),
        lanes=BudgetLanes(
            monthly_envelope_usd=45,
            analysis_usd=10,
            turn_usd=30,
            emergency_usd=5,
        ),
    )


class Control:
    """What the browser test says this Turn should do, and when.

    One Turn at a time, which is all the acceptance needs: every property under
    test is about one Turn and its subscribers.
    """

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.text = ""
        self.publisher: Any | None = None

    def reset(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.text = ""
        self.publisher = None

    def say(self, text: str) -> None:
        """Publish one ``content.delta``, exactly as the loop would.

        The delta is appended here as well as published, so the answer the
        terminal transaction stores is the concatenation of what was streamed —
        the invariant the reconnect property is written against.
        """
        if self.publisher is None:
            raise HTTPException(status_code=409, detail="No Turn is running")
        self.text += text
        self.publisher.content_delta(text)

    def churn(self, count: int) -> None:
        """Publish ``count`` events that consume a sequence and nothing else.

        The way a slow subscriber is made to overflow its bounded queue without
        changing what the answer says: one tool call, republished under the same
        id, so the browser upserts a single row and the transcript is untouched.
        """
        if self.publisher is None:
            raise HTTPException(status_code=409, detail="No Turn is running")
        payload = TurnToolCall(
            id=CHURN_CALL_ID,
            name="web_search",
            summary="Tìm trên web: kiểm tra hàng đợi",
        ).as_wire()
        for _ in range(count):
            self.publisher.tool_call(payload)


CONTROL = Control()


class ScriptedLoop:
    """A Turn that publishes on command and ends when told.

    Built by the same factory signature :class:`AgentLoop` is, so
    :class:`TurnService` cannot tell the difference and nothing in the lifecycle
    is bypassed to make the test possible.
    """

    def __init__(self, control: Control, *, checkpoint, publisher) -> None:
        self._control = control
        self._checkpoint = checkpoint
        self._publisher = publisher

    async def run(self, request, cancelled) -> TurnOutcome:
        self._control.publisher = self._publisher
        self._control.started.set()
        await self._control.release.wait()
        status = TurnStatus.CANCELLED if cancelled() else TurnStatus.COMPLETE
        calls = (
            (
                TurnToolCall(
                    id=CHURN_CALL_ID,
                    name="web_search",
                    status=ToolCallStatus.OK,
                    summary="Tìm trên web: kiểm tra hàng đợi",
                ),
            )
            if self._control.publisher.tool_calls
            else ()
        )
        return TurnOutcome(
            status=status,
            terminal_reason="cancelled_by_user" if cancelled() else None,
            text=self._control.text or None,
            rounds_used=0,
            rounds_exhausted=False,
            tool_calls=calls,
            usage=Usage(),
        )


class OpenLedger:
    """Admits every Turn. Budget refusals have their own tests (#85)."""

    def preflight_turn(self, user_id: int, *, output_tokens: int) -> None:
        return None


def build_service() -> AlphaDeskService:
    store = AgentPersistence()
    slots = SessionSlots()
    config = _config()

    def loop_factory(*, checkpoint, publisher):
        return ScriptedLoop(CONTROL, checkpoint=checkpoint, publisher=publisher)

    return AlphaDeskService(
        turns=TurnService(store=store, loop_factory=loop_factory, config=config),
        admission=TurnAdmission(OpenLedger(), slots=slots),
        # Generous on purpose: the reconnect property drives several subscribes
        # in a row, and throttling them is a different ticket's assertion.
        subscriptions=SubscriptionLimiter(per_user=1000, per_turn=1000, window=60),
        store=store,
        config=config,
        client=None,
    )


# The Alpha Desk tables, for a database migrated before `agent_*` existed. The
# real migration owns them; this only means a developer's box that is one
# revision behind still runs the acceptance.
Base.metadata.create_all(
    sync_engine,
    tables=[
        AgentThread.__table__,
        AgentMessage.__table__,
        AgentToolCall.__table__,
        AgentTurn.__table__,
        AgentKnowledge.__table__,
        LlmCallUsage.__table__,
    ],
    checkfirst=True,
)

set_alpha_desk(build_service())


# -- the control surface ---------------------------------------------------

control_router = APIRouter(prefix="/e2e", tags=["e2e"])


class SayRequest(BaseModel):
    text: str


class ChurnRequest(BaseModel):
    count: int = 400


class PurgeRequest(BaseModel):
    email: str


@control_router.post("/reset")
async def reset() -> dict[str, bool]:
    """Forget the previous Turn. Never touches one that is still running."""
    CONTROL.reset()
    return {"ok": True}


@control_router.get("/turn")
async def turn_state() -> dict[str, bool]:
    return {"started": CONTROL.started.is_set(), "released": CONTROL.release.is_set()}


@control_router.post("/turn/wait")
async def wait_for_turn() -> dict[str, bool]:
    """Block until the Turn is actually executing, so the test need not poll."""
    try:
        await asyncio.wait_for(CONTROL.started.wait(), timeout=10)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="No Turn started") from None
    return {"started": True}


@control_router.post("/turn/say")
async def say(request: SayRequest) -> dict[str, int]:
    CONTROL.say(request.text)
    return {"chars": len(CONTROL.text)}


@control_router.post("/turn/churn")
async def churn(request: ChurnRequest) -> dict[str, int]:
    CONTROL.churn(request.count)
    return {"published": request.count}


@control_router.post("/turn/finish")
async def finish() -> dict[str, bool]:
    CONTROL.release.set()
    return {"ok": True}


@control_router.post("/purge")
async def purge(request: PurgeRequest) -> dict[str, bool]:
    """Delete an account the browser registered, and everything it wrote.

    The acceptance registers a throwaway user through the real form, so it
    leaves a real row behind. Cleaning up from the test rather than from a
    fixture is what keeps the harness honest about which process owns the data.
    """
    with get_sync_db() as session:
        user = session.execute(
            select(User).where(User.email == request.email)
        ).scalar_one_or_none()
        if user is None:
            return {"deleted": False}
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
            session.execute(
                delete(AgentMessage).where(AgentMessage.thread_id.in_(threads))
            )
            session.execute(delete(AgentThread).where(AgentThread.id.in_(threads)))
        session.execute(delete(AgentKnowledge).where(AgentKnowledge.user_id == user.id))
        session.execute(delete(LlmCallUsage).where(LlmCallUsage.user_id == user.id))
        session.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
        session.execute(delete(User).where(User.id == user.id))
        session.commit()
    return {"deleted": True}


app.include_router(control_router)

__all__ = ["CONTROL", "app", "build_service"]
