"""One bounded, read-only look at what a listed symbol traded at.

This is the first tool in this deployment that returns *numbers* rather than
somebody's prose, and almost everything below exists because of that difference.
A web page carries its own units and its own date in the words around the
figure; a dataframe carries neither, and the two facts that decide whether a
number can ever be cited — what it is measured in, and when it was knowable —
live in the provider's documentation rather than in the payload.

So this module's real job is not fetching. It is turning five floats and an
integer into an evidence row that ``evidence/ledger.py`` can check:

**The scale is applied here, once.** KB Securities reports equity prices in
thousands of dong: ``72.5`` is 72.500 đồng, and a figure passed through
untouched would be off by three orders of magnitude in an answer that cited it
correctly. The multiplication happens at the boundary, and the raw value is
hashed before it happens so the audit trail still holds the number the provider
actually sent.

**The time is a bar close, not a row stamp.** The provider returns naive
timestamps — daily bars at 07:00, which is an artefact of the encoding rather
than an hour anything happened, and intraday bars at their *opening* minute. A
bar is knowable when it closes, so that is what ``published_at`` gets, in ICT.
The same rule is what excludes today's unfinished session: a bar whose close is
still in the future is not evidence of anything yet, and it is dropped here
rather than left for the temporal gate to label ``TEMPORALLY_INVALID`` when the
truthful answer is that it does not exist.

**The excerpt is text, not JSON.** ``ledger._numbers_supported`` asks whether a
number a claim states is printed in the evidence it cites, in the claim's own
unit. That check reads ``EvidenceRef.excerpt`` as a page of prose, so the rows
are rendered as sentences with their units beside them and their prices already
in full dong. A JSON dump would satisfy nothing: the figures would be there and
the units would not.

What this is not: a market terminal. One symbol per call, one dataset, no
ingestion, no cache, no scheduler, no indicator, no screener. The provider is
Vnstock Community, whose licence is personal and non-commercial, so the tool is
unavailable outside the internal profile no matter what credentials a host has.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import io
import json
import logging
import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from src.core.config import Settings, get_settings

from ..registry import (
    ContentTrust,
    ToolAccess,
    ToolConcurrency,
    ToolEffect,
    ToolEntry,
    ToolContext,
    ToolIdempotency,
    ToolPermission,
    object_schema,
    register,
)
from ..symbols import normalize_symbol

logger = logging.getLogger(__name__)

TOOLSET = "market_data"

#: The clock every bar boundary is expressed in. Vietnamese sessions are the
#: only thing this tool reads, and a naive timestamp compared against a UTC
#: ``as_of`` is a seven-hour error in whichever direction hurts most.
ICT = ZoneInfo("Asia/Ho_Chi_Minh")

#: The connector, the upstream feed, and the name a citation carries.
#:
#: ``PUBLISHER`` is the securities company whose server answered, not Vnstock
#: and not the exchange. That distinction is the whole reason a market claim
#: settles at ``SINGLE_SOURCE``: the number came from a broker's feed, and
#: calling it an exchange figure would be a provenance claim nobody can support.
#: The connector package, named here and nowhere the model can read: it is how
#: the host reached the feed, not a source a reader could go and check, and a
#: package name inside the result came back out of the answer as if it were one.
PROVIDER = "vnstock"
SOURCE = "kbs"
PUBLISHER = "KB Securities"

#: The profile this tool may exist on. Community Vnstock is licensed for
#: personal, research and non-commercial use, so every other deployment is
#: refused here rather than at the point somebody notices.
INTERNAL_PROFILE = "personal_internal"

#: What the provider means by one unit of price. Equity and ETF prices come back
#: in thousands of dong; the tool multiplies once and states that it did.
PRICE_SCALE = 1000
CURRENCY = "VND"

#: When a Vietnamese equity session ends. A daily bar is knowable from here.
SESSION_CLOSE = time(15, 0)

#: The intervals this tool offers, and how long one bar of each covers. Two,
#: because two answer the questions the desk actually asks: a daily series for
#: a movement over weeks, and a quarter-hour series when "recently" means today.
#: Both were called against the live provider before being written down.
INTERVALS: Mapping[str, timedelta | None] = {
    "1D": None,
    "15m": timedelta(minutes=15),
}

#: What each interval is called in a sentence a reader sees. The excerpt and the
#: citation are prose, and ``1D`` in the middle of one is a code the reader has
#: to decode — while every code the model reads is a code it may repeat back.
INTERVAL_LABELS: Mapping[str, str] = {
    "1D": "nến ngày",
    "15m": "nến 15 phút",
}

#: How wide a window one call may ask for, per interval. Not a quota — a bound
#: on how much a single result can weigh, since every row of it goes into the
#: model's context and into an evidence excerpt.
MAX_SPAN_DAYS: Mapping[str, int] = {"1D": 400, "15m": 40}

#: The window a call gets when the model names no dates: the last three months
#: of daily bars, ending today. The host picks it because the model picks it
#: badly — on 2026-09-26 a model told today's date in the Turn context still
#: asked for 2024-01-01 → 2025-01-20, the year it remembered, and answered a
#: question about "now" from a series that ended twenty months earlier. With the
#: window the host's, a question about the present cannot start in the past.
DEFAULT_SPAN_DAYS: Mapping[str, int] = {"1D": 92, "15m": 5}

#: How far before today a requested ``end`` may fall before the result says so.
#: A week covers a long holiday; past it the most likely reading is that the
#: model is working in the wrong year, and the note puts today in front of it.
STALE_END_DAYS = 7

#: The most rows one call returns. A window that holds more is answered with its
#: most recent rows and says so, rather than being refused: the recent end is
#: what a question about a move is about.
MAX_ROWS = 250

#: The ceiling the registry enforces on the serialised result.
MAX_RESULT_CHARS = 24_000

#: How long one provider round trip may take before the call is given up on.
FETCH_TIMEOUT_SECONDS = 20.0

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: Stable failure vocabulary. The provider's own message is never passed through
#: as if it were trustworthy prose — it is third-party text, and a model reading
#: "rate limited, upgrade your plan" as an instruction is exactly the boundary
#: ``untrusted.py`` exists to hold.
INVALID_REQUEST = "invalid_request"
NO_DATA = "no_data"
PROVIDER_UNAVAILABLE = "provider_unavailable"
RATE_LIMITED = "rate_limited"
SCHEMA_DRIFT = "schema_drift"
AMBIGUOUS_TIME = "ambiguous_time"

#: The columns the provider contract promises. A payload missing one of them is
#: a contract change, and coercing around it would put a wrong number in an
#: answer rather than a refusal in a trace.
REQUIRED_COLUMNS = ("time", "open", "high", "low", "close", "volume")


class MarketDataError(ValueError):
    """A refusal with a code the loop can act on and a reason a reader can read."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _iso_date(value: Any, field: str) -> date:
    text = str(value or "").strip()
    if not _ISO_DATE.match(text):
        raise MarketDataError(
            INVALID_REQUEST, f"{field} must be a date written as YYYY-MM-DD"
        )
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise MarketDataError(INVALID_REQUEST, f"{field} is not a real date") from exc


