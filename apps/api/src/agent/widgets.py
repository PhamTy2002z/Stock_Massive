"""The server-owned Widget registry, its validator, and the replay behind it.

``docs/adr/0012``: **a chart is a typed, versioned Widget from a server-owned
registry — never a model-authored spec.**  The model names a Widget and binds it
to evidence it gathered in this Turn.  Everything else — the pinned version, the
colours, the axis, the scale, the units — belongs to the server, and this module
is where that ownership is enforced.

## The selection arrives through the output contract, not a thirteenth tool

The Tool Catalog is fixed at twelve and its ordering is part of
``tool_catalog_version``, which is also part of the prompt cache key and of what
an Eval Fixture is frozen against.  A tool that drew a picture would move all
three.  So the selection is a marker in the answer text, described by the
*Visual evidence* section of the System Prompt Contract, and
:func:`extract_selections` lifts it out
*before* the answer is split into blocks.  That ordering is why the Recommendation
Validator never sees a Widget marker and never has to know one exists.

## What is validated, and what a rejection costs

Everything ``docs/adr/0012`` lists, before anything is persisted:

- the binding resolves inside **this Turn's** Tool Call Traces, through the same
  :class:`~src.agent.grounding.TraceIndex` the Recommendation Validator uses, so
  "another Turn's trace fails" is a property of the data structure rather than a
  check somebody remembered to write;
- every requested field is a **Signal Registry declaration**, and its ``unit``
  and ``as_of`` are the ones the trace carried;
- the ``(name, version)`` combination is supported, the version being the
  server's;
- at most **one Widget per answer**, unless the user asked for a second.

A rejection raises :class:`WidgetRejected` and nothing else happens.  The text
answer is already complete and stays untouched: an unknown Widget is missed
cleanly here rather than failing at render time inside the transcript, which is
the whole argument for a registry over a chart grammar.

## What is stored is a descriptor, never the series

A :class:`WidgetSpec` holds a **fixed-date retrieval descriptor**.  Embedding the
series would copy the same price array into the database once per chart forever,
and there is no ``widgets`` table.  :class:`WidgetDataResolver` turns the
descriptor back into data: a 24-hour Redis entry when the chart is fresh, and a
reconstruction from the store after that, which is sound because EOD data is
settled.  A reopened Thread therefore re-renders **the same fixed historical
slice**; ``latest`` is never re-evaluated, and *update with new data* is a new
Turn.  A slice that can no longer be reconstructed resolves to an explicit
unavailable state rather than to today's numbers.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from enum import Enum
from typing import Any

from src.stocks.signals import registered_field

from .context import TranscriptToolCall
from .grounding import Citation, EvidenceRef, EvidenceSource, GroundingFailure, TraceIndex
from .tools.data import availability

logger = logging.getLogger(__name__)

# Its own pattern, and deliberately not a member of the Recommendation
# Validator's marker alternation. A Widget selection is not evidence for a
# figure, and putting it in that family would make it a candidate attribution
# for the number in front of it. It is lifted out of the answer before the
# blocks are split, so the two protocols never meet.
SELECTION_PATTERN = re.compile(r"\[widget:([^\]\n]{1,600})\]")

# A model-written title is prose, like the block text around it. It is bounded
# and stripped of the two characters that would let it impersonate a marker.
MAX_TITLE_CHARS = 80

# Shared with ``tools/data.py``: the hot cache is one mechanism, and a Widget
# descriptor that expired on a different clock than the Data Reference inside it
# would resolve half from Redis and half from the store.
CACHE_TTL_SECONDS = 24 * 60 * 60

DEEP_LINK_ROUTE = "/analytics/deep-dive"

# How many Widgets one answer may carry.
#
# ``docs/specs/0004`` D11 raised this from one to three, and the reason is the
# product's own moat argument: an answer whose figures arrive as data blocks is
# what a general chatbot cannot produce, and one picture per answer made that
# unreachable for a question about several things at once — a comparison, a
# trend and the quarters behind them are three shapes, not three versions of one.
#
# The anti-spam rule it replaces still exists, one number higher. Three is what
# an answer may choose on its own; the fourth is only for a reader who asked for
# more visuals in their own words, which is the one signal the backend owns
# (:func:`user_requested_multiple`). Neither number is something the model can
# set, and neither is read from the answer.
WIDGET_CEILING = 3
WIDGET_CEILING_ON_REQUEST = 4

# The columns a quarterly-financials table draws, in this order.
#
# Server-owned, like every other presentation default in ADR-0012: the model
# names the Widget and binds it to the periods it read, and what a reader sees
# in the columns is not the model's choice. Four income-statement figures rather
# than the sixteen ``get_financials`` can serve, because a table wider than that
# is unreadable at 360px and because these four are the ones the question behind
# this Widget asks — how much came in, and how much of it survived to the bottom.
#
# Every one is a stored figure in dong. Nothing here is computed at render time:
# a margin is a division, and a figure this system divided in a component would
# be a figure with no Signal Registry declaration behind it (``docs/adr/0010``).
QUARTERLY_COLUMNS: tuple[str, ...] = (
    "revenue_vnd",
    "gross_profit_vnd",
    "operating_profit_vnd",
    "net_profit_after_tax_vnd",
)

#: The tool a quarterly-financials selection binds to, and the only one.
FINANCIALS_TOOL = "get_financials"


class BindingKind(str, Enum):
    """What shape of evidence a Widget binds to.

    The kind decides how the binding is resolved, and the two ways differ in
    kind rather than in degree: a *figure* carries a unit and a sanctioned
    reading and goes through the citation path, and a *descriptor* carries
    neither and goes through :meth:`TraceIndex.resolve_descriptor`.
    """

    CROSS_SYMBOL = "cross_symbol"
    RANKING = "ranking"
    SERIES = "series"
    POSITION = "position"
    PERIODS = "periods"


@dataclass(frozen=True)
class WidgetDefinition:
    """One registry entry: the server's half of the contract."""

    name: str
    version: int
    binding: BindingKind
    min_refs: int
    max_refs: int
    summary: str


