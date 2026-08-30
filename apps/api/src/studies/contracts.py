"""What an analysis recipe has to declare before a model may ask for it.

A **Study** is one named, versioned, deterministic *template*: a ``plan`` of
steps and a ``board`` written against their names. It exists because the lane
already had a way to hand a model *one figure* — a Signal Field — and no way to
hand a person *a picture*. A picture is a matrix of thirty sessions by seventeen
buckets; put that in a message and the context is gone, and the model will read
the wrong cell anyway.

So the split is structural rather than stylistic:

**The engine computes, and a template has no private engine.** A ``QueryStep``
goes through the reader a model's own ``query`` call goes through, a
``ComputeStep`` through the sandbox and the validator a model's ``compute`` goes
through, and a ``ReadStep`` is the one narrow privilege — on the *read* axis, for
the three answers the query layer has no source for, and never for arithmetic.

**The artifact holds the numbers.** Every step's frame is persisted and served
to the browser directly. None of them enters a model message — not truncated,
not summarised, not "just this once". The test that proves it reads the
transcript.

**The composer draws.** ``board`` is a literal written against step names, so
the registry can check at import that every frame it draws is one the plan
produces and every widget it suggests is one the browser has — a failure where
it was written rather than a blank panel in front of a reader.

**The model reads only the headline.** ``StudyDefinition.headline`` is the entire
model-facing surface, budgeted at roughly three hundred tokens. It is handed the
frames and nothing else, so every figure in it came out of a cell by
construction. Everything a sentence could honestly say about the picture has to
be in it, because the picture itself is not on offer.

Modelled on ``src/stocks/signals/fields.py`` deliberately: no defaults on the
declaration, so a Study that forgets to say what question it answers is a
``TypeError`` where it is written rather than a gap a reviewer has to notice.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Literal
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
#: ``winner`` and ``loser`` are the comparison pair, and they are not ``up`` and
#: ``down`` wearing another name. A number that *rose* and a number that is
#: *better than the one beside it* are different claims: VIC's drawdown falling
#: is ``down`` and also ``winner``, and a chart that had to choose between them
#: would have to drop one of the two things the picture is about.
#:
#: ``benchmark`` marks the line something is being compared *against* — an index,
#: a sector median — so a reader can tell the reference from the subject without
#: a legend. ``warning`` marks a cell a reader should not read past without the
#: caveat beside it. ``stale`` marks a number that is real but older than the
#: rest of the picture, which is the one condition a frame can carry that no
#: refusal covers: it has a value, and the value is from another day.
PLAIN_ROLES: frozenset[str] = frozenset(
    {
        "series",
        "muted",
        "focus",
        "up",
        "down",
        "neutral",
        "winner",
        "loser",
        "benchmark",
        "warning",
        "stale",
    }
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
    ``cell_roles`` is keyed ``(row index, column)`` and describes one cell.

    **Three granularities rather than two, because a comparison needs the third.**
    A table of symbols against fields has a winner per *column* and a symbol per
    *row*, and the claim being made is about neither: it is that this symbol wins
    on this field. Expressed with ``point_roles`` it would say the whole row
    wins, which is exactly the sentence a comparison exists to avoid. The three
    do not overlap and none of them defaults to anything, so a frame saying
    nothing about meaning is drawn as it was before any of this existed.
    """

    kind: FrameKind
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]
    unit: str | None
    labels: Mapping[str, str]
    column_roles: Mapping[str, str] = field(default_factory=dict)
    point_roles: tuple[str | None, ...] = ()
    cell_roles: Mapping[tuple[int, str], str] = field(default_factory=dict)

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

        for (index, column), role in self.cell_roles.items():
            if not 0 <= index < len(self.rows):
                raise ValueError(
                    f"cell role {role!r} names row {index}, and this Frame has "
                    f"{len(self.rows)}"
                )
            if column not in self.columns:
                raise ValueError(
                    f"cell role {role!r} names column {column!r}, which this "
                    "Frame does not have"
                )
            problem = role_error(role)
            if problem is not None:
                raise ValueError(f"cell ({index}, {column!r}): {problem}")

    def to_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "columns": list(self.columns),
            "rows": [list(row) for row in self.rows],
            "unit": self.unit,
            "labels": dict(self.labels),
            "columnRoles": dict(self.column_roles),
            "pointRoles": list(self.point_roles),
            # A list of triples rather than a nested object: a JSON key can only
            # be a string, so a ``(row, column)`` key would have to be spelled
            # ``"3|roe"`` and parsed back at the far end — a second encoding for
            # the browser to agree with, and one more thing to get wrong.
            "cellRoles": [
                {"row": index, "column": column, "role": role}
                for (index, column), role in sorted(self.cell_roles.items())
            ],
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