def _bar_close(stamp: datetime, interval: str) -> datetime:
    """When the bar starting at ``stamp`` finished, in ICT.

    Daily rows arrive stamped 07:00, which is an encoding artefact rather than a
    time of day, so only the calendar date is read off them and the close is the
    session's. Intraday rows are stamped at the minute the bar opened, so the
    close is that plus the bar's own width.
    """
    width = INTERVALS[interval]
    if width is None:
        return datetime.combine(stamp.date(), SESSION_CLOSE, tzinfo=ICT)
    return stamp.replace(tzinfo=ICT) + width


def _price(value: Any) -> int:
    """One provider price as whole dong.

    Rounded rather than truncated, and to an integer rather than a float: dong
    has no subunit in quoted equity prices, and a price that renders as
    ``72499.99999`` in an excerpt is a number no claim can ever match.
    """
    return int(round(float(value) * PRICE_SCALE))


def _grouped(value: int) -> str:
    """A whole number as a Vietnamese page prints it: ``4.611.900``."""
    return f"{value:,}".replace(",", ".")


def _render_rows(
    symbol: str,
    interval: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    latest: Mapping[str, Any] | None = None,
    date_note: str | None = None,
) -> str:
    """The rows as a page of text, which is the only form the ledger can check.

    Every figure carries its unit in the same breath, because
    ``numbers.contains`` accepts a value with fewer than three significant
    digits only when its unit is printed beside it — and a volume of ``500`` or
    a price a claim rounds to ``72`` is exactly that case.

    The latest session leads, dated, and a stale window's note comes before
    anything else: the figure check dates each number by the session its line
    names, and a reader of the excerpt meets the present before the past.
    """
    # The connector's own name is deliberately absent. This line is the one
    # sentence about the data the model reads in prose, and a package name in it
    # comes back out in the answer as if it were a source the reader could go
    # and check. The publisher is the source; how the host reached it is not.
    head = (
        f"{symbol} · {INTERVAL_LABELS[interval]} · nguồn {PUBLISHER} · "
        f"giá đã quy đổi sang {CURRENCY} đầy đủ"
    )
    lines = [head]
    if date_note:
        lines.append(f"LƯU Ý: {date_note}")
    if latest:
        lines.append(_latest_line(latest))
    for row in rows:
        lines.append(
            f"{row['bar_closed_at']}: "
            f"mở {_grouped(row['open'])} đồng · "
            f"cao {_grouped(row['high'])} đồng · "
            f"thấp {_grouped(row['low'])} đồng · "
            f"đóng {_grouped(row['close'])} đồng · "
            f"khối lượng {_grouped(row['volume'])} cổ phiếu"
        )
    return "\n".join(lines)