# The v1 registry. Pie, radar, candlestick, 3D, arbitrary specs and image
# generation are outside it, and a name absent from here is an unknown Widget
# whatever the model calls it.
WIDGET_REGISTRY: Mapping[str, WidgetDefinition] = {
    definition.name: definition
    for definition in (
        WidgetDefinition(
            name="metric_comparison",
            version=1,
            binding=BindingKind.CROSS_SYMBOL,
            # Two, because one symbol is not a comparison and the answer should
            # have stayed text. Twelve, because past that a bar chart is a table
            # and the component switches to one anyway.
            min_refs=2,
            max_refs=12,
            summary="one registered field across symbols",
        ),
        WidgetDefinition(
            name="ranked_symbols",
            version=1,
            binding=BindingKind.RANKING,
            min_refs=1,
            max_refs=1,
            summary="ordered Universe screening results",
        ),
        WidgetDefinition(
            name="metric_trend",
            version=1,
            binding=BindingKind.SERIES,
            min_refs=1,
            max_refs=1,
            summary="a registered analytical field over a fixed historical window",
        ),
        WidgetDefinition(
            name="relative_position",
            version=1,
            binding=BindingKind.POSITION,
            min_refs=1,
            max_refs=1,
            summary="where a value sits against its own history or the Universe",
        ),
        WidgetDefinition(
            name="quarterly_financials",
            version=1,
            binding=BindingKind.PERIODS,
            # One reference, because the binding is the whole served list of
            # periods rather than a figure inside one of them: a selection
            # naming two of them would be two tables.
            min_refs=1,
            max_refs=1,
            summary="stored statement figures across reporting periods",
        ),
    )
}


# The pictures Stock 360 already owns, as the tool and first path segment a
# binding would have to reach through to redraw one. Enumerated rather than
# inferred: "is this a price chart" is not a question a validator can answer
# from a field path, and a guess that goes the wrong way either refuses a
# legitimate Widget or ships a second drawing of a number that already has one.
#
# ``docs/adr/0012``: OHLCV, candlesticks, volume, valuation history, price
# ranges and peer valuation deep-link instead. One number lives in one place.
STOCK_360_SUBJECTS: Mapping[tuple[str, str], str] = {
    ("get_price_series", "data_ref"): "daily price history",
    ("get_price_series", "sample"): "daily price history",
    ("get_price_series", "summary"): "the session price range",
    ("get_financials", "periods"): "valuation history",
}


# The phrasings that count as *the user asked for a second visual*. A closed
# list, in both languages the product answers in, because the alternative is a
# model assertion — and ``docs/adr/0015`` does not let a model certify that it
# passed a backend check. Being conservative here costs a user an occasional
# second chart; being permissive costs every user the anti-spam rule.
# What turns a mention of a chart into a refusal of one. Substring matching
# cannot tell "vẽ biểu đồ" from "đừng vẽ biểu đồ", and of the two readings the
# expensive one is treating a refusal as a request: it raises the Widget ceiling
# and it turns a silent failure into a *Retry* box for something nobody wanted.
# So a negation anywhere in the message withdraws the request, which errs
# towards drawing less.
_NEGATIONS = ("đừng", "không", "khỏi", "chớ", "no chart", "without a chart", "don't")

_VISUAL_PHRASES = (
    "biểu đồ",
    "đồ thị",
    "chart",
    "graph",
    "vẽ",
    "trực quan",
    "visual",
    "plot",
)

_SECOND_WIDGET_PHRASES = (
    "hai biểu đồ",
    "2 biểu đồ",
    "hai đồ thị",
    "2 đồ thị",
    "hai chart",
    "2 chart",
    "cả hai biểu đồ",
    "từng biểu đồ riêng",
    "two charts",
    "2 charts",
    "both charts",
    "two graphs",
    "separate charts",
)


