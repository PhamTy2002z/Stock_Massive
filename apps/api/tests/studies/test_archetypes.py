"""An archetype is a claim about the question, and the check is that it holds."""

from __future__ import annotations

import pytest

from src.studies import archetypes, composer


def shape(**overrides):
    base = dict(
        kind="table",
        rows=4,
        label_column="label",
        numeric_columns=("value",),
        time_axis=False,
        entity_axis=False,
        part_of_whole=False,
        checklist=False,
    )
    base.update(overrides)
    return composer.Shape(**base)


ENTITY = shape(entity_axis=True, rows=2)
SERIES = shape(kind="series", time_axis=True, rows=30)
PARTS = shape(part_of_whole=True)
PLAIN = shape()


@pytest.mark.parametrize(
    "archetype, shapes",
    [
        ("compare", [ENTITY]),
        ("profile", [PLAIN]),
        ("screen", [PLAIN]),
        ("timeline", [SERIES]),
        ("decompose", [PARTS]),
    ],
)
def test_a_board_holding_what_its_archetype_needs_reports_nothing(archetype, shapes):
    assert archetypes.check(archetype, shapes) == []


@pytest.mark.parametrize(
    "archetype, shapes",
    [
        ("compare", [SERIES]),
        ("timeline", [ENTITY]),
        ("decompose", [ENTITY]),
    ],
)
def test_a_board_that_declared_one_thing_and_drew_another_is_named(archetype, shapes):
    violations = archetypes.check(archetype, shapes)
    assert [violation.code for violation in violations] == ["slot_type_mismatch"]


def test_declaring_nothing_is_a_profile_and_a_profile_accepts_anything():
    assert archetypes.check(None, [PLAIN]) == []
    assert archetypes.check(None, [SERIES]) == []


def test_an_archetype_nothing_knows_is_named_rather_than_ignored():
    assert [v.code for v in archetypes.check("dashboard", [PLAIN])] == [
        "slot_type_mismatch"
    ]


def test_an_extra_picture_does_not_break_the_claim():
    """A comparison that also shows a trend is still a comparison.

    The archetype is a check on presence, not a cage: refusing the extra picture
    would make declaring one a reason to declare nothing.
    """
    assert archetypes.check("compare", [ENTITY, SERIES, PARTS]) == []


def test_a_board_with_no_pictures_at_all_fails_every_required_slot():
    assert archetypes.check("compare", []) != []
    assert archetypes.check("profile", []) != []
