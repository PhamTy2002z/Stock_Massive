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
from datetime import datetime, time, timezone
from statistics import median
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
from src.stocks.trading_day import latest_trading_day, trading_days_before
from src.stocks.universe import build_universe
from src.studies import frames_buffer
from src.studies.contracts import Frame, Provenance

from ..registry import (
    ContentTrust,
    ToolAccess,
    ToolConcurrency,
    ToolContext,
    ToolEffect,
    ToolEntry,
    ToolIdempotency,
    register,
)
from ..signal_tool_contract import (
    GET_FIELD_DESCRIPTION,
    GET_FIELD_SCHEMA,
    GET_SERIES_DESCRIPTION,
    GET_SERIES_SCHEMA,
    LIST_FIELDS_DESCRIPTION,
    LIST_FIELDS_SCHEMA,
)

TOOLSET = "signals"

#: Where a runaway result is cut. A bug-stop rather than a budget: the largest
#: honest answer either tool can give is the whole catalog, and that is an order
#: of magnitude under this.
MAX_RESULT_CHARS = 32_000

#: The most sessions a series may span, whatever the field costs to read.
#:
#: A ceiling on the *picture* rather than on the work: past a hundred and twenty
#: points a chart four hundred pixels wide is a texture, and the question it
#: answers is the same one sixty points answer.
MAX_SERIES_SESSIONS = 120

#: The most sessions-of-bars one series may read, in total.
#:
#: The real cost, and the reason the ceiling above is not the only one. A field
#: is computed over its own window, so a series is ``points × window`` session
#: reads: a momentum field declaring 273 sessions costs two hundred times what a
#: twenty-session field costs for the same picture. This number is what stops a
#: perfectly reasonable-looking request from spending a round — the clamp lands
#: on the number of points, and the answer says how many were actually read.
MAX_WINDOW_READS = 12_000

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

#: What a reader is shown when one of these fields is looked up, in Vietnamese.
#:
#: A second name for each field, and deliberately not the one that travels with
#: the figure. ``envelope.profile_entry_for`` gives a field the **Analysis Field
#: Profile**'s label where it has one and its own id where it does not, and
#: refuses to invent the missing ones on the grounds that a label beside a number
#: is an interpretation of it. That refusal is right and this table does not
#: touch it: nothing here reaches a payload, a figure or the model. These are rail
#: rows — the line a person reads to see *which* field was looked up — and for
#: that job an id is not a label at all.
#:
#: Which is what a real Turn showed: fourteen rows reading ``get_field``, because
#: sixteen of the thirty registered fields have no profile label and the rail had
#: nothing else to print.
#:
#: Written out rather than derived, and checked both ways at import
#: (:func:`_check_the_display_names_hold`) so a field added to the **Signal
#: Registry** without a row here fails the build instead of reaching a screen as
#: its own id.
DISPLAY_NAMES: Mapping[str, str] = MappingProxyType(
    {
        "band_pressure.limit_days_in_window": "Số phiên chạm biên",
        "company_profile.foreign_room_pct": "Room ngoại còn lại",
        "drawdown_stats.current_drawdown_pct": "Sụt giá hiện tại",
        "drawdown_stats.days_underwater": "Số phiên dưới đỉnh",
        "drawdown_stats.max_drawdown_pct": "Sụt giá sâu nhất",
        "drawdown_stats.mdd_over_expected": "Sụt giá so mức kỳ vọng",
        "factor_percentiles.book_yield_percentile": "Phân vị lợi suất sổ sách",
        "factor_percentiles.earnings_yield_percentile": "Phân vị lợi suất lợi nhuận",
        "factor_percentiles.roe_percentile": "Phân vị ROE",
        "factor_percentiles.size_percentile": "Phân vị quy mô",
        "foreign_flow_pressure.net_value_over_adtv": "Áp lực dòng tiền ngoại",
        "foreign_flow_pressure.net_volume_over_adtv": "Khối lượng ròng ngoại",
        "foreign_flow_pressure.persistence_run_days": "Chuỗi phiên ròng ngoại",
        "indicator_pack.bollinger_percent_b_20": "Bollinger %B (20)",
        "indicator_pack.macd_12_26_vnd": "MACD (12/26)",
        "indicator_pack.rsi_14": "RSI (14)",
        "liquidity_profile.adtv_percentile": "Phân vị thanh khoản",
        "liquidity_profile.adtv_shares": "Khối lượng giao dịch bình quân",
        "liquidity_profile.adtv_vnd": "Giá trị giao dịch bình quân",
        "liquidity_profile.amihud_illiq": "Độ kém thanh khoản Amihud",
        "mean_reversion.half_life_sessions": "Chu kỳ bán rã hồi quy",
        "mean_reversion.trailing_z": "Độ lệch so trung bình",
        "momentum_rank.percentile_12_2": "Phân vị động lượng",
        "price_zone.ordinary_range_pct": "Biên độ ngày thường",
        "realized_volatility.yang_zhang_annualized_pct": "Biến động thực tế",
        "relative_strength.beta_vs_market_index": "Beta so chỉ số thị trường",
        "risk_adjusted.sharpe_annualized": "Sharpe (năm hoá)",
        "risk_adjusted.sortino_annualized": "Sortino (năm hoá)",
        "trend_signal.total_return_12m_pct": "Hiệu suất giá 12 tháng",
        "volatility_regime.gk_variance_robust_z": "Chế độ biến động",
    }
)

