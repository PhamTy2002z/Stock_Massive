"""Reading the store as a table, for questions nobody wrote a recipe for.

``get_field`` answers one number and ``get_series`` answers one field across
time. Both are one symbol wide, and the question they cannot reach is the one a
reader actually asks about two companies: *which of these is stronger, and on
what*. That question is a table — symbols down one axis, quarters or fields
across the other — and neither of the two tools can produce one.

Two tools here, and they are the data axis of the analysis compiler.

**``query`` opens the store's own tables.** Six sources, one call, a frame back.
It does not compute anything: a daily bar is a daily bar, a statement line is
the number the company filed. What it adds is the shape — many symbols, many
periods, one grid — and the Vietnamese heading every column needs before a
reader can meet it.

**``compare_fields`` puts symbols against Signal Fields.** Every rule
``get_field`` holds, held per cell: a registered field only, a symbol in the
Universe only, the most recent closed session only, and a refusal becomes a
``null`` with its reason counted rather than a gap nobody can see. What it adds
is the *role*: which symbol wins each column, decided by the direction the field
itself declares and by nothing this tool knows.

**Neither returns numbers to the model.** Both return a frame id and a summary
small enough to read in a sentence — how many rows, how many columns, as of
when, how many cells the store refused and for which symbols. The numbers stay
where the Signal Desk can draw them, which is the rule ``run_study`` and
``get_series`` already hold and the reason this lane can put a picture in front
of a reader at all.

**The ceilings are on the frame and not on the work.** ``MAX_QUERY_ROWS`` and
``MAX_QUERY_CELLS`` bound what one call may build, because a model asking for
ten symbols across every line of an insurer's balance sheet for thirty-four
quarters is asking a reasonable-sounding question whose answer is a hundred
thousand cells nobody can read. The refusal names the size so the next call can
be narrower rather than a guess.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.alpha.envelope import figure_for_field
from src.core.database import get_sync_db
from src.stocks.financial import reads as financial_reads
from src.stocks.intraday import reads as intraday_reads
from src.alpha.models import FinancialStatementItem
from src.stocks.models import BarDaily
from src.stocks.shared.exceptions import StockServiceError
from src.stocks.shared.validators import validate_symbol
from src.stocks.signals.bars import reference_snapshots
from src.stocks.signals.corporate_actions import CorporateActionStore
from src.stocks.signals.fields import Direction
from src.stocks.signals.registry import REGISTRY
from src.stocks.signals.serving import serve_cross_section
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
    object_schema,
    register,
)
from .signals import display_name_of

TOOLSET = "signals"

#: Where a runaway result is cut, in characters. A bug-stop rather than a
#: budget: everything either tool returns is a summary of fixed shape, and the
#: largest honest one is an order of magnitude under this.
MAX_RESULT_CHARS = 32_000

#: The most symbols one call may name. Ten because a frame wider than ten
#: entities has stopped being a comparison — past that a reader is scanning a
#: list, which is what a screener is for and this is not.
MAX_SYMBOLS = 10

#: The most fields one comparison may put across the top, for the same reason.
MAX_COMPARE_FIELDS = 8

#: How tall and how large a frame this may build. Two ceilings rather than one
#: because they bound different mistakes: a thousand rows of two columns is a
#: series nobody asked for, and ten rows of five thousand columns is a statement
#: read whole. Both are answers to reasonable-sounding requests, and neither is
#: a picture.
MAX_QUERY_ROWS = 5_000
MAX_QUERY_CELLS = 50_000

#: How many sessions a bar window defaults to when the call does not say.
DEFAULT_SESSIONS = 60

#: How many quarters a statement or ratio read defaults to.
DEFAULT_PERIODS = 8

#: The widest window a call may name. A ceiling on the *request* and not only
#: on the frame, because the frame ceilings below are checked after the read has
#: happened: ``window=34`` across ten symbols with no ``items`` pulls tens of
#: thousands of rows into memory and builds the whole grid before anything says
#: it is too large. This is what stops that before the query runs. It is above
#: any honest picture — 250 daily sessions, and the store holds 34 quarters.
MAX_WINDOW = 250

#: The most statement or ratio line ids one call may name, for the same reason.
MAX_ITEMS = 60

#: How wide the widest reporting template on this market is, used to size a
#: statement read *before* it runs. An insurer's balance sheet, measured
#: 2026-08-30 while seeding the label table. An estimate and not a promise: the
#: real width is the union of what the named symbols filed, and the frame
#: ceilings still hold after the read.
WIDEST_STATEMENT_LINES = 200

#: How many column headings the summary shows the model. Enough to recognise
#: what the frame is, and short enough that the summary stays a sentence:
#: ``columnCount`` says how wide it really is.
SUMMARY_COLUMNS = 12

#: One day, for turning a quarter label into the instant a frame is frozen at.
_ONE_DAY = timedelta(days=1)

#: The six tables this opens, and the only names ``source`` accepts.
SOURCES: tuple[str, ...] = (
    "bar_daily",
    "intraday_15m",
    "statement",
    "ratio",
    "reference",
    "corporate_actions",
)

#: Which statements a ``statement`` read may be narrowed to.
STATEMENTS: tuple[str, ...] = ("income", "balance", "cashflow")

#: The columns a daily bar frame offers, in the order a reader meets them, and
#: the Vietnamese each is headed with. Written out rather than read off the ORM:
#: a column heading is a sentence for a person, and deriving one from an
#: attribute name is how a panel ends up headed ``last_price``.
BAR_COLUMNS: Mapping[str, str] = {
    "open": "Giá mở cửa",
    "high": "Giá cao nhất",
    "low": "Giá thấp nhất",
    "close": "Giá đóng cửa",
    "volume": "Khối lượng",
}

#: The same, for a 15-minute bucket.
INTRADAY_COLUMNS: Mapping[str, str] = {
    "open": "Giá mở cửa",
    "high": "Giá cao nhất",
    "low": "Giá thấp nhất",
    "close": "Giá đóng cửa",
    "volume": "Khối lượng",
}

#: What a reference row offers. ``shares`` is the canonical count
#: ``ReferenceSnapshot.canonical_shares()`` chose, not a sum of the types.
REFERENCE_COLUMNS: Mapping[str, str] = {
    "shares": "Số lượng cổ phiếu",
    "share_type": "Loại cổ phiếu",
    "total_foreign_room": "Room ngoại tối đa",
    "current_foreign_room": "Room ngoại còn lại",
}

#: What a corporate action row offers, under the column names the table itself
#: uses.
#:
#: ``exercise_ratio`` is deliberately *not* headed "Tỉ lệ". The store's own note
#: on the column (``stocks/models.py``) says the feed puts a share ratio there on
#: an issue and a payment as a fraction of par there on a cash dividend — "stored
#: as given and read by kind, never by name". A heading that promised a ratio
#: would make the same mistake the column was written to stop, one layer further
#: out, in front of a reader.
ACTION_COLUMNS: Mapping[str, str] = {
    "ex_date": "Ngày giao dịch không hưởng quyền",
    "kind": "Loại sự kiện",
    "exercise_ratio": "Tỉ lệ/giá trị theo công bố",
    "value_per_share": "Giá trị trên mỗi cổ phiếu",
    "confirmation": "Trạng thái xác nhận",
}

#: Headings for the columns every multi-entity frame leads with.
SYMBOL_LABEL = "Mã"
SESSION_LABEL = "Phiên"
PERIOD_LABEL = "Kỳ"
BUCKET_LABEL = "Khung giờ"

SessionOpener = Callable[[], Any]


QUERY_DESCRIPTION = (
    "Read this system's own store as a table: many symbols, many periods, many "
    "columns, in one call. Six sources — bar_daily (closed daily sessions), "
    "intraday_15m (15-minute buckets), statement (quarterly financial statement "
    "lines), ratio (reported financial ratios), reference (share count and "
    "foreign room), corporate_actions (dividends, splits, issues). Returns a "
    "frameId plus a small summary: how many rows and columns, what it is as of, "
    "and how many cells the store had nothing for. The numbers themselves are "
    "kept where the Signal Desk can draw them and are never put in this "
    "conversation — pass the frameId to render_signal_desk to show them. Use it "
    "when the question is about a table: comparing companies' financials, a "
    "window of sessions for several symbols, what a company's share count is. "
    "It computes nothing; it reads what was filed."
)

QUERY_SCHEMA = object_schema(
    {
        "source": {
            "type": "string",
            "enum": list(SOURCES),
            "description": "Which of this system's tables to read.",
        },
        "symbols": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
            "maxItems": MAX_SYMBOLS,
            "description": (
                f"Up to {MAX_SYMBOLS} tickers, each in this system's Universe."
            ),
        },
        "columns": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "description": (
                "Which columns to read, for the sources that offer a choice "
                "(bar_daily, intraday_15m, reference, corporate_actions). Omit "
                "for all of them."
            ),
        },
        "window": {
            "type": "integer",
            "minimum": 1,
            "maximum": MAX_WINDOW,
            "description": (
                "How many closed sessions (bar_daily, intraday_15m) or quarters "
                f"(statement, ratio) to read. Defaults to {DEFAULT_SESSIONS} "
                f"sessions or {DEFAULT_PERIODS} quarters. Ignored by reference "
                "and corporate_actions, which are not windowed."
            ),
        },
        "statement": {
            "type": "string",
            "enum": list(STATEMENTS),
            "description": (
                "Narrow a statement read to one of the three. Omit for all three."
            ),
        },
        "items": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "maxItems": MAX_ITEMS,
            "description": (
                "Which statement or ratio line ids to read, exactly as the "
                "provider spells them. Omit to read every line the symbols "
                "filed, which for a whole balance sheet is large enough to be "
                "refused."
            ),
        },
    },
    ("source", "symbols"),
)

COMPARE_DESCRIPTION = (
    "Put two to ten symbols against up to eight Signal Fields, as a table with "
    "one row per symbol and one column per field, read on the most recent "
    "closed session. Each column is marked with which symbol wins and which "
    "loses, where the field declares a better direction; a field that does not "
    "is left unmarked rather than guessed at. A cell the store refuses is null "
    "with its reason counted. Returns a frameId and a summary — the numbers stay "
    "where the Signal Desk draws them. Use it when the question is which of "
    "several companies is stronger on figures this system computes."
)

COMPARE_SCHEMA = object_schema(
    {
        "symbols": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 2,
            "maxItems": MAX_SYMBOLS,
            "description": (
                f"Two to {MAX_SYMBOLS} tickers, each in this system's Universe."
            ),
        },
        "field_ids": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
            "maxItems": MAX_COMPARE_FIELDS,
            "description": (
                "Up to eight fieldIds from list_fields, exactly as spelled there."
            ),
        },
    },
    ("symbols", "field_ids"),
)


def summarise_query(arguments: Mapping[str, Any]) -> str:
    """The rail row for a store read: which table, and for how many companies."""
    source = str(arguments.get("source") or "").strip()
    symbols = arguments.get("symbols")
    count = len(symbols) if isinstance(symbols, list) else 0
    name = _SOURCE_DISPLAY.get(source, "dữ liệu")
    if count == 1 and isinstance(symbols, list):
        return f"Đọc {name}: {str(symbols[0]).upper()}"
    if count:
        return f"Đọc {name}: {count} mã"
    return f"Đọc {name}"


def summarise_compare_fields(arguments: Mapping[str, Any]) -> str:
    """The rail row for a comparison: how many companies, on how many figures."""
    symbols = arguments.get("symbols")
    fields = arguments.get("field_ids")
    symbol_count = len(symbols) if isinstance(symbols, list) else 0
    field_count = len(fields) if isinstance(fields, list) else 0
    if symbol_count and field_count:
        return f"So sánh {symbol_count} mã trên {field_count} chỉ báo"
    return "So sánh chỉ báo giữa các mã"


#: What each source is called on the rail. Vietnamese, because the rail is read
#: by whoever asked about a company.
_SOURCE_DISPLAY: Mapping[str, str] = {
    "bar_daily": "giá theo phiên",
    "intraday_15m": "giá trong phiên",
    "statement": "báo cáo tài chính",
    "ratio": "chỉ số tài chính",
    "reference": "thông tin niêm yết",
    "corporate_actions": "sự kiện quyền",
}


class SourceUnavailable(LookupError):
    """The store has nothing to answer this read with, in one sentence.

    Raised rather than returned because this is the shared reader, and its two
    callers answer a refusal differently: the tool relays it to the model as a
    ``cannot_read`` result, and the template runner turns it into a
    ``StudyRefused`` the reader sees. A single return shape would have made one
    of them translate the other's vocabulary.
    """


@dataclass(frozen=True)
class SourceRead:
    """One of the store's tables, read and stamped, before anything persists it."""

    frame: Frame
    provenance: Provenance
    params: dict[str, Any]
    title: str
    newest: date | None
    refusals: Mapping[str, int]
    detail: Mapping[str, Any]


