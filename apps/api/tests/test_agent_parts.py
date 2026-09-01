"""The typed parts a Turn produces, and the allowlist that keeps them light.

What is asserted here is the property that cannot be seen at runtime: a progress
part travels on a channel the browser renders, so the day something hands it a
page's text or a model's sentence, the part has to arrive without it. The
allowlist is the mechanism, and these are its tests.

A question part is held to the mirror-image rule. Progress must never be the
thing that ends a Turn, so what it cannot carry is dropped; a question *is* the
ending, and a card the reader cannot answer is a dead end — so what it cannot
carry raises instead.
"""

from __future__ import annotations

import uuid
from dataclasses import FrozenInstanceError

import pytest

from src.agent.parts import (
    ATTEMPT_CANCELLED,
    ATTEMPT_COMPLETED,
    ATTEMPT_ERROR,
    ATTEMPT_RUNNING,
    ATTEMPT_STATUSES,
    DEFAULT_SKIP_LABEL,
    MAX_CODE_CHARS,
    MAX_QUESTION_LABEL_CHARS,
    MAX_QUESTION_OPTIONS,
    MAX_QUESTION_PROMPT_CHARS,
    MIN_QUESTION_OPTIONS,
    PROGRESS_FIELDS,
    PROGRESS_WIRE_FIELDS,
    QUESTION_ANSWERED,
    QUESTION_PENDING,
    QUESTION_SKIPPED,
    QUESTION_STATES,
    QUESTION_SUPERSEDED,
    QUESTION_WIRE_FIELDS,
    RECOVERY_ACTIONS,
    RECOVERY_COMPRESS,
    RECOVERY_EMPTY_NUDGE,
    RECOVERY_LOWER_OUTPUT_CAP,
    ProgressKind,
    ProgressPart,
    QuestionOption,
    QuestionPart,
    progress_payload,
    question_option_ids,
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


# -- the question a Turn can end with --------------------------------------


def options(count: int = 2) -> list[QuestionOption]:
    return [
        QuestionOption(id=f"opt_{index}", label=f"Lựa chọn {index}")
        for index in range(count)
    ]


def question(**overrides) -> QuestionPart:
    fields = {
        "question_id": str(uuid.uuid4()),
        "prompt": "Bạn đang giữ VCB hay tính mua mới?",
        "options": options(),
    }
    fields.update(overrides)
    return QuestionPart(**fields)


def test_the_four_outcomes_are_the_ones_a_row_can_hold():
    assert QUESTION_STATES == (
        QUESTION_PENDING,
        QUESTION_ANSWERED,
        QUESTION_SKIPPED,
        QUESTION_SUPERSEDED,
    )


def test_a_question_is_single_select_until_something_says_otherwise():
    """The flag exists from the first version; the safe default is one choice."""
    assert question().multi_select is False
    assert question(multi_select=True).multi_select is True


def test_skipping_is_always_offered_and_says_what_it_costs():
    """No card is a door: the default label promises the work still runs."""
    assert question().skip_label == DEFAULT_SKIP_LABEL
    assert "giả định" in DEFAULT_SKIP_LABEL


def test_the_wire_shape_is_what_the_row_and_the_client_both_read():
    part = question(
        question_id="3f8d4c1a-0000-4000-8000-000000000001",
        options=[
            QuestionOption(id="hold", label="Đang giữ", detail="Đã có vị thế"),
            QuestionOption(id="new", label="Mua mới"),
        ],
    )

    wire = part.as_wire()

    assert tuple(wire) == QUESTION_WIRE_FIELDS
    assert wire == {
        "question_id": "3f8d4c1a-0000-4000-8000-000000000001",
        "prompt": "Bạn đang giữ VCB hay tính mua mới?",
        "options": [
            {"id": "hold", "label": "Đang giữ", "detail": "Đã có vị thế"},
            {"id": "new", "label": "Mua mới", "detail": None},
        ],
        "multi_select": False,
        "skip_label": DEFAULT_SKIP_LABEL,
    }


def test_one_choice_is_not_a_question_and_five_is_a_form():
    """The bound is the discipline: an unanswerable ask should be research."""
    with pytest.raises(ValueError):
        question(options=options(MIN_QUESTION_OPTIONS - 1))
    with pytest.raises(ValueError):
        question(options=options(MAX_QUESTION_OPTIONS + 1))
    assert len(question(options=options(MAX_QUESTION_OPTIONS)).options) == 4


def test_two_options_under_one_id_would_make_an_answer_ambiguous():
    with pytest.raises(ValueError):
        question(
            options=[
                QuestionOption(id="same", label="Một"),
                QuestionOption(id="same", label="Hai"),
            ]
        )


def test_a_question_with_nothing_to_read_is_refused_rather_than_published():
    """Unlike a progress part, there is no safe reduced version of a card."""
    with pytest.raises(ValueError):
        question(prompt="   ")
    with pytest.raises(ValueError):
        question(prompt="x" * (MAX_QUESTION_PROMPT_CHARS + 1))
    with pytest.raises(ValueError):
        question(skip_label="")
    with pytest.raises(ValueError):
        QuestionOption(id="opt_0", label="x" * (MAX_QUESTION_LABEL_CHARS + 1))
    with pytest.raises(ValueError):
        QuestionOption(id="", label="Một")


def test_the_id_is_the_row_it_will_be_recorded_under():
    """A non-UUID would fail at the write instead of where it was built."""
    with pytest.raises(ValueError):
        question(question_id="question-1")


def test_options_given_as_a_list_are_frozen_with_the_part():
    part = question(options=options())

    assert isinstance(part.options, tuple)
    with pytest.raises(FrozenInstanceError):
        part.prompt = "khác"  # type: ignore[misc]


def test_the_ids_a_stored_question_offered_are_read_back_off_its_payload():
    """One reader of the options, so validating an answer has one answer."""
    part = question(options=options(3))

    assert question_option_ids(part.as_wire()) == part.option_ids
    # A payload from anywhere else is read defensively rather than trusted.
    assert question_option_ids({}) == ()
    assert question_option_ids({"options": "hold"}) == ()
    assert question_option_ids({"options": [{"label": "no id"}]}) == ()
