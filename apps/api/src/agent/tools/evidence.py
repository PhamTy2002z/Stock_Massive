"""The one place a model may copy a number, and the check that it copied.

Every other frame in this lane is built by the engine out of the store. This one
is built out of a page, because some questions have no number in the store — a
policy rate, a competitor that never listed, a figure quoted in a story — and
answering them in prose while every in-store question gets a picture is a lane
that behaves differently depending on where the data happens to live.

So the model may write rows. And because it may, every row is checked: the value
has to be **printed on a page this Turn actually fetched**, found by
:mod:`src.agent.evidence.numbers` under the literal test that module explains. A
row whose number is not there is dropped with its reason named and counted; a
frame that keeps some rows and drops others says so in its health, so the
provenance strip a reader sees is not the same as one built from a clean read.

Three properties this rests on, none of them new:

**The page is already stored.** ``fetch_url`` writes its whole result into the
Tool Call Trace, which exists precisely so an answer can be checked against what
the model saw. Nothing is fetched again here — a second fetch could return a
different page, and then the check would be against a page the answer was not
written from.

**The Turn is the scope.** A URL fetched in some other conversation is not
evidence for this one, so the lookup joins through the Turn rather than trusting
a URL the model typed.

**The frame says it is web.** ``source="web"`` is a closed vocabulary word with a
reader-facing consequence: the browser badges it differently, because a number
this deployment measured and a number it copied are not the same claim.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.alpha.models import TOOL_CALL_OK, AgentToolCall, AgentTurn
from src.core.database import get_sync_db
from src.studies import frames_buffer
from src.studies.contracts import Frame, Provenance

from ..evidence import numbers
from ..messages import dedup_key
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

TOOLSET = "web"

#: Where a runaway result is cut. A bug-stop: what this returns is a summary of
#: fixed shape whose largest honest form is a fraction of this.
MAX_RESULT_CHARS = 8_000

#: How many rows one evidence frame may hold. Twenty, because a table copied off
#: a page past that length is a table that should have been read as a table, and
#: because every row is a number somebody has to be able to check by eye.
MAX_EVIDENCE_ROWS = 20

#: How long the sentence under an evidence frame may be. Shorter than a Study's
#: because it is describing somebody else's page rather than this system's own
#: measurement, and the URL is beside it.
MAX_CAPTION = 140

#: How long one row's own heading may be.
MAX_LABEL = 80

PAGE_NOT_FETCHED = "evidence_page_not_fetched"
NOTHING_MATCHED = "evidence_no_row_matched"
NOT_ON_PAGE = "evidence_number_not_on_page"
AMBIGUOUS = "evidence_number_ambiguous"

#: The two columns an evidence frame has. Named here because both the frame and
#: the summary refer to them, and two spellings of one column name is how a
#: panel ends up with an empty axis.
LABEL_COLUMN = "label"
VALUE_COLUMN = "value"

SessionOpener = Any


EVIDENCE_DESCRIPTION = (
    "Put figures from a page you have already read this turn onto the Signal "
    "Desk. Give the url of a fetch_url call from this same turn and the rows you "
    "read off it — each one a label, a value, and the unit it is in. Every value "
    "is checked against the text of that page: a number that is not printed "
    "there is dropped and named, so copy figures exactly as the page writes "
    "them, and give the unit ('%', 'tỷ đồng', 'nghìn tỷ') because a small round "
    "number with no unit cannot be told apart from a coincidence. Returns a "
    "frameId and how many rows were kept — pass the frameId to render_signal_"
    "desk. Use it when the answer needs a figure this system's own store does "
    "not hold: a policy rate, a macro series, a company outside the Universe."
)

EVIDENCE_SCHEMA = object_schema(
    {
        "url": {
            "type": "string",
            "minLength": 1,
            "description": (
                "The page these figures came from. It must be a url fetch_url "
                "read successfully earlier in this same turn."
            ),
        },
        "rows": {
            "type": "array",
            "minItems": 1,
            "maxItems": MAX_EVIDENCE_ROWS,
            "description": "The figures read off that page, in reading order.",
            "items": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": MAX_LABEL,
                        "description": "What this figure is, in Vietnamese.",
                    },
                    "value": {
                        "type": "number",
                        "description": (
                            "The number exactly as the page prints it — 3.2 for "
                            "'3,2 nghìn tỷ', not 3200000000000."
                        ),
                    },
                    "unit": {
                        "type": "string",
                        "description": (
                            "The unit printed beside it on the page. Required in "
                            "practice for any value under three significant "
                            "digits."
                        ),
                    },
                },
                "required": ["label", "value"],
            },
        },
        "caption": {
            "type": "string",
            "maxLength": MAX_CAPTION,
            "description": "One sentence naming what this table is.",
        },
    },
    ("url", "rows"),
)


def summarise_evidence(arguments: Mapping[str, Any]) -> str:
    """The rail row for a page's figures: how many, off which site."""
    rows = arguments.get("rows")
    count = len(rows) if isinstance(rows, list) else 0
    host = _host(str(arguments.get("url") or ""))
    if count and host:
        return f"Lấy {count} số từ {host}"
    if host:
        return f"Lấy số từ {host}"
    return "Lấy số từ trang đã đọc"


