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

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from ..trading_day import latest_trading_day
from .bars import WindowHealth, prepare_bars
from .cross_sectional import CROSS_SECTION_MIN_SYMBOLS, percentile_of
from .fields import FieldReading, FieldValue, FieldWindow, SignalField, Unit
from .fundamentals import fundamentals_on_or_before
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


@dataclass(frozen=True)
class CrossSection:
    """One cross-sectional field answered for a whole sample, or refused for it.

    **The exclusions are part of the answer, not swept out of it.** A ranking
    over the symbols that happened to have enough history is a different ranking
    from one over the Universe, and a reader cannot tell the two apart unless
    the number ranked and the names dropped travel with the percentiles. Every
    exclusion carries the Signal Issue that caused it, so "not listed long
    enough" and "no quarterly statement stored" stay different facts.

    ``refusal`` is the whole call declining, which happens on one condition: too
    few symbols survived for a percentile to mean anything. Then ``values`` is
    empty and the exclusions are still reported, because the reason the call
    could not be answered is exactly what a surface has to say instead.
    """

    field: SignalField
    as_of: date | None
    ranked: int
    values: Mapping[str, FieldValue]
    excluded: Mapping[str, SignalIssue]
    refusal: SignalIssue | None = None


def serve_cross_section(
    session: Session,
    symbols: Sequence[str],
    field: SignalField,
    *,
    end: date | None = None,
) -> CrossSection:
    """Rank one field across a sample of symbols on one dated cutoff.

    Every symbol reaches its bars through the same gateway one symbol would, at
    the same ``min_sessions``, against the same cutoff — a percentile whose
    members were measured on different days is not a percentile. The peer list
    is handed to the gateway once per symbol rather than resolved inside it, so
    the Universe is read once for the call.

    The quarterly statements every factor field needs are loaded for the whole
    sample in a single query before the loop, not per symbol. They are loaded
    for every cross-section rather than only for the fields that read them: one
    indexed query answering a hundred symbols is cheaper than the declaration it
    would take to skip it, and a field that does not read the standing is handed
    one it ignores.

    **The cost this does pay is the gateway's own liquidity standing**, which is
    measured per prepared window and therefore once per symbol here, each time
    over the same peers and the same twenty sessions. On a hundred-symbol sample
    that is a hundred repetitions of one cross-sectional read. It is accepted
    rather than special-cased: the alternative is a second path into peer
    sessions that bypasses ``prepare_bars()``, and the whole thesis of the
    gateway is that no such path exists. The fix, when it is worth making, is to
    let the gateway take a resolved peer standing rather than to let a field
    around it.
    """
    if field.ranked is None:
        raise ValueError(
            f"{field.name} is answered for one symbol rather than across a "
            "sample, so it is served through serve_field"
        )

    names = tuple(dict.fromkeys(symbol.upper() for symbol in symbols))
    end = end or latest_trading_day(session)
    if end is None or not names:
        return CrossSection(
            field=field,
            as_of=end,
            ranked=0,
            values={},
            excluded={},
            refusal=SignalIssue.INSUFFICIENT_CROSS_SECTION,
        )

    statements = fundamentals_on_or_before(session, names, end)
    measured: dict[str, tuple[FieldReading, WindowHealth]] = {}
    excluded: dict[str, SignalIssue] = {}
    for name in names:
        frame, health = prepare_bars(
            session,
            name,
            field.min_sessions,
            min_sessions=field.min_sessions,
            end=end,
            peers=names,
        )
        if frame is None or health.refusal is not None:
            excluded[name] = health.refusal or SignalIssue.INSUFFICIENT_HISTORY
            continue
        reading = field.ranked(
            FieldWindow(
                frame=frame, health=health, fundamental=statements.get(name)
            )
        )
        if reading.value is None:
            excluded[name] = reading.refusal or SignalIssue.INSUFFICIENT_HISTORY
            continue
        measured[name] = (reading, health)

    if len(measured) < CROSS_SECTION_MIN_SYMBOLS:
        return CrossSection(
            field=field,
            as_of=end,
            ranked=len(measured),
            values={},
            excluded=excluded,
            refusal=SignalIssue.INSUFFICIENT_CROSS_SECTION,
        )

    sample = [reading.value for reading, _ in measured.values()]
    values = {
        name: FieldValue(
            field=field,
            value=percentile_of(reading.value, sample),  # type: ignore[arg-type]
            health=health,
            extras={
                **reading.extras,
                # The two a percentile may not ship without, and they are the
                # call's rather than the symbol's: every member was ranked in
                # the same sample on the same date.
                "n": len(sample),
                "as_of": end.isoformat(),
                "excluded_symbols": len(excluded),
            },
            degraded_reason=degradation_of(field, reading, health),
        )
        for name, (reading, health) in measured.items()
    }
    return CrossSection(
        field=field,
        as_of=end,
        ranked=len(sample),
        values=values,
        excluded=excluded,
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
