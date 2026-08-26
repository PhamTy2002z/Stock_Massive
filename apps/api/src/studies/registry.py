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
* a ``view`` that names a frame ``compute`` never produces — an exception on a
  live question rather than at the moment the mismatch was written.

The first three are refused here. The last cannot be known without data, so the
runner checks it on every run (``runner.py``) and a test pins it per Study.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel

from . import widgets
from .contracts import KNOWN_REQUIREMENTS, StudyDefinition

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
    if not definition.frames:
        raise ImportError(
            f"study {definition.name!r} declares no frames, so there is nothing "
            "for a canvas to draw"
        )
    if not definition.widgets:
        raise ImportError(f"study {definition.name!r} declares no widgets")
    unknown = [
        f"{name} v{version}"
        for name, version in definition.widgets
        if not widgets.known(name, version)
    ]
    if unknown:
        raise ImportError(
            f"study {definition.name!r} draws with widgets no viewer has: "
            + ", ".join(unknown)
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
            # What this Study reads before it computes. In the catalog because
            # the answer to "can I ask this now" is a fact about the inputs, and
            # a model that cannot see them would have to discover the answer by
            # asking.
            "requires": list(definition.requires),
        }
        for definition in sorted(REGISTRY.values(), key=lambda item: item.name)
    )


__all__ = ["REGISTRY", "catalog", "register", "study"]
