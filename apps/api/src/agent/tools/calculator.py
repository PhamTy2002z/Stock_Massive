"""Arithmetic the answer needs, done by the host and printed with its formula.

A growth rate, a P/B recomputed at today's price, a difference between two
quarters: none of these is printed in any source, so before this tool the figure
check could only label them ``chưa kiểm chứng`` — and it did, on every Turn that
said "tăng 52,7% từ đầu năm". The model still decides *what* to compute. The
host does the arithmetic, prints the formula and the inputs beside the result,
and the figure check accepts the result only when every input is itself a figure
this Turn read from a source (``evidence/grounding.py``). A calculation over an
invented input is an invented number with extra steps, and is labelled as one.

The operations are a fixed list rather than an expression language. Six cover
what an equity answer computes, and a list is a surface the model cannot turn
into code execution.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from ..registry import (
    ContentTrust,
    ToolAccess,
    ToolConcurrency,
    ToolContext,
    ToolEffect,
    ToolEntry,
    ToolIdempotency,
    ToolPermission,
    object_schema,
    register,
)

TOOLSET = "market_data"
TOOL_NAME = "calculate"
MAX_INPUTS = 12

#: operation → (how many inputs, the result's default unit, the formula shape).
OPERATIONS: Mapping[str, tuple[int | None, str | None, str]] = {
    "divide": (2, "lần", "{a} / {b}"),
    "percent_of": (2, "%", "{a} / {b} × 100"),
    "percent_change": (2, "%", "({a} − {b}) / {b} × 100"),
    "difference": (2, None, "{a} − {b}"),
    "sum": (None, None, " + "),
    "multiply": (None, None, " × "),
}


class CalculationError(ValueError):
    pass


def _decimal(value: Any, label: str) -> Decimal:
    if isinstance(value, bool):
        raise CalculationError(f"{label} is not a number")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise CalculationError(f"{label} is not a number") from exc
    if not number.is_finite():
        raise CalculationError(f"{label} is not a finite number")
    return number


def vn_number(value: Decimal, decimals: int) -> str:
    """A number the way a Vietnamese page prints it: ``1.234,56``."""
    quantum = Decimal(1).scaleb(-decimals)
    rounded = value.quantize(quantum, rounding=ROUND_HALF_UP)
    text = f"{rounded:,.{decimals}f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def _written(value: Decimal, unit: str) -> str:
    decimals = max(0, -int(value.normalize().as_tuple().exponent)) if value != value.to_integral() else 0
    text = vn_number(value, min(decimals, 4))
    return f"{text}%" if unit == "%" else f"{text} {unit}".rstrip()


def compute(operation: str, inputs: Sequence[Mapping[str, Any]], *, decimals: int = 2) -> dict[str, Any]:
    """Run one operation over labelled inputs; the whole result, formula included."""
    if operation not in OPERATIONS:
        raise CalculationError(f"operation must be one of {', '.join(OPERATIONS)}")
    arity, default_unit, shape = OPERATIONS[operation]
    if not 1 <= len(inputs) <= MAX_INPUTS or (arity is not None and len(inputs) != arity):
        raise CalculationError(
            f"{operation} takes {arity if arity is not None else f'1 to {MAX_INPUTS}'} inputs"
        )
    values: list[Decimal] = []
    shown: list[str] = []
    cleaned: list[dict[str, Any]] = []
    for position, item in enumerate(inputs, start=1):
        label = str(item.get("label") or f"giá trị {position}").strip()[:80]
        unit = str(item.get("unit") or "").strip()[:20]
        number = _decimal(item.get("value"), label)
        values.append(number)
        shown.append(f"{label} {_written(number, unit)}")
        cleaned.append({"label": label, "value": str(number), "unit": unit})

    if operation in ("divide", "percent_of", "percent_change") and values[1] == 0:
        raise CalculationError("the second input is zero")
    if operation == "divide":
        result = values[0] / values[1]
        formula = shape.format(a=shown[0], b=shown[1])
    elif operation == "percent_of":
        result = values[0] / values[1] * 100
        formula = shape.format(a=shown[0], b=shown[1])
    elif operation == "percent_change":
        result = (values[0] - values[1]) / values[1] * 100
        formula = shape.format(a=shown[0], b=shown[1])
    elif operation == "difference":
        result = values[0] - values[1]
        formula = shape.format(a=shown[0], b=shown[1])
    elif operation == "sum":
        result = sum(values, Decimal(0))
        formula = shape.join(shown)
    else:
        result = Decimal(1)
        for number in values:
            result *= number
        formula = shape.join(shown)

    unit = default_unit if default_unit is not None else cleaned[0]["unit"]
    rounded = result.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    printed = f"{vn_number(rounded, decimals)}%" if unit == "%" else f"{vn_number(rounded, decimals)} {unit}".rstrip()
    return {
        "operation": operation,
        "inputs": cleaned,
        "formula": formula,
        "result": str(rounded),
        "unit": unit,
        "result_text": printed,
    }


class CalculatorTools:
    def entries(self) -> tuple[ToolEntry, ...]:
        return (
            ToolEntry(
                name=TOOL_NAME,
                toolset=TOOLSET,
                description=(
                    "Compute a number the answer states but no source prints: a "
                    "ratio (divide), a share (percent_of), a growth or change "
                    "(percent_change: first input is the new value, second the old), "
                    "a difference, a sum or a product. Use it for every derived "
                    "figure instead of computing in your head. Each input must be a "
                    "figure you read from a tool in this turn, with its label and "
                    "unit; the result comes back with its formula, and a result built "
                    "on an input no tool returned is marked unverified."
                ),
                schema=object_schema(
                    {
                        "operation": {"type": "string", "enum": list(OPERATIONS)},
                        "inputs": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": MAX_INPUTS,
                            "items": object_schema(
                                {
                                    "label": {"type": "string"},
                                    "value": {"type": "number"},
                                    "unit": {"type": "string"},
                                },
                                ("label", "value", "unit"),
                            ),
                        },
                        "decimals": {"type": "integer", "minimum": 0, "maximum": 4},
                    },
                    ("operation", "inputs"),
                ),
                handler=self.calculate,
                display_name="Tính toán",
                summarise=_summarise,
                effect=ToolEffect.READ,
                idempotency=ToolIdempotency.IDEMPOTENT,
                # No boundary is crossed; STORE is the registry's local-side access.
                access=ToolAccess.STORE,
                content_trust=ContentTrust.TRUSTED_STRUCTURED,
                concurrency=ToolConcurrency.PARALLEL_SAFE,
                permission=ToolPermission.ALLOW,
                is_async=False,
                timeout_seconds=5.0,
                contract_version="1",
                max_result_size_chars=4_000,
            ),
        )

    def calculate(self, context: ToolContext, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        decimals = arguments.get("decimals")
        done = compute(
            str(arguments.get("operation") or ""),
            list(arguments.get("inputs") or ()),
            decimals=2 if decimals is None else int(decimals),
        )
        return {
            **done,
            "publisher": "Máy tính của hệ thống",
            "source": "calculator",
            "source_class": "store",
            "evidence_kind": "calculation",
            "title": f"Phép tính: {done['formula']}"[:240],
            "excerpt": f"Phép tính: {done['formula']} = {done['result_text']}",
        }


def _summarise(arguments: Mapping[str, Any]) -> str:
    labels = [str(item.get("label") or "") for item in arguments.get("inputs") or () if isinstance(item, Mapping)]
    return f"Tính toán · {arguments.get('operation') or '?'} · {', '.join(label for label in labels if label)[:80]}"


def register_calculator_tools() -> tuple[ToolEntry, ...]:
    return tuple(register(entry) for entry in CalculatorTools().entries())


__all__ = [
    "CalculationError",
    "CalculatorTools",
    "OPERATIONS",
    "TOOL_NAME",
    "compute",
    "register_calculator_tools",
    "vn_number",
]
