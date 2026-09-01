"""The typed parts a Turn produces, and the allowlist that keeps them light.

What is asserted here is the property that cannot be seen at runtime: a progress
part travels on a channel the browser renders, so the day something hands it a
page's text or a model's sentence, the part has to arrive without it. The
allowlist is the mechanism, and these are its tests.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from src.agent.parts import (
    ATTEMPT_CANCELLED,
    ATTEMPT_COMPLETED,
    ATTEMPT_ERROR,
    ATTEMPT_RUNNING,
    ATTEMPT_STATUSES,
    MAX_CODE_CHARS,
    PROGRESS_FIELDS,
    PROGRESS_WIRE_FIELDS,
    RECOVERY_ACTIONS,
    RECOVERY_COMPRESS,
    RECOVERY_EMPTY_NUDGE,
    RECOVERY_LOWER_OUTPUT_CAP,
    ProgressKind,
    ProgressPart,
    progress_payload,
    wire_parts,
)

AT = "2026-09-01T09:00:00+00:00"


def part(kind: ProgressKind, seq: int = 1, **fields) -> ProgressPart:
    return ProgressPart(
        seq=seq,
        kind=kind,
        round=0,
        payload=progress_payload(kind, **fields),
        at=AT,
    )


def test_every_kind_declares_what_it_may_carry():
    """A kind with no entry would be a part nobody decided the shape of."""
    assert set(PROGRESS_FIELDS) == set(ProgressKind)


def test_the_closed_vocabularies_are_the_ones_the_loop_reports_with():
    assert ATTEMPT_STATUSES == {
        ATTEMPT_RUNNING,
        ATTEMPT_COMPLETED,
        ATTEMPT_ERROR,
        ATTEMPT_CANCELLED,
    }
    assert RECOVERY_ACTIONS == {
        RECOVERY_COMPRESS,
        RECOVERY_LOWER_OUTPUT_CAP,
        RECOVERY_EMPTY_NUDGE,
    }


def test_a_key_nobody_allowlisted_is_dropped_rather_than_carried():
    payload = progress_payload(
        ProgressKind.TOOL_ROUND,
        calls=2,
        external_used=1,
        call_ids=["call_0", "call_1"],
        # What the round actually searched for. It belongs on the tool.call
        # channel and in the Trace, and a page's neighbourhood must not reach a
        # rendered channel a second time under a name nobody reviewed.
        query="lãi suất huy động",
    )

    assert payload == {
        "calls": 2,
        "external_used": 1,
        "call_ids": ["call_0", "call_1"],
    }


def test_a_kind_nobody_declared_is_refused_outright():
    """No shape to fall back to, so there is nothing safe to publish."""
    with pytest.raises(ValueError):
        progress_payload("verification_pass")  # type: ignore[arg-type]


def test_a_declared_kind_named_as_a_string_resolves_to_the_enum():
    """The enum is the authority on the shape, whichever way a caller spells it."""
    assert progress_payload("rounds_exhausted", rounds=4) == {"rounds": 4}  # type: ignore[arg-type]


def test_prose_cannot_ride_in_on_an_allowed_key():
    """The barrier is by key *and* by value: a code is short, prose is not."""
    payload = progress_payload(
        ProgressKind.TOOLS_HALTED, reason="x" * (MAX_CODE_CHARS + 1)
    )

    assert payload == {}


def test_a_structured_payload_is_never_admitted():
    """A tool's own object is how a page's text would arrive here."""
    payload = progress_payload(
        ProgressKind.LANE_SELECTED,
        lane="deep",
        reason={"keyword": "memo", "page": "<html>…</html>"},
    )

    assert payload == {"lane": "deep"}


def test_the_wire_shape_is_the_five_fields_the_transport_restates():
    wire = part(
        ProgressKind.MODEL_ATTEMPT, status=ATTEMPT_ERROR, terminal_reason="gateway_timeout"
    ).as_wire()

    assert tuple(wire) == PROGRESS_WIRE_FIELDS
    assert wire == {
        "seq": 1,
        "kind": "model_attempt",
        "round": 0,
        "payload": {"status": "error", "terminal_reason": "gateway_timeout"},
        "at": AT,
    }


def test_a_none_terminal_reason_is_carried_rather_than_dropped():
    """A reader must not have to tell "no reason" from "no such key"."""
    payload = progress_payload(
        ProgressKind.MODEL_ATTEMPT, status=ATTEMPT_COMPLETED, terminal_reason=None
    )

    assert payload == {"status": "completed", "terminal_reason": None}


def test_the_deadline_part_carries_nothing_and_still_has_a_payload():
    assert part(ProgressKind.DEADLINE).as_wire()["payload"] == {}


def test_the_ordinal_is_what_orders_the_trail():
    """Not the publisher's sequence: a Turn publishes deltas between its parts."""
    parts = [
        part(ProgressKind.LANE_SELECTED, seq=1, lane="light", reason="default"),
        part(ProgressKind.MODEL_ATTEMPT, seq=2, status=ATTEMPT_RUNNING),
        part(ProgressKind.MODEL_ATTEMPT, seq=3, status=ATTEMPT_COMPLETED),
    ]

    trail = wire_parts(parts)

    assert [entry["seq"] for entry in trail] == [1, 2, 3]
    assert [entry["kind"] for entry in trail] == [
        "lane_selected",
        "model_attempt",
        "model_attempt",
    ]


def test_a_part_cannot_be_edited_after_it_happened():
    """An account of an event that can be rewritten is not an account."""
    with pytest.raises(FrozenInstanceError):
        part(ProgressKind.DEADLINE).seq = 9  # type: ignore[misc]