def _latest_line(latest: Mapping[str, Any]) -> str:
    session = date.fromisoformat(str(latest["session_date"]))
    today = date.fromisoformat(str(latest["today"]))
    when = (
        "phiên hôm nay"
        if latest.get("session_today")
        else f"hôm nay {today.strftime('%d/%m/%Y')} chưa có phiên đóng cửa"
    )
    line = (
        f"{latest['bar_closed_at']}: PHIÊN GẦN NHẤT {session.strftime('%d/%m/%Y')} "
        f"({when}) · đóng {_grouped(int(latest['close']))} đồng"
    )
    if latest.get("change") is not None and latest.get("previous_session_date"):
        previous = date.fromisoformat(str(latest["previous_session_date"]))
        change = int(latest["change"])
        sign = "+" if change > 0 else ("-" if change < 0 else "")
        line += f" · thay đổi {sign}{_grouped(abs(change))} đồng"
        if latest.get("change_pct") is not None:
            pct = float(latest["change_pct"])
            line += f" ({'+' if pct > 0 else ('-' if pct < 0 else '')}{abs(pct):.2f}%)".replace(".", ",")
        line += f" so với phiên {previous.strftime('%d/%m/%Y')}"
    line += f" · khối lượng {_grouped(int(latest['volume']))} cổ phiếu"
    return line


def _import_vnstock() -> Any:
    """Import the provider package, catching what its start-up prints.

    The package announces a sponsorship programme when it loads. This catches
    the part of it written through ``sys.stdout``; the banner itself is drawn by
    the package's own console, which holds the real stream, so a line or two
    still reaches the log the first time a process makes a market call.

    Left at that rather than redirected at the file descriptor: swapping fd 1
    under a running server races every other thread writing a log line, which is
    a much worse failure than one banner per process.
    """
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        return importlib.import_module(PROVIDER)