def read_source(
    session: Session,
    *,
    source: str,
    symbols: Sequence[str],
    arguments: Mapping[str, Any],
    now: datetime | None = None,
) -> SourceRead:
    """Read one source into a stamped frame, or say why the store cannot.

    The one place a source name becomes numbers. ``query`` calls it with the
    symbols a model named and persists what comes back; a Study template calls it
    with the symbols its parameters resolve to and files the frame as a step. The
    readers, the size ceiling and the provenance are therefore written once —
    a template reading the store by a second road would be a template whose
    numbers could differ from the same question asked in chat.
    """
    if source not in SOURCES:
        raise ValueError(
            f"{source!r} is not a source this system holds; the six are "
            + ", ".join(SOURCES)
        )
    built = _READERS[source](session, list(symbols), arguments)
    if isinstance(built, dict):
        raise SourceUnavailable(str(built.get("detail") or "cannot read"))
    frame, newest, refusals, method_notes, detail = built

    too_big = _too_big(frame)
    if too_big is not None:
        raise SourceUnavailable(too_big)

    provenance = Provenance(
        source="store",
        as_of=now
        if now is not None
        else (
            datetime.combine(newest, time(), tzinfo=timezone.utc)
            if newest is not None
            else datetime.now(timezone.utc)
        ),
        sessions_used=_answered(frame),
        health="normal" if not refusals else "degraded",
        reason=(None if not refusals else f"{sum(refusals.values())} ô không có số"),
        method_notes=method_notes,
        query={"source": source, "symbols": list(symbols), **detail},
    )
    return SourceRead(
        frame=frame,
        provenance=provenance,
        params={"source": source, "symbols": list(symbols), **detail},
        title=_title(source, list(symbols)),
        newest=newest,
        refusals=refusals,
        detail=detail,
    )


