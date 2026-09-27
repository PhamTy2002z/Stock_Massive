"""The notes a reader asked the agent to keep, as the reader manages them.

```
GET    /api/v1/memory/facts?limit=50&offset=0   → newest first, with the total
DELETE /api/v1/memory/facts/{factId}            → 204, or 404
DELETE /api/v1/memory/facts                     → {"deleted": n}
```

The rows are the ones ``remember_fact`` writes and ``recall_facts`` reads, and
the same boundary holds here as there: every statement is scoped to the
resolved user in SQL, and the user id is never a parameter. Another reader's
note and a note that does not exist answer the same 404, because a caller who
could tell them apart has been told an id exists.

Like the flag routes, this admits nothing and reaches no model, so it takes a
plain database session rather than the desk service: a reader must be able to
clear their notes while the model route is down.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import delete, func, select

from src.agent.schemas import (
    DeletedCountResponse,
    RowId,
    MemoryFactListResponse,
    MemoryFactResponse,
)
from src.agent.tools.memory import CONVERSATION_SOURCE
from src.alpha.models import AgentKnowledge
from src.auth.dependencies import CurrentUser
from src.core.database import DbSession

router = APIRouter(prefix="/memory", tags=["alpha-desk"])

SessionDep = DbSession

MAX_PAGE = 100


def _fact(row: AgentKnowledge) -> MemoryFactResponse:
    return MemoryFactResponse(
        id=row.id,
        title=row.title,
        body=row.body,
        symbol=row.symbol,
        source_url=None if row.source_url == CONVERSATION_SOURCE else row.source_url,
        source_name=row.source_name,
        as_of=row.as_of,
        created_at=row.created_at,
    )


@router.get("/facts", response_model=MemoryFactListResponse)
async def list_facts(
    current_user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MemoryFactListResponse:
    """This reader's notes, newest first, one page at a time."""
    owned = AgentKnowledge.user_id == current_user.id
    total = await session.scalar(select(func.count()).select_from(AgentKnowledge).where(owned))
    rows = await session.scalars(
        select(AgentKnowledge)
        .where(owned)
        .order_by(AgentKnowledge.created_at.desc(), AgentKnowledge.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return MemoryFactListResponse(items=[_fact(row) for row in rows], total=total or 0)


@router.delete("/facts/{fact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fact(fact_id: RowId, current_user: CurrentUser, session: SessionDep) -> Response:
    """Forget one note. Not reversible."""
    result = await session.execute(
        delete(AgentKnowledge).where(
            AgentKnowledge.id == fact_id, AgentKnowledge.user_id == current_user.id
        )
    )
    if not result.rowcount:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fact not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/facts", response_model=DeletedCountResponse)
async def delete_all_facts(current_user: CurrentUser, session: SessionDep) -> DeletedCountResponse:
    """Forget every note this reader kept, in one statement."""
    result = await session.execute(
        delete(AgentKnowledge).where(AgentKnowledge.user_id == current_user.id)
    )
    return DeletedCountResponse(deleted=result.rowcount or 0)


__all__ = ["router"]
