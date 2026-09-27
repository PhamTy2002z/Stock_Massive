"""``/api/v1/connectors``: the settings page's routes.

Every route is the signed-in user's own: a connector id of somebody else's is
404, exactly like an id that does not exist. Nothing here ever returns a
credential — ``describe`` has no field that could carry one.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from src.auth.dependencies import CurrentUser

from .service import (
    ConnectorNotFound,
    ConnectorRefused,
    connectors,
    describe,
    describe_catalog,
)

router = APIRouter(prefix="/connectors", tags=["connectors"])

_REFUSAL_STATUS = {
    "connectors_disabled": status.HTTP_403_FORBIDDEN,
    "custom_url_not_allowed": status.HTTP_403_FORBIDDEN,
}


def _refused(error: ConnectorRefused) -> HTTPException:
    return HTTPException(
        status_code=_REFUSAL_STATUS.get(error.code, status.HTTP_422_UNPROCESSABLE_ENTITY),
        detail={"reason": error.code, "message": str(error)},
    )


def _missing() -> HTTPException:
    return HTTPException(status_code=404, detail="Connector not found")


class AddConnector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_id: int | None = None
    name: str | None = Field(default=None, max_length=120)
    url: str | None = Field(default=None, max_length=2000)
    header_name: str | None = Field(default=None, max_length=64)
    header_value: str | None = Field(default=None, max_length=4000)
    oauth: bool = False


class EditConnector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    header_value: str | None = Field(default=None, max_length=4000)


class ToolPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["allow", "ask", "deny"]


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_access: Literal["on_demand", "preloaded"]


@router.get("")
async def list_connectors(current_user: CurrentUser) -> dict[str, Any]:
    service = connectors()
    if not service.enabled():
        return {"enabled": False, "custom_url_allowed": False, "tool_access": "on_demand", "catalog": [], "connectors": []}
    mine = await service.mine(current_user.id)
    return {
        "enabled": True,
        "custom_url_allowed": service.custom_url_allowed(current_user.id),
        "tool_access": await service.tool_access(current_user.id),
        "catalog": [describe_catalog(entry) for entry in await service.catalog()],
        "connectors": [describe(row, catalog) for row, catalog in mine],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_connector(payload: AddConnector, current_user: CurrentUser) -> dict[str, Any]:
    service = connectors()
    try:
        if payload.catalog_id is not None:
            row = await service.add_from_catalog(
                current_user.id, payload.catalog_id, header_value=payload.header_value
            )
        else:
            row = await service.add_custom(
                current_user.id,
                name=payload.name or "",
                url=payload.url or "",
                header_name=payload.header_name,
                header_value=payload.header_value,
                oauth=payload.oauth,
            )
        row, catalog = await service.get(current_user.id, row.id)
    except ConnectorRefused as refused:
        raise _refused(refused) from refused
    except ConnectorNotFound as missing:
        raise _missing() from missing
    return describe(row, catalog)


@router.put("/preferences")
async def set_preferences(payload: Preferences, current_user: CurrentUser) -> dict[str, Any]:
    service = connectors()
    try:
        service.require_enabled()
        mode = await service.set_tool_access(current_user.id, payload.tool_access)
    except ConnectorRefused as refused:
        raise _refused(refused) from refused
    return {"tool_access": mode}


@router.get("/{connector_id}")
async def get_connector(connector_id: uuid.UUID, current_user: CurrentUser) -> dict[str, Any]:
    try:
        row, catalog = await connectors().get(current_user.id, connector_id)
    except ConnectorNotFound as missing:
        raise _missing() from missing
    return describe(row, catalog)


@router.patch("/{connector_id}")
async def edit_connector(
    connector_id: uuid.UUID, payload: EditConnector, current_user: CurrentUser
) -> dict[str, Any]:
    service = connectors()
    try:
        if payload.enabled is not None:
            await service.set_enabled(current_user.id, connector_id, payload.enabled)
        if payload.header_value:
            await service.set_header(current_user.id, connector_id, payload.header_value)
        row, catalog = await service.get(current_user.id, connector_id)
    except ConnectorNotFound as missing:
        raise _missing() from missing
    except ConnectorRefused as refused:
        raise _refused(refused) from refused
    return describe(row, catalog)


@router.put("/{connector_id}/tools/{tool_name}")
async def set_tool_policy(
    connector_id: uuid.UUID, tool_name: str, payload: ToolPolicy, current_user: CurrentUser
) -> dict[str, Any]:
    service = connectors()
    try:
        await service.set_policy(current_user.id, connector_id, tool_name, payload.action)
        row, catalog = await service.get(current_user.id, connector_id)
    except ConnectorNotFound as missing:
        raise _missing() from missing
    except ConnectorRefused as refused:
        raise _refused(refused) from refused
    return describe(row, catalog)


@router.post("/{connector_id}/refresh")
async def refresh_connector(connector_id: uuid.UUID, current_user: CurrentUser) -> dict[str, Any]:
    service = connectors()
    try:
        await service.refresh(current_user.id, connector_id)
        row, catalog = await service.get(current_user.id, connector_id)
    except ConnectorNotFound as missing:
        raise _missing() from missing
    return describe(row, catalog)


@router.post("/{connector_id}/accept")
async def accept_changes(connector_id: uuid.UUID, current_user: CurrentUser) -> dict[str, Any]:
    service = connectors()
    try:
        await service.accept_pending(current_user.id, connector_id)
        row, catalog = await service.get(current_user.id, connector_id)
    except ConnectorNotFound as missing:
        raise _missing() from missing
    return describe(row, catalog)


@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connector(connector_id: uuid.UUID, current_user: CurrentUser) -> Response:
    try:
        await connectors().delete(current_user.id, connector_id)
    except ConnectorNotFound as missing:
        raise _missing() from missing
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{connector_id}/oauth/start")
async def start_oauth(connector_id: uuid.UUID, current_user: CurrentUser) -> dict[str, str]:
    from . import oauth

    try:
        url = await oauth.start(connectors(), current_user.id, connector_id)
    except ConnectorNotFound as missing:
        raise _missing() from missing
    except ConnectorRefused as refused:
        raise _refused(refused) from refused
    return {"authorize_url": url}


@router.get("/oauth/callback", include_in_schema=False)
async def oauth_callback(
    state: str = Query(..., max_length=64),
    code: str | None = Query(default=None, max_length=4000),
    error: str | None = Query(default=None, max_length=200),
) -> RedirectResponse:
    """Where the provider sends the browser back. Unauthenticated by design:
    the ``state`` is the proof, it is single-use, and it expires in ten minutes."""
    from . import oauth

    outcome = await oauth.finish(connectors(), state=state, code=code, error=error)
    return RedirectResponse(oauth.return_url(connectors().settings, outcome), status_code=303)


__all__ = ["router"]