class MarketDataTools:
    """The one market capability, and the settings that decide it exists."""

    def __init__(self, *, settings: Settings | None = None) -> None:
        self._injected_settings = settings
        # Whether the package is importable, remembered once. A failed import is
        # remembered too: retrying it on every schema build would pay the
        # package's own start-up cost on every round of every Turn.
        self._package: bool | None = None

    @property
    def _settings(self) -> Settings:
        # Read per call, on the same reasoning as ``WebTools``: the profile and
        # the flag are configuration, and a process that reloads it should not
        # keep serving the answer it started with.
        return self._injected_settings or get_settings()

    # -- availability ------------------------------------------------------

    def _package_importable(self) -> bool:
        if self._package is None:
            try:
                _import_vnstock()
            except Exception:  # noqa: BLE001 - a broken probe reads as unavailable
                logger.info("Market data provider is not importable; tool stays off")
                self._package = False
            else:
                self._package = True
        return self._package

    def available(self) -> bool:
        """Three gates, and all three have to hold.

        The profile is first and is the one that cannot be worked around: the
        provider's community licence is personal and non-commercial, so a
        production host with a valid credential and the flag on still gets
        ``False``. The flag is the deployment's own decision on top of that, and
        the import check is whether the call could be made at all.
        """
        settings = self._settings
        if settings.deployment_profile != INTERNAL_PROFILE:
            return False
        if not settings.market_data_enabled:
            return False
        return self._package_importable()

    # -- registration ------------------------------------------------------

    def entries(self) -> tuple[ToolEntry, ...]:
        return (
            ToolEntry(
                name="get_market_data",
                toolset=TOOLSET,
                description=(
                    "Read one listed Vietnamese symbol's price and volume history "
                    "for a date range. Prices come back in whole dong and every "
                    "bar is stamped with the time it closed. Use it whenever an "
                    "answer rests on prices or volumes; do not use it for news, "
                    "financial statements or company events. Take the symbol from "
                    "the question or from a source you read; if you only have a "
                    "company name, find its ticker first. Derive start and end "
                    "from the question only when it names a period; leave them "
                    "out for anything about now and the host reads the last three "
                    "months ending today. The result starts with the latest "
                    "session — quote current figures from there, with its date. A "
                    f"daily window may span {MAX_SPAN_DAYS['1D']} days and a 15m "
                    f"window {MAX_SPAN_DAYS['15m']} days; at most the latest "
                    f"{MAX_ROWS} bars come back. Provider-reported "
                    "figures from a securities company's feed, not from the "
                    "exchange: cite them as one source."
                ),
                schema=object_schema(
                    {
                        "symbol": {
                            "type": "string",
                            "minLength": 1,
                            "description": "Ticker on HOSE, HNX or UPCOM, e.g. FPT.",
                        },
                        "start": {
                            "type": "string",
                            "description": (
                                "First session to include, YYYY-MM-DD. Omit it "
                                "unless the question names a period."
                            ),
                        },
                        "end": {
                            "type": "string",
                            "description": (
                                "Last session to include, YYYY-MM-DD. Omit it and "
                                "the host uses today."
                            ),
                        },
                        "interval": {
                            "type": "string",
                            "enum": list(INTERVALS),
                            "description": (
                                "One bar per trading day (1D) or per quarter hour "
                                "(15m). Use 15m only when the question turns on "
                                "something inside a single session."
                            ),
                        },
                    },
                    ("symbol", "interval"),
                ),
                handler=self.get_market_data,
                display_name="Đọc dữ liệu giá",
                summarise=_summarise,
                effect=ToolEffect.READ,
                idempotency=ToolIdempotency.IDEMPOTENT,
                access=ToolAccess.NETWORK,
                # Provider-reported figures a stranger's server composed. The
                # numbers are the point of the call and the surrounding strings
                # still are not instructions.
                content_trust=ContentTrust.UNTRUSTED,
                concurrency=ToolConcurrency.PARALLEL_SAFE,
                permission=ToolPermission.ALLOW,
                resource_arg="symbol",
                # The handler blocks: the provider client is synchronous, so it
                # is moved off the event loop rather than stalling its round.
                is_async=False,
                timeout_seconds=FETCH_TIMEOUT_SECONDS,
                contract_version="1",
                check_fn=self.available,
                max_result_size_chars=MAX_RESULT_CHARS,
            ),
        )

    # -- the call ----------------------------------------------------------

    def get_market_data(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        now = (context.now or datetime.now(tz=ICT)).astimezone(ICT)
        symbol, start, end, interval = _validate(arguments, today=now.date())
        # The evidence boundary the question named, when it named one. A bar
        # that closed after it is not admissible and is dropped here, so the
        # model never sees a row it could not have known about.
        horizon = min(now, context.as_of.astimezone(ICT)) if context.as_of else now

        frame = self._history(symbol, start, end, interval)
        raw_payload, records = _raw(frame)
        rows, dropped_future = _normalise(records, start, end, interval, horizon)

        if not rows:
            raise MarketDataError(
                NO_DATA,
                f"{symbol} has no {interval} bars closing between {start} and {end}",
            )

        truncated = len(rows) > MAX_ROWS
        if truncated:
            # The recent end, because a question about a move is about the end
            # of the series rather than its beginning.
            rows = rows[-MAX_ROWS:]

        latest = _latest(rows, interval, now.date())
        date_note = _date_note(end, now.date())
        excerpt = _render_rows(symbol, interval, rows, latest=latest, date_note=date_note)
        return {
            "symbol": symbol,
            "interval": interval,
            "interval_label": INTERVAL_LABELS[interval],
            # The connector and its version are deployment facts, and this
            # payload is read by a model that quotes what it is given. They stay
            # in the host's own logs, where an auditor looks, rather than in the
            # context a sentence is composed from.
            "source": SOURCE,
            "publisher": PUBLISHER,
            "source_class": "store",
            "currency": CURRENCY,
            "price_unit": "VND",
            "price_scale_applied": PRICE_SCALE,
            "timezone": str(ICT),
            "requested": {"start": start.isoformat(), "end": end.isoformat()},
            "actual": {
                "start": rows[0]["bar_closed_at"],
                "end": rows[-1]["bar_closed_at"],
            },
            # Ahead of the rows on purpose. A model reads the head of a result
            # and skims the rest, so the one figure a question about "now" needs
            # is the first one it meets, already dated.
            "latest": latest,
            "date_note": date_note,
            "row_count": len(rows),
            "rows_dropped_after_horizon": dropped_future,
            "truncated": truncated,
            "quality": "partial" if (truncated or dropped_future) else "ok",
            "retrieved_at": now.isoformat(),
            # The hash is of what the provider sent, before the scale was
            # applied and before anything was filtered. One hash rather than
            # two: the normalised rows follow from the raw ones deterministically,
            # so a second digest would be a number nobody could ever disagree with.
            "content_sha256": hashlib.sha256(raw_payload).hexdigest(),
            "rows": rows,
            "excerpt": excerpt,
        }

    def _history(self, symbol: str, start: date, end: date, interval: str) -> Any:
        """One provider operation. No pagination loop, no fan-out, no fallback."""
        if not self.available():
            raise MarketDataError(
                PROVIDER_UNAVAILABLE,
                "market data is not enabled on this deployment",
            )
        module = _import_vnstock()
        try:
            quote = module.Quote(source=SOURCE, symbol=symbol)
            # The provider reads ``end`` as exclusive: asking for a range that
            # finishes on the last session returns everything before it, and a
            # range whose two ends are the same day raises rather than returning
            # that day. One day is added here and ``_normalise`` cuts the result
            # back to the range that was actually asked for.
            return quote.history(
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                interval=interval,
            )
        except Exception as exc:  # noqa: BLE001 - provider failures are classified
            raise _classify(exc, symbol) from exc


def _validate(
    arguments: Mapping[str, Any], *, today: date
) -> tuple[str, date, date, str]:
    """Everything the model may choose, checked before anything leaves the host.

    ``start`` and ``end`` are optional and the host fills them: ``end`` is
    today, ``start`` the default span before it. A strict route restates every
    property, so "omitted" also arrives as ``null`` or an empty string.
    """
    try:
        symbol = normalize_symbol(str(arguments.get("symbol") or ""))
    except ValueError as exc:
        raise MarketDataError(INVALID_REQUEST, str(exc)) from exc

    interval = str(arguments.get("interval") or "1D").strip()
    if interval not in INTERVALS:
        raise MarketDataError(
            INVALID_REQUEST,
            f"interval must be one of {', '.join(INTERVALS)}",
        )

    end = _iso_date(arguments["end"], "end") if _given(arguments.get("end")) else today
    start = (
        _iso_date(arguments["start"], "start")
        if _given(arguments.get("start"))
        else end - timedelta(days=DEFAULT_SPAN_DAYS[interval])
    )
    if start > end:
        raise MarketDataError(INVALID_REQUEST, "start must not be after end")

    span = (end - start).days + 1
    cap = MAX_SPAN_DAYS[interval]
    if span > cap:
        raise MarketDataError(
            INVALID_REQUEST,
            f"a {interval} request covers at most {cap} days and this one covers {span}",
        )
    return symbol, start, end, interval


def _given(value: Any) -> bool:
    return value is not None and bool(str(value).strip())


def _latest(
    rows: Sequence[Mapping[str, Any]], interval: str, today: date
) -> dict[str, Any]:
    """The most recent bar, its change on the one before, and whether it is today's.

    Computed here rather than left to the model because it is arithmetic on two
    rows the host already holds: a change the model works out in its head is a
    number no source prints, and one the host prints is a number the figure
    check can find.
    """
    last = rows[-1]
    closed = datetime.fromisoformat(str(last["bar_closed_at"]))
    session = closed.astimezone(ICT).date()
    latest: dict[str, Any] = {
        "session_date": session.isoformat(),
        "bar_closed_at": last["bar_closed_at"],
        "close": last["close"],
        "volume": last["volume"],
        "session_today": session == today,
        "today": today.isoformat(),
        "previous_session_date": None,
        "previous_close": None,
        "change": None,
        "change_pct": None,
    }
    if len(rows) > 1 and interval == "1D":
        before = rows[-2]
        previous = before["close"]
        latest["previous_session_date"] = (
            datetime.fromisoformat(str(before["bar_closed_at"])).astimezone(ICT).date().isoformat()
        )
        latest["previous_close"] = previous
        latest["change"] = last["close"] - previous
        if previous:
            latest["change_pct"] = round((last["close"] - previous) * 100 / previous, 2)
    return latest


def _date_note(end: date, today: date) -> str | None:
    """A sentence saying today's date, when the window asked for ends well before it."""
    if (today - end).days <= STALE_END_DAYS:
        return None
    return (
        f"Hôm nay là {today.strftime('%d/%m/%Y')}; khoảng dữ liệu bạn xin kết thúc "
        f"{end.strftime('%d/%m/%Y')}. Số liệu dưới đây không phải giá hiện tại. Nếu "
        "câu hỏi hỏi về hiện tại, gọi lại mà không truyền start và end."
    )


def _classify(exc: Exception, symbol: str) -> MarketDataError:
    """A provider exception as one of this tool's own codes.

    The provider wraps a weekend, a bad ticker and an outage in whichever
    exception its retry decorator happened to raise, so the text is read for a
    signal and everything unrecognised becomes ``provider_unavailable`` — the
    answer that is true when nothing more specific is known.
    """
    text = str(exc).casefold()
    if "429" in text or "rate" in text and "limit" in text:
        return MarketDataError(RATE_LIMITED, "the provider is rate limiting this host")
    if "not found" in text or "invalid symbol" in text or "symbol" in text:
        return MarketDataError(
            INVALID_REQUEST, f"the provider does not recognise {symbol}"
        )
    if "no data" in text or "empty" in text:
        return MarketDataError(NO_DATA, f"the provider returned no rows for {symbol}")
    return MarketDataError(
        PROVIDER_UNAVAILABLE, "the market data provider did not answer this call"
    )


def _raw(frame: Any) -> tuple[bytes, list[Mapping[str, Any]]]:
    """The payload exactly as it arrived, and the rows read out of it.

    The bytes are what gets hashed, so they are built before any renaming or
    rescaling: an audit that cannot reproduce the provider's own numbers is not
    an audit.
    """
    if frame is None:
        raise MarketDataError(NO_DATA, "the provider returned nothing")
    records = [
        {str(key): value for key, value in record.items()}
        for record in frame.to_dict(orient="records")
    ]
    # Emptiness is answered before the schema is, because an empty result has no
    # columns to be missing: a quiet week reported as ``schema_drift`` would send
    # a reader looking for a contract change that never happened.
    if not records:
        raise MarketDataError(NO_DATA, "the provider returned no rows for this range")
    columns = [str(name) for name in getattr(frame, "columns", [])] or list(records[0])
    missing = [name for name in REQUIRED_COLUMNS if name not in columns]
    if missing:
        raise MarketDataError(
            SCHEMA_DRIFT,
            f"the provider payload is missing {', '.join(missing)}",
        )
    payload = json.dumps(
        records, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return payload, records


def _normalise(
    records: Sequence[Mapping[str, Any]],
    start: date,
    end: date,
    interval: str,
    horizon: datetime,
) -> tuple[list[dict[str, Any]], int]:
    """Provider rows as evidence rows, filtered to what was asked and knowable.

    The date filter is applied here and not trusted to the provider: one of the
    two upstream sources has been observed returning a hundred rows for a
    five-day request, and a caller that believed the argument would have handed
    the model ninety-five sessions it never asked about.
    """
    rows: list[dict[str, Any]] = []
    dropped_future = 0
    for record in records:
        stamp = record.get("time")
        if not isinstance(stamp, datetime):
            try:
                stamp = datetime.fromisoformat(str(stamp))
            except (TypeError, ValueError) as exc:
                raise MarketDataError(
                    AMBIGUOUS_TIME, "a provider row has no readable timestamp"
                ) from exc
        if stamp.tzinfo is not None:
            stamp = stamp.astimezone(ICT).replace(tzinfo=None)
        closed_at = _bar_close(stamp, interval)
        if not (start <= closed_at.date() <= end):
            continue
        if closed_at > horizon:
            # An unfinished bar. Not evidence of a close that has not happened.
            dropped_future += 1
            continue
        try:
            row = {
                "bar_opened_at": stamp.replace(tzinfo=ICT).isoformat(),
                "bar_closed_at": closed_at.isoformat(),
                "open": _price(record["open"]),
                "high": _price(record["high"]),
                "low": _price(record["low"]),
                "close": _price(record["close"]),
                "volume": int(record["volume"]),
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise MarketDataError(
                SCHEMA_DRIFT, "a provider row has a value this tool cannot read"
            ) from exc
        rows.append(row)
    rows.sort(key=lambda item: item["bar_closed_at"])
    return rows, dropped_future


def _summarise(arguments: Mapping[str, Any]) -> str:
    """The rail row, composed because no single argument says what was read."""
    symbol = str(arguments.get("symbol") or "?").strip().upper()
    interval = str(arguments.get("interval") or "1D").strip()
    start = str(arguments.get("start") or "").strip()
    end = str(arguments.get("end") or "").strip()
    if not start and not end:
        return f"Đọc dữ liệu giá {symbol} · {interval} · 3 tháng gần nhất"
    return f"Đọc dữ liệu giá {symbol} · {interval} · {start or '…'} → {end or 'hôm nay'}"


def register_market_data_tools(*, settings: Settings | None = None) -> tuple[ToolEntry, ...]:
    tools = MarketDataTools(settings=settings)
    return tuple(register(entry) for entry in tools.entries())


__all__ = [
    "CURRENCY",
    "DEFAULT_SPAN_DAYS",
    "ICT",
    "INTERNAL_PROFILE",
    "INTERVALS",
    "INTERVAL_LABELS",
    "MAX_ROWS",
    "MAX_SPAN_DAYS",
    "MarketDataError",
    "MarketDataTools",
    "PRICE_SCALE",
    "PUBLISHER",
    "PROVIDER",
    "SOURCE",
    "TOOLSET",
    "register_market_data_tools",
]
