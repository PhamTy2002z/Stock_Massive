"""The only model-facing serialization path for computed Signal Fields."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.stocks.signals import FieldValue, registered_field, schema_description

REGISTERED_FIELD_VALUES_KEY = "_registered_field_values"


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
    return {
        "field": field.name,
        "value": value,
        "unit": field.unit.value,
        "sign": field.sign.value,
        "claim": field.claim.value,
        "kind": field.kind.value,
        "details": allowed_details,
        "refusal": refusal,
    }


def serialize_field_value(answer: FieldValue) -> dict[str, Any]:
    """Serialize a computed answer only if its declaration is the registry's."""

    declared = registered_field(answer.field.name)
    if declared is not answer.field:
        raise ValueError(
            f"{answer.field.name} is not the Signal Registry declaration"
        )
    health = answer.health
    return {
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
        "window_health": {
            "sessions_used": health.sessions_used,
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
        },
    }