#: Where a frame's numbers came from, as a closed vocabulary.
#:
#: Three words and not a free string, because the reader-facing consequence
#: differs per word: ``store`` is this deployment's own measurement and carries
#: its health and its ``as_of``; ``web`` is a number read off a page somebody
#: else published, and the badge beside it has to say so; ``derived`` is
#: arithmetic this Turn did on frames it already had, which is neither of the
#: first two and must not be able to pass as ``store``.
#:
#: It was a free ``str`` and every caller wrote ``"store"``. Closing it is what
#: makes a badge on the browser a decision the engine took rather than a string
#: comparison the far end guesses at.
FrameSource = Literal["store", "web", "derived"]

#: The same three words as a set, for the check. Written out rather than derived
#: from the ``Literal`` with ``get_args`` so the failure is a name a reader can
#: grep for rather than a typing introspection.
FRAME_SOURCES: frozenset[str] = frozenset({"store", "web", "derived"})


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

    source: FrameSource
    as_of: datetime
    sessions_used: int
    health: Health
    reason: str | None
    method_notes: tuple[str, ...] = ()
    # What was asked for, in the terms the asking layer used: the source name, the
    # symbols, the window, the refusal counts. Kept for the operator reading the
    # row and for the replay that has to rebuild the same frame after a code
    # change — not for the reader, and not for the model, neither of which ever
    # sees it. Free-shaped on purpose: the six sources answer to six different
    # sets of arguments, and a typed union of them here would be the query
    # schema written a second time.
    query: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.source not in FRAME_SOURCES:
            raise ValueError(
                f"{self.source!r} is not where numbers come from; use one of "
                + ", ".join(sorted(FRAME_SOURCES))
            )
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
            "query": dict(self.query),
        }


#: Which spelling of a Signal Desk spec a row holds.
#:
#: Version 1 is a title and a flat list of blocks — every artifact written before
#: the board grammar existed, and every Study still writing one. Version 2 is the
#: board: a KPI strip, sections, resolved captions, an appendix and a lint score.
#:
#: The number is on the payload rather than inferred from which keys are present,
#: because inference is how a v1 row with an empty section list comes to be read
#: as a v2 board with nothing in it.
SPEC_VERSION_V1 = 1
SPEC_VERSION_V2 = 2


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
            # Stated rather than left absent. A browser branching on the version
            # would otherwise have to read "no version" as "version one", which
            # is true today and is exactly the sort of true-today the next
            # spelling breaks.
            "specVersion": SPEC_VERSION_V1,
            "title": self.title,
            "blocks": [block.to_payload() for block in self.blocks],
        }


@dataclass(frozen=True)
class ResolvedValue:
    """One cell, looked up and formatted at the moment the board was frozen.

    Stored resolved rather than as a reference for the same reason ``as_of`` is
    stored: re-opening a thread renders the board that was written, and a board
    that re-read its own frames on every open would be a board whose figures
    could move under a reader who was told they were frozen. It also means the
    browser never looks a number up — it draws the string it is handed, and the
    one place that decides how a number reads is ``studies/format.py``.

    ``frame``, ``row`` and ``column`` travel anyway, because a reader who wants
    to know where a figure came from is owed the cell, and an export that carried
    only the rendering would be an export of the picture rather than the evidence.
    """

    text: str
    raw: Any
    unit: str | None
    frame: str
    row: int
    column: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "raw": self.raw,
            "unit": self.unit,
            "frame": self.frame,
            "row": self.row,
            "column": self.column,
        }