class QueryTools:
    """Read the store as a table, and compare symbols on registered fields."""

    def __init__(self, *, session_opener: SessionOpener = get_sync_db) -> None:
        self._session_opener = session_opener

    def entries(self) -> tuple[ToolEntry, ...]:
        return (
            ToolEntry(
                name="query",
                toolset=TOOLSET,
                description=QUERY_DESCRIPTION,
                schema=QUERY_SCHEMA,
                handler=self.query,
                display_name="Đọc bảng dữ liệu",
                summarise=summarise_query,
                effect=ToolEffect.READ,
                idempotency=ToolIdempotency.IDEMPOTENT,
                access=ToolAccess.STORE,
                content_trust=ContentTrust.TRUSTED_STRUCTURED,
                concurrency=ToolConcurrency.PARALLEL_SAFE,
                contract_version="1",
                # A synchronous store read and a row written at the end of it.
                # The executor moves it to a worker thread rather than letting a
                # ten-symbol statement read stall the rest of the round.
                is_async=False,
                max_result_size_chars=MAX_RESULT_CHARS,
            ),
            ToolEntry(
                name="compare_fields",
                toolset=TOOLSET,
                description=COMPARE_DESCRIPTION,
                schema=COMPARE_SCHEMA,
                handler=self.compare_fields,
                display_name="So sánh chỉ báo",
                summarise=summarise_compare_fields,
                effect=ToolEffect.READ,
                idempotency=ToolIdempotency.IDEMPOTENT,
                access=ToolAccess.STORE,
                content_trust=ContentTrust.TRUSTED_STRUCTURED,
                concurrency=ToolConcurrency.PARALLEL_SAFE,
                contract_version="1",
                is_async=False,
                max_result_size_chars=MAX_RESULT_CHARS,
            ),
        )

    # -- query ----------------------------------------------------------------

    def query(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Read one of the store's tables as a frame, and keep the frame."""
        source = str(arguments.get("source") or "").strip()
        if source not in SOURCES:
            raise ValueError(
                f"{source!r} is not a source this system holds; the six are "
                + ", ".join(SOURCES)
            )

        with self._open() as session:
            resolved = _symbols(arguments.get("symbols"), session)
            if isinstance(resolved, dict):
                return resolved
            symbols = resolved.resolved
            uncovered = resolved.outside

            try:
                read = read_source(
                    session,
                    source=source,
                    symbols=symbols,
                    arguments=arguments,
                    now=context.now,
                )
            except SourceUnavailable as unavailable:
                return _cannot(str(unavailable))
            frame = read.frame
            as_of = read.newest
            refusals = read.refusals
            detail = read.detail

            frame_id = frames_buffer.store_frame(
                session,
                kind=frames_buffer.QUERY_KIND,
                frame=frame,
                provenance=read.provenance,
                params=read.params,
                title=read.title,
                turn_id=context.turn_id,
                thread_id=context.thread_id,
            )

        # ``frameId`` first, and it is not a style choice. A result over its
        # declared size is replaced by a preview of its *head* (``agent/
        # budget.py``), so whatever is written last is what a long answer loses —
        # and losing the frame id loses the only thing that can be drawn, after
        # a row has already been written and committed. The tool would succeed
        # and be useless.
        return {
            "frameId": str(frame_id),
            "source": source,
            "symbols": list(symbols),
            "rows": len(frame.rows),
            "columnCount": len(frame.columns),
            # A sample and not the list. A statement read across ten symbols is
            # the union of every line any of them filed — measured at 574 columns
            # — and the full names plus their Vietnamese labels are tens of
            # thousands of characters of summary for a picture the model never
            # sees. The model needs to know the frame is wide and roughly what is
            # in it; the reader gets every heading, in the panel, where headings
            # belong.
            "columnSample": [
                {"name": name, "label": frame.labels[name]}
                for name in frame.columns[:SUMMARY_COLUMNS]
            ],
            "asOf": as_of.isoformat() if as_of is not None else None,
            "unit": frame.unit,
            # Counted per symbol and not only in total: "eight cells missing" is
            # a fact about the frame, and "eight cells missing, all of them
            # VCB's" is a fact about the answer.
            "missing": dict(sorted(refusals.items())),
            # Named, not silently dropped: a frame covering nine of ten symbols
            # is only honest if the tenth is in the answer beside it.
            "notCovered": list(uncovered),
            "detail": detail,
        }

    # -- compare_fields -------------------------------------------------------

    def compare_fields(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Put symbols against fields, and mark which wins each column."""
        raw_fields = arguments.get("field_ids")
        if not isinstance(raw_fields, list) or not raw_fields:
            raise ValueError("field_ids must name at least one registered Signal Field")
        if len(raw_fields) > MAX_COMPARE_FIELDS:
            raise ValueError(
                f"compare_fields puts at most {MAX_COMPARE_FIELDS} fields across "
                f"the top and {len(raw_fields)} were named"
            )
        field_ids: list[str] = []
        for raw in raw_fields:
            field_id = str(raw).strip()
            if field_id not in REGISTRY:
                raise ValueError(
                    f"{field_id!r} is not a registered Signal Field. Call "
                    "list_fields for the ids this system computes."
                )
            if field_id not in field_ids:
                field_ids.append(field_id)

        with self._open() as session:
            resolved = _symbols(arguments.get("symbols"), session, minimum=2)
            if isinstance(resolved, dict):
                return resolved
            symbols = resolved.resolved
            uncovered = resolved.outside

            day = latest_trading_day(session)
            if day is None:
                return _cannot(
                    "This system holds no closed session yet, so there is "
                    "nothing to compare on."
                )

            # One sample and one ranking per *field*, hoisted out of the pair
            # loop. ``figure_for_field`` takes both for exactly this reason — its
            # own docstring says "a cohort measures its rankings once and passes
            # them in" — and left to measure its own, a ranked field re-ranks the
            # whole Universe once per symbol: ten symbols against five percentile
            # fields is fifty cross-sections where five answer the question. Each
            # one prepares a window of up to 273 sessions for every symbol in the
            # sample, on a tool that holds a worker thread while it runs.
            peers = build_universe(session).symbols
            missing_peers = tuple(
                symbol for symbol in symbols if symbol not in peers
            )
            sample = peers + missing_peers
            rankings = {
                field_id: serve_cross_section(
                    session, sample, REGISTRY[field_id], end=day
                )
                for field_id in field_ids
                if REGISTRY[field_id].ranked is not None
            }

            columns = ("symbol", *field_ids)
            labels = {"symbol": SYMBOL_LABEL} | {
                field_id: display_name_of(field_id) for field_id in field_ids
            }
            rows: list[tuple[Any, ...]] = []
            values: dict[str, list[float | None]] = {
                field_id: [] for field_id in field_ids
            }
            refusals: dict[str, int] = {}
            units: dict[str, str | None] = {}

            for symbol in symbols:
                cells: list[Any] = [symbol]
                for field_id in field_ids:
                    figure = figure_for_field(
                        session,
                        symbol,
                        day,
                        field_id,
                        cross_sections=rankings,
                        peers=sample,
                    )
                    if figure.value is None:
                        code = figure.reason_code or "refused"
                        refusals[code] = refusals.get(code, 0) + 1
                    else:
                        units.setdefault(field_id, figure.unit)
                    cells.append(figure.value)
                    values[field_id].append(figure.value)
                rows.append(tuple(cells))

            answered = sum(
                1
                for field_id in field_ids
                for value in values[field_id]
                if value is not None
            )
            if answered == 0:
                return _cannot(
                    "None of the figures asked for could be computed for any of "
                    f"{', '.join(symbols)} on {day.isoformat()}"
                    + (f" ({', '.join(sorted(refusals))})" if refusals else "")
                )

            frame = Frame(
                kind="table",
                columns=columns,
                rows=tuple(rows),
                # No single unit: the columns are eight different figures in
                # eight different units, and one stamped on the frame would be a
                # claim about all of them. Each column's unit rides in the
                # payload below instead.
                unit=None,
                labels=labels,
                cell_roles=_comparison_roles(field_ids, values),
            )
            provenance = Provenance(
                source="store",
                as_of=_as_of(context, day),
                sessions_used=1,
                health="normal" if not refusals else "degraded",
                reason=(
                    None
                    if not refusals
                    else f"{sum(refusals.values())} ô không có số"
                ),
                method_notes=(),
                query={
                    "symbols": list(symbols),
                    "field_ids": list(field_ids),
                    "trading_day": day.isoformat(),
                },
            )
            frame_id = frames_buffer.store_frame(
                session,
                kind=frames_buffer.COMPARE_KIND,
                frame=frame,
                provenance=provenance,
                params={
                    "symbols": list(symbols),
                    "field_ids": list(field_ids),
                    "trading_day": day.isoformat(),
                },
                title=f"So sánh {', '.join(symbols)}",
                turn_id=context.turn_id,
                thread_id=context.thread_id,
            )

        return {
            # First, for the reason ``query`` puts it first.
            "frameId": str(frame_id),
            "symbols": list(symbols),
            "fields": [
                {
                    "fieldId": field_id,
                    "label": display_name_of(field_id),
                    "unit": units.get(field_id),
                    "better": _better_of(field_id),
                    "answered": sum(
                        1 for value in values[field_id] if value is not None
                    ),
                }
                for field_id in field_ids
            ],
            "asOf": day.isoformat(),
            "cellsAnswered": answered,
            "cellsAsked": len(symbols) * len(field_ids),
            "missing": dict(sorted(refusals.items())),
            # Named, not silently dropped: a frame covering nine of ten symbols
            # is only honest if the tenth is in the answer beside it.
            "notCovered": list(uncovered),
        }

    @contextmanager
    def _open(self) -> Iterator[Session]:
        with self._session_opener() as session:
            yield session


# -- roles --------------------------------------------------------------------


def _better_of(field_id: str) -> str | None:
    field = REGISTRY.get(field_id)
    better = getattr(field, "better", None) if field is not None else None
    return None if better is None else better.value


def _comparison_roles(
    field_ids: Sequence[str], values: Mapping[str, Sequence[float | None]]
) -> dict[tuple[int, str], str]:
    """Which cell wins and which loses, per column, where the field says so.

    Per column and never per row, which is the whole reason ``cell_roles``
    exists: the claim is *this symbol wins on this figure*, and a role on the row
    would say the symbol wins outright — a sentence a comparison exists to avoid
    making.

    A column with no declared direction gets no roles at all. So does a column
    where fewer than two symbols answered: with one number there is nothing to
    be better than, and marking it a winner would dress a lone survivor as a
    victor. Ties get no roles either, for the same reason — two identical numbers
    have no winner between them.
    """
    roles: dict[tuple[int, str], str] = {}
    for field_id in field_ids:
        better = _better_of(field_id)
        if better is None:
            continue
        answered = [
            (index, value)
            for index, value in enumerate(values[field_id])
            if value is not None
        ]
        if len(answered) < 2:
            continue
        ordered = sorted(answered, key=lambda pair: pair[1])
        low_index, low_value = ordered[0]
        high_index, high_value = ordered[-1]
        if low_value == high_value:
            continue
        if better == Direction.HIGHER.value:
            roles[(high_index, field_id)] = "winner"
            roles[(low_index, field_id)] = "loser"
        else:
            roles[(low_index, field_id)] = "winner"
            roles[(high_index, field_id)] = "loser"
    return roles


# -- readers ------------------------------------------------------------------


def _read_bar_daily(
    session: Session, symbols: Sequence[str], arguments: Mapping[str, Any]
):
    """Closed daily sessions for several symbols, oldest first."""
    columns = _columns(arguments, BAR_COLUMNS)
    if isinstance(columns, dict):
        return columns
    window = _window(arguments, DEFAULT_SESSIONS)

    newest = latest_trading_day(session)
    if newest is None:
        return _cannot("This system holds no closed session yet.")
    days = sorted({newest, *trading_days_before(session, newest, window - 1)})

    rows_by_key: dict[tuple[str, date], Any] = {
        (row.symbol, row.trading_day): row
        for row in session.execute(
            select(BarDaily).where(
                BarDaily.symbol.in_(list(symbols)),
                BarDaily.trading_day.in_(days),
            )
        ).scalars()
    }

    frame_columns = ("symbol", "session", *columns)
    labels = {"symbol": SYMBOL_LABEL, "session": SESSION_LABEL} | {
        name: BAR_COLUMNS[name] for name in columns
    }
    rows: list[tuple[Any, ...]] = []
    refusals: dict[str, int] = {}
    for symbol in symbols:
        for day in days:
            held = rows_by_key.get((symbol, day))
            if held is None:
                # A session the symbol did not trade is not a row of nulls: it is
                # a session that is not this symbol's, and inventing a row for it
                # would put a gap on a chart where there is no gap.
                refusals[f"{symbol}:session_not_stored"] = (
                    refusals.get(f"{symbol}:session_not_stored", 0) + 1
                )
                continue
            rows.append(
                (symbol, day.isoformat(), *(_number(getattr(held, name)) for name in columns))
            )

    if not rows:
        return _cannot(
            f"No closed session for {', '.join(symbols)} is stored in the last "
            f"{window} the market held."
        )
    frame = Frame(
        kind="table",
        columns=frame_columns,
        rows=tuple(rows),
        unit=None,
        labels=labels,
    )
    return frame, days[-1], refusals, (), {"window": window, "columns": list(columns)}


def _read_intraday(
    session: Session, symbols: Sequence[str], arguments: Mapping[str, Any]
):
    """15-minute buckets of the most recent closed sessions."""
    columns = _columns(arguments, INTRADAY_COLUMNS)
    if isinstance(columns, dict):
        return columns
    window = _window(arguments, 1)

    frame_columns = ("symbol", "session", "bucket", *columns)
    labels = {
        "symbol": SYMBOL_LABEL,
        "session": SESSION_LABEL,
        "bucket": BUCKET_LABEL,
    } | {name: INTRADAY_COLUMNS[name] for name in columns}
    rows: list[tuple[Any, ...]] = []
    refusals: dict[str, int] = {}
    newest: date | None = None
    for symbol in symbols:
        bars = intraday_reads.bars_for(session, symbol, window)
        if not bars:
            refusals[f"{symbol}:intraday_not_stored"] = 1
            continue
        for bar in bars:
            newest = bar.trading_day if newest is None else max(newest, bar.trading_day)
            rows.append(
                (
                    symbol,
                    bar.trading_day.isoformat(),
                    bar.bucket_label,
                    *(_number(getattr(bar, name)) for name in columns),
                )
            )

    if not rows:
        return _cannot(
            f"This system holds no 15-minute history for {', '.join(symbols)}."
        )
    frame = Frame(
        kind="table",
        columns=frame_columns,
        rows=tuple(rows),
        unit=None,
        labels=labels,
    )
    return frame, newest, refusals, (), {"window": window, "columns": list(columns)}


def _read_statement(
    session: Session, symbols: Sequence[str], arguments: Mapping[str, Any]
):
    """Quarterly statement lines: one row per (symbol, quarter), one column per line."""
    window = _window(arguments, DEFAULT_PERIODS)
    statement = arguments.get("statement")
    statement = str(statement).strip() if statement else None
    if statement is not None and statement not in STATEMENTS:
        raise ValueError(
            f"{statement!r} is not a statement; the three are "
            + ", ".join(STATEMENTS)
        )

    periods = financial_reads.periods_for_many(
        session, symbols, statement=statement
    )[:window]
    if not periods:
        return _cannot(
            f"This system holds no filed quarter for {', '.join(symbols)}."
        )
    periods = sorted(periods)

    wanted_items = _items(arguments)
    if wanted_items is None:
        # The read that has to be bounded *before* it runs. Without ``items``
        # this asks for every line every named symbol filed — measured at 574
        # columns for ten symbols — and the cell ceiling below would only say so
        # after the whole grid was built in memory. The estimate is the honest
        # worst case: the widest statement measured on this market is an
        # insurer's, and a caller that means "the whole statement" for one symbol
        # and one quarter still gets it.
        estimated = len(symbols) * len(periods) * WIDEST_STATEMENT_LINES
        if estimated > MAX_QUERY_CELLS:
            return _cannot(
                f"Reading every line for {len(symbols)} symbols across "
                f"{len(periods)} quarters is about {estimated} cells against a "
                f"ceiling of {MAX_QUERY_CELLS}. Name the lines the question is "
                "about in items, or ask for fewer symbols or quarters."
            )
    pairs: list[tuple[str, str]] | None = None
    if wanted_items is not None:
        statements = (statement,) if statement is not None else STATEMENTS
        pairs = [(name, item) for name in statements for item in wanted_items]

    held = financial_reads.lines_for_many(session, symbols, periods, pairs)
    if statement is not None:
        held = {
            key: value for key, value in held.items() if key[2] == statement
        }
    if not held:
        return _cannot(
            "No line asked for is filed for "
            f"{', '.join(symbols)} in the {len(periods)} quarters read."
        )

    # The columns are the lines that actually landed, in a stable order, so a
    # frame never carries a column of nothing but nulls.
    line_keys = sorted({(key[2], key[3]) for key in held})
    labels_by_key = _statement_labels(session, line_keys)
    column_names = [f"{name}.{item}" for name, item in line_keys]

    frame_columns = ("symbol", "period", *column_names)
    labels = {"symbol": SYMBOL_LABEL, "period": PERIOD_LABEL} | {
        f"{name}.{item}": labels_by_key.get((name, item), item)
        for name, item in line_keys
    }
    # Which quarters each symbol actually filed, so a missing cell can name the
    # input that is missing. The rows are the union of every symbol's quarters,
    # so a symbol that filed four of eight would otherwise report every cell of
    # its four empty rows as a line it did not report — the wrong cause, and one
    # a model will relay as a fact about the company.
    filed = financial_reads.periods_held_by(session, symbols)
    rows: list[tuple[Any, ...]] = []
    refusals: dict[str, int] = {}
    for symbol in symbols:
        held_periods = filed.get(symbol, frozenset())
        for period in periods:
            cells: list[Any] = [symbol, period]
            quarter_filed = period in held_periods
            if not quarter_filed:
                key = f"{symbol}:quarter_not_filed"
                refusals[key] = refusals.get(key, 0) + 1
            for name, item in line_keys:
                value = held.get((symbol, period, name, item))
                if value is None and quarter_filed:
                    key = f"{symbol}:statement_line_missing"
                    refusals[key] = refusals.get(key, 0) + 1
                cells.append(_number(value))
            rows.append(tuple(cells))

    frame = Frame(
        kind="table",
        columns=frame_columns,
        rows=tuple(rows),
        unit="vnd",
        labels=labels,
    )
    unlabelled = sum(1 for key in line_keys if key not in labels_by_key)
    notes = (
        (f"{unlabelled} chỉ tiêu chưa có tên tiếng Việt",) if unlabelled else ()
    )
    return (
        frame,
        _period_end(periods[-1]),
        refusals,
        notes,
        {"periods": list(periods), "statement": statement, "lines": len(line_keys)},
    )


def _read_ratio(
    session: Session, symbols: Sequence[str], arguments: Mapping[str, Any]
):
    """Reported financial ratios: one row per (symbol, quarter)."""
    window = _window(arguments, DEFAULT_PERIODS)
    # The ratio table's own quarters, not the statement table's. The two are
    # filled from two independent provider responses and one can succeed where
    # the other failed, so asking the wrong table drops real quarters silently.
    periods = financial_reads.ratio_periods_for_many(session, symbols)[:window]
    if not periods:
        return _cannot(
            f"This system holds no reported ratio for {', '.join(symbols)}."
        )
    periods = sorted(periods)

    held = financial_reads.ratios_for_many(
        session, symbols, periods, _items(arguments)
    )
    if not held:
        return _cannot(
            f"This system holds no reported ratio for {', '.join(symbols)} in "
            f"the {len(periods)} quarters read."
        )

    item_ids = sorted({key[2] for key in held})
    labels_by_key = _statement_labels(session, [("ratio", item) for item in item_ids])

    frame_columns = ("symbol", "period", *item_ids)
    labels = {"symbol": SYMBOL_LABEL, "period": PERIOD_LABEL} | {
        item: labels_by_key.get(("ratio", item), item) for item in item_ids
    }
    rows: list[tuple[Any, ...]] = []
    refusals: dict[str, int] = {}
    for symbol in symbols:
        for period in periods:
            cells: list[Any] = [symbol, period]
            for item in item_ids:
                value = held.get((symbol, period, item))
                if value is None:
                    key = f"{symbol}:ratio_not_stored"
                    refusals[key] = refusals.get(key, 0) + 1
                cells.append(_number(value))
            rows.append(tuple(cells))

    frame = Frame(
        kind="table",
        columns=frame_columns,
        rows=tuple(rows),
        # The units follow whichever source reported them and differ per line —
        # this provider answers ROE as a percent where another answers a
        # fraction — so no unit is stamped on the frame.
        unit=None,
        labels=labels,
    )
    return (
        frame,
        _period_end(periods[-1]),
        refusals,
        ("Đơn vị theo nguồn công bố, không quy đổi",),
        {"periods": list(periods), "lines": len(item_ids)},
    )


def _read_reference(
    session: Session, symbols: Sequence[str], arguments: Mapping[str, Any]
):
    """Share count and foreign room: one row per symbol, not windowed."""
    columns = _columns(arguments, REFERENCE_COLUMNS)
    if isinstance(columns, dict):
        return columns

    held = reference_snapshots(session, symbols)
    frame_columns = ("symbol", "as_of", *columns)
    labels = {"symbol": SYMBOL_LABEL, "as_of": "Ngày ghi nhận"} | {
        name: REFERENCE_COLUMNS[name] for name in columns
    }
    rows: list[tuple[Any, ...]] = []
    refusals: dict[str, int] = {}
    newest: date | None = None
    for symbol in symbols:
        found = held.get(symbol)
        if found is None:
            refusals[f"{symbol}:reference_not_stored"] = 1
            continue
        snapshot, observed_on = found
        newest = observed_on if newest is None else max(newest, observed_on)
        count = snapshot.canonical_shares()
        available = {
            "shares": None if count is None else int(count.value),
            "share_type": None if count is None else count.share_type.value,
            "total_foreign_room": snapshot.total_foreign_room,
            "current_foreign_room": snapshot.current_foreign_room,
        }
        rows.append(
            (symbol, observed_on.isoformat(), *(available[name] for name in columns))
        )

    if not rows:
        return _cannot(
            f"This system holds no listing record for {', '.join(symbols)}."
        )
    frame = Frame(
        kind="table",
        columns=frame_columns,
        rows=tuple(rows),
        unit=None,
        labels=labels,
    )
    return frame, newest, refusals, (), {"columns": list(columns)}


def _read_corporate_actions(
    session: Session, symbols: Sequence[str], arguments: Mapping[str, Any]
):
    """Dated corporate actions, oldest first, not windowed by session."""
    columns = _columns(arguments, ACTION_COLUMNS)
    if isinstance(columns, dict):
        return columns

    store = CorporateActionStore(session)
    by_symbol = store.for_symbols(list(symbols))
    frame_columns = ("symbol", *columns)
    labels = {"symbol": SYMBOL_LABEL} | {
        name: ACTION_COLUMNS[name] for name in columns
    }
    rows: list[tuple[Any, ...]] = []
    refusals: dict[str, int] = {}
    newest: date | None = None
    for symbol in symbols:
        actions = by_symbol.get(symbol, ())
        if not actions:
            # "No dated action" and not "no action": ``for_symbols`` excludes the
            # undated ones by construction, so a symbol whose only entitlement
            # has no ex-date yet lands here too, and saying it has none would be
            # a different claim from the one the read can support.
            refusals[f"{symbol}:no_dated_corporate_action"] = 1
            continue
        for action in actions:
            # ``for_symbols`` filters ``ex_date IS NOT NULL``, so this is never
            # ``None`` — asserted rather than tested, because a test here would
            # be a branch that can only be reached by that filter changing.
            assert action.ex_date is not None
            newest = action.ex_date if newest is None else max(newest, action.ex_date)
            # Read straight off the row and never through ``getattr`` with a
            # default. A default turns a column this table does not have into a
            # ``None`` on every row, and the summary then tells the model that
            # nothing was missing — which is how two columns can be dead for a
            # release without a single test going red. The first version of this
            # read asked for ``ratio`` and ``cash_amount``; the columns are
            # ``exercise_ratio`` and ``value_per_share``.
            available = {
                "ex_date": action.ex_date.isoformat(),
                "kind": _text(action.kind),
                "exercise_ratio": _number(action.exercise_ratio),
                "value_per_share": _number(action.value_per_share),
                "confirmation": _text(action.confirmation),
            }
            rows.append((symbol, *(available[name] for name in columns)))

    if not rows:
        return _cannot(
            f"This system holds no dated corporate action for {', '.join(symbols)}."
        )
    frame = Frame(
        kind="table",
        columns=frame_columns,
        rows=tuple(rows),
        unit=None,
        labels=labels,
    )
    return frame, newest, refusals, (), {"columns": list(columns)}


_READERS: Mapping[str, Callable[..., Any]] = {
    "bar_daily": _read_bar_daily,
    "intraday_15m": _read_intraday,
    "statement": _read_statement,
    "ratio": _read_ratio,
    "reference": _read_reference,
    "corporate_actions": _read_corporate_actions,
}


# -- shared -------------------------------------------------------------------


@dataclass(frozen=True)
class SymbolSelection:
    """The symbols a call can be answered for, and the ones it cannot.

    Two lists rather than one, because the caller has to put the second in the
    result: an answer covering nine of ten symbols is only honest if it says
    which one is missing and why.
    """

    resolved: list[str]
    outside: list[str]


def _symbols(
    raw: Any, session: Session, *, minimum: int = 1
) -> SymbolSelection | dict[str, Any]:
    """The tickers this call is for, each checked against the Universe.

    Checked here and not by the schema, for the reason ``get_field`` checks it:
    a schema is what the model is *told*, and the Universe is what this system
    has promised data for. A symbol outside it is refused by name rather than
    answered with an empty frame.
    """
    if not isinstance(raw, list) or len(raw) < minimum:
        return _cannot(
            f"This call reads at least {minimum} symbol"
            + ("s" if minimum > 1 else "")
            + " and fewer were named."
        )
    if len(raw) > MAX_SYMBOLS:
        return _cannot(
            f"This call reads at most {MAX_SYMBOLS} symbols and {len(raw)} were "
            "named. Ask for the ones the question is about."
        )
    universe = build_universe(session)
    resolved: list[str] = []
    outside: list[str] = []
    for item in raw:
        named = str(item).strip()
        try:
            symbol = validate_symbol(named)
        except StockServiceError:
            outside.append(named)
            continue
        if not universe.contains(symbol):
            outside.append(symbol)
            continue
        if symbol not in resolved:
            resolved.append(symbol)
    if len(resolved) < minimum:
        # Nothing readable is a refusal; some of it readable is an answer with a
        # gap named in it. Refusing the whole call for one symbol outside the
        # Universe costs a round to learn something the refusal already said —
        # measured on a VN30 question, where four of thirty symbols turned six
        # calls into twelve and left no round for drawing the answer.
        named_gap = (
            f" This system holds no data for {', '.join(outside)}: they are not "
            "in the set of symbols it has promised to cover."
            if outside
            else ""
        )
        return _cannot(
            f"This call reads at least {minimum} distinct symbol"
            + ("s" if minimum > 1 else "")
            + f" this system covers and {len(resolved)} of the named ones qualify."
            + named_gap
        )
    return SymbolSelection(resolved=resolved, outside=outside)


def _columns(
    arguments: Mapping[str, Any], offered: Mapping[str, str]
) -> tuple[str, ...] | dict[str, Any]:
    """The columns asked for, in the source's own order, or all of them."""
    raw = arguments.get("columns")
    if raw is None or (isinstance(raw, list) and not raw):
        return tuple(offered)
    if not isinstance(raw, list):
        raise ValueError("columns is a list of column names, or is left out")
    wanted = {str(item).strip() for item in raw}
    unknown = sorted(wanted - set(offered))
    if unknown:
        return _cannot(
            f"This source has no column {', '.join(unknown)}; it offers "
            + ", ".join(offered)
        )
    # The source's order, not the caller's: a frame's column order is what a
    # reader meets, and open/high/low/close read in that order for a reason.
    return tuple(name for name in offered if name in wanted)


def _items(arguments: Mapping[str, Any]) -> list[str] | None:
    raw = arguments.get("items")
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ValueError("items is a list of line ids, or is left out")
    wanted = [str(item).strip() for item in raw if str(item).strip()]
    if len(wanted) > MAX_ITEMS:
        raise ValueError(
            f"items names at most {MAX_ITEMS} lines and {len(wanted)} were given"
        )
    return wanted or None


def _window(arguments: Mapping[str, Any], default: int) -> int:
    """The window asked for, clamped, or the source's own default.

    ``bool`` is excluded explicitly because ``isinstance(True, int)`` is true in
    Python: a model answering ``window: true`` would otherwise get a silent
    one-session read instead of a schema error.
    """
    asked = arguments.get("window")
    if isinstance(asked, bool) or not isinstance(asked, int) or asked <= 0:
        return default
    return min(asked, MAX_WINDOW)


def _statement_labels(
    session: Session, keys: Sequence[tuple[str, str]]
) -> dict[tuple[str, str], str]:
    """The Vietnamese heading for each line, where the label table has one."""
    if not keys:
        return {}
    rows = session.execute(
        select(
            FinancialStatementItem.statement,
            FinancialStatementItem.item_id,
            FinancialStatementItem.label_vi,
        ).where(
            FinancialStatementItem.item_id.in_(sorted({item for _, item in keys}))
        )
    ).all()
    held = {(name, item): label for name, item, label in rows}
    return {key: held[key] for key in keys if key in held}


def _answered(frame: Frame) -> int:
    """How much of the window came back, in the unit the frame's own axis names.

    The field means "how much of the window answered", and a reader is shown it
    as a count of sessions. Rows are that count only when the frame has one row
    per session: a fifteen-minute read of thirty sessions is four hundred and
    eighty rows and thirty sessions, and a ten-symbol daily read is six hundred
    rows and sixty. Counting rows put the first of those on a panel as "480
    phiên" — off by the width of the grid, and read as a claim about how much
    history the picture rests on.

    Distinct sessions where there is a session axis, distinct quarters where
    there is a period one, and rows where there is neither, which is the honest
    answer for a reference or a corporate-action read.
    """
    for axis in ("session", "period"):
        if axis in frame.columns:
            position = frame.columns.index(axis)
            return len({row[position] for row in frame.rows})
    return len(frame.rows)


def _too_big(frame: Frame) -> str | None:
    """Why this frame is too large to be a picture, or ``None`` when it is not."""
    rows = len(frame.rows)
    cells = rows * len(frame.columns)
    if rows > MAX_QUERY_ROWS:
        return (
            f"That read builds {rows} rows against a ceiling of {MAX_QUERY_ROWS}. "
            "Narrow the window or the symbols."
        )
    if cells > MAX_QUERY_CELLS:
        return (
            f"That read builds {cells} cells against a ceiling of "
            f"{MAX_QUERY_CELLS}. Name the lines the question is about rather "
            "than reading a whole statement."
        )
    return None


def _title(source: str, symbols: Sequence[str]) -> str:
    """What the row is called for an operator and for a panel that opens it."""
    return f"{_SOURCE_DISPLAY.get(source, source)}: {', '.join(symbols)}"


def _period_end(period: str) -> date:
    """The last day of a ``YYYY-Qn`` label, for a frame's ``as_of``.

    A quarter is a range and ``as_of`` is an instant, so the freeze is the end of
    the quarter read. Text arithmetic rather than a parse of the whole label:
    the format is fixed by the store (``financial/reads.py``) and the quarter is
    one digit.
    """
    year = int(period[:4])
    quarter = int(period[-1])
    month = quarter * 3
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - _ONE_DAY


def _number(value: Any) -> float | None:
    """A cell as JSON holds it, or ``None`` where the store had nothing."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return value
    return float(value)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    return getattr(value, "value", None) or str(value)


def _as_of(context: ToolContext, newest: date | None) -> datetime:
    """The instant this frame is frozen at.

    The caller's clock where there is one, so a test asserting the stamp and the
    handler writing it read the same instant; otherwise the newest day read,
    which is the honest answer for a run outside a Turn.
    """
    if context.now is not None:
        return context.now
    if newest is None:
        return datetime.now(timezone.utc)
    return datetime.combine(newest, time(), tzinfo=timezone.utc)


def _cannot(sentence: str) -> dict[str, Any]:
    """A refusal shaped so the model reads it and the loop does not mistake it.

    Returned rather than raised, on ``tools/signals.py``'s reasoning: the
    question was well formed and the answer is that the store has nothing to
    say, which is a fact to relay rather than a tool failure to retry.
    """
    return {"error": "cannot_read", "detail": sentence}


def register_query_tools(
    *, session_opener: SessionOpener = get_sync_db
) -> tuple[ToolEntry, ...]:
    """Register both tools and hand back what was registered."""
    tools = QueryTools(session_opener=session_opener)
    return tuple(register(entry) for entry in tools.entries())


__all__ = [
    "ACTION_COLUMNS",
    "BAR_COLUMNS",
    "COMPARE_DESCRIPTION",
    "COMPARE_SCHEMA",
    "INTRADAY_COLUMNS",
    "MAX_COMPARE_FIELDS",
    "MAX_ITEMS",
    "MAX_QUERY_CELLS",
    "MAX_QUERY_ROWS",
    "MAX_RESULT_CHARS",
    "MAX_WINDOW",
    "MAX_SYMBOLS",
    "QUERY_DESCRIPTION",
    "QUERY_SCHEMA",
    "REFERENCE_COLUMNS",
    "SOURCES",
    "SUMMARY_COLUMNS",
    "WIDEST_STATEMENT_LINES",
    "STATEMENTS",
    "QueryTools",
    "register_query_tools",
    "summarise_compare_fields",
    "summarise_query",
]
