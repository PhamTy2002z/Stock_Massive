"""Model-facing contract shared by both Signal Tool registrations and eval."""

from __future__ import annotations

from .registry import object_schema

SIGNAL_AXES = ("technical", "fundamental", "money_flow", "news")

LIST_FIELDS_DESCRIPTION = (
    "List every Signal Field this system can compute, with the unit it is in "
    "and the minimum number of sessions it needs. Use it when a figure you "
    "were given is refused for want of history, or when the evidence you hold "
    "does not answer the question this symbol raises."
)
LIST_FIELDS_SCHEMA = object_schema(
    {
        "axis": {
            "type": "string",
            "enum": list(SIGNAL_AXES),
            "description": (
                "Restrict the list to one axis. Omit it for the whole catalog."
            ),
        }
    }
)

GET_FIELD_DESCRIPTION = (
    "Read one Signal Field out of this system's own store for one symbol, on "
    "the most recent closed session. Returns the figure with its unit, its "
    "sanctioned reading, its health and the date it is as of — or the named "
    "reason the store cannot answer it. There is no way to ask for a session "
    "that has not closed. It returns ONE number and is not the way to draw "
    "anything: a shape over time or across buckets is what run_study is for."
)
GET_FIELD_SCHEMA = object_schema(
    {
        "field_id": {
            "type": "string",
            "minLength": 1,
            "description": (
                "A fieldId from list_fields, exactly as it is spelled there."
            ),
        },
        "symbol": {
            "type": "string",
            "minLength": 1,
            "description": (
                "The ticker to read it for. Omit it where the caller is already "
                "opened for one symbol, which is what an Analysis is; naming a "
                "different one there is refused."
            ),
        },
    },
    ("field_id",),
)

GET_SERIES_DESCRIPTION = (
    "Read one Signal Field for one symbol across the most recent closed "
    "sessions, as a series rather than a single number. Returns a small summary "
    "— first, last, min, max, median, how many sessions answered — plus a "
    "frameId. The series itself is kept where the canvas can draw it and is "
    "never put in this conversation: pass the frameId to render_canvas to show "
    "it to the reader. Use it when the question is about a shape over time — a "
    "trend, a range, a comparison across sessions — and there is no study for it."
)
GET_SERIES_SCHEMA = object_schema(
    {
        "field_id": {
            "type": "string",
            "minLength": 1,
            "description": (
                "A fieldId from list_fields, exactly as it is spelled there."
            ),
        },
        "symbol": {
            "type": "string",
            "minLength": 1,
            "description": "The ticker to read it for, from the Universe.",
        },
        "sessions": {
            "type": "integer",
            "description": (
                "How many recent closed sessions to read. Clamped to what this "
                "field can afford; the answer says how many were actually read."
            ),
        },
    },
    ("field_id", "symbol"),
)

__all__ = [
    "GET_FIELD_DESCRIPTION",
    "GET_FIELD_SCHEMA",
    "GET_SERIES_DESCRIPTION",
    "GET_SERIES_SCHEMA",
    "LIST_FIELDS_DESCRIPTION",
    "LIST_FIELDS_SCHEMA",
    "SIGNAL_AXES",
]