class WidgetRejected(Exception):
    """One selection that will not be shown, and why.

    Not a :class:`~src.agent.grounding.GroundingFailure`, and the difference is
    the point. A block that cannot be proven ends the Turn ``incomplete``,
    because a figure nobody can attribute must never reach a reader. A Widget
    that cannot be validated costs the reader a picture and nothing else, so it
    is dropped and the answer is released whole.

    ``deep_link`` is set only where the refusal has somewhere better to send the
    reader: a chart Stock 360 already owns.
    """

    def __init__(self, code: str, detail: str, *, deep_link: str | None = None) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.deep_link = deep_link

    def as_wire(self) -> dict[str, Any]:
        return {"code": self.code, "deep_link": self.deep_link}


@dataclass(frozen=True)
class WidgetSelection:
    """What the model wrote, before anything has been checked.

    Parsed, not validated: the name may not exist, the references may point at
    another Turn, and the title may be the model's third attempt at one. It is
    kept as a separate type from :class:`WidgetSpec` so that no code path can
    hold one and mistake it for the other.
    """

    name: str
    refs: tuple[EvidenceRef, ...]
    title: str


@dataclass(frozen=True)
class WidgetSpec:
    """A validated selection: the fixed-date descriptor a message stores.

    The series is deliberately absent. What is kept is enough to reconstruct the
    same historical slice and nothing more, which is what makes a reopened
    Thread a historical record rather than a fresh query wearing an old date.
    """

    name: str
    version: int
    title: str
    fields: tuple[str, ...]
    unit: str | None
    as_of: str
    descriptor: Mapping[str, Any]
    tool_call_ids: tuple[str, ...]
    # Whether the user asked for a picture. Not a preference: ``docs/adr/0012``
    # makes failure asymmetric on the web side, and this is the only place the
    # user's own words are available to answer it from.
    requested: bool = False

    @property
    def descriptor_id(self) -> str:
        return descriptor_id(self.descriptor)

    def as_wire(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "title": self.title,
            "fields": list(self.fields),
            "unit": self.unit,
            "as_of": self.as_of,
            "descriptor": dict(self.descriptor),
            "descriptor_id": self.descriptor_id,
            "tool_call_ids": list(self.tool_call_ids),
            "requested": self.requested,
        }


def descriptor_id(descriptor: Mapping[str, Any]) -> str:
    """A stable identity for one fixed slice, and the Redis key behind it.

    Derived from the descriptor rather than assigned, so the same slice
    requested twice is one cache entry and a descriptor that differs by a single
    day is a different one.
    """
    encoded = json.dumps(descriptor, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]


def _asks_for(user_text: str, phrases: Sequence[str]) -> bool:
    """Whether the user's own words ask for one of these things.

    Substring matching over a closed list, and a negation anywhere withdraws
    the ask. Both halves are deliberately blunt: the alternative is a model
    assertion, and ``docs/adr/0015`` does not let a model certify that it
    passed a backend check. Erring towards "no" costs a reader an occasional
    chart; erring towards "yes" spends the anti-spam rule on a message that
    said not to.
    """
    lowered = user_text.casefold()
    if any(negation in lowered for negation in _NEGATIONS):
        return False
    return any(phrase in lowered for phrase in phrases)


def user_requested_multiple(user_text: str) -> bool:
    """Whether this Turn's user text explicitly asked for more than one visual.

    Read off the user's own words, which is the only signal the backend owns.
    The model cannot set it, and there is no field it could set.
    """
    return _asks_for(user_text, _SECOND_WIDGET_PHRASES)


def user_requested_visual(user_text: str) -> bool:
    """Whether the user asked for a picture at all, in their own words.

    Recorded on the spec because the *web* needs it and cannot work it out:
    ``docs/adr/0012`` makes failure asymmetric — an agent-added Widget that
    fails disappears without noise, and a user-requested one leaves a short
    unavailable state with Retry, because the user is owed an answer to a
    question they asked. Only the backend holds the user's text, so only the
    backend can answer this honestly, and the model cannot set it.
    """
    return _asks_for(user_text, _VISUAL_PHRASES)


def extract_selections(text: str) -> tuple[str, tuple[WidgetSelection, ...]]:
    """Lift every Widget marker out of an answer, and hand back both halves.

    Called before the answer is split into blocks, so that a selection can never
    be mistaken for an evidence reference and a dropped selection can never
    leave a stray marker in what the reader sees.

    A marker whose body does not parse is discarded with the rest of the marker.
    That is the same degradation as any other rejection: the answer survives,
    and the picture does not.
    """
    selections: list[WidgetSelection] = []
    for match in SELECTION_PATTERN.finditer(text):
        parsed = _parse_selection(match.group(1))
        if parsed is not None:
            selections.append(parsed)
    return SELECTION_PATTERN.sub("", text), tuple(selections)


