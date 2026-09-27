"""Approvals a running Turn is waiting on, one future per tool call.

A call that needs a person's approval parks here, keyed by ``(turn_id,
call_id)``, so two calls in one round are approved independently. The wait ends
one of five ways, and only the first is a yes:

- the owner answers ``allow_once`` or ``always``;
- the owner answers ``deny``;
- :data:`APPROVAL_TIMEOUT_SECONDS` pass;
- the Turn is stopped;
- the connector is switched off or deleted (:meth:`ApprovalHub.deny_connector`).

In process, like the Turn registry it sits beside: a Turn and the request that
answers it reach the same process because the Turn's SSE stream already does.

# ponytail: single-process hub; move to Redis pub/sub when the API runs more
# than one worker behind the same Turns.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

APPROVAL_TIMEOUT_SECONDS = 300.0
ALLOW_ONCE, ALWAYS, DENY = "allow_once", "always", "deny"
DECISIONS = (ALLOW_ONCE, ALWAYS, DENY)
TIMED_OUT, CANCELLED, CONNECTOR_GONE = "timeout", "cancelled", "connector_off"


@dataclass
class _Pending:
    user_id: int
    connector_id: uuid.UUID
    can_always: bool
    future: asyncio.Future[str] = field(default_factory=lambda: asyncio.get_running_loop().create_future())


class ApprovalHub:
    def __init__(self) -> None:
        self._pending: dict[tuple[str, str], _Pending] = {}

    def pending_count(self) -> int:
        return len(self._pending)

    async def wait(
        self,
        *,
        turn_id: uuid.UUID | str,
        call_id: str,
        user_id: int,
        connector_id: uuid.UUID,
        can_always: bool,
        cancel_event: asyncio.Event | None = None,
        timeout: float = APPROVAL_TIMEOUT_SECONDS,
    ) -> str:
        """Block until one of the five endings; return the decision or why not."""
        key = (str(turn_id), call_id)
        entry = _Pending(user_id=user_id, connector_id=connector_id, can_always=can_always)
        self._pending[key] = entry
        waiters = [entry.future]
        stop = None
        if cancel_event is not None:
            stop = asyncio.ensure_future(cancel_event.wait())
            waiters.append(stop)
        try:
            done, _ = await asyncio.wait(waiters, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
            if entry.future in done:
                return entry.future.result()
            return CANCELLED if stop is not None and stop in done else TIMED_OUT
        finally:
            self._pending.pop(key, None)
            if stop is not None:
                stop.cancel()

    def resolve(self, *, user_id: int, turn_id: uuid.UUID | str, call_id: str, decision: str) -> bool:
        """Answer one waiting call. ``False`` when nothing of this user's waits."""
        if decision not in DECISIONS:
            raise ValueError("decision is allow_once, always or deny")
        entry = self._pending.get((str(turn_id), call_id))
        if entry is None or entry.user_id != user_id or entry.future.done():
            return False
        if decision == ALWAYS and not entry.can_always:
            raise PermissionError("this tool can only be approved once at a time")
        entry.future.set_result(decision)
        return True

    def deny_connector(self, connector_id: uuid.UUID) -> int:
        """Settle every call waiting on a connector that was switched off."""
        settled = 0
        for entry in list(self._pending.values()):
            if entry.connector_id == connector_id and not entry.future.done():
                entry.future.set_result(CONNECTOR_GONE)
                settled += 1
        return settled


hub = ApprovalHub()

UNSUPPORTED = "unsupported"
PREVIEW_CHARS = 600


def _preview(arguments: Mapping[str, Any]) -> str:
    from src.agent.security import redact_trace_value

    text = json.dumps(redact_trace_value(dict(arguments)), ensure_ascii=False, default=str)
    return text if len(text) <= PREVIEW_CHARS else text[: PREVIEW_CHARS - 1] + "…"


def make_approver(
    *,
    overlay: Any,
    publisher: Any,
    turn_id: uuid.UUID,
    user_id: int,
    cancel_event: asyncio.Event | None,
    service: Any,
    timeout: float = APPROVAL_TIMEOUT_SECONDS,
):
    """The executor's approver for one Turn: card out, answer back, in order.

    A client that did not declare ``approvals`` gets ``unsupported`` at once —
    the Turn does not wait five minutes for a card nobody can draw.
    """

    async def approve(call: Any, entry: Any, arguments: Mapping[str, Any]) -> str:
        about = overlay.tools.get(call.name)
        if about is None or not overlay.approvals_supported:
            return UNSUPPORTED
        expires = datetime.now(timezone.utc) + timedelta(seconds=timeout)
        publisher.approval_requested(
            {
                "call_id": call.id,
                "connector": about.connector_name,
                "tool": about.tool_name,
                "display": entry.display_name,
                "effect": about.effect,
                "arguments_preview": _preview(arguments),
                "can_always": about.can_always,
                "expires_at": expires.isoformat(),
            }
        )
        decision = await hub.wait(
            turn_id=turn_id,
            call_id=call.id,
            user_id=user_id,
            connector_id=about.connector_id,
            can_always=about.can_always,
            cancel_event=cancel_event,
            timeout=timeout,
        )
        publisher.approval_resolved(call.id, decision)
        if decision == ALWAYS:
            try:
                await service.set_policy(user_id, about.connector_id, about.tool_name, "allow")
            except Exception as exc:  # noqa: BLE001 - this call is still approved
                logger.warning("Could not keep 'always' for %s: %s", about.wire, exc)
        return decision

    return approve

__all__ = [
    "ALLOW_ONCE",
    "ALWAYS",
    "APPROVAL_TIMEOUT_SECONDS",
    "ApprovalHub",
    "CANCELLED",
    "CONNECTOR_GONE",
    "DECISIONS",
    "DENY",
    "TIMED_OUT",
    "UNSUPPORTED",
    "hub",
    "make_approver",
]
