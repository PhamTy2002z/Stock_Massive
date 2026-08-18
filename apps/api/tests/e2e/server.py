"""The real application, with the model replaced by a Turn the test drives.

This is the FastAPI end of the end-to-end streaming acceptance (ADR-0013,
spec 0003 §7). Unit tests on either side of the proxy prove the two halves; they
cannot prove that an intermediary streams, because both halves are in the same
process and there is no intermediary. So the browser drives Next, Next proxies
FastAPI, and *this* is the FastAPI — ``src.main:app`` itself, with its routers,
its middleware, its lifespan and its shutdown path.

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
import uuid
from datetime import date
from types import MappingProxyType
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select

from src.agent.admission import TurnAdmission
from src.agent.events import Activity
from src.agent.grounding import BlockKind, ReleasedBlock
from src.agent.limits import SubscriptionLimiter
from src.agent.loop import SessionSlots, TurnOutcome, TurnStatus
from src.agent.persistence import AgentPersistence
from src.agent.prompt import AnswerKind
from src.agent.service import AlphaDeskService, set_alpha_desk
from src.agent.turns import TurnService
from src.alpha.models import (
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


def _config() -> LLMConfig:
    """A route the admission arithmetic can fund, pointing at nothing.

    No call is ever made through it — the scripted loop below is what runs — but
    the configuration is read by Budget Validation and by the Evidence Manifest,
    and both would be answering about a route that did not exist otherwise.
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
            monthly_envelope_usd=50,
            analysis_usd=10,
            turn_usd=30,
            emergency_usd=5,
            eval_usd=5,
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
        self.blocks: list[ReleasedBlock] = []
        self.publisher: Any | None = None

    def reset(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.blocks = []
        self.publisher = None

    def say(self, text: str) -> None:
        """Release one content block, exactly as the Gate would have."""
        if self.publisher is None:
            raise HTTPException(status_code=409, detail="No Turn is running")
        block = ReleasedBlock(text=text, kind=BlockKind.PROSE, citations=())
        self.blocks.append(block)
        self.publisher.content_block(block.as_wire())

    def churn(self, count: int) -> None:
        """Publish `count` activity events and nothing else.

        The way a slow subscriber is made to overflow its bounded queue without
        changing what the answer says: activity is ephemeral, so none of this
        reaches the transcript.
        """
        if self.publisher is None:
            raise HTTPException(status_code=409, detail="No Turn is running")
        phases = [Activity.SEARCHING, Activity.READING_DATA, Activity.ANALYZING]
        for index in range(count):
            self.publisher.activity(phases[index % len(phases)])


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
        self._publisher.activity(Activity.ANALYZING)
        await self._control.release.wait()
        status = TurnStatus.CANCELLED if cancelled() else TurnStatus.COMPLETE
        blocks = tuple(self._control.blocks)
        return TurnOutcome(
            status=status,
            terminal_reason="cancelled_by_user" if cancelled() else None,
            text="\n\n".join(block.text for block in blocks) or None,
            answer_kind=AnswerKind.EDUCATION,
            rounds_used=0,
            rounds_exhausted=False,
            tool_calls=(),
            usage=Usage(),
            blocks=blocks,
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
        turns=TurnService(
            store=store,
            loop_factory=loop_factory,
            config=config,
            tool_catalog_version="e2e-catalog",
            git_sha="e2e",
        ),
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
    return {"blocks": len(CONTROL.blocks)}


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
        session.execute(delete(LlmCallUsage).where(LlmCallUsage.user_id == user.id))
        session.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
        session.execute(delete(User).where(User.id == user.id))
        session.commit()
    return {"deleted": True}


app.include_router(control_router)

__all__ = ["CONTROL", "app", "build_service"]
