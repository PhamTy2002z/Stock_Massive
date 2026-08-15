"""The one way a registered field is answered for one symbol.

There is one gateway to bars, so there is one path from a gateway to an answer.
Written once here rather than once per computation module, because a second
spelling of it is a second place a field could quietly reach a bar some other
way — and the whole thesis of ``prepare_bars()`` is that no such place exists.

What it does is small and is meant to be: ask the gateway for the window the
field declares it needs, hand back the gateway's own refusal where there is one,
and otherwise run the field's own computation and dress the result with the
window's health. Every field in the package goes through it, and none of them
takes a window length or a degradation rule of its own.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from .bars import prepare_bars
from .fields import FieldValue, SignalField
from .issues import SignalIssue


def serve_field(
    session: Session,
    symbol: str,
    field: SignalField,
    *,
    end: date | None = None,
) -> FieldValue:
    """Answer for one field and one symbol, or refuse under the gateway's name.

    The field carries its own computation, so there is no pairing for a caller to
    get wrong: serving the Sharpe declaration with the Sortino arithmetic is not
    a mistake to be caught in review, it is not expressible.

    A window the gateway refuses is refused here under the same Signal Issue.
    There is no second path to a bar, and a field that fell back to one would be
    the sixth tool a review checklist fails at.
    """
    if field.reading is None:
        raise ValueError(f"{field.name} declares no computation to serve")

    frame, health = prepare_bars(
        session,
        symbol,
        field.min_sessions,
        min_sessions=field.min_sessions,
        end=end,
    )
    if frame is None or health.refusal is not None:
        return FieldValue(
            field=field, value=None, health=health, refusal=health.refusal
        )

    reading = field.reading(frame)
    if reading.value is None:
        return FieldValue(
            field=field,
            value=None,
            health=health,
            refusal=reading.refusal or SignalIssue.INSUFFICIENT_HISTORY,
        )
    return FieldValue(
        field=field,
        value=reading.value,
        health=health,
        extras=reading.extras,
        degraded_reason=health.limit_lock_degradation,
    )