@dataclass(frozen=True)
class KpiCell:
    """One figure on the strip: what it is called, what it is, and what it means."""

    label: str
    value: ResolvedValue
    delta: ResolvedValue | None
    role: str | None
    span: int

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("a KPI with no label is a number nobody can read")
        if self.role is not None:
            problem = role_error(self.role)
            if problem is not None:
                raise ValueError(f"kpi {self.label!r}: {problem}")

    def to_payload(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "value": self.value.to_payload(),
            "delta": None if self.delta is None else self.delta.to_payload(),
            "role": self.role,
            "span": self.span,
        }


@dataclass(frozen=True)
class VisualBlock:
    """One picture on the board, and the record of how it came to be that one.

    ``upgraded_from`` and ``downgraded`` are kept rather than dropped once the
    decision is made. The first says the server overruled the model's suggestion,
    which is a thing an operator reading a board later needs to be able to see;
    the second says no rule matched and the numbers are shown plainly, which is
    a thing the *reader* is told.
    """

    widget: str
    widget_version: int
    frame: str
    options: Mapping[str, Any]
    span: int
    source: FrameSource
    upgraded_from: str | None = None
    downgraded: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "kind": "visual",
            "widget": self.widget,
            "widgetVersion": self.widget_version,
            "frame": self.frame,
            "options": dict(self.options),
            "span": self.span,
            "source": self.source,
            "upgradedFrom": self.upgraded_from,
            "downgraded": self.downgraded,
        }


@dataclass(frozen=True)
class CaptionBlock:
    """One sentence, its holes, and what went into each hole.

    Both the template and the resolved text travel. The template with its
    ``{a}`` markers is what lets the browser draw each figure as a mark a reader
    can hover to see which cell it came from; the resolved text is what an export
    and a screen reader get, and neither should have to re-run the substitution.
    """

    template: str
    text: str
    refs: Mapping[str, ResolvedValue]
    span: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "kind": "caption",
            "template": self.template,
            "text": self.text,
            "refs": {
                key: value.to_payload() for key, value in sorted(self.refs.items())
            },
            "span": self.span,
        }


BoardBlock = VisualBlock | CaptionBlock


@dataclass(frozen=True)
class BoardSection:
    """One idea of the board: an optional heading and the blocks under it."""

    heading: str | None
    blocks: tuple[BoardBlock, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "heading": self.heading,
            "blocks": [block.to_payload() for block in self.blocks],
        }


@dataclass(frozen=True)
class BoardSpec:
    """A Signal Desk as the compiler produces it: version 2 of the spec.

    Held separately from :class:`SignalDeskSpec` rather than by widening it,
    because the two are read by different code on both sides of the wire and a
    single class with half its fields empty is how a v1 row comes to be drawn as
    a broken v2 board. The version on the payload is what the browser branches
    on, and every field below is already resolved: nothing here needs a frame
    lookup to render.
    """

    title: str
    archetype: str
    kpis: tuple[KpiCell, ...]
    sections: tuple[BoardSection, ...]
    appendix: VisualBlock | None
    lint: Mapping[str, Any]
    auto_composed: bool

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("a board with no title is a panel nobody can name")
        if not self.sections:
            raise ValueError("a board with no sections draws nothing")

    @property
    def block_count(self) -> int:
        """How many boxes a skeleton should hold while the numbers are fetched."""
        total = sum(len(section.blocks) for section in self.sections)
        return total + (1 if self.appendix is not None else 0)

    def to_payload(self) -> dict[str, Any]:
        return {
            "specVersion": SPEC_VERSION_V2,
            "title": self.title,
            "archetype": self.archetype,
            "kpis": [kpi.to_payload() for kpi in self.kpis],
            "sections": [section.to_payload() for section in self.sections],
            "appendix": None if self.appendix is None else self.appendix.to_payload(),
            "lint": dict(self.lint),
            "autoComposed": self.auto_composed,
        }


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
    #: Somewhere a plan's steps can put a thing they all need, resolved once.
    #:
    #: Two reads of one plan asking the store the same question twice is not only
    #: wasteful, it can *disagree with itself*: each statement is its own
    #: snapshot under read-committed, so a quarterly scan or an intraday ingest
    #: committing between two steps makes one frame describe a store the next
    #: frame no longer sees. A run is meant to be a single instant — that is what
    #: ``as_of`` claims — so a fact resolved once belongs here rather than being
    #: fetched again.
    #:
    #: Mutable inside a frozen context on purpose: what is frozen is *which* run
    #: this is, and a per-run memo does not change that. It lives exactly as long
    #: as the run, so nothing here can answer a later question.
    scratch: dict[str, Any] = field(default_factory=dict)


