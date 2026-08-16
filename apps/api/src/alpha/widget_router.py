"""Reading back the fixed slice a stored Widget spec names (#89).

One route, and its shape is the security property. The client asks for a
**descriptor that is already on a message it owns** — never for a descriptor of
its own composition — so the only slice anybody can resolve is the one their own
answer was written against. That also makes "reopening a Thread renders the same
historical slice" true by construction rather than by discipline: there is no
parameter through which a different day could be requested.

``GET`` rather than ``POST`` because this is a pure read of a settled window. It
is idempotent, it is cacheable, and the 24-hour Redis entry behind it is a hot
cache for exactly the same reason.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from src.agent.persistence import AgentPersistence
from src.agent.tools.data import StoreBackedTools
from src.agent.widgets import WidgetDataResolver
from src.auth.dependencies import CurrentUser

router = APIRouter(prefix="/widgets", tags=["widgets"])


def get_resolver() -> WidgetDataResolver:
    """The resolver, as a dependency so a test can substitute the store."""
    return WidgetDataResolver(tools=StoreBackedTools())


def get_store() -> AgentPersistence:
    return AgentPersistence()


Store = Annotated[AgentPersistence, Depends(get_store)]
Resolver = Annotated[WidgetDataResolver, Depends(get_resolver)]


@router.get("/{message_id}/{descriptor_id}")
async def resolve_widget(
    message_id: int,
    descriptor_id: str,
    current_user: CurrentUser,
    store: Store,
    resolver: Resolver,
) -> dict[str, Any]:
    """The data for one Widget on one of the caller's own messages."""
    message = await store.read_message(current_user.id, message_id)
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Message not found"
        )
    widgets = message.content.get("widgets") or []
    spec = next(
        (
            widget
            for widget in widgets
            if isinstance(widget, dict) and widget.get("descriptor_id") == descriptor_id
        ),
        None,
    )
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found"
        )
    return dict(await resolver.resolve(spec.get("descriptor") or {}))
