"""Fail-closed validation for the JSON Schema subset tool declarations use."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


class ArgumentSchemaError(ValueError):
    """Arguments do not satisfy the frozen schema offered to the model."""


_COMMON = {"type", "description", "enum"}
_BY_TYPE = {
    "object": {"properties", "required", "additionalProperties"},
    "string": {"minLength", "maxLength"},
    "integer": {"minimum", "maximum"},
    "number": {"minimum", "maximum"},
    "boolean": set(),
    "array": {"items", "minItems", "maxItems"},
}


def assert_supported_schema(schema: Mapping[str, Any], *, path: str = "arguments") -> None:
    """Reject declaration keywords this executor would otherwise ignore."""

    if not isinstance(schema, Mapping):
        raise TypeError(f"{path} schema must be an object")
    declared = schema.get("type")
    kinds = (
        tuple(declared)
        if isinstance(declared, Sequence) and not isinstance(declared, (str, bytes))
        else (declared,)
    )
    if not kinds or any(kind not in _BY_TYPE for kind in kinds):
        raise ValueError(f"{path} schema has unsupported type {declared!r}")
    allowed = set().union(*(_BY_TYPE[kind] for kind in kinds))
    unknown = set(schema) - _COMMON - allowed
    if unknown:
        names = ", ".join(sorted(str(name) for name in unknown))
        raise ValueError(f"{path} schema has unsupported keyword(s): {names}")
    if "enum" in schema and (
        not isinstance(schema["enum"], Sequence)
        or isinstance(schema["enum"], (str, bytes))
    ):
        raise ValueError(f"{path}.enum must be a sequence")
    if "object" in kinds:
        properties = schema.get("properties", {})
        if not isinstance(properties, Mapping):
            raise ValueError(f"{path}.properties must be an object")
        required = schema.get("required", ())
        if not isinstance(required, Sequence) or isinstance(required, (str, bytes)):
            raise ValueError(f"{path}.required must be a sequence")
        missing = set(required) - set(properties)
        if missing:
            raise ValueError(f"{path}.required names undeclared properties")
        additional = schema.get("additionalProperties", True)
        if not isinstance(additional, bool):
            raise ValueError(f"{path}.additionalProperties must be boolean")
        for name, child in properties.items():
            assert_supported_schema(child, path=f"{path}.{name}")
    if "array" in kinds:
        items = schema.get("items")
        if not isinstance(items, Mapping):
            raise ValueError(f"{path}.items must be an object schema")
        assert_supported_schema(items, path=f"{path}[]")


def validate_arguments(arguments: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    """Validate without echoing argument values into the error or trace."""

    _validate(arguments, schema, path="arguments")


def _validate(value: Any, schema: Mapping[str, Any], *, path: str) -> None:
    kind = schema["type"]
    if isinstance(kind, Sequence) and not isinstance(kind, (str, bytes)):
        for candidate in kind:
            try:
                _validate(value, {**schema, "type": candidate}, path=path)
            except ArgumentSchemaError:
                continue
            return
        raise ArgumentSchemaError(f"{path} does not match an allowed type")
    if kind == "object":
        if not isinstance(value, Mapping):
            raise ArgumentSchemaError(f"{path} must be an object")
        properties = schema.get("properties", {})
        for name in schema.get("required", ()):
            if name not in value:
                raise ArgumentSchemaError(f"{path}.{name} is required")
        if schema.get("additionalProperties") is False:
            extras = sorted(set(value) - set(properties))
            if extras:
                raise ArgumentSchemaError(
                    f"{path} contains undeclared field {extras[0]!r}"
                )
        for name, child in properties.items():
            if name in value:
                _validate(value[name], child, path=f"{path}.{name}")
    elif kind == "string":
        if not isinstance(value, str):
            raise ArgumentSchemaError(f"{path} must be a string")
        _bounded(len(value), schema, path, "Length")
    elif kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ArgumentSchemaError(f"{path} must be an integer")
        _numeric(value, schema, path)
    elif kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ArgumentSchemaError(f"{path} must be a number")
        if not math.isfinite(float(value)):
            raise ArgumentSchemaError(f"{path} must be finite")
        _numeric(value, schema, path)
    elif kind == "boolean":
        if not isinstance(value, bool):
            raise ArgumentSchemaError(f"{path} must be boolean")
    elif kind == "array":
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            raise ArgumentSchemaError(f"{path} must be an array")
        _bounded(len(value), schema, path, "Items")
        for index, item in enumerate(value):
            _validate(item, schema["items"], path=f"{path}[{index}]")
    if "enum" in schema and value not in schema["enum"]:
        raise ArgumentSchemaError(f"{path} is not an allowed value")


def _bounded(value: int, schema: Mapping[str, Any], path: str, suffix: str) -> None:
    minimum = schema.get(f"min{suffix}")
    maximum = schema.get(f"max{suffix}")
    if minimum is not None and value < int(minimum):
        raise ArgumentSchemaError(f"{path} is shorter than allowed")
    if maximum is not None and value > int(maximum):
        raise ArgumentSchemaError(f"{path} is longer than allowed")


def _numeric(value: int | float, schema: Mapping[str, Any], path: str) -> None:
    if "minimum" in schema and value < schema["minimum"]:
        raise ArgumentSchemaError(f"{path} is below the minimum")
    if "maximum" in schema and value > schema["maximum"]:
        raise ArgumentSchemaError(f"{path} is above the maximum")


__all__ = [
    "ArgumentSchemaError",
    "assert_supported_schema",
    "validate_arguments",
]