def _parse_selection(body: str) -> WidgetSelection | None:
    name, separator, remainder = body.partition("|")
    if not separator:
        logger.info("Dropped a Widget selection with no binding: %r", body)
        return None
    references, _, title = remainder.partition("|")
    refs: list[EvidenceRef] = []
    for candidate in references.split(","):
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            refs.append(EvidenceRef.parse(candidate))
        except GroundingFailure:
            logger.info("Dropped a Widget selection with a malformed reference: %r", body)
            return None
    if not refs:
        return None
    return WidgetSelection(
        name=name.strip().casefold(),
        refs=tuple(refs),
        title=_clean_title(title),
    )


def _clean_title(title: str) -> str:
    """The model's title, bounded and unable to impersonate a marker."""
    stripped = title.replace("[", "").replace("]", "").strip()
    stripped = re.sub(r"\s+", " ", stripped)
    return stripped[:MAX_TITLE_CHARS].strip()


class WidgetValidator:
    """Every check ``docs/adr/0012`` puts in front of persistence.

    Constructed per Turn, because two of the answers it needs are facts about
    *this* Turn: the Trading Day the slice is dated to, and whether the user
    asked for a second visual.
    """

    def __init__(
        self,
        *,
        trading_day: date,
        allow_second: bool = False,
        requested: bool = False,
    ) -> None:
        self._trading_day = trading_day
        self._allow_second = allow_second
        self._requested = requested

    def validate_all(
        self,
        selections: Sequence[WidgetSelection],
        traces: TraceIndex,
    ) -> tuple[tuple[WidgetSpec, ...], tuple[WidgetRejected, ...]]:
        """Validate a Turn's selections under the one-per-answer ceiling.

        Returns both halves rather than raising, because the caller's job is to
        emit what survived and record what did not — and a rejection is never a
        reason to withhold the answer.
        """
        ceiling = WIDGET_CEILING_ON_REQUEST if self._allow_second else WIDGET_CEILING
        specs: list[WidgetSpec] = []
        rejections: list[WidgetRejected] = []
        for selection in selections:
            if len(specs) >= ceiling:
                rejections.append(
                    WidgetRejected(
                        "widget_ceiling",
                        f"the answer already carries {len(specs)} Widget(s) and the "
                        "user did not ask for another",
                    )
                )
                continue
            try:
                specs.append(self.validate(selection, traces))
            except WidgetRejected as rejected:
                logger.info("Rejected a Widget selection: %s", rejected)
                rejections.append(rejected)
        return tuple(specs), tuple(rejections)

    def validate(self, selection: WidgetSelection, traces: TraceIndex) -> WidgetSpec:
        """Prove one selection, or refuse it. The answer is untouched either way."""
        definition = WIDGET_REGISTRY.get(selection.name)
        if definition is None:
            raise WidgetRejected(
                "unknown_widget",
                f"{selection.name!r} is not a registered Widget; the registry holds "
                + ", ".join(sorted(WIDGET_REGISTRY)),
            )
        if not definition.min_refs <= len(selection.refs) <= definition.max_refs:
            raise WidgetRejected(
                "binding_arity",
                f"{definition.name} takes between {definition.min_refs} and "
                f"{definition.max_refs} references and was given "
                f"{len(selection.refs)}",
            )
        self._refuse_stock_360(definition, selection, traces)
        builder = {
            BindingKind.CROSS_SYMBOL: self._cross_symbol,
            BindingKind.RANKING: self._ranking,
            BindingKind.SERIES: self._series,
            BindingKind.POSITION: self._position,
            BindingKind.PERIODS: self._periods,
        }[definition.binding]
        spec = builder(definition, selection, traces)
        self._refuse_future_slice(spec)
        # Stamped once, here, rather than threaded through four builders that
        # would each have to remember it.
        return replace(spec, requested=self._requested)

    def _refuse_future_slice(self, spec: WidgetSpec) -> None:
        """A picture cannot be dated past the Turn that drew it.

        The bindings all take their date off the trace, so this is not a check
        against the model — it is a check against a tool result, a clock or a
        store that disagrees with the Trading Day this Turn was admitted for. A
        chart dated tomorrow is the one staleness failure that looks like
        freshness, so it is refused rather than drawn.
        """
        try:
            dated = date.fromisoformat(spec.as_of)
        except ValueError:
            raise WidgetRejected(
                "missing_as_of", f"{spec.as_of!r} is not a Trading Day"
            ) from None
        if dated > self._trading_day:
            raise WidgetRejected(
                "future_slice",
                f"the selection is dated {dated.isoformat()} but this Turn is dated "
                f"{self._trading_day.isoformat()}",
            )

    # -- the four bindings -------------------------------------------------

    def _cross_symbol(
        self,
        definition: WidgetDefinition,
        selection: WidgetSelection,
        traces: TraceIndex,
    ) -> WidgetSpec:
        """One registered field, several symbols, one unit, one date."""
        citations = [self._cite(ref, traces) for ref in selection.refs]
        names = {citation.field_name for citation in citations}
        if len(names) != 1:
            raise WidgetRejected(
                "mixed_fields",
                "a metric comparison plots one field across symbols, and this "
                f"selection names {len(names)}",
            )
        field_name = next(iter(names))
        unit = self._one_unit(citations)
        as_of = self._one_as_of(citations)
        symbols = self._symbols(citations, traces)
        return WidgetSpec(
            name=definition.name,
            version=definition.version,
            title=selection.title,
            fields=(field_name,),
            unit=unit,
            as_of=as_of,
            descriptor={
                "kind": BindingKind.CROSS_SYMBOL.value,
                "field": field_name,
                "symbols": list(symbols),
                "as_of": as_of,
            },
            tool_call_ids=tuple(citation.call_id for citation in citations),
        )

    def _position(
        self,
        definition: WidgetDefinition,
        selection: WidgetSelection,
        traces: TraceIndex,
    ) -> WidgetSpec:
        """One registered value, against the range or sample it was ranked in."""
        citation = self._cite(selection.refs[0], traces)
        symbols = self._symbols([citation], traces)
        return WidgetSpec(
            name=definition.name,
            version=definition.version,
            title=selection.title,
            fields=(str(citation.field_name),),
            unit=citation.unit,
            as_of=str(citation.as_of),
            descriptor={
                "kind": BindingKind.POSITION.value,
                "field": citation.field_name,
                "symbol": symbols[0],
                "as_of": citation.as_of,
            },
            tool_call_ids=(citation.call_id,),
        )

    def _ranking(
        self,
        definition: WidgetDefinition,
        selection: WidgetSelection,
        traces: TraceIndex,
    ) -> WidgetSpec:
        """The ordered result of a screen, stored as the screen that produced it.

        The descriptor is the *question*, not the answer: the criteria, the sort
        and the day. Re-running it against a settled EOD store returns the same
        ranking, and storing the rows instead would put a copy of the Universe
        in every message that ever ranked it.
        """
        ref = selection.refs[0]
        # The tool is checked before the path is walked, because "you bound a
        # ranking to a computation cluster" is the diagnosis, and "that path
        # does not exist" is only what it looks like from inside the walk.
        named = traces.call(ref.call_id)
        if named is None or named.name != "screen_universe":
            raise WidgetRejected(
                "wrong_binding",
                "a ranked symbols Widget binds to screen_universe, not to "
                + (named.name if named is not None else repr(ref.call_id)),
            )
        call, _leaf = self._descriptor_binding(ref, traces)
        result = call.result if isinstance(call.result, Mapping) else {}
        as_of = result.get("as_of")
        if not as_of:
            raise WidgetRejected(
                "missing_as_of",
                "the screen carries no date, so its ranking cannot be replayed to the "
                "same slice",
            )
        arguments = dict(call.arguments or {})
        sort_by = str(arguments.get("sort_by", "adtv_vnd"))
        return WidgetSpec(
            name=definition.name,
            version=definition.version,
            title=selection.title,
            fields=(sort_by,),
            unit=None,
            as_of=str(as_of),
            descriptor={
                "kind": BindingKind.RANKING.value,
                "criteria": dict(arguments.get("criteria") or {}),
                "sort_by": sort_by,
                "order": str(arguments.get("order", "desc")),
                "limit": int(arguments.get("limit", 20)),
                "as_of": str(as_of),
            },
            tool_call_ids=(call.call_id,),
        )

    def _series(
        self,
        definition: WidgetDefinition,
        selection: WidgetSelection,
        traces: TraceIndex,
    ) -> WidgetSpec:
        """One registered field over a fixed window, as its Data Reference.

        The only Data Reference v1 produces is ``ohlcv``, and ``ohlcv`` is a
        chart Stock 360 owns — so in this build every series binding is refused
        by :meth:`_refuse_stock_360` before it reaches here, and this path opens
        when a tool first returns a Data Reference over a registered field. The
        Widget is registered now rather than later because ``docs/adr/0012``
        pins the version, and a version invented at the moment of first use is a
        version nobody reviewed.
        """
        ref = selection.refs[0]
        call, leaf = self._descriptor_binding(ref, traces)
        if not isinstance(leaf, Mapping) or "id" not in leaf:
            raise WidgetRejected(
                "wrong_binding",
                f"{ref.field_path!r} in tool call {ref.call_id!r} is not a Data "
                "Reference",
            )
        field_name = str(leaf.get("field") or "")
        self._require_registered(field_name)
        end = leaf.get("end")
        if not end:
            raise WidgetRejected(
                "missing_as_of", "the Data Reference names no last session"
            )
        return WidgetSpec(
            name=definition.name,
            version=definition.version,
            title=selection.title,
            fields=(field_name,),
            unit=registered_field(field_name).unit.value,
            as_of=str(end),
            descriptor={
                "kind": BindingKind.SERIES.value,
                "data_ref": dict(leaf),
                "as_of": str(end),
            },
            tool_call_ids=(call.call_id,),
        )

    def _periods(
        self,
        definition: WidgetDefinition,
        selection: WidgetSelection,
        traces: TraceIndex,
    ) -> WidgetSpec:
        """Stored statement figures across the reporting periods a call served.

        A descriptor binding rather than a citation one, for the reason
        :meth:`TraceIndex.resolve_descriptor` exists: a period row is a stored
        provider figure with no Signal Registry declaration, so it carries no
        unit and no sanctioned interpretation and would fail :meth:`_cite` on the
        ``as_of`` it does not have. What pins the slice instead is the list of
        period ends, copied off the result the model actually read.

        Two dates are kept and they are different facts. ``as_of`` is the newest
        period the table shows, which is what the reader is told the figures are
        dated to. ``trading_day`` is the Turn's own session, and it is the *read
        boundary* on replay: a filing for June arrives in August, so rebuilding
        the slice against June would silently drop the row it is meant to show.
        """
        ref = selection.refs[0]
        named = traces.call(ref.call_id)
        if named is None or named.name != FINANCIALS_TOOL:
            raise WidgetRejected(
                "wrong_binding",
                f"a quarterly financials Widget binds to {FINANCIALS_TOOL}, not to "
                + (named.name if named is not None else repr(ref.call_id)),
            )
        call, leaf = self._descriptor_binding(ref, traces)
        rows = [row for row in leaf if isinstance(row, Mapping)] if isinstance(
            leaf, Sequence
        ) and not isinstance(leaf, (str, bytes)) else []
        if not rows:
            raise WidgetRejected(
                "wrong_binding",
                f"{ref.field_path!r} in tool call {ref.call_id!r} is not the served "
                "list of reporting periods",
            )
        period_ends = [str(row.get("period_end") or "") for row in rows]
        if not all(period_ends):
            raise WidgetRejected(
                "missing_as_of",
                "a reporting period came back with no period end, so the slice is "
                "not fixed",
            )
        result = call.result if isinstance(call.result, Mapping) else {}
        symbol = result.get("symbol")
        if not isinstance(symbol, str) or not symbol:
            raise WidgetRejected(
                "unknown_symbol", f"tool call {ref.call_id!r} names no symbol to table"
            )
        # Only the columns the store actually answered with. A column of empty
        # cells is a claim that the figure exists and was not fetched, which is
        # the opposite of what an absent line item means.
        served = {
            name
            for row in rows
            for name in (row.get("figures") or {})
            if isinstance(row.get("figures"), Mapping)
        }
        columns = tuple(name for name in QUARTERLY_COLUMNS if name in served)
        if not columns:
            raise WidgetRejected(
                "missing_figures",
                "none of the statement figures this table draws was served for any "
                "of the periods",
            )
        as_of = max(period_ends)
        return WidgetSpec(
            name=definition.name,
            version=definition.version,
            title=selection.title,
            fields=columns,
            # Every column is a money figure in dong, which is why the unit is
            # one value on the spec rather than one per column.
            unit="vnd",
            as_of=as_of,
            descriptor={
                "kind": BindingKind.PERIODS.value,
                "symbol": symbol.upper(),
                "period_ends": period_ends,
                "figures": list(columns),
                "trading_day": self._trading_day.isoformat(),
                "as_of": as_of,
            },
            tool_call_ids=(call.call_id,),
        )

    # -- the shared checks -------------------------------------------------

    def _cite(self, ref: EvidenceRef, traces: TraceIndex) -> Citation:
        """Resolve one figure the way the Recommendation Validator would.

        A :class:`GroundingFailure` becomes a rejection rather than propagating:
        the failure is real, but its consequence here is a missing picture, not
        a blocked answer.
        """
        try:
            citation = traces.resolve(ref)
        except GroundingFailure as failure:
            raise WidgetRejected("unresolvable_binding", failure.detail) from failure
        if citation.source is not EvidenceSource.REGISTERED_FIELD:
            raise WidgetRejected(
                "unregistered_field",
                f"{ref.field_path!r} is {citation.source.value} evidence; a Widget "
                "plots registered fields computed in code",
            )
        self._require_registered(str(citation.field_name))
        if not citation.unit:
            raise WidgetRejected(
                "missing_unit",
                f"{citation.field_name} came back without the unit its reading "
                "depends on",
            )
        if not citation.as_of:
            raise WidgetRejected(
                "missing_as_of",
                f"{citation.field_name} carries no date, so the slice is not fixed",
            )
        return citation

    @staticmethod
    def _require_registered(name: str) -> None:
        """The Signal Registry is the authority on what a field is."""
        try:
            registered_field(name)
        except (KeyError, ValueError) as exc:
            raise WidgetRejected(
                "unregistered_field",
                f"{name!r} is not a Signal Registry declaration",
            ) from exc

    @staticmethod
    def _one_unit(citations: Sequence[Citation]) -> str:
        units = {citation.unit for citation in citations}
        if len(units) != 1:
            raise WidgetRejected(
                "mixed_units",
                "the selection puts " + ", ".join(sorted(str(u) for u in units))
                + " on one axis",
            )
        return str(next(iter(units)))

    @staticmethod
    def _one_as_of(citations: Sequence[Citation]) -> str:
        """Every bar in a comparison is dated to the same session.

        Two dates on one axis is a comparison of two different days told as one
        picture, which is the kind of thing a reader cannot see and cannot
        dispute.
        """
        dates = {citation.as_of for citation in citations}
        if len(dates) != 1:
            raise WidgetRejected(
                "mixed_dates",
                "the selection compares figures from "
                + ", ".join(sorted(str(day) for day in dates)),
            )
        return str(next(iter(dates)))

    @staticmethod
    def _symbols(citations: Sequence[Citation], traces: TraceIndex) -> tuple[str, ...]:
        """The symbol each cited call answered about, in the order cited."""
        symbols: list[str] = []
        for citation in citations:
            call = traces.call(citation.call_id)
            result = call.result if call is not None else None
            symbol = result.get("symbol") if isinstance(result, Mapping) else None
            if not isinstance(symbol, str) or not symbol:
                raise WidgetRejected(
                    "unknown_symbol",
                    f"tool call {citation.call_id!r} names no symbol to plot",
                )
            symbols.append(symbol.upper())
        if len(set(symbols)) != len(symbols):
            raise WidgetRejected(
                "duplicate_symbols",
                "the selection plots the same symbol more than once",
            )
        return tuple(symbols)

    @staticmethod
    def _descriptor_binding(
        ref: EvidenceRef, traces: TraceIndex
    ) -> tuple[TranscriptToolCall, Any]:
        try:
            return traces.resolve_descriptor(ref)
        except GroundingFailure as failure:
            raise WidgetRejected("unresolvable_binding", failure.detail) from failure

    @staticmethod
    def _refuse_stock_360(
        definition: WidgetDefinition,
        selection: WidgetSelection,
        traces: TraceIndex,
    ) -> None:
        """Never redraw a chart Stock 360 already owns; deep-link to it instead.

        The periods binding is the one exception, and it is an exception about
        *what is drawn* rather than about which tool answered. ``get_financials``
        is listed below because the valuation-history **chart** on the deep-dive
        screen is drawn from those periods; a quarterly table of filed figures is
        not that chart, and refusing it would send a reader asking for the
        numbers to a screen that shows them as a line.
        """
        if definition.binding is BindingKind.PERIODS:
            return
        for ref in selection.refs:
            call = traces.call(ref.call_id)
            if call is None:
                continue
            head = ref.field_path.split(".", 1)[0]
            subject = STOCK_360_SUBJECTS.get((call.name, head))
            if subject is None:
                continue
            result = call.result if isinstance(call.result, Mapping) else {}
            symbol = result.get("symbol")
            link = DEEP_LINK_ROUTE
            if isinstance(symbol, str) and symbol:
                link = f"{DEEP_LINK_ROUTE}?symbol={symbol.upper()}"
            raise WidgetRejected(
                "owned_by_stock_360",
                f"{subject} is already drawn on the deep-dive screen and is never "
                "redrawn here",
                deep_link=link,
            )