#: How a step's frame is filed, in the vocabulary ``frames_buffer`` already
#: knows. A read is a read whichever road it came down, and a calculation is a
#: calculation; inventing a third word for "a step of a template" would give the
#: browser a kind with no meaning and the operator a row that reads as special.
STEP_KINDS: frozenset[str] = frozenset({"query", "read", "compute"})


@dataclass(frozen=True)
class QueryStep:
    """One of the store's tables, read through the same reader chat reads it by.

    ``symbols`` and ``arguments`` are callables of the context rather than a
    literal mapping because a template's window is its parameters — thirty
    sessions or two hundred and fifty — and a template that spelled them once at
    import would answer every question with the first one asked.
    """

    name: str
    title: str
    source: str
    symbols: Callable[["StudyContext"], Sequence[str]]
    arguments: Callable[["StudyContext"], Mapping[str, Any]]
    #: What a reader is owed about how this step's numbers were arrived at.
    #: Declared on the step because neither layer that builds a step's
    #: provenance can know it: ``read_source`` describes a table and
    #: ``derived_provenance`` describes a calculation, and "the concentration
    #: zone is two adjacent bins of twenty" is a fact about *this question*.
    #: They lead the merged strip, so a cap falls on the engine's own lines
    #: rather than on these.
    method_notes: tuple[str, ...] = ()
    check: Callable[[Frame, "StudyContext"], None] | None = None

    kind: ClassVar[str] = "query"


@dataclass(frozen=True)
class ReadStep:
    """A read the query layer does not offer, named and owned by one template.

    **The narrow privilege, and why it is on the read axis rather than the
    calculation one.** Three of the store's answers have no ``query`` source:
    the exchange's tick grid under a price ladder, the statement concept a
    filer's own template decides, and a screen across more symbols than a model
    is ever handed. All three are *facts about the store's shape* — reads — and
    none of them is arithmetic. So a template may name a reader; it may not name
    a calculator. Every number a template derives still goes through
    ``studies/compute`` and its validator, on exactly the terms a model gets.

    Nothing reaches this from a model: the only route to a template is
    ``run_study(name)``, and the name is a registered one.
    """

    name: str
    title: str
    read: Callable[["StudyContext"], tuple[Frame, Provenance]]
    #: What a reader is owed about how this step's numbers were arrived at.
    #: Declared on the step because neither layer that builds a step's
    #: provenance can know it: ``read_source`` describes a table and
    #: ``derived_provenance`` describes a calculation, and "the concentration
    #: zone is two adjacent bins of twenty" is a fact about *this question*.
    #: They lead the merged strip, so a cap falls on the engine's own lines
    #: rather than on these.
    method_notes: tuple[str, ...] = ()
    check: Callable[[Frame, "StudyContext"], None] | None = None

    kind: ClassVar[str] = "read"


@dataclass(frozen=True)
class ComputeStep:
    """Arithmetic over earlier steps, in the sandbox, under the same validator.

    ``inputs`` names steps rather than frames, and the runner binds them to
    ``f0``…``f5`` in the order written — the same names a model writes against.
    A template has no privilege here on purpose: a literal it types is refused
    at import by the same validator, exactly as a model's would be at call time.

    ``constants`` is a callable of the context because a template's assumptions
    *are* its parameters — the growth floor a screen was asked for, whether the
    question meant shares or money. A literal mapping would bake the first
    question ever asked into every answer after it.
    """

    name: str
    title: str
    code: str
    inputs: tuple[str, ...] = ()
    constants: Callable[["StudyContext"], Mapping[str, Any]] = lambda _context: {}
    output_kind: FrameKind | None = None
    #: How wide and how tall this step's answer may be, where the ceilings a
    #: model's calculation answers to are too narrow for an honest picture.
    #: ``None`` takes the sandbox's own default.
    max_rows: int | None = None
    max_columns: int | None = None
    #: What a reader is owed about how this step's numbers were arrived at.
    #: Declared on the step because neither layer that builds a step's
    #: provenance can know it: ``read_source`` describes a table and
    #: ``derived_provenance`` describes a calculation, and "the concentration
    #: zone is two adjacent bins of twenty" is a fact about *this question*.
    #: They lead the merged strip, so a cap falls on the engine's own lines
    #: rather than on these.
    method_notes: tuple[str, ...] = ()
    check: Callable[[Frame, "StudyContext"], None] | None = None

    kind: ClassVar[str] = "compute"


