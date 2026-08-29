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

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
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

#: How many interchangeable categorical slots the palette offers. Six because a
#: picture that needs a seventh hue has stopped being readable as categories —
#: past that a reader is matching swatches to a legend rather than seeing groups.
CATEGORY_SLOTS = 6

#: What a series or a row *is*, said by the layer that knows what it measured.
#:
#: A role is a claim about meaning, not a colour: the engine says "this quarter
#: fell", the browser decides what "fell" looks like in the theme the reader has
#: on. That is why the vocabulary is closed and lives here — a Study inventing
#: ``"orange"`` would be the engine reaching across the wire to paint, and a
#: Study inventing ``"bearish"`` would be a meaning nothing renders.
#:
#: ``focus`` is spent once per picture. It marks the one element the answer is
#: about; a second one spends the only mark that means "this one". The browser
#: enforces that rather than trusting it — see ``chart-theme.ts``.
#:
#: ``up`` and ``down`` are the market pair and belong only where the number
#: genuinely rose or fell. ``category:1``–``category:6`` are interchangeable
#: group hues carrying no direction at all, which is why the two families should
#: not appear in one picture: a chart doing both is describing two things at once.
PLAIN_ROLES: frozenset[str] = frozenset(
    {"series", "muted", "focus", "up", "down", "neutral"}
)

CATEGORY_ROLES: frozenset[str] = frozenset(
    f"category:{slot}" for slot in range(1, CATEGORY_SLOTS + 1)
)

ROLES: frozenset[str] = PLAIN_ROLES | CATEGORY_ROLES


