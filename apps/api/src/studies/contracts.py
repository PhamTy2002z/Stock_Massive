"""What an analysis recipe has to declare before a model may ask for it.

A **Study** is one named, versioned, deterministic recipe: given parameters a
model chose, it computes numbers and says how to draw them. It exists because
the lane already had a way to hand a model *one figure* — a Signal Field — and
no way to hand a person *a picture*. A picture is a matrix of thirty sessions by
seventeen buckets; put that in a message and the context is gone, and the model
will read the wrong cell anyway.

So the split is structural rather than stylistic:

**The engine computes.** ``compute`` is pure of the model: it reads the store,
does arithmetic, and returns numbers nobody has narrated yet.

**The artifact holds the numbers.** ``StudyResult.frames`` is persisted and
served to the browser directly. It never enters a model message — not truncated,
not summarised, not "just this once". The test that proves it reads the
transcript.

**The registry draws.** ``view`` picks widgets by name and version out of a
catalog the browser reads from the same file (``contracts/
signal-desk-widget-catalog.json``), so a widget the browser cannot draw is a failure
at import here rather than a blank panel there.

**The model reads only the headline.** ``StudyResult.headline`` is the entire
model-facing surface, budgeted at roughly three hundred tokens. Everything a
sentence could honestly say about the picture has to be in it, because the
picture itself is not on offer.

Modelled on ``src/stocks/signals/fields.py`` deliberately: no defaults on the
declaration, so a Study that forgets to say what question it answers is a
``TypeError`` where it is written rather than a gap a reviewer has to notice.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID

from pydantic import BaseModel

from src.stocks.signals.issues import SignalIssue

if TYPE_CHECKING:  # pragma: no cover - import cycle only matters to a checker
    from sqlalchemy.orm import Session

FrameKind = Literal["series", "matrix", "table"]

#: Every input a Study may name in ``StudyDefinition.requires``.
#:
#: Names only, and deliberately here rather than beside the functions that fetch
#: them: ``warmup.py`` imports the provider client, and a registry that checked
#: against that module would drag a network dependency into every import of a
#: Study. So the set is declared where nothing is imported, the registry checks a
#: declaration against it, and ``warmup`` holds itself equal to it at its own
#: import — a requirement can therefore neither be declared without a fetcher nor
#: fetched without being declarable.
KNOWN_REQUIREMENTS: frozenset[str] = frozenset({"intraday_bar_15m"})

#: How the health of a Study's inputs is described to a reader. Same three words
#: the signal serving path uses, for the same reason: a person comparing a
#: figure with a picture should not have to learn two vocabularies for "this is
#: thinner than usual".
Health = Literal["normal", "degraded", "unavailable"]


class StudyRefused(Exception):
    """The Study ran and has no numbers to show, and says which input was short.

    Not an error. "Ran" and "returned numbers" are two different things
    (``CLAUDE.md``): a Study whose window holds nine sessions where it needs ten
    executed correctly and refused correctly, and the tool layer records it as
    ``ok`` with an outcome of ``no_value:<issue>``. An exception carries it
    because a refused Study has no frames, so there is no artifact to persist
    and nothing for the Signal Desk to draw — a result object would be a shell whose
    every field said "not this time".
    """

    def __init__(self, issue: SignalIssue, detail: str) -> None:
        super().__init__(f"{issue.value}: {detail}")
        self.issue = issue
        self.detail = detail


@dataclass(frozen=True)
class Frame:
    """One series, matrix, or table of numbers — and never model-visible.

    ``rows`` is positional against ``columns`` so the payload the browser
    receives is as narrow as the numbers themselves; a list of objects would
    repeat every column name thirty times for a heatmap that is mostly cells.

    ``labels`` maps a column name to the Vietnamese a person reads. It is here
    rather than in the browser because the column names are chosen by whoever
    wrote the Study, and a label invented at the far end of the wire is an
    interpretation of a number by the layer least equipped to make one.
    """

    kind: FrameKind
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    unit: str | None
    labels: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError("a Frame with no columns describes nothing")
        width = len(self.columns)
        for index, row in enumerate(self.rows):
            if len(row) != width:
                raise ValueError(
                    f"row {index} has {len(row)} cells against "
                    f"{width} columns"
                )
        unlabelled = [name for name in self.columns if name not in self.labels]
        if unlabelled:
            raise ValueError(
                "every column needs a Vietnamese label; missing: "
                + ", ".join(unlabelled)
            )

    def to_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "columns": list(self.columns),
            "rows": [list(row) for row in self.rows],
            "unit": self.unit,
            "labels": dict(self.labels),
        }


@dataclass(frozen=True)
class Provenance:
    """Where the numbers came from, frozen at the moment they were computed.

    ``as_of`` is the freeze. Re-opening a thread a week later has to render the
    same picture the answer was written about, so the artifact carries the
    instant it was built rather than being recomputed against a store that has
    moved on.
    """

    source: str
    as_of: datetime
    sessions_used: int
    health: Health
    reason: str | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "asOf": self.as_of.isoformat(),
            "sessionsUsed": self.sessions_used,
            "health": self.health,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SignalDeskBlock:
    """One widget, the frame it draws, and the options the server chose.

    ``options`` is decided here and not in the browser because the choices that
    change what a chart *claims* — which column is the bar, whether a scale
    starts at zero — belong with the person who knows what the numbers mean.
    """

    widget: str
    widget_version: int
    frame: str
    options: Mapping[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return {
            "widget": self.widget,
            "widgetVersion": self.widget_version,
            "frame": self.frame,
            "options": dict(self.options),
        }


@dataclass(frozen=True)
class SignalDeskSpec:
    """The panel: a title and the blocks, in the order a reader meets them."""

    title: str
    blocks: tuple[SignalDeskBlock, ...]

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("a Signal Desk with no title is a panel nobody can name")
        if not self.blocks:
            raise ValueError("a Signal Desk with no blocks draws nothing")

    def to_payload(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "blocks": [block.to_payload() for block in self.blocks],
        }


@dataclass(frozen=True)
class StudyResult:
    """What ``compute`` hands back: a headline for the model, frames for the eye."""

    headline: Mapping[str, Any]
    frames: Mapping[str, Frame]
    provenance: Provenance

    def __post_init__(self) -> None:
        if not self.headline:
            raise ValueError("a Study with no headline tells the model nothing")
        if not self.frames:
            raise ValueError("a Study with no frames has nothing to draw")


@dataclass(frozen=True)
class StudyContext:
    """Everything ``compute`` is allowed to read, and nothing it has to build.

    ``universe`` is resolved by the runner rather than by each Study: building
    it needs both settings and a session, and a Study that built its own would
    be a second answer to "which symbols has this system promised data for".
    """

    params: BaseModel
    session: "Session"
    as_of: datetime
    universe: tuple[str, ...]


@dataclass(frozen=True)
class StudyDefinition:
    """The declaration. No defaults, so an omission fails at import.

    ``frames`` and ``widgets`` are declared rather than discovered because the
    alternative is discovering them at the only moment that matters — a real
    question, with a person waiting. Declared, the runner can check that what
    ``compute`` produced is what was promised, and the import-time check can
    refuse a widget the browser has no drawing for.
    """

    name: str
    version: int
    question: str
    display_name: str
    params_model: type[BaseModel]
    requires: tuple[str, ...]
    frames: tuple[str, ...]
    widgets: tuple[tuple[str, int], ...]
    compute: Callable[[StudyContext], StudyResult]
    view: Callable[[StudyResult], SignalDeskSpec]

    @property
    def params_schema(self) -> Mapping[str, Any]:
        """The model-facing JSON schema, derived from the validating model.

        One source. A hand-written schema beside a pydantic model is two
        contracts that agree until someone widens one of them.
        """
        return self.params_model.model_json_schema()


@dataclass(frozen=True)
class StoredArtifact:
    """A persisted run: the id to fetch it by, and the parts each reader needs.

    The model is handed ``headline`` and ``provenance``; the browser fetches the
    row by ``id`` and gets ``signal_desk_spec`` with the frames. Splitting them here
    rather than at the transport is what makes "frames never reach the model" a
    property of the type rather than of everyone's discipline.
    """

    id: UUID
    study_name: str
    study_version: int
    headline: Mapping[str, Any]
    provenance: Provenance
    signal_desk_spec: SignalDeskSpec


__all__ = [
    "KNOWN_REQUIREMENTS",
    "SignalDeskBlock",
    "SignalDeskSpec",
    "Frame",
    "FrameKind",
    "Health",
    "Provenance",
    "StoredArtifact",
    "StudyContext",
    "StudyDefinition",
    "StudyRefused",
    "StudyResult",
]
