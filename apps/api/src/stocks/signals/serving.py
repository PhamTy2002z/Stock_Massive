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

from collections.abc import Sequence
from datetime import date

from sqlalchemy.orm import Session

from .bars import WindowHealth, prepare_bars
from .fields import FieldReading, FieldValue, FieldWindow, SignalField, Unit
from .issues import SignalIssue


def serve_field(
    session: Session,
    symbol: str,
    field: SignalField,
    *,
    end: date | None = None,
    peers: Sequence[str] | None = None,
) -> FieldValue:
    """Answer for one field and one symbol, or refuse under the gateway's name.

    The field carries its own computation, so there is no pairing for a caller to
    get wrong: serving the Sharpe declaration with the Sortino arithmetic is not
    a mistake to be caught in review, it is not expressible.

    A window the gateway refuses is refused here under the same Signal Issue.
    There is no second path to a bar, and a field that fell back to one would be
    the sixth tool a review checklist fails at.

    ``peers`` is handed straight to the gateway, which is the cross-section its
    liquidity standing is measured against. A caller serving many symbols passes
    it so the Universe is resolved once rather than once per symbol; a caller
    serving one leaves it out and gets the Universe.
    """
    if field.reading is None:
        raise ValueError(f"{field.name} declares no computation to serve")

    frame, health = prepare_bars(
        session,
        symbol,
        field.min_sessions,
        min_sessions=field.min_sessions,
        end=end,
        peers=peers,
    )
    if frame is None or health.refusal is not None:
        return FieldValue(
            field=field, value=None, health=health, refusal=health.refusal
        )

    reading = field.reading(FieldWindow(frame=frame, health=health))
    if reading.value is None:
        return FieldValue(
            field=field,
            value=None,
            health=health,
            # A refusal carries what the computation had reached before it: a
            # field refused for a missing input names the input, and dropping
            # the extras here would leave the surface with a code and nothing to
            # say about it.
            extras=reading.extras,
            refusal=reading.refusal or SignalIssue.INSUFFICIENT_HISTORY,
        )
    return FieldValue(
        field=field,
        value=reading.value,
        health=health,
        extras=reading.extras,
        degraded_reason=degradation_of(field, reading, health),
    )


def degradation_of(
    field: SignalField,
    reading: FieldReading,
    health: WindowHealth,
) -> SignalIssue | None:
    """Which of the reasons an answer is less than whole gets reported.

    A ``FieldValue`` carries one, so the three candidates are ordered rather than
    collected, from the most specific to the most general:

    1. **The computation's own**, because only it knows that its answer rested
       on an input the window merely happens to lack — a band distance on UPCOM
       is degraded for that field and for no other.
    2. **A share-count change under a share-denominated field**, decided from the
       declared ``unit`` rather than from the field's name. Money crosses an
       ex-date and shares do not (``docs/adr/0006``), so this is exactly the set
       of fields whose numbers change unit partway through the window, and
       reading it off the unit is what stops a field from forgetting to say so.
    3. **A window too limit-locked to read a range from**, which is a property of
       the window and applies to whatever was computed over it.
    """
    if reading.degraded_reason is not None:
        return reading.degraded_reason
    if field.unit is Unit.SHARES and not health.quantities_comparable:
        return SignalIssue.VOLUME_BASIS_BREAK
    return health.limit_lock_degradation