def role_error(role: object) -> str | None:
    """Why this is not a role, or ``None`` when it is one."""
    if not isinstance(role, str):
        return f"a role is a string, got {type(role).__name__}"
    if role in ROLES:
        return None
    return (
        f"{role!r} is not a role; use one of "
        + ", ".join(sorted(PLAIN_ROLES))
        + f", or category:1..{CATEGORY_SLOTS}"
    )


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

    ``column_roles`` and ``point_roles`` carry meaning, not colour, for the same
    reason ``labels`` carries Vietnamese: only the layer that computed a number
    knows whether it rose, whether it is the one the answer is about, or whether
    it is simply the third of four groups. Both are optional and both default to
    nothing, so a picture that says nothing about meaning is drawn exactly as it
    was before any of this existed.

    ``column_roles`` is keyed by column and describes a whole series — the second
    line on a two-line chart. ``point_roles`` is positional against ``rows`` and
    describes one bar, point or tile, with ``None`` for a row making no claim.
    """

    kind: FrameKind
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    unit: str | None
    labels: Mapping[str, str]
    column_roles: Mapping[str, str] = field(default_factory=dict)
    point_roles: tuple[str | None, ...] = ()

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
        self._check_roles()

    def _check_roles(self) -> None:
        """A role naming nothing, or nothing nameable, fails where it is written.

        Both halves matter. An unknown role word would reach the browser and be
        silently ignored — a Study would have said something about its numbers
        and nobody would ever see it. A role attached to a column that is not
        there is the same failure with a rename behind it.
        """
        for column, role in self.column_roles.items():
            if column not in self.columns:
                raise ValueError(
                    f"role {role!r} names column {column!r}, which this Frame "
                    "does not have"
                )
            problem = role_error(role)
            if problem is not None:
                raise ValueError(f"column {column!r}: {problem}")

        if self.point_roles and len(self.point_roles) != len(self.rows):
            raise ValueError(
                f"{len(self.point_roles)} point roles against "
                f"{len(self.rows)} rows"
            )
        for index, role in enumerate(self.point_roles):
            if role is None:
                continue
            problem = role_error(role)
            if problem is not None:
                raise ValueError(f"row {index}: {problem}")

    def to_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "columns": list(self.columns),
            "rows": [list(row) for row in self.rows],
            "unit": self.unit,
            "labels": dict(self.labels),
            "columnRoles": dict(self.column_roles),
            "pointRoles": list(self.point_roles),
        }


#: How long the one sentence under a picture may be. A limit rather than a
#: guideline because the surface it lands on is a strip beside a chart: past
#: roughly this it wraps to a paragraph, and a reader checking whether the
#: numbers are thin stops reading a paragraph.
REASON_LIMIT = 120

#: How long one note about method may be. Longer than a reason because a
#: limitation genuinely takes a clause to state, and short enough that stating
#: two of them in one note is not an option.
METHOD_NOTE_LIMIT = 160

#: Words that are this system talking about itself. A reader asked about a
#: company and every one of these answers with plumbing.
_SHOP_WORDS = frozenset(
    {
        "artifact",
        "column",
        "dataframe",
        "endpoint",
        "frame",
        "payload",
        "provider",
        "roster",
        "schema",
        "store",
        "universe",
        "widget",
    }
)

#: Anything shaped like an identifier. This is what catches the names nobody
#: thought to ban — a column, a function, a ranking formula — without a list
#: that has to be kept current with the code.
_CODE_NAME = re.compile(r"[A-Za-z]+_[A-Za-z0-9_]+")

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")


def _check_reader_sentence(field_name: str, text: str, limit: int) -> None:
    """One sentence a reader can use, or a ``ValueError`` naming what is wrong.

    Everything on the provenance strip is read by somebody who asked about a
    company, so it is Vietnamese about the data and never about this system. The
    real case: a strip that printed the whole ranking formula, the price
    adjustment policy and where the symbol list came from, in one line, as the
    answer to "how fresh is this".
    """
    if not text.strip():
        raise ValueError(f"{field_name} is empty; leave it out instead")
    if len(text) > limit:
        raise ValueError(
            f"{field_name} is {len(text)} characters against a limit of {limit}: "
            "say why the data is thin, and put the method beside it"
        )
    identifier = _CODE_NAME.search(text)
    if identifier is not None:
        raise ValueError(
            f"{field_name} carries the code name {identifier.group()!r}; a reader "
            "asked about a company, so say it in Vietnamese"
        )
    for word in _WORD.findall(text):
        if word.lower() in _SHOP_WORDS:
            raise ValueError(
                f"{field_name} carries {word!r}, which is this system describing "
                "itself rather than the data"
            )


@dataclass(frozen=True)
class Provenance:
    """Where the numbers came from, frozen at the moment they were computed.

    ``as_of`` is the freeze. Re-opening a thread a week later has to render the
    same picture the answer was written about, so the artifact carries the
    instant it was built rather than being recomputed against a store that has
    moved on.

    **``reason`` and ``method_notes`` answer two different questions.** One
    reader wants to know whether this picture is thinner than usual and stops
    there; another wants to know how the numbers were arrived at before they
    trust a ranking. Both used to arrive as a single joined line, so the first
    reader met five clauses of methodology and the second had to find the one
    that mattered inside it. ``reason`` is now the first question only, in a
    sentence; ``method_notes`` is the second, one limitation per entry.
    """

    source: str
    as_of: datetime
    sessions_used: int
    health: Health
    reason: str | None
    method_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.reason is not None:
            _check_reader_sentence("reason", self.reason, REASON_LIMIT)
        for index, note in enumerate(self.method_notes):
            _check_reader_sentence(
                f"method_notes[{index}]", note, METHOD_NOTE_LIMIT
            )

    def to_payload(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "asOf": self.as_of.isoformat(),
            "sessionsUsed": self.sessions_used,
            "health": self.health,
            "reason": self.reason,
            "methodNotes": list(self.method_notes),
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
    "CATEGORY_ROLES",
    "CATEGORY_SLOTS",
    "KNOWN_REQUIREMENTS",
    "METHOD_NOTE_LIMIT",
    "PLAIN_ROLES",
    "REASON_LIMIT",
    "ROLES",
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
    "role_error",
]