class WidgetDataResolver:
    """A stored descriptor, turned back into the same slice it always named.

    Two layers, in this order and no other: a 24-hour Redis entry, and the
    store behind it. The cache is not a source — it is a copy of what the store
    would rebuild, so an expiry costs a query and never a different answer. That
    is only sound because EOD data is settled, which is exactly why the
    descriptor pins a day rather than saying ``latest``.

    Nothing here chooses a day. A reopened Thread resolves the day the
    descriptor carries, and *update with new data* is a new Turn.

    **One thing is not pinned, and it is worth stating rather than implying.**
    A cross-sectional field — anything whose unit is ``percentile`` — is a rank
    *within the Universe*, and ``build_universe`` has no as-of dimension
    anywhere in this codebase: ADR-0001 defines the Universe as the active
    cohort, full stop. So a percentile replayed after the cache expires is the
    old day's figures ranked against the current cohort. The window, the field
    and the symbols are the ones the answer was written with; the peer set is
    today's. Giving the Universe a temporal dimension is a change to ADR-0001
    rather than to this module, so it is named here instead of quietly
    approximated.
    """

    def __init__(
        self,
        *,
        tools: Any,
        redis: Any | None = None,
        ttl_seconds: int = CACHE_TTL_SECONDS,
    ) -> None:
        self._tools = tools
        self._redis = redis
        self._ttl = ttl_seconds

    async def resolve(self, descriptor: Mapping[str, Any]) -> Mapping[str, Any]:
        """The data for one descriptor, or an explicit unavailable state."""
        key = f"alpha:widget:{descriptor_id(descriptor)}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        try:
            payload = await self._rebuild(descriptor)
        except WidgetRejected:
            raise
        except Exception as exc:  # noqa: BLE001 - the state is the answer
            # A slice that cannot be rebuilt resolves to the unavailable state
            # rather than propagating. The alternative is a transcript that
            # throws while re-reading a year-old answer, which is the failure
            # ``docs/adr/0012`` refuses on both sides of persistence.
            logger.info("A Widget slice could not be reconstructed: %s", exc)
            return {**_descriptor_echo(descriptor), **availability(False)}
        self._cache_set(key, payload)
        return payload

    async def _rebuild(self, descriptor: Mapping[str, Any]) -> Mapping[str, Any]:
        kind = str(descriptor.get("kind"))
        if kind == BindingKind.CROSS_SYMBOL.value:
            return {
                **_descriptor_echo(descriptor),
                **await self._tools.replay_field(
                    symbols=list(descriptor["symbols"]),
                    field_name=str(descriptor["field"]),
                    as_of=date.fromisoformat(str(descriptor["as_of"])),
                ),
            }
        if kind == BindingKind.POSITION.value:
            return {
                **_descriptor_echo(descriptor),
                **await self._tools.replay_field(
                    symbols=[str(descriptor["symbol"])],
                    field_name=str(descriptor["field"]),
                    as_of=date.fromisoformat(str(descriptor["as_of"])),
                ),
            }
        if kind == BindingKind.RANKING.value:
            screen = await self._tools.replay_screen(
                criteria=dict(descriptor.get("criteria") or {}),
                sort_by=str(descriptor["sort_by"]),
                order=str(descriptor["order"]),
                limit=int(descriptor["limit"]),
                as_of=date.fromisoformat(str(descriptor["as_of"])),
            )
            rows = list(screen.get("symbols") or ())
            return {
                **_descriptor_echo(descriptor),
                "rows": rows,
                "sort_by": screen.get("sort_by"),
                "order": screen.get("order"),
                "matched_count": screen.get("matched_count"),
                **availability(bool(rows)),
            }
        if kind == BindingKind.PERIODS.value:
            served = await self._tools.replay_financials(
                symbol=str(descriptor["symbol"]),
                period_ends=[str(day) for day in descriptor["period_ends"]],
                figures=[str(name) for name in descriptor["figures"]],
                trading_day=date.fromisoformat(str(descriptor["trading_day"])),
            )
            return {**_descriptor_echo(descriptor), **served}
        if kind == BindingKind.SERIES.value:
            reference = dict(descriptor["data_ref"])
            resolved = await self._tools.resolve_data_ref(reference)
            return {
                **_descriptor_echo(descriptor),
                **_series_points(resolved, str(reference.get("field") or "")),
            }
        raise WidgetRejected("unknown_descriptor", f"{kind!r} is not a Widget binding")

    def _cache_get(self, key: str) -> Mapping[str, Any] | None:
        if self._redis is None:
            return None
        try:
            raw = self._redis.get(key)
        except Exception:  # noqa: BLE001 - a cache miss is the safe reading
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw.decode() if isinstance(raw, bytes) else raw)
        except (ValueError, AttributeError):
            return None

    def _cache_set(self, key: str, payload: Mapping[str, Any]) -> None:
        if self._redis is None:
            return
        try:
            self._redis.set(
                key,
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str),
                ex=self._ttl,
            )
        except Exception:  # noqa: BLE001 - the store already answered
            return