#: What a reader is shown for an axis, when the catalog is asked for one.
AXIS_DISPLAY_NAMES: Mapping[str, str] = MappingProxyType(
    {
        Axis.TECHNICAL.value: "kỹ thuật",
        Axis.FUNDAMENTAL.value: "cơ bản",
        Axis.MONEY_FLOW.value: "dòng tiền",
        Axis.NEWS.value: "tin tức",
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



def display_name_of(field_id: str) -> str:
    """The phrase a person reads for this field, or its id if it has none.

    The fallback is unreachable for a registered field — the import check below
    refuses a build where one is missing — and is kept for the one caller that
    can pass anything: a rail row built from whatever the model actually put in
    ``field_id``, which may be a name nothing holds.
    """
    return DISPLAY_NAMES.get(field_id, field_id)


def summarise_get_field(arguments: Mapping[str, Any]) -> str:
    """The rail row for one field read: which figure, and for which company.

    Composed here rather than from one argument, because one argument cannot say
    it. The field alone would read the same for every symbol in a Turn that
    compared two, and the symbol alone would not say what was looked up.

    The symbol is absent in the Analysis lane, where it is a trusted fact rather
    than an argument, and the row is then the field alone — which is right: every
    row of that rail is about the one company the Analysis is for.
    """
    field_id = str(arguments.get("field_id") or "").strip()
    label = display_name_of(field_id) if field_id else "chỉ báo"
    symbol = str(arguments.get("symbol") or "").strip().upper()
    return f"Đọc chỉ báo: {label} — {symbol}" if symbol else f"Đọc chỉ báo: {label}"


def summarise_get_series(arguments: Mapping[str, Any]) -> str:
    """The rail row for a series read: which figure, which company, how far back."""
    field_id = str(arguments.get("field_id") or "").strip()
    label = display_name_of(field_id) if field_id else "chỉ báo"
    symbol = str(arguments.get("symbol") or "").strip().upper()
    sessions = arguments.get("sessions")
    span = f" · {sessions} phiên" if isinstance(sessions, int) else ""
    return f"Đọc chuỗi: {label} — {symbol}{span}" if symbol else f"Đọc chuỗi: {label}{span}"


def points_affordable(window_sessions: int, asked: int) -> int:
    """How many points a series of this field may hold, given what it costs.

    Written as its own function because it is the whole of the cost rule and a
    test should be able to state it without a store: a field's window multiplied
    by the points asked for is the number of session reads, and this is where
    that product is held under :data:`MAX_WINDOW_READS`.
    """
    ceiling = max(1, MAX_WINDOW_READS // max(1, window_sessions))
    return max(1, min(MAX_SERIES_SESSIONS, ceiling, asked))


def summarise_list_fields(arguments: Mapping[str, Any]) -> str:
    """The rail row for a catalog read, naming the axis when one was asked for."""
    raw = str(arguments.get("axis") or "").strip()
    axis = AXIS_DISPLAY_NAMES.get(raw)
    return f"Xem danh mục chỉ báo: {axis}" if axis else "Xem danh mục chỉ báo"

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
                description=LIST_FIELDS_DESCRIPTION,
                schema=LIST_FIELDS_SCHEMA,
                handler=self.list_fields,
                display_name="Xem danh mục chỉ báo",
                summarise=summarise_list_fields,
                # This system's own field registry. Nothing here was written
                # outside the deployment, so the message layer does not wrap it.
                effect=ToolEffect.READ,
                idempotency=ToolIdempotency.IDEMPOTENT,
                access=ToolAccess.STORE,
                content_trust=ContentTrust.TRUSTED_STRUCTURED,
                concurrency=ToolConcurrency.SERIALIZED,
                contract_version="1",
                # Pure: a registry read, no session, no socket. There is nothing
                # here to move off the event loop.
                is_async=True,
                max_result_size_chars=MAX_RESULT_CHARS,
            ),
            ToolEntry(
                name="get_field",
                toolset=TOOLSET,
                description=GET_FIELD_DESCRIPTION,
                schema=GET_FIELD_SCHEMA,
                handler=self.get_field,
                display_name="Đọc chỉ báo",
                summarise=summarise_get_field,
                effect=ToolEffect.READ,
                idempotency=ToolIdempotency.IDEMPOTENT,
                access=ToolAccess.STORE,
                content_trust=ContentTrust.TRUSTED_STRUCTURED,
                concurrency=ToolConcurrency.SERIALIZED,
                contract_version="1",
                # ``serve_field`` takes a synchronous Session, so this blocks;
                # the executor moves it to a worker thread rather than letting
                # one store read stall the rest of the round.
                is_async=False,
                max_result_size_chars=MAX_RESULT_CHARS,
            ),
            ToolEntry(
                name="get_series",
                toolset=TOOLSET,
                description=GET_SERIES_DESCRIPTION,
                schema=GET_SERIES_SCHEMA,
                handler=self.get_series,
                display_name="Đọc chuỗi chỉ báo",
                summarise=summarise_get_series,
                effect=ToolEffect.READ,
                idempotency=ToolIdempotency.IDEMPOTENT,
                access=ToolAccess.STORE,
                content_trust=ContentTrust.TRUSTED_STRUCTURED,
                concurrency=ToolConcurrency.SERIALIZED,
                contract_version="1",
                # Sixty windows of a synchronous store read, and a row written
                # at the end of them. It belongs on a worker thread more than
                # anything else in this file does.
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

    def get_series(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Read one field across a window of sessions, and keep the series.

        Every rule ``get_field`` holds, held here per point: a registered field
        only, a symbol in the Universe only, and no session that has not closed.
        A point the store refuses is a ``null`` in the series with its reason
        counted in the provenance — dropping it would close a gap the reader
        should see, and writing a zero would invent a number.

        The series does not come back. What comes back is a summary small enough
        to read in a sentence and the id the canvas draws it by.
        """
        field_id = str(arguments.get("field_id") or "").strip()
        if not field_id:
            raise ValueError("field_id must name a registered Signal Field")
        field = REGISTRY.get(field_id)
        if field is None:
            raise ValueError(
                f"{field_id!r} is not a registered Signal Field. Call list_fields "
                "for the ids this system computes."
            )

        asked = arguments.get("sessions")
        wanted = asked if isinstance(asked, int) and asked > 0 else 60

        with self._open() as session:
            pair = _pair(context, arguments, session)
            if isinstance(pair, dict):
                return pair
            symbol, newest = pair

            points = points_affordable(field.window_sessions, wanted)
            # Newest first out of the store, oldest first on the chart: a series
            # read right to left is a series nobody reads.
            days = [newest, *trading_days_before(session, newest, points - 1)]
            days.sort()

            rows: list[tuple[Any, ...]] = []
            reasons: dict[str, int] = {}
            answered = 0
            unit: str | None = None
            for day in days:
                figure = figure_for_field(session, symbol, day, field_id)
                if figure.value is None:
                    code = figure.reason_code or "refused"
                    reasons[code] = reasons.get(code, 0) + 1
                else:
                    answered += 1
                    unit = unit or figure.unit
                rows.append((day.isoformat(), figure.value))

            if answered == 0:
                # Every point refused is a refusal about the window rather than
                # a series with holes, and there is nothing to draw.
                return _cannot(
                    f"{display_name_of(field_id)} could not be computed for "
                    f"{symbol} on any of the {len(days)} sessions read"
                    + (f" ({', '.join(sorted(reasons))})" if reasons else "")
                )

            frame = Frame(
                kind="series",
                columns=("session", "value"),
                rows=tuple(rows),
                unit=unit,
                labels={"session": "Phiên", "value": display_name_of(field_id)},
            )
            provenance = Provenance(
                source="store",
                as_of=_as_of(context, days[-1]),
                sessions_used=answered,
                health="normal" if not reasons else "degraded",
                reason=(
                    None
                    if not reasons
                    else ", ".join(
                        f"{code}: {count}" for code, count in sorted(reasons.items())
                    )
                ),
            )
            frame_id = frames_buffer.store_series(
                session,
                frame=frame,
                provenance=provenance,
                params={
                    "field_id": field_id,
                    "symbol": symbol,
                    "sessions": len(days),
                },
                turn_id=context.turn_id,
                thread_id=context.thread_id,
            )

        values = [value for _, value in rows if value is not None]
        return {
            "fieldId": field_id,
            "symbol": symbol,
            "label": display_name_of(field_id),
            "unit": unit,
            # The whole model-facing surface. Enough to say what the series does
            # in a sentence, and not enough to describe a point the reader can
            # see and the model cannot.
            "summary": {
                "first": values[0],
                "last": values[-1],
                "min": min(values),
                "max": max(values),
                "median": median(values),
            },
            "sessionsRead": len(days),
            "sessionsUsed": answered,
            "sessionsAsked": wanted,
            "health": provenance.health,
            "refusals": dict(sorted(reasons.items())),
            # What render_canvas draws it by. The series itself is in the row
            # this names, and there is no way to ask for it here.
            "frameId": str(frame_id),
        }

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


def _as_of(context: ToolContext, newest: Any) -> datetime:
    """The instant this series is frozen at.

    The caller's clock where there is one, so a test asserting the stamp and the
    handler writing it read the same instant; otherwise the end of the newest
    session read, which is the honest answer for a run outside a Turn.
    """
    if context.now is not None:
        return context.now
    return datetime.combine(newest, time(), tzinfo=timezone.utc)


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


def _check_the_display_names_hold() -> None:
    """Refuse to import a display table that does not cover the registry.

    Both directions, for the reason the axis table is checked both ways. A
    registered field with no row here reaches a reader as its own id, which is
    the defect this table exists to fix and would reappear silently for whichever
    field was added next. A row for a field nothing registers is a phrase
    describing something that is gone.
    """
    registered = set(REGISTRY)
    missing = sorted(registered - set(DISPLAY_NAMES))
    if missing:
        raise ValueError(
            "these registered fields have no display name, so a reader would be "
            f"shown their ids: {', '.join(missing)}"
        )
    stale = sorted(set(DISPLAY_NAMES) - registered)
    if stale:
        raise ValueError(
            f"these display names describe fields nothing registers: {', '.join(stale)}"
        )
    for field_id, shown in DISPLAY_NAMES.items():
        if not shown.strip() or shown == field_id:
            raise ValueError(
                f"{field_id} needs a display name a person can read; its own id "
                "is not one"
            )


_check_the_catalog_holds()
_check_the_display_names_hold()
_CATALOG_LABELS: Mapping[str, str] = _labels()


def register_signal_tools(**kwargs: Any) -> tuple[ToolEntry, ...]:
    """Register both store tools and hand the registrations back to the caller."""
    tools = SignalTools(**kwargs)
    return tuple(register(entry) for entry in tools.entries())


__all__ = [
    "AXIS_DISPLAY_NAMES",
    "CATALOG_AXES",
    "DISPLAY_NAMES",
    "MAX_RESULT_CHARS",
    "TOOLSET",
    "SignalTools",
    "axis_of",
    "catalog",
    "display_name_of",
    "namespace_of",
    "MAX_SERIES_SESSIONS",
    "MAX_WINDOW_READS",
    "points_affordable",
    "summarise_get_field",
    "summarise_get_series",
    "summarise_list_fields",
    "register_signal_tools",
]
