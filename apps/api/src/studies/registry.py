"""The single place a Study becomes reachable by a model.

Mirrors ``src/stocks/signals/registry.py`` in the one respect that matters: the
model-facing surface serializes registered Studies only, so a recipe that is not
here has no route to a model and needs no prohibition. What it adds is a
two-way check at import, because the ways a Study declaration rots are all
silent at runtime:

* a name registered twice — the second wins and the first disappears from the
  catalog with nothing raised;
* a widget the browser has no component for — a blank panel, discovered by a
  person, in Vietnamese;
* an input nothing fetches — a refusal on a live question that reads as a
  statement about the company rather than about the store;
* a board that names a frame the plan never produces, or a calculation whose
  inputs name a step that runs after it — an exception on a live question rather
  than at the moment the mismatch was written.

All four are refused here. The last became checkable when the board stopped
being a function of the numbers and became a literal written against step names:
what a template draws is now knowable without running it.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel

from . import grammar, widgets
from .compute import validator
from .contracts import (
    KNOWN_REQUIREMENTS,
    ComputeStep,
    QueryStep,
    StudyDefinition,
)

#: How many frames the sandbox binds for one calculation, held equal to the
#: ceiling the model-facing tool declares. A template writing a seventh input
#: would be a template whose step never ran.
MAX_COMPUTE_INPUTS = 6

#: The sources ``query`` offers, named here rather than imported: the readers
#: live in the tool layer, and this package does not import that one.
QUERY_SOURCES: frozenset[str] = frozenset(
    {"bar_daily", "intraday_15m", "statement", "ratio", "reference", "corporate_actions"}
)

REGISTRY: dict[str, StudyDefinition] = {}


def register(definition: StudyDefinition) -> StudyDefinition:
    """Admit a Study, or refuse to import the module that declared it."""
    _check(definition)
    if definition.name in REGISTRY:
        raise ImportError(
            f"study {definition.name!r} is registered twice; the second "
            "registration would hide the first from the catalog"
        )
    REGISTRY[definition.name] = definition
    return definition


def _check(definition: StudyDefinition) -> None:
    if not definition.name or not definition.name.islower():
        raise ImportError(
            f"study name {definition.name!r} must be a lowercase identifier — "
            "it is what a model writes in a tool call"
        )
    if definition.version < 1:
        raise ImportError(f"study {definition.name!r} needs a version from 1 up")
    for field in ("question", "display_name"):
        if not getattr(definition, field).strip():
            raise ImportError(
                f"study {definition.name!r} has no {field}; the catalog a model "
                "chooses from would list it as a blank"
            )
    if not issubclass(definition.params_model, BaseModel):
        raise ImportError(
            f"study {definition.name!r} must declare params as a pydantic model "
            "so the schema the model reads and the validation the server runs "
            "come from one source"
        )
    unfetchable = [
        name for name in definition.requires if name not in KNOWN_REQUIREMENTS
    ]
    if unfetchable:
        raise ImportError(
            f"study {definition.name!r} requires inputs nothing knows how to "
            "fetch: " + ", ".join(unfetchable)
        )
    if definition.archetype not in grammar.ARCHETYPES:
        raise ImportError(
            f"study {definition.name!r} declares archetype "
            f"{definition.archetype!r}; the five are "
            + ", ".join(sorted(grammar.ARCHETYPES))
        )
    _check_plan(definition)
    _check_board(definition)


def _check_plan(definition: StudyDefinition) -> None:
    """Every step named once, and every calculation fed by a step before it."""
    if not definition.plan:
        raise ImportError(
            f"study {definition.name!r} declares no steps, so there is nothing "
            "for a Signal Desk to draw"
        )
    seen: set[str] = set()
    for step in definition.plan:
        if not step.name:
            raise ImportError(f"study {definition.name!r} has a step with no name")
        if step.name in seen:
            raise ImportError(
                f"study {definition.name!r} names the step {step.name!r} twice; "
                "the second frame would hide the first from the board"
            )
        if isinstance(step, ComputeStep):
            ahead = [name for name in step.inputs if name not in seen]
            if ahead:
                raise ImportError(
                    f"study {definition.name!r} feeds step {step.name!r} from "
                    + ", ".join(ahead)
                    + ", which it has not produced yet"
                )
            if len(step.inputs) > MAX_COMPUTE_INPUTS:
                raise ImportError(
                    f"study {definition.name!r} feeds step {step.name!r} from "
                    f"{len(step.inputs)} frames, and the sandbox binds "
                    f"{MAX_COMPUTE_INPUTS}"
                )
        if isinstance(step, ComputeStep):
            broken = validator.validate(step.code)
            if broken:
                # The point of the whole plane, checked where a template is
                # written rather than where one runs. A template has no
                # privilege over a model here: a figure it types is refused at
                # import, so "no market number is typed" is a property of the
                # build rather than of anyone's care.
                raise ImportError(
                    f"study {definition.name!r} writes a calculation the "
                    f"validator refuses in step {step.name!r}: "
                    + "; ".join(
                        f"{item.code} line {item.line}: {item.detail}"
                        for item in broken
                    )
                )
        if isinstance(step, QueryStep) and step.source not in QUERY_SOURCES:
            raise ImportError(
                f"study {definition.name!r} reads {step.source!r}, which is not "
                "one of the store's sources: " + ", ".join(sorted(QUERY_SOURCES))
            )
        seen.add(step.name)


def _check_board(definition: StudyDefinition) -> None:
    """The board parses, draws only steps this plan runs, and names real widgets."""
    try:
        board = grammar.parse(definition.board)
    except grammar.BoardMalformed as malformed:
        raise ImportError(
            f"study {definition.name!r} declares a board that is not one: "
            f"{malformed}"
        ) from malformed

    steps = set(definition.step_names)
    unknown = sorted(set(grammar.frame_references(board)) - steps)
    if unknown:
        raise ImportError(
            f"study {definition.name!r} draws frames its plan never produces: "
            + ", ".join(unknown)
        )
    for section in board.sections:
        for block in section.blocks:
            hint = getattr(block, "widget", None)
            if hint is not None and not any(name == hint for name, _version in widgets.CATALOG):
                raise ImportError(
                    f"study {definition.name!r} suggests widget {hint!r}, which "
                    "no viewer has"
                )


def study(name: str) -> StudyDefinition:
    """The Study by name, or a ``KeyError`` naming what is registered."""
    try:
        return REGISTRY[name]
    except KeyError:
        registered = ", ".join(sorted(REGISTRY)) or "nothing yet"
        raise KeyError(
            f"no study named {name!r}; registered: {registered}"
        ) from None


def catalog() -> tuple[Mapping[str, object], ...]:
    """What ``list_studies`` shows a model: name, question, and how to call it.

    The question rather than a description, because the choice a model is making
    is *which question do I have*. Sorted by name so a prompt cache is not
    invalidated by dictionary order.
    """
    return tuple(
        {
            "name": definition.name,
            "version": definition.version,
            "question": definition.question,
            "displayName": definition.display_name,
            "params": definition.params_schema,
            # The shape of the answer, not of the data. A model choosing
            # between a template and composing its own board is choosing
            # between two answers to one question, and the archetype is the
            # only word that says what the template's answer looks like.
            "archetype": definition.archetype,
            # What this Study reads before it computes. In the catalog because
            # the answer to "can I ask this now" is a fact about the inputs, and
            # a model that cannot see them would have to discover the answer by
            # asking.
            "requires": list(definition.requires),
        }
        for definition in sorted(REGISTRY.values(), key=lambda item: item.name)
    )


__all__ = ["REGISTRY", "catalog", "register", "study"]