def _series_points(resolved: Mapping[str, Any], field: str) -> dict[str, Any]:
    """One `(date, value)` series, whatever column the store answered with.

    A Data Reference is a *store* shape — the OHLCV one carries five columns —
    and a trend Widget takes one series. Naming the column here rather than in
    the component is the same rule as everywhere else in this module: the server
    decides what a Widget is looking at, and the component draws what it is
    given.
    """
    rows = resolved.get("series") or ()
    column = "close_price" if field == "ohlcv" else "value"
    points = [
        {"date": row.get("date"), "value": row.get(column)}
        for row in rows
        if isinstance(row, Mapping)
    ]
    present = any(point["value"] is not None for point in points)
    return {
        "field": field,
        # A price series is dong; a registered field brings its own declaration.
        "unit": "vnd" if field == "ohlcv" else registered_field(field).unit.value,
        "series": points,
        **availability(present),
    }


def _descriptor_echo(descriptor: Mapping[str, Any]) -> dict[str, Any]:
    """What every resolution carries back, whether or not it found data.

    The kind and the date ride along so that an unavailable state is still
    *dated* — a reader told a slice is missing should be told which slice.
    """
    return {
        "kind": descriptor.get("kind"),
        "as_of": descriptor.get("as_of"),
        "descriptor_id": descriptor_id(descriptor),
    }


__all__ = [
    "CACHE_TTL_SECONDS",
    "DEEP_LINK_ROUTE",
    "FINANCIALS_TOOL",
    "MAX_TITLE_CHARS",
    "QUARTERLY_COLUMNS",
    "SELECTION_PATTERN",
    "STOCK_360_SUBJECTS",
    "WIDGET_CEILING",
    "WIDGET_CEILING_ON_REQUEST",
    "WIDGET_REGISTRY",
    "BindingKind",
    "WidgetDataResolver",
    "WidgetDefinition",
    "WidgetRejected",
    "WidgetSelection",
    "WidgetSpec",
    "WidgetValidator",
    "descriptor_id",
    "extract_selections",
    "user_requested_multiple",
    "user_requested_visual",
]
