"""Asking the evidence plane a question, one registered field at a time.

Two tools, and both lanes have them. That is a reversal of ``1e7b936`` — *a
general assistant that reads none of this system's data* — and it is a reversal
rather than a drift because the decision was taken when there was no way to read
the store that carried a figure's ``health`` and its ``asOf`` along with it.
These two tools are that way. A conversation reading a figure it can name the
date and the condition of is a different thing from a conversation reading a bare
number out of a table.

What they are for is measured rather than assumed. A fixed **Analysis Field
Profile** hands every symbol on every Trading Day the same eleven figures, and
sixteen of the thirty registered **Signal Field**s have therefore never reached
an Analysis at all (``plans/reports/baseline-oneshot-260822.md``). These two
tools are the route to those sixteen: a catalog to see what exists, and one call
to read one of them.

**The result shape already existed.** ``EvidenceFigure.as_wire()`` is what the
one-shot lane has always shown the model — value, unit, kind, sanctioned
reading, health, ``reasonCode``, ``reason``, ``asOf`` — so a figure fetched mid
loop is indistinguishable from a figure that was seeded. Nothing about how a
served field becomes a figure is written here; ``alpha/envelope.py`` owns that
and is asked.

**One tool, two signatures, and the difference is not a compromise.** In the
Analysis lane the symbol arrives through ``ToolContext``: the Run is keyed by
``(symbol, trading_day)``, so an argument naming a symbol would be a route to
reading a company this Analysis was not opened for. In a conversation there is no
such key — the symbol *is* the user's request, typed into the message — so there
it is an argument, checked against the Universe. The handler resolves one before
the other: a context that names a symbol wins, and an argument disagreeing with
it is refused rather than obeyed. The Analysis lane's boundary is therefore
enforced by the handler rather than by the absence of a field from a schema,
which is the stronger of the two — a schema is what the model is *told*.

**No lane may name a Trading Day or a peer list.** A day is a route to a session
that has not closed; a peer list is the sample a percentile is a position within,
and a model choosing its own comparison group chooses its own answer. In a
conversation the day is the newest session the store holds, resolved here.
``registry.py`` states the general form of this rule for a user and a thread, and
it is the same rule.

**No spill layer.** A figure measures about 730 bytes and the whole catalog of
thirty is roughly 22KB; the worst case here is a model asking for everything
this system knows how to compute, and that still fits any window this lane
runs on. So ``max_result_size_chars`` is set where it stops a bug rather than
where it manages a budget, and the truncate/dedup ladder the chat lane needs is
deliberately not ported.

**The catalog omits the sanctioned reading.** An ``interpretation`` is 227–663
characters and about 60% of a figure's weight; thirty of them would be most of
what the model reads before it has asked for anything. It travels with the field
that was actually requested, where it is the thing that makes the number
readable.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from types import MappingProxyType
from typing import Any

from sqlalchemy.orm import Session

from src.alpha.envelope import figure_for_field
from src.alpha.field_profile import (
    PRICE_ZONE_FIELD_ID,
    AnalysisIndustry,
    Axis,
    profile_for,
)
from src.core.database import get_sync_db
from src.stocks.shared.exceptions import StockServiceError
from src.stocks.shared.validators import validate_symbol
from src.stocks.signals.registry import REGISTRY
from src.stocks.trading_day import latest_trading_day
from src.stocks.universe import build_universe

from ..registry import ToolContext, ToolEntry, object_schema, register

TOOLSET = "signals"

#: Where a runaway result is cut. A bug-stop rather than a budget: the largest
#: honest answer either tool can give is the whole catalog, and that is an order
#: of magnitude under this.
MAX_RESULT_CHARS = 32_000

#: Which axis of an Analysis a field's namespace belongs to.
#:
#: Written out rather than derived, because it cannot be derived: the profile
#: assigns an axis only to the fields it names, and the sixteen fields these
#: tools exist to reach are exactly the ones it does not name. What *is* derived
#: is the agreement — :func:`_check_the_catalog_holds` refuses to import a table
#: that puts a field on a different axis from the one the profile already puts it
#: on, so the two cannot drift.
#:
#: ``price_zone`` is the one namespace with no profile axis to agree with. The
#: profile keeps it off the Technical axis so it consumes no slot there
#: (``alpha/field_profile.py``), which is a statement about slots rather than
#: about what kind of evidence it is. Asked what axis it reads on, the honest
#: answer is technical.
CATALOG_AXES: Mapping[str, Axis] = MappingProxyType(
    {
        "band_pressure": Axis.TECHNICAL,
        "company_profile": Axis.MONEY_FLOW,
        "drawdown_stats": Axis.TECHNICAL,
        "factor_percentiles": Axis.FUNDAMENTAL,
        "foreign_flow_pressure": Axis.MONEY_FLOW,
        "indicator_pack": Axis.TECHNICAL,
        "liquidity_profile": Axis.MONEY_FLOW,
        "mean_reversion": Axis.TECHNICAL,
        "momentum_rank": Axis.TECHNICAL,
        "price_zone": Axis.TECHNICAL,
        "realized_volatility": Axis.TECHNICAL,
        "relative_strength": Axis.TECHNICAL,
        "risk_adjusted": Axis.TECHNICAL,
        "trend_signal": Axis.TECHNICAL,
        "volatility_regime": Axis.TECHNICAL,
    }
)

SessionOpener = Callable[[], Any]


def namespace_of(field_id: str) -> str:
    """The part of an id before the dot, which is what carries the axis."""
    return field_id.split(".", 1)[0]


def axis_of(field_id: str) -> Axis:
    """Which axis this registered field reads on."""
    return CATALOG_AXES[namespace_of(field_id)]


def catalog(axis: Axis | None = None) -> tuple[Mapping[str, Any], ...]:
    """Every registered field, or every one on one axis, in registration order.

    Registration order rather than sorted, for the reason the tool registry keeps
    its own: this list is part of a cacheable prompt prefix, and an order that
    moved with a dict would move the prefix.
    """
    return tuple(
        {
            "fieldId": field.name,
            "label": _CATALOG_LABELS[field.name],
            "axis": axis_of(field.name).value,
            "unit": field.unit.value,
            "kind": field.kind.value,
            # The whole reason a refusal is actionable. A field refused for
            # ``insufficient_history`` at 250 sessions is answerable by a field
            # that needs 60, and this is the number that says which.
            "minSessions": field.min_sessions,
        }
        for field in REGISTRY.values()
        if axis is None or axis_of(field.name) is axis
    )


class SignalTools:
    """Read the catalog, and read one registered field for the pair in context."""

    def __init__(self, *, session_opener: SessionOpener = get_sync_db) -> None:
        # A session is not a trusted fact and so does not travel in
        # ``ToolContext``; it is opened and closed around one read, the same way
        # ``alpha/production.py`` takes its session factory as an argument.
        self._session_opener = session_opener

    def entries(self) -> tuple[ToolEntry, ...]:
        return (
            ToolEntry(
                name="list_fields",
                toolset=TOOLSET,
                description=(
                    "List every Signal Field this system can compute, with the "
                    "unit it is in and the minimum number of sessions it needs. "
                    "Use it when a figure you were given is refused for want of "
                    "history, or when the evidence you hold does not answer the "
                    "question this symbol raises."
                ),
                schema=object_schema(
                    {
                        "axis": {
                            "type": "string",
                            "enum": [axis.value for axis in Axis],
                            "description": (
                                "Restrict the list to one axis. Omit it for the "
                                "whole catalog."
                            ),
                        }
                    }
                ),
                handler=self.list_fields,
                # This system's own field registry. Nothing here was written
                # outside the deployment, so the message layer does not wrap it.
                reads_external=False,
                # Pure: a registry read, no session, no socket. There is nothing
                # here to move off the event loop.
                is_async=True,
                max_result_size_chars=MAX_RESULT_CHARS,
            ),
            ToolEntry(
                name="get_field",
                toolset=TOOLSET,
                description=(
                    "Read one Signal Field out of this system's own store for one "
                    "symbol, on the most recent closed session. Returns the figure "
                    "with its unit, its sanctioned reading, its health and the "
                    "date it is as of — or the named reason the store cannot "
                    "answer it. There is no way to ask for a session that has not "
                    "closed."
                ),
                schema=object_schema(
                    {
                        "field_id": {
                            "type": "string",
                            "minLength": 1,
                            "description": (
                                "A fieldId from list_fields, exactly as it is "
                                "spelled there."
                            ),
                        },
                        "symbol": {
                            "type": "string",
                            "minLength": 1,
                            "description": (
                                "The ticker to read it for. Omit it where the "
                                "caller is already opened for one symbol, which "
                                "is what an Analysis is; naming a different one "
                                "there is refused."
                            ),
                        },
                    },
                    ("field_id",),
                ),
                handler=self.get_field,
                reads_external=False,
                # ``serve_field`` takes a synchronous Session, so this blocks;
                # the executor moves it to a worker thread rather than letting
                # one store read stall the rest of the round.
                is_async=False,
                max_result_size_chars=MAX_RESULT_CHARS,
            ),
        )

    def list_fields(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        raw = arguments.get("axis")
        axis = None
        if raw is not None and str(raw).strip():
            try:
                axis = Axis(str(raw).strip())
            except ValueError:
                raise ValueError(
                    f"{raw!r} is not an axis; the four are "
                    f"{', '.join(item.value for item in Axis)}"
                ) from None
        fields = catalog(axis)
        return {
            "axis": None if axis is None else axis.value,
            "count": len(fields),
            "fields": list(fields),
        }

    def get_field(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        field_id = str(arguments.get("field_id") or "").strip()
        if not field_id:
            raise ValueError("field_id must name a registered field")
        if field_id not in REGISTRY:
            # A result rather than a raise the model cannot read: it asked for a
            # name that does not exist, and what it needs back is the fact that
            # nothing holds it plus where the real names are. Inventing a refused
            # figure instead would tell it the store had looked.
            raise ValueError(
                f"{field_id!r} is not a registered Signal Field. Call list_fields "
                "for the ids this system computes."
            )
        with self._open() as session:
            pair = _pair(context, arguments, session)
            if isinstance(pair, dict):
                return pair
            symbol, trading_day = pair
            figure = figure_for_field(session, symbol, trading_day, field_id)
        return figure.as_wire()

    @contextmanager
    def _open(self) -> Iterator[Session]:
        with self._session_opener() as session:
            yield session


def _pair(
    context: ToolContext, arguments: Mapping[str, Any], session: Session
) -> tuple[str, Any] | dict[str, Any]:
    """The symbol and Trading Day this call is for, or a sentence saying why not.

    **The context is asked first and it is final.** An Analysis is opened for one
    pair, so where the context names a symbol that is the symbol; an argument
    naming a different one is refused rather than obeyed, which closes the route
    that the argument's absence from the Analysis lane's schema only discouraged.
    An argument naming the *same* symbol is allowed through, because it is not a
    request for anything else.

    **Without a context, the symbol is the user's own request.** A conversation
    is not keyed by anything, so a ticker typed into the message is the only place
    the subject can come from. It is validated and checked against the Universe:
    a symbol this system never collected has no figures, and a refusal saying so
    is the honest answer where an empty one reads as "nothing is happening at that
    company".

    **The Trading Day is never an argument in either lane.** The newest closed
    session in the store, resolved here — a day the model could name is a day it
    could name before it closed.
    """
    named = str(arguments.get("symbol") or "").strip().upper()
    if context.symbol:
        held = context.symbol.upper()
        if named and named != held:
            return _cannot(
                f"This call reads {held} and cannot read {named}. It was opened "
                f"for one symbol, and the figures it serves are {held}'s."
            )
        if context.trading_day is None:
            return _cannot(
                "This call names a symbol and no Trading Day, so there is no "
                "session to read it on."
            )
        return held, context.trading_day

    if not named:
        return _cannot(
            "get_field reads one symbol and none was named. Give the ticker the "
            "question is about."
        )
    try:
        symbol = validate_symbol(named)
    except StockServiceError:
        return _cannot(
            f"{named!r} is not the shape of a ticker on this market, so this "
            "system holds nothing under it."
        )
    if not build_universe(session).contains(symbol):
        return _cannot(
            f"{symbol} is outside the Universe this system collects, so there is "
            "no stored session to compute a field from. It is not a statement "
            "about the company."
        )
    trading_day = latest_trading_day(session)
    if trading_day is None:
        return _cannot(
            "This system holds no closed session yet, so there is no day to read "
            "a field on."
        )
    return symbol, trading_day


def _cannot(sentence: str) -> dict[str, Any]:
    """A refusal shaped so the model reads it and the loop does not mistake it.

    Returned rather than raised: the question was well formed and the answer is
    that the store has nothing to say, which is a fact the model should relay
    rather than a tool failure it will read as the tool being broken. It carries
    no ``fieldId``, so ``alpha/analysis_loop`` cannot fold it into an envelope as
    a figure.
    """
    return {"error": "cannot_read", "detail": sentence}


def _labels() -> Mapping[str, str]:
    """One label per registered field, taken from the profile where it has one.

    Asked of ``alpha/envelope.py`` rather than restated, so a figure listed in
    the catalog and the same figure fetched by id carry one label. Built at
    import: the profile is fixed at import too, and thirty lookups per call
    would be thirty lookups for an answer that cannot change.
    """
    from src.alpha.envelope import profile_entry_for

    return MappingProxyType(
        {name: profile_entry_for(name).label for name in REGISTRY}
    )


def _check_the_catalog_holds() -> None:
    """Refuse to import an axis table that disagrees with the profile.

    Two directions, because a one-way check is the one that rots. A registered
    namespace with no axis would make its fields unlistable under any filter and
    unreachable through the catalog they exist to be reached through; an axis
    entry for a namespace nothing registers is a line describing a field that is
    gone.

    And the agreement itself: every field the **Analysis Field Profile** places
    on an axis has to be placed on that same axis here. Two answers to "which
    axis is this" is the defect this table is most likely to acquire, because
    only one of the two is visible in a payload.
    """
    registered = {namespace_of(name) for name in REGISTRY}
    missing = sorted(registered - set(CATALOG_AXES))
    if missing:
        raise ValueError(
            "these registered namespaces have no axis, so their fields could "
            f"not be listed: {', '.join(missing)}"
        )
    stale = sorted(set(CATALOG_AXES) - registered)
    if stale:
        raise ValueError(
            f"these namespaces have an axis and no registered field: {', '.join(stale)}"
        )

    for industry in AnalysisIndustry:
        for axis, fields in profile_for(industry).items():
            for entry in fields:
                if entry.field_id not in REGISTRY:
                    # Named by the profile and computed by nothing — a bank
                    # metric or a news count. The envelope emits it refused; the
                    # catalog cannot list what it cannot serve.
                    continue
                placed = axis_of(entry.field_id)
                if placed is not axis:
                    raise ValueError(
                        f"{entry.field_id} is on the {axis.value} axis of the "
                        f"{industry.value} profile and on {placed.value} here"
                    )

    if axis_of(PRICE_ZONE_FIELD_ID) is not Axis.TECHNICAL:
        raise ValueError(
            f"{PRICE_ZONE_FIELD_ID} is core evidence and reads on the technical "
            "axis, whatever slot it does or does not consume"
        )


_check_the_catalog_holds()
_CATALOG_LABELS: Mapping[str, str] = _labels()


def register_signal_tools(**kwargs: Any) -> tuple[ToolEntry, ...]:
    """Register both store tools and hand the registrations back to the caller."""
    tools = SignalTools(**kwargs)
    return tuple(register(entry) for entry in tools.entries())


__all__ = [
    "CATALOG_AXES",
    "MAX_RESULT_CHARS",
    "TOOLSET",
    "SignalTools",
    "axis_of",
    "catalog",
    "namespace_of",
    "register_signal_tools",
]
