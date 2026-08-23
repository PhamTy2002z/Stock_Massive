"""Every fact an Analysis will display, assembled before a model sees any of it.

The envelope is the answer to one question: *what is true about this symbol on
this Trading Day, according to data this system already holds?* It is built from
durable stored rows and registered **Signal Field**s and from nothing else — no
**Provider Source**, no legacy live vnstock service, no tool loop, and no path to
a stored session except ``prepare_bars()``, which answers even the readiness
probe. That boundary is what makes a nightly artifact reproducible: an Analysis
rebuilt tomorrow from the same store has to say the same thing, and a live call
is a number nobody can rebuild.

**The model cannot manufacture or edit any of this.** Everything here is
backend-owned, and the fragment the model returns supplies judgment and narration
over it (spec 0003 §8.6). That is why the envelope carries units, kinds,
interpretations and health rather than only numbers: a figure handed over without
its sanctioned reading is a figure a narrator gets to interpret freely.

Three things in here are load-bearing and each is derived rather than accepted:

**Health is three values and a reason, never four states.** ``ok | degraded |
refused``, with the cause carried separately as a stable code out of the
**Signal Issue** vocabulary. ``insufficient_history`` is a refusal *reason*, and
a fourth state for it would be a second spelling of ``refused``.

**Section health is computed here and cannot be supplied.** It is a property of
the figures rather than a field beside them, so there is nowhere a caller — or a
model — could hand one in. A section is ``refused`` when nothing in it can be
used, ``ok`` when everything in it is healthy, and ``degraded`` in between, which
is the honest reading of a usable figure sitting beside a refused one.

**A profile field with nothing behind it is still emitted.** Refused, with reason
``unavailable`` and ``value: null``. Dropping it would make two Analyses carrying
the same ``fieldProfileVersion`` mean two different things, and nothing
downstream could tell.

The wire keys are camelCase, unlike this repository's REST shapes. They are the
artifact contract spec 0003 §8.6–§8.9 names key by key — ``asOf``,
``reasonCode``, ``fieldProfileVersion`` — and the model's output schema has to
match the input it was shown, so the artifact keeps the spec's spelling while the
REST layer keeps the repository's.

What this module does not do: it does not call a model, it does not write a row,
and it does not decide whether a run may be attempted a fourth time. It answers
for one pair or refuses it under a name from the pipeline's closed taxonomy.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable

from sqlalchemy.orm import Session

from src.stocks.listing_roster import ListingRosterStore
from src.stocks.signals.bars import WindowHealth, prepare_bars
from src.stocks.signals.fields import FieldValue, SignalField
from src.stocks.signals.issues import SignalIssue
from src.stocks.signals.registry import REGISTRY
from src.stocks.signals.serving import CrossSection, serve_cross_section, serve_field
from src.stocks.universe import build_universe

from .field_profile import (
    AXIS_ORDER,
    FIELD_PROFILE_VERSION,
    PRICE_ZONE_FIELD_ID,
    AnalysisIndustry,
    Axis,
    ProfileField,
    industry_for_icb,
    profile_for,
)
from .producer import ProductionFailure
from .reasons import sentence_for

# The template version of the envelope itself, stamped into the fingerprint's
# input. A reshaped envelope over identical evidence is a different input to a
# generation, and a fingerprint that could not tell them apart would reconcile an
# Analysis against a snapshot it was never built from.
ENVELOPE_SCHEMA_VERSION = 1

# Where a `stored` figure keeps the date it stopped being current. Three names
# rather than one because the stored figures in the profile are stamped by three
# different calendars: a quarterly statement by its `period_end`, a foreign room
# by the session its board was read in, a percentile by the date its sample was
# cut at. Read in this order, most specific first, so a percentile over quarterly
# statements is stamped by the quarter rather than by the cut.
_STORED_AS_OF_KEYS = ("period_end", "foreign_room_as_of", "as_of")


class Health(str, Enum):
    """What a figure or a section is worth, as the wire spells it.

    Three values, not four. Why a figure is not ``ok`` travels beside it as a
    ``reasonCode``, so the state stays a judgement a surface can branch on and
    the cause stays a fact the vocabulary owns.
    """

    OK = "ok"
    DEGRADED = "degraded"
    REFUSED = "refused"

    @property
    def usable(self) -> bool:
        """Whether a figure in this state may be cited at all.

        A refused figure stays in the artifact as honesty evidence — the reason
        a number is missing is exactly what a surface has to show in its place —
        but it can never support the verdict (spec 0003 §8.3).
        """
        return self is not Health.REFUSED


@dataclass(frozen=True)
class EvidenceFigure:
    """One figure the Analysis may display, or the named reason there is none.

    ``interpretation`` is the sanctioned reading and is never written here: a
    registered field's comes from the **Signal Registry**, and an unregistered
    one's comes from the profile entry that named it. Two copies of an
    interpretation are two interpretations as soon as one of them is edited.

    ``reason`` is the sentence a reader gets where a number would be, and it is
    present exactly when ``reason_code`` is. The code alone is honest to a
    machine and blank to a person, and a refusal displayed as honesty evidence is
    only evidence if it says something.

    ``sessions_used`` and ``window_days`` ride on every figure rather than only
    on the envelope, for the reason **Window Health** exists at all: a number
    drawn from twelve sessions and one drawn from two hundred look identical
    until the answer says which it is, and the fields in one envelope do not
    share a window — each declares its own ``min_sessions``.
    """

    field_id: str
    label: str
    value: float | None
    unit: str | None
    kind: str | None
    source: str | None
    interpretation: str
    health: Health
    reason_code: str | None
    reason: str | None
    as_of: date | None
    sessions_used: int | None
    window_days: int | None
    extras: Mapping[str, Any]

    @property
    def citable(self) -> bool:
        """Whether the model may point at this figure to support a verdict."""
        return self.health.usable and self.value is not None

    def as_wire(self) -> dict[str, Any]:
        return {
            "fieldId": self.field_id,
            "label": self.label,
            "value": self.value,
            "unit": self.unit,
            "kind": self.kind,
            "source": self.source,
            "interpretation": self.interpretation,
            "health": self.health.value,
            "reasonCode": self.reason_code,
            "reason": self.reason,
            "asOf": None if self.as_of is None else self.as_of.isoformat(),
            "sessionsUsed": self.sessions_used,
            "windowDays": self.window_days,
            "extras": _jsonable(self.extras),
        }


@dataclass(frozen=True)
class EvidenceSection:
    """One axis of the artifact, with the health the backend derived for it.

    Section membership and section order are not the model's to choose, so
    neither is expressible here: the figures arrive in the order the profile
    names them, the section arrives in the order ``AXIS_ORDER`` fixes, and
    ``health`` is derived from the figures rather than stored beside them.
    """

    axis: Axis
    figures: tuple[EvidenceFigure, ...]

    @property
    def health(self) -> Health:
        """The three-rule derivation, and the only place it is written.

        ``refused`` when nothing in the section can be used, ``ok`` when
        everything in it is healthy, ``degraded`` for every mixture — a usable
        figure sitting beside degraded or refused evidence is not a healthy
        section, and saying so is the difference between honesty evidence and a
        section that merely looks whole.
        """
        if not any(figure.health.usable for figure in self.figures):
            return Health.REFUSED
        if all(figure.health is Health.OK for figure in self.figures):
            return Health.OK
        return Health.DEGRADED

    @property
    def citable_field_ids(self) -> tuple[str, ...]:
        return tuple(figure.field_id for figure in self.figures if figure.citable)

    def as_wire(self) -> dict[str, Any]:
        return {
            "axis": self.axis.value,
            "health": self.health.value,
            "figures": [figure.as_wire() for figure in self.figures],
        }


@dataclass(frozen=True)
class EvidenceEnvelope:
    """Everything backend-owned about one ``(symbol, trading_day)``.

    The fingerprint is over the wire form rather than over this object, so it is
    a hash of what was actually sent. Recomputed from a stored payload it comes
    out the same, which is the only version of the guarantee worth having: an
    Analysis is reconciled against the evidence a dispute can read, not against
    an in-memory object nobody kept.
    """

    symbol: str
    company_name: str | None
    exchange: str | None
    industry: AnalysisIndustry
    trading_day: date
    price_zone: EvidenceFigure
    sections: tuple[EvidenceSection, ...]
    window_health: Mapping[str, Any]
    field_profile_version: str = FIELD_PROFILE_VERSION
    schema_version: int = ENVELOPE_SCHEMA_VERSION

    @property
    def figures(self) -> tuple[EvidenceFigure, ...]:
        """Every figure, price zone first and then the axes in their order."""
        return (self.price_zone,) + tuple(
            figure for section in self.sections for figure in section.figures
        )

    def figure(self, field_id: str) -> EvidenceFigure | None:
        """One figure by id, or None where the profile never named it."""
        for figure in self.figures:
            if figure.field_id == field_id:
                return figure
        return None

    @property
    def citable_field_ids(self) -> frozenset[str]:
        """Every id the model is allowed to cite, price zone included.

        A frozenset rather than a list: the question asked of it is membership,
        asked once per cited id by the validation behind the generation.
        """
        return frozenset(figure.field_id for figure in self.figures if figure.citable)

    @property
    def field_ids(self) -> frozenset[str]:
        """Every id the envelope carries, whether or not it may be cited."""
        return frozenset(figure.field_id for figure in self.figures)

    def as_wire(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "fieldProfileVersion": self.field_profile_version,
            "symbol": self.symbol,
            "companyName": self.company_name,
            "exchange": self.exchange,
            "industry": self.industry.value,
            "tradingDay": self.trading_day.isoformat(),
            "priceZone": self.price_zone.as_wire(),
            "sections": [section.as_wire() for section in self.sections],
            "windowHealth": _jsonable(self.window_health),
        }

    def fingerprint(self) -> str:
        """SHA-256 over the normalized envelope, insensitive to key order.

        ``sort_keys`` is what makes it insensitive: two dictionaries built in
        different orders are the same evidence, and a fingerprint that moved with
        insertion order would report a changed input every time a key was written
        somewhere else in this file. Nothing dated by a clock is in the input —
        the envelope carries the data's own ``asOf`` stamps and no
        ``generatedAt`` — so the digest is a statement about evidence rather than
        about when it was assembled.
        """
        canonical = json.dumps(
            self.as_wire(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# How the industry a symbol's profile is built for is decided. A seam rather than
# a call, so an artifact can be built for a stated industry without the register
# having to be written first — which is what makes the per-industry blocks
# testable while none of their metrics has a store behind it.
IndustryResolver = Callable[[Session, str], AnalysisIndustry]


def stored_industry(session: Session, symbol: str) -> AnalysisIndustry:
    """Which industry the store says this symbol is in.

    Read off the listing register, which is where the ICB level-2 code lands
    when the market's register is refreshed — a stored row, so the answer is
    reproducible and no Provider Source is asked what business a company is in.

    A symbol the register has never carried and one it carries with no code
    both answer ``unclassified``: neither is a statement that the profile has
    nothing extra for this business, which is what ``other`` means. The two stay
    apart here for the same reason they are separate values at all.
    """
    listing = ListingRosterStore(session).identity_of(symbol)
    return industry_for_icb(None if listing is None else listing.icb_code)


def build_envelope(
    session: Session,
    symbol: str,
    trading_day: date,
    *,
    industry: IndustryResolver = stored_industry,
    cross_sections: Mapping[str, CrossSection] | None = None,
    peers: Sequence[str] | None = None,
) -> EvidenceEnvelope:
    """Assemble the evidence for one pair, or refuse the pair by name.

    Two refusals and no others, both from the pipeline's closed taxonomy:
    ``missing_market_snapshot`` where the store holds no session for this symbol
    on this exact day, and ``insufficient_core_evidence`` where the price zone
    could not be read or where nothing else in the envelope can be cited beside
    it. Every other axis fails on its own — a missing quarterly statement refuses
    the Fundamental section and leaves the Analysis standing.

    ``cross_sections`` and ``peers`` are what a nightly pass measures once for a
    whole cohort. Left out, this call measures them for itself, which is what a
    single on-demand Analysis needs and what makes them an optimisation rather
    than a second code path. ``cross_sections={}`` is a caller stating there are
    no rankings, and every percentile in the artifact says so by name.
    """
    symbol = symbol.upper()
    _require_stored_session(session, symbol, trading_day)

    sample = tuple(peers) if peers is not None else _sample_around(session, symbol)
    if cross_sections is None:
        cross_sections = measure_cross_sections(session, trading_day, peers=sample)

    # Served once and read twice: the figure the artifact displays and the Window
    # Health the envelope carries come out of the same call, because two calls
    # could disagree about a window the store was written to in between.
    served_zone = serve_field(
        session, symbol, REGISTRY[PRICE_ZONE_FIELD_ID], end=trading_day, peers=sample
    )
    price_zone = _from_field_value(price_zone_entry(), served_zone)
    if not price_zone.citable:
        raise ProductionFailure(
            "insufficient_core_evidence",
            f"Không đọc được vùng giá thường ngày của mã {symbol} ở "
            f"phiên {trading_day.isoformat()}: {price_zone.reason_code}.",
        )

    resolved_industry = industry(session, symbol)
    profile = profile_for(resolved_industry)
    listing = ListingRosterStore(session).identity_of(symbol)
    envelope = EvidenceEnvelope(
        symbol=symbol,
        company_name=None if listing is None else listing.company_name,
        exchange=None if listing is None else listing.exchange.value,
        industry=resolved_industry,
        trading_day=trading_day,
        price_zone=price_zone,
        sections=tuple(
            EvidenceSection(
                axis=axis,
                figures=tuple(
                    _figure_for(
                        session, symbol, trading_day, entry, sample, cross_sections
                    )
                    for entry in profile[axis]
                ),
            )
            for axis in AXIS_ORDER
        ),
        window_health=_window_health_wire(served_zone.health),
    )

    # The price zone alone is a structurally complete artifact with nothing in
    # it: an Analysis whose only evidence is how far the symbol usually moves
    # says nothing a reader could act on. One further citable figure is the bar
    # spec 0003 §8.2 sets, and it is checked after the sections are built because
    # that is the first moment there is anything to check.
    if len(envelope.citable_field_ids) < 2:
        raise ProductionFailure(
            "insufficient_core_evidence",
            f"Mã {symbol} không có figure nào khác vùng giá để trích dẫn "
            f"cho phiên {trading_day.isoformat()}.",
        )

    return envelope


def measure_cross_sections(
    session: Session,
    trading_day: date,
    *,
    peers: Sequence[str] | None = None,
) -> Mapping[str, CrossSection]:
    """Rank every cross-sectional field the profile names, once for a cohort.

    A percentile is a position within a sample, so it cannot be answered for one
    symbol at a time — and answered once per symbol it would be answered against
    a sample that changed underneath it. Ranked here, for the whole Universe on
    one cutoff, every symbol in an evening's cohort reads its position out of the
    same ranking.

    A field whose sample was too thin comes back refused rather than absent, and
    the envelope turns that into an ``insufficient_cross_section`` figure — which
    is what a hundred-name Universe on a quiet board actually produces.
    """
    names = tuple(peers) if peers is not None else build_universe(session).symbols
    return {
        field_id: serve_cross_section(
            session, names, REGISTRY[field_id], end=trading_day
        )
        for field_id in ranked_field_ids()
    }


def ranked_field_ids() -> tuple[str, ...]:
    """Every profile field answered across a sample rather than for one symbol.

    Gathered over all five industries, not over one: a nightly pass ranks once
    for a cohort that may hold a bank beside a retailer, and a ranking measured
    for the industry that happened to come first would leave the rest unread.
    """
    return tuple(
        sorted(
            {
                entry.field_id
                for industry in AnalysisIndustry
                for fields in profile_for(industry).values()
                for entry in fields
                if entry.registered and REGISTRY[entry.field_id].ranked is not None
            }
        )
    )


# Every field the profile names anywhere, by id. Built once at import over all
# five industries rather than searched per call: a bank's block and a retailer's
# both name fields no other industry does, and a lookup that walked one profile
# would miss whichever industry it was not handed.
_PROFILE_ENTRIES: Mapping[str, ProfileField] = MappingProxyType(
    {
        entry.field_id: entry
        for industry in AnalysisIndustry
        for fields in profile_for(industry).values()
        for entry in fields
    }
)


def price_zone_entry() -> ProfileField:
    """The price zone as a profile entry, so one figure builder serves both.

    It is not in ``profile_for`` because it consumes no axis slot, and it is not
    a second shape because that would be a second set of rules for turning a
    served field into a figure.
    """
    return ProfileField(
        field_id=PRICE_ZONE_FIELD_ID,
        label="Ordinary daily range",
        description=REGISTRY[PRICE_ZONE_FIELD_ID].interpretation,
    )


def profile_entry_for(field_id: str) -> ProfileField:
    """The profile entry a registered field is dressed as, named or not.

    A field the **Analysis Field Profile** names carries the profile's own
    label, so a figure fetched one at a time reads identically to the same
    figure inside a seeded envelope — two labels for one field would make the
    same number look like two.

    A registered field the profile never names has no label anywhere, and its id
    stands in for one. That is not a gap to be filled with an invented phrase:
    sixteen of the thirty registered fields are in exactly this position
    (``plans/reports/baseline-oneshot-260822.md``), and a label written here
    would be a second interpretation of a field whose only sanctioned reading
    lives in the **Signal Registry**.
    """
    if field_id == PRICE_ZONE_FIELD_ID:
        return price_zone_entry()
    named = _PROFILE_ENTRIES.get(field_id)
    if named is not None:
        return named
    field = REGISTRY.get(field_id)
    if field is None:
        raise KeyError(field_id)
    return ProfileField(
        field_id=field_id,
        label=field_id,
        description=field.interpretation,
    )


def figure_for_field(
    session: Session,
    symbol: str,
    trading_day: date,
    field_id: str,
    *,
    cross_sections: Mapping[str, CrossSection] | None = None,
    peers: Sequence[str] | None = None,
) -> EvidenceFigure:
    """One registered field, answered for one pair, as the wire's figure.

    The same three shapes :func:`_figure_for` handles, reached by id rather than
    by walking a profile — which is what a caller asking for a field the profile
    never named needs. Every rule about how a served field becomes a figure
    stays in this module: a second place that dressed one would be a second set
    of rules, and the health mapping is the rule that matters.

    ``cross_sections`` left out means "measure what this field needs", the same
    thing it means to :func:`build_envelope`: a cohort measures its rankings
    once and passes them in, and a single answer measures its own.

    Raises ``KeyError`` for an id the **Signal Registry** does not hold. The
    caller decides what that is — for a tool it is a result the model reads, and
    inventing a refused figure for a field that does not exist would tell the
    model the store had looked.
    """
    field = REGISTRY.get(field_id)
    if field is None:
        raise KeyError(field_id)

    entry = profile_entry_for(field_id)
    sample = tuple(peers) if peers is not None else _sample_around(session, symbol)

    if field.ranked is None:
        return _from_field_value(
            entry,
            serve_field(session, symbol, field, end=trading_day, peers=sample),
        )

    ranking = None if cross_sections is None else cross_sections.get(field_id)
    if ranking is None and cross_sections is None:
        ranking = serve_cross_section(session, sample, field, end=trading_day)
    return _from_cross_section(symbol, entry, field, ranking)


def _figure_for(
    session: Session,
    symbol: str,
    trading_day: date,
    entry: ProfileField,
    peers: Sequence[str],
    cross_sections: Mapping[str, CrossSection],
) -> EvidenceFigure:
    """Read one profile entry, however it is answered — or refuse it honestly.

    Three shapes arrive here and only one of them queries the store: a field with
    no registered computation is refused without a query, a cross-sectional field
    is read out of a ranking that was already measured, and a single-symbol field
    is served through the one gateway.
    """
    if not entry.registered:
        return _unavailable(entry)

    field = REGISTRY[entry.field_id]
    if field.ranked is not None:
        return _from_cross_section(
            symbol, entry, field, cross_sections.get(entry.field_id)
        )

    return _from_field_value(
        entry, serve_field(session, symbol, field, end=trading_day, peers=peers)
    )


def _unavailable(entry: ProfileField) -> EvidenceFigure:
    """A field the profile names that nothing in this system computes.

    Emitted rather than dropped, which is the whole reason the profile names it.
    ``unavailable`` is the **Signal Issue** for a figure this system does not
    hold at all, as distinct from one it holds and cannot use.
    """
    return _refused(entry, SignalIssue.UNAVAILABLE)


def _from_cross_section(
    symbol: str,
    entry: ProfileField,
    field: SignalField,
    ranking: CrossSection | None,
) -> EvidenceFigure:
    """This symbol's place in a ranking, or the reason it has none.

    A symbol excluded from the sample keeps the exclusion's own Signal Issue —
    "no quarterly statement stored" and "not listed long enough" are different
    facts and a surface says different things about them. A ranking that was
    refused outright hands its refusal to every member, because there is no
    position to report when there was no distribution.

    A ranking nobody measured is ``ranking_unavailable`` and never
    ``unavailable``: the field is registered and computable, and what is missing
    is the sample rather than the computation. Collapsing the two would make a
    cohort that skipped a ranking look like a field this system never built.
    """
    if ranking is None:
        return _refused(entry, SignalIssue.RANKING_UNAVAILABLE, field=field)

    ranked = ranking.values.get(symbol)
    if ranked is not None:
        return _from_field_value(entry, ranked)

    return _refused(
        entry,
        ranking.excluded.get(symbol)
        or ranking.refusal
        or SignalIssue.INSUFFICIENT_CROSS_SECTION,
        field=field,
    )


def _refused(
    entry: ProfileField,
    issue: SignalIssue,
    *,
    field: SignalField | None = None,
) -> EvidenceFigure:
    """A figure with no number, and everything a reader needs in its place.

    No ``asOf``. A refused figure has no reading for a date to belong to, and
    stamping one would let a surface print an age beside a blank.
    """
    return EvidenceFigure(
        field_id=entry.field_id,
        label=entry.label,
        value=None,
        unit=None if field is None else field.unit.value,
        kind=None if field is None else field.kind.value,
        source=None if field is None else field.source.value,
        interpretation=entry.description if field is None else field.interpretation,
        health=Health.REFUSED,
        reason_code=issue.value,
        reason=sentence_for(issue),
        as_of=None,
        sessions_used=None,
        window_days=None if field is None else field.min_sessions,
        extras={},
    )


def _from_field_value(entry: ProfileField, served: FieldValue) -> EvidenceFigure:
    """Dress one served field as the wire's idea of a figure.

    The health mapping is the one rule that matters and it is ordered: a refusal
    wins over a degradation, because a field that could not answer has nothing
    for a degradation to describe.
    """
    if served.refusal is not None:
        health, issue = Health.REFUSED, served.refusal
    elif served.degraded_reason is not None:
        health, issue = Health.DEGRADED, served.degraded_reason
    else:
        health, issue = Health.OK, None

    return EvidenceFigure(
        field_id=entry.field_id,
        label=entry.label,
        value=served.value,
        unit=served.field.unit.value,
        kind=served.field.kind.value,
        source=served.field.source.value,
        interpretation=served.field.interpretation,
        health=health,
        reason_code=None if issue is None else issue.value,
        reason=None if issue is None else sentence_for(issue),
        # A degraded figure keeps its own stamp, which is the whole of the
        # freshness rule: a stale figure may be cited only where the narration
        # can make its age visible, and the age is this.
        as_of=None if served.refusal is not None else _as_of_of(served),
        sessions_used=served.health.sessions_used,
        window_days=served.field.min_sessions,
        extras=served.extras,
    )


def _as_of_of(served: FieldValue) -> date | None:
    """When this figure stopped being current.

    A computed figure is as of the newest session behind it, which is a fact
    about the window. A stored one is as of the calendar its own source keeps —
    a quarter, a board read, a ranking cut — and reading the window's last
    session for it would stamp a five-month-old statement with tonight's date.
    """
    for key in _STORED_AS_OF_KEYS:
        stamp = served.extras.get(key)
        if isinstance(stamp, date):
            return stamp
        if isinstance(stamp, str):
            try:
                return date.fromisoformat(stamp)
            except ValueError:
                continue
    return served.health.last_session


def _require_stored_session(session: Session, symbol: str, day: date) -> None:
    """Refuse the run unless the store holds this symbol's session for this day.

    The exact day, never the newest one at or before it. A Market Snapshot from
    yesterday relabelled as today is precisely the manufactured Analysis the
    availability deadline is forbidden from producing (``docs/adr/0014``), and
    the difference between the two questions is the whole guarantee.

    Asked through ``prepare_bars()`` rather than with a query of its own, so this
    module keeps one path to stored sessions and the boundary can be proven by
    reading its imports. A one-session window is requested and only
    ``sessions_used`` is read: the gateway may still refuse such a window over a
    band or a gap it found, and a refused window is a different fact from an
    absent session.
    """
    _, health = prepare_bars(session, symbol, 1, min_sessions=1, end=day)
    if health.sessions_used == 0:
        raise ProductionFailure(
            "missing_market_snapshot",
            f"Không có phiên {day.isoformat()} nào được lưu cho mã {symbol}.",
        )


def _sample_around(session: Session, symbol: str) -> tuple[str, ...]:
    """The Universe, with the symbol under analysis guaranteed to be in it.

    A Watchlist addition is Universe-restricted, so the only way the symbol is
    absent is that the Universe changed under a run that was already queued.
    Ranking it against a sample it is not in would leave every percentile in the
    artifact refused for a reason about configuration rather than about the
    company.
    """
    universe = build_universe(session).symbols
    return universe if symbol in universe else universe + (symbol,)


def _window_health_wire(health: WindowHealth) -> dict[str, Any]:
    """Window Health as the artifact carries it.

    The window the **price zone** was read over, because that is the one window
    every Analysis has: it is core evidence, a refused one fails the run, and no
    other field in the profile is guaranteed to have answered at all. Every
    figure additionally carries its own ``sessionsUsed`` and ``windowDays``,
    since the fields in one envelope do not share a window.
    """
    regime = health.band_regime
    return {
        "windowDays": health.window_days,
        "minSessions": health.min_sessions,
        "sessionsUsed": health.sessions_used,
        "firstSession": _jsonable(health.first_session),
        "lastSession": _jsonable(health.last_session),
        "limitLockDays": health.limit_lock_days,
        "bandUndecidedDays": health.band_undecided_days,
        "bandRegime": None
        if regime is None
        else {
            "exchange": None if regime.exchange is None else regime.exchange.value,
            "limitRatio": _jsonable(regime.limit_ratio),
            "anchorBasis": None
            if regime.anchor_basis is None
            else regime.anchor_basis.value,
            "uniform": regime.uniform,
        },
        "adjustment": {
            "applied": health.adjustment.applied,
            "actionsApplied": health.adjustment.actions_applied,
            "actionsInWindow": health.adjustment.actions_in_window,
            "exDatesApplied": [
                _jsonable(day) for day in health.adjustment.ex_dates_applied
            ],
        },
        "adtvPercentile": None if health.adtv is None else health.adtv.percentile,
        "quantitiesComparable": health.quantities_comparable,
        "refusal": _jsonable(health.refusal),
        "degradations": [issue.value for issue in health.degradations],
    }


def _jsonable(value: Any) -> Any:
    """Whatever a figure carried, in a form ``json.dumps`` can hash.

    Recursive because ``extras`` is the computations' own dictionary and this
    module does not get to dictate its shape — a field is free to return a date,
    a Decimal or a nested mapping, and the fingerprint has to survive all three.
    """
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


__all__ = [
    "ENVELOPE_SCHEMA_VERSION",
    "EvidenceEnvelope",
    "EvidenceFigure",
    "EvidenceSection",
    "Health",
    "IndustryResolver",
    "build_envelope",
    "figure_for_field",
    "measure_cross_sections",
    "price_zone_entry",
    "profile_entry_for",
    "ranked_field_ids",
    "stored_industry",
]