Step = QueryStep | ReadStep | ComputeStep


@dataclass(frozen=True)
class StudyDefinition:
    """The declaration. No defaults where an omission should fail at import.

    A Study is a *template*: a plan of steps and a board written against their
    names. It computes nothing of its own and draws nothing of its own — the
    plan runs through the same reader and the same sandbox a model's question
    does, and the board compiles through the same composer. What is left that is
    genuinely the Study's is the two things a model cannot supply: the sequence
    that answers this question, and the shape that shows it.

    ``board`` is a literal mapping rather than a callable, and that is what makes
    the registry able to check at import that every frame the board names is a
    step the plan produces. Its ``title`` may carry ``{param}`` placeholders,
    which is the one thing about a board that genuinely varies per run.

    ``headline`` is a callable and is handed the frames and nothing else, so
    every figure in the three hundred tokens the model reads came out of a frame
    by construction rather than by discipline.
    """

    name: str
    version: int
    question: str
    display_name: str
    params_model: type[BaseModel]
    requires: tuple[str, ...]
    archetype: str
    plan: tuple[Step, ...]
    board: Mapping[str, Any]
    headline: Callable[[BaseModel, Mapping[str, Mapping[str, Any]]], Mapping[str, Any]]
    #: Raised before a step runs, for the refusals that are about the question
    #: rather than about the data — a symbol outside the Universe, above all.
    #: Reading the store to say "this is not a symbol I cover" would be a read
    #: whose only outcome is a refusal.
    precheck: Callable[["StudyContext"], None] | None = None

    @property
    def params_schema(self) -> Mapping[str, Any]:
        """The model-facing JSON schema, derived from the validating model.

        One source. A hand-written schema beside a pydantic model is two
        contracts that agree until someone widens one of them.
        """
        return self.params_model.model_json_schema()

    @property
    def step_names(self) -> tuple[str, ...]:
        return tuple(step.name for step in self.plan)


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
    signal_desk_spec: BoardSpec
    #: Each step's frame, addressable as ``"<artifact id>#<step>"``. Handed to
    #: the model so a template's own numbers can be re-mixed into a board it
    #: composes itself, which is the whole reason a step is an artifact rather
    #: than an intermediate. Not stored on the composition row: the ids are
    #: fresh every run, and a row carrying them could never be regenerated
    #: byte-for-byte.
    steps: Mapping[str, str] = field(default_factory=dict)


__all__ = [
    "BoardBlock",
    "BoardSection",
    "BoardSpec",
    "CATEGORY_ROLES",
    "CaptionBlock",
    "KpiCell",
    "ResolvedValue",
    "SPEC_VERSION_V1",
    "SPEC_VERSION_V2",
    "VisualBlock",
    "CATEGORY_SLOTS",
    "KNOWN_REQUIREMENTS",
    "METHOD_NOTE_LIMIT",
    "PLAIN_ROLES",
    "REASON_LIMIT",
    "ROLES",
    "SignalDeskBlock",
    "SignalDeskSpec",
    "FRAME_SOURCES",
    "Frame",
    "FrameKind",
    "FrameSource",
    "Health",
    "Provenance",
    "ComputeStep",
    "QueryStep",
    "ReadStep",
    "STEP_KINDS",
    "Step",
    "StoredArtifact",
    "StudyContext",
    "StudyDefinition",
    "StudyRefused",
    "role_error",
]
