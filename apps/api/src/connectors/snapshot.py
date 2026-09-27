"""What a server's tool list becomes before the model is shown any of it.

A server's ``tools/list`` is written by whoever runs the server. Every field in
it is untrusted, and two of them are dangerous in their own way: the name
becomes an identifier the model calls, and the description becomes prompt text.
So a tool is kept only when

- its name can be made a wire name (``mcp__<connector>__<tool>``, at most 64 of
  ``[A-Za-z0-9_]``) that no other kept tool already has — a collision after
  cleaning or cutting gets a hash suffix, it never replaces the first;
- its input schema, after dropping keywords that only annotate, is inside the
  subset the executor validates (``agent/schema_validation.py``);
- neither its description nor any parameter description trips
  ``threat_patterns`` — a description that addresses the model is an attempt to
  instruct it, and it is refused rather than sanitised;
- it is among the first :data:`MAX_TOOLS_PER_CONNECTOR`.

Everything refused is recorded with a reason, so the settings page can say why a
tool the server offers is missing. The fingerprint covers exactly what the model
would see, so any change to it is a change the user is asked to accept.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from src.agent.schema_validation import assert_supported_schema
from src.agent.threat_patterns import findings_in

MAX_TOOLS_PER_CONNECTOR = 50
MAX_WIRE_NAME = 64
MAX_DESCRIPTION_CHARS = 1_000
WIRE_PREFIX = "mcp__"

#: Keywords that describe a schema without constraining it. Dropped, so a
#: pydantic-generated schema (which titles everything) is not refused for it.
_ANNOTATION_KEYWORDS = frozenset(
    {"title", "default", "examples", "$schema", "$comment", "deprecated", "readOnly", "writeOnly", "format", "pattern"}
)
_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9_]+")


@dataclass(frozen=True)
class Snapshot:
    tools: tuple[dict[str, Any], ...]
    dropped: tuple[dict[str, str], ...]
    fingerprint: str
    truncated: int = 0


def clean_slug(text: str, *, limit: int = 20) -> str:
    slug = _UNSAFE_NAME.sub("_", text.strip().lower()).strip("_")[:limit].strip("_")
    return slug or "connector"


def _wire_name(slug: str, name: str, taken: set[str]) -> str:
    base = f"{WIRE_PREFIX}{slug}__{_UNSAFE_NAME.sub('_', name).strip('_') or 'tool'}"
    candidate = base[:MAX_WIRE_NAME]
    if candidate not in taken:
        return candidate
    suffix = hashlib.sha1(name.encode()).hexdigest()[:6]
    candidate = f"{base[: MAX_WIRE_NAME - 7]}_{suffix}"
    counter = 1
    while candidate in taken:
        # Two names with the same hash prefix: vanishingly rare, and still
        # never an overwrite.
        counter += 1
        candidate = f"{base[: MAX_WIRE_NAME - 9]}_{suffix[:4]}{counter:02d}"
    return candidate


def normalise_schema(schema: Any) -> dict[str, Any]:
    """The schema with annotation-only keywords removed and ``X | None`` folded.

    An optional parameter pydantic writes as ``anyOf: [X, {type: null}]`` becomes
    ``X``: the model omits an optional parameter rather than sending null.
    Anything else outside the subset is left for :func:`assert_supported_schema`
    to refuse.
    """
    if not isinstance(schema, Mapping):
        raise ValueError("the input schema is not an object")
    cleaned: dict[str, Any] = {}
    for key, value in schema.items():
        if key in _ANNOTATION_KEYWORDS:
            continue
        if key == "properties" and isinstance(value, Mapping):
            cleaned[key] = {str(name): normalise_schema(child) for name, child in value.items()}
        elif key == "items" and isinstance(value, Mapping):
            cleaned[key] = normalise_schema(value)
        else:
            cleaned[key] = value
    options = cleaned.get("anyOf")
    if isinstance(options, list):
        concrete = [item for item in options if not (isinstance(item, Mapping) and item.get("type") == "null")]
        if len(concrete) == 1 and len(options) == 2:
            merged = {k: v for k, v in cleaned.items() if k != "anyOf"}
            merged.update(normalise_schema(concrete[0]))
            cleaned = merged
        elif concrete and len(concrete) == len(options) and all(
            isinstance(item, Mapping) and isinstance(item.get("type"), str) for item in concrete
        ):
            # ``string | array of string``: one schema whose type is the list,
            # when no two options claim the same keyword.
            parts = [normalise_schema(item) for item in concrete]
            keys = [key for part in parts for key in part if key != "type"]
            if len(keys) == len(set(keys)) and len({part["type"] for part in parts}) == len(parts):
                merged = {k: v for k, v in cleaned.items() if k != "anyOf"}
                for part in parts:
                    merged.update({k: v for k, v in part.items() if k != "type"})
                merged["type"] = [part["type"] for part in parts]
                cleaned = merged
    if cleaned.get("type") == "object":
        cleaned.setdefault("properties", {})
    return cleaned


def _flagged(tool: Mapping[str, Any]) -> list[str]:
    texts = [str(tool.get("description") or ""), str(tool.get("title") or "")]
    stack = [tool.get("input_schema") or {}]
    while stack:
        node = stack.pop()
        if isinstance(node, Mapping):
            if isinstance(node.get("description"), str):
                texts.append(node["description"])
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return sorted({finding for text in texts for finding in findings_in(text)})


def fingerprint(tools: Iterable[Mapping[str, Any]]) -> str:
    material = [
        {key: tool.get(key) for key in ("name", "description", "schema", "read_only", "destructive")}
        for tool in sorted(tools, key=lambda item: str(item.get("name")))
    ]
    return hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def build(slug: str, listed: Sequence[Mapping[str, Any]]) -> Snapshot:
    """Keep, clean and name the tools a server listed. See the module docstring."""
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, str]] = []
    taken: set[str] = set()
    seen_names: set[str] = set()
    truncated = 0
    for tool in listed:
        name = str(tool.get("name") or "").strip()
        if not name:
            dropped.append({"name": "", "reason": "no_name"})
            continue
        if name in seen_names:
            dropped.append({"name": name, "reason": "duplicate_name"})
            continue
        seen_names.add(name)
        if len(kept) >= MAX_TOOLS_PER_CONNECTOR:
            truncated += 1
            dropped.append({"name": name, "reason": "over_tool_limit"})
            continue
        findings = _flagged(tool)
        if findings:
            dropped.append({"name": name, "reason": "suspicious_text:" + ",".join(findings)})
            continue
        try:
            schema = normalise_schema(tool.get("input_schema") or {"type": "object"})
            if schema.get("type") != "object":
                raise ValueError("the input schema is not an object schema")
            assert_supported_schema(schema)
        except (TypeError, ValueError) as exc:
            dropped.append({"name": name, "reason": f"unsupported_schema: {str(exc)[:160]}"})
            continue
        annotations = tool.get("annotations") or {}
        wire = _wire_name(slug, name, taken)
        taken.add(wire)
        kept.append(
            {
                "name": name,
                "wire": wire,
                "title": str(annotations.get("title") or tool.get("title") or "")[:120],
                "description": str(tool.get("description") or "").strip()[:MAX_DESCRIPTION_CHARS],
                "schema": schema,
                "read_only": annotations.get("read_only_hint"),
                "destructive": annotations.get("destructive_hint"),
            }
        )
    return Snapshot(tools=tuple(kept), dropped=tuple(dropped), fingerprint=fingerprint(kept), truncated=truncated)


def from_mcp(tools: Iterable[Any]) -> list[dict[str, Any]]:
    """``mcp_types.Tool`` objects as the plain mappings :func:`build` reads."""
    listed = []
    for tool in tools:
        annotations = tool.annotations.model_dump() if tool.annotations is not None else {}
        listed.append(
            {
                "name": tool.name,
                "title": tool.title,
                "description": tool.description,
                "input_schema": tool.input_schema,
                "annotations": annotations,
            }
        )
    return listed


__all__ = [
    "MAX_TOOLS_PER_CONNECTOR",
    "MAX_WIRE_NAME",
    "Snapshot",
    "WIRE_PREFIX",
    "build",
    "clean_slug",
    "fingerprint",
    "from_mcp",
    "normalise_schema",
]