@dataclass(frozen=True)
class FetchedPage:
    """One page this Turn read, as the trace remembers it."""

    url: str
    text: str
    fetched_at: datetime


class EvidenceTool:
    """Turn figures read off a fetched page into a frame, checking every one."""

    def __init__(self, *, session_opener: SessionOpener = get_sync_db) -> None:
        self._session_opener = session_opener

    def entries(self) -> tuple[ToolEntry, ...]:
        return (
            ToolEntry(
                name="frame_from_evidence",
                toolset=TOOLSET,
                description=EVIDENCE_DESCRIPTION,
                schema=EVIDENCE_SCHEMA,
                handler=self.frame_from_evidence,
                display_name="Lấy số từ trang đã đọc",
                summarise=summarise_evidence,
                effect=ToolEffect.READ,
                idempotency=ToolIdempotency.IDEMPOTENT,
                # The store, not the network. Nothing is fetched here: the page
                # is read out of the Tool Call Trace, which is the only copy the
                # answer was actually written from.
                access=ToolAccess.STORE,
                content_trust=ContentTrust.TRUSTED_STRUCTURED,
                concurrency=ToolConcurrency.PARALLEL_SAFE,
                contract_version="1",
                is_async=False,
                max_result_size_chars=MAX_RESULT_CHARS,
            ),
        )

    def frame_from_evidence(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Check every row against the page, and file what survived as a frame."""
        url = str(arguments.get("url") or "").strip()
        if not url:
            raise ValueError("url must name the page these figures came from")
        rows = _rows(arguments.get("rows"))
        caption = str(arguments.get("caption") or "").strip()[:MAX_CAPTION]

        with self._open() as session:
            page = _page_read_this_turn(session, context.turn_id, url)
            if page is None:
                return {
                    "error": PAGE_NOT_FETCHED,
                    "detail": (
                        f"{url} is not a page this turn read. Call fetch_url on "
                        "it first, then bring its figures here."
                    ),
                }

            kept: list[tuple[str, float]] = []
            units: list[str] = []
            refused: list[dict[str, str]] = []
            for label, value, unit in rows:
                verdict = numbers.contains(page.text, value, unit)
                if verdict is numbers.Verdict.MATCHED:
                    kept.append((label, value))
                    units.append(unit)
                    continue
                refused.append(
                    {
                        "label": label,
                        "reason": (
                            NOT_ON_PAGE
                            if verdict is numbers.Verdict.NOT_ON_PAGE
                            else AMBIGUOUS
                        ),
                    }
                )

            if not kept:
                return {
                    "error": NOTHING_MATCHED,
                    "detail": (
                        f"None of the {len(rows)} figures is printed on that "
                        "page as written. Copy them as the page spells them, "
                        "and give the unit beside each one."
                    ),
                    "refused": refused,
                }

            frame = Frame(
                kind="table",
                columns=(LABEL_COLUMN, VALUE_COLUMN),
                rows=tuple((label, value) for label, value in kept),
                # One unit for the frame only when every kept row agrees. A
                # column holding percentages beside billions has no single unit,
                # and inventing one for the axis is worse than leaving it off.
                unit=_common(units),
                labels={LABEL_COLUMN: "Chỉ tiêu", VALUE_COLUMN: "Giá trị"},
            )
            provenance = Provenance(
                source="web",
                as_of=_frozen_at(page.fetched_at),
                sessions_used=len(kept),
                health="normal" if not refused else "degraded",
                reason=(
                    None
                    if not refused
                    else f"{len(refused)} dòng không có trên trang đã đọc"
                ),
                method_notes=(
                    "Số lấy từ trang đã đọc, không phải số đo của hệ thống",
                ),
                query={
                    "url": page.url,
                    "matched": len(kept),
                    "refused": len(refused),
                },
            )
            frame_id = frames_buffer.store_frame(
                session,
                kind=frames_buffer.EVIDENCE_KIND,
                frame=frame,
                provenance=provenance,
                params={
                    "url": page.url,
                    "caption": caption,
                    "matched": len(kept),
                    "refused": refused,
                },
                title=caption or f"Số liệu từ {_host(page.url) or 'trang đã đọc'}",
                turn_id=context.turn_id,
                thread_id=context.thread_id,
            )

        return {
            "frameId": str(frame_id),
            "url": page.url,
            "matched": len(kept),
            "refusedCount": len(refused),
            # Named, not counted only: "two rows dropped" is a fact about the
            # frame, and "the two dropped are the ones the answer turned on" is a
            # fact about the answer.
            "refused": refused,
            "asOf": provenance.as_of.date().isoformat(),
            "unit": frame.unit,
            "health": provenance.health,
        }

    @contextmanager
    def _open(self) -> Iterator[Session]:
        with self._session_opener() as session:
            yield session


def _rows(raw: Any) -> tuple[tuple[str, float, str], ...]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("rows must carry at least one figure read off the page")
    if len(raw) > MAX_EVIDENCE_ROWS:
        raise ValueError(
            f"an evidence frame holds at most {MAX_EVIDENCE_ROWS} rows and "
            f"{len(raw)} were given"
        )
    built: list[tuple[str, float, str]] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise ValueError("every row is {label, value, unit?}")
        label = str(entry.get("label") or "").strip()[:MAX_LABEL]
        if not label:
            raise ValueError("every row needs a label saying what the figure is")
        value = entry.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"row {label!r} needs a numeric value")
        built.append((label, float(value), str(entry.get("unit") or "").strip()))
    return tuple(built)


def _page_read_this_turn(
    session: Session, turn_id: Any, url: str
) -> FetchedPage | None:
    """The page this Turn read at that URL, out of the Tool Call Trace.

    Joined through the Turn rather than filtered on the trace alone, because the
    trace is anchored to the request message and the Turn is what "this turn"
    means. Newest first: a page fetched twice in one Turn is the same page, and
    the later read is the one the model was looking at.

    The URL is compared by the same key the source rail dedupes by, so a link
    the model retyped without ``www.`` still finds the page it read. The
    comparison only; the URL recorded on the frame is the one the fetch returned.
    """
    if turn_id is None:
        return None
    wanted = dedup_key(url)
    rows = session.execute(
        select(AgentToolCall.arguments, AgentToolCall.result, AgentToolCall.started_at)
        .join(
            AgentTurn,
            AgentTurn.request_message_id == AgentToolCall.request_message_id,
        )
        .where(
            AgentTurn.id == turn_id,
            AgentToolCall.tool_name == "fetch_url",
            AgentToolCall.status == TOOL_CALL_OK,
        )
        .order_by(AgentToolCall.started_at.desc(), AgentToolCall.id.desc())
    ).all()

    for arguments, result, started_at in rows:
        payload = _payload(result)
        if payload is None or payload.get("reason"):
            continue
        final = str(payload.get("url") or "")
        asked = str((arguments or {}).get("url") or "")
        if wanted and dedup_key(final) != wanted and dedup_key(asked) != wanted:
            continue
        text = "\n".join(
            part
            for part in (str(payload.get("title") or ""), str(payload.get("content") or ""))
            if part
        )
        if not text.strip():
            continue
        return FetchedPage(
            url=final or asked or url,
            text=text,
            fetched_at=_when(payload.get("retrieved_at")) or started_at,
        )
    return None


def _payload(result: Any) -> Mapping[str, Any] | None:
    """What ``fetch_url`` returned, out of the row the loop wrote for it.

    The trace stores the result as the model read it — one JSON string under
    ``text`` — rather than as the mapping the handler returned, because that is
    the invariant the trace exists for: *what the model actually saw*. So it is
    parsed back rather than read as a field.
    """
    if not isinstance(result, Mapping):
        return None
    text = result.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, Mapping) else None


def _common(units: Sequence[str]) -> str | None:
    kept = {unit for unit in units if unit}
    if len(kept) == 1 and len(units) == len([unit for unit in units if unit]):
        return next(iter(kept))
    return None


def _frozen_at(fetched_at: datetime | None) -> datetime:
    """The day the page was read, which is the day its figures are from.

    A day and not the instant: a figure published on a page is a fact about that
    day, and freezing the minute would make two frames built from one page in one
    Turn claim different vintages.
    """
    if fetched_at is None:
        return datetime.now(timezone.utc)
    stamp = fetched_at if fetched_at.tzinfo else fetched_at.replace(tzinfo=timezone.utc)
    return datetime.combine(stamp.astimezone(timezone.utc).date(), time(), tzinfo=timezone.utc)


def _when(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time(), tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _host(url: str) -> str:
    from urllib.parse import urlsplit

    try:
        return urlsplit(url).hostname or ""
    except ValueError:
        return ""


def register_evidence_tool(
    *, session_opener: SessionOpener = get_sync_db
) -> tuple[ToolEntry, ...]:
    """Register the evidence-frame tool and hand back what was registered."""
    tool = EvidenceTool(session_opener=session_opener)
    return tuple(register(entry) for entry in tool.entries())


__all__ = [
    "AMBIGUOUS",
    "EVIDENCE_DESCRIPTION",
    "EVIDENCE_SCHEMA",
    "LABEL_COLUMN",
    "MAX_CAPTION",
    "MAX_EVIDENCE_ROWS",
    "MAX_RESULT_CHARS",
    "NOTHING_MATCHED",
    "NOT_ON_PAGE",
    "PAGE_NOT_FETCHED",
    "VALUE_COLUMN",
    "EvidenceTool",
    "FetchedPage",
    "register_evidence_tool",
    "summarise_evidence",
]
