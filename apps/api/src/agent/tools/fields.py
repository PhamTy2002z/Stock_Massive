"""The only model-facing serialization path for computed Signal Fields."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from src.stocks.signals import (
    FieldValue,
    SignalField,
    SignalIssue,
    WindowHealth,
    registered_field,
    schema_description,
)

REGISTERED_FIELD_VALUES_KEY = "_registered_field_values"
SHARED_WINDOW_HEALTH_KEY = "_shared_window_health"


@dataclass(frozen=True)
class RefusedRegisteredField:
    """A cross-sectional field refused before it could produce a FieldValue."""

    field: SignalField
    refusal: SignalIssue


def sanctioned_interpretation(field: SignalField) -> str:
    """The one sentence that rides beside a value, derived and never stored.

    The complete sanctioned interpretation already rides in the model-visible
    tool schema.  Its opening sentence is the self-contained definition a result
    needs beside the value; repeating the full multi-paragraph caveat for seven
    fields would break the catalog's 4 KB per-call contract.  The surrounding
    mapping key is the field id, so it is not duplicated in the sentence.

    Shared with the Recommendation Validator deliberately: the validator
    compares what a tool serialized against what the registry declares, and a
    second copy of this derivation is how a block comes to pass a check against
    the wrong sentence.
    """

    return field.interpretation.split(". ", 1)[0].rstrip(".") + "."


def registered_field_schema(name: str) -> dict[str, Any]:
    """Describe a registered value once in tool schema, including its null FPR."""

    field = registered_field(name)
    return {"type": ["number", "null"], "description": schema_description(field)}


def serialize_registered_field(
    name: str,
    *,
    value: float | None,
    details: Mapping[str, Any] | None = None,
    refusal: str | None = None,
) -> dict[str, Any]:
    """Project one Signal Registry declaration; arbitrary fields have no route.

    ``null_fpr`` is intentionally absent.  It is stable catalog metadata and is
    already in :func:`registered_field_schema`, so repeating it in every result
    would spend the response budget without adding evidence about this call.
    """

    field = registered_field(name)
    supplied = details or {}
    allowed_details = {
        key: supplied[key] for key in field.output_keys if key in supplied
    }
    interpretation = sanctioned_interpretation(field)
    return {
        "value": value,
        "unit": field.unit.value,
        "sign": field.sign.value,
        "interpretation": interpretation,
        "claim": field.claim.value,
        "kind": field.kind.value,
        "source": field.source.value,
        "details": allowed_details,
        "refusal": refusal,
    }


def serialize_window_health(health: WindowHealth) -> dict[str, Any]:
    """Project the one canonical health object without re-deriving its facts."""

    return {
        "sessions_used": health.sessions_used,
        "first_session": (
            health.first_session.isoformat() if health.first_session is not None else None
        ),
        "last_session": (
            health.last_session.isoformat() if health.last_session is not None else None
        ),
        "limit_lock_days": health.limit_lock_days,
        "band_regime": (
            {
                "exchange": (
                    health.band_regime.exchange.value
                    if health.band_regime.exchange is not None
                    else None
                ),
                "limit_ratio": (
                    float(health.band_regime.limit_ratio)
                    if health.band_regime.limit_ratio is not None
                    else None
                ),
                "anchor_basis": (
                    health.band_regime.anchor_basis.value
                    if health.band_regime.anchor_basis is not None
                    else None
                ),
                "exchange_as_of": health.band_regime.exchange_as_of.value,
                "uniform": health.band_regime.uniform,
            }
            if health.band_regime is not None
            else None
        ),
        "adjustment": {
            "applied": health.adjustment.applied,
            "actions_applied": health.adjustment.actions_applied,
            "actions_in_window": health.adjustment.actions_in_window,
        },
        "adtv_percentile": (
            health.adtv.percentile if health.adtv is not None else None
        ),
        "round_trip_actionable": health.sessions_used >= 3,
        "settlement_floor_sessions": 3,
        "refusal": health.refusal.value if health.refusal is not None else None,
        "degradations": [reason.value for reason in health.degradations],
    }


def serialize_field_value(
    answer: FieldValue, *, include_window_health: bool = True
) -> dict[str, Any]:
    """Serialize a computed answer only if its declaration is the registry's."""

    declared = registered_field(answer.field.name)
    if declared is not answer.field:
        raise ValueError(
            f"{answer.field.name} is not the Signal Registry declaration"
        )
    health = answer.health
    payload = {
        **serialize_registered_field(
            answer.field.name,
            value=answer.value,
            details=answer.extras,
            refusal=answer.refusal.value if answer.refusal is not None else None,
        ),
        "degraded_reason": (
            answer.degraded_reason.value
            if answer.degraded_reason is not None
            else None
        ),
    }
    if include_window_health:
        payload["window_health"] = serialize_window_health(health)
    return payload


def serialize_refused_field(answer: RefusedRegisteredField) -> dict[str, Any]:
    """Keep a registered cross-sectional slot visible when the sample refused."""

    declared = registered_field(answer.field.name)
    if declared is not answer.field:
        raise ValueError(
            f"{answer.field.name} is not the Signal Registry declaration"
        )
    return {
        **serialize_registered_field(
            answer.field.name,
            value=None,
            refusal=answer.refusal.value,
        ),
        "degraded_reason": None,
    }
