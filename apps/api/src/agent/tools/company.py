"""What a listed company announced: corporate events and its news, by ticker.

Both read Vietcap through the shared provider door and come back the way every
data tool here does — one line per item, starting with the date it belongs to —
so the figure check can date a dividend or a transaction volume the same way it
dates a close (``evidence/grounding.py``).

**Which date leads an event line** is the date the event is about, not when it
was announced: the ex-right date of a dividend, the date of a meeting. The
announcement date follows on the line. A sentence about "cổ tức 450 đồng, GDKHQ
23/07" is checked against the ex-right date, and that is the date it names.

**News is a headline and a date.** The feed rarely carries the article body, and
a headline is not evidence of every figure an article reports; a news line
older than 30 days is marked as an old source when an answer leans on it.
"""

from __future__ import annotations

import hashlib
import importlib
import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

from src.core.config import Settings, get_settings

from ..registry import (
    ContentTrust,
    ToolAccess,
    ToolConcurrency,
    ToolContext,
    ToolEffect,
    ToolEntry,
    ToolIdempotency,
    ToolPermission,
    object_schema,
    register,
)
from ..symbols import normalize_symbol
from . import vnstock_provider
from .market_data import FETCH_TIMEOUT_SECONDS, ICT, INTERNAL_PROFILE, is_index
from .vnstock_provider import MarketDataError, import_vnstock

TOOLSET = "market_data"
PUBLISHER = "Vietcap"
DEFAULT_ITEMS = 10
MAX_ITEMS = 30
MAX_RESULT_CHARS = 16_000


def _day(value: Any) -> date | None:
    raw = str(value or "")[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _vn_date(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def _percent(value: Any) -> str | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number == 0:
        return None
    return f"{number * 100:.2f}".rstrip("0").rstrip(".").replace(".", ",") + "%"


def _money(value: Any) -> str | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number == 0:
        return None
    return f"{number:,.0f}".replace(",", ".") + " đồng/cổ phiếu"


def event_lines(records: Sequence[Mapping[str, Any]], limit: int) -> list[str]:
    """Events newest first, each dated by the day it is about."""
    lines: list[tuple[date, str]] = []
    for record in records:
        title = str(record.get("event_title_vi") or record.get("event_name_vi") or "").strip()
        about = (
            _day(record.get("exright_date"))
            or _day(record.get("display_date1"))
            or _day(record.get("public_date"))
        )
        if not title or about is None:
            continue
        parts = [title]
        amount = _money(record.get("value_per_share"))
        ratio = _percent(record.get("exercise_ratio"))
        if amount:
            parts.append(amount + (f" (tỷ lệ {ratio})" if ratio else ""))
        elif ratio:
            parts.append(f"tỷ lệ {ratio}")
        for key, label in (
            ("exright_date", "ngày GDKHQ"),
            ("record_date", "ngày chốt quyền"),
            ("payout_date", "ngày thanh toán"),
            ("start_date", "từ"),
            ("end_date", "đến"),
            ("public_date", "công bố"),
        ):
            stamp = _day(record.get(key))
            if stamp:
                parts.append(f"{label} {_vn_date(stamp)}")
        lines.append((about, f"{about.isoformat()}: " + " · ".join(parts)))
    lines.sort(key=lambda item: item[0], reverse=True)
    return [text for _, text in lines[:limit]]


def news_lines(records: Sequence[Mapping[str, Any]], limit: int) -> list[str]:
    """Headlines newest first, each dated by its publication."""
    lines: list[tuple[str, str]] = []
    for record in records:
        title = str(record.get("news_title") or "").strip()
        published = str(record.get("public_date") or "").strip()
        day = _day(published)
        if not title or day is None:
            continue
        summary = str(record.get("news_short_content") or "").strip()
        text = f"{day.isoformat()}: {title}" + (f" — {summary[:240]}" if summary else "")
        lines.append((published, text))
    lines.sort(key=lambda item: item[0], reverse=True)
    return [text for _, text in lines[:limit]]


class CompanyTools:
    def __init__(self, *, settings: Settings | None = None) -> None:
        self._settings_override = settings

    def available(self) -> bool:
        settings = self._settings_override or get_settings()
        return settings.deployment_profile == INTERNAL_PROFILE and settings.market_data_enabled

    def entries(self) -> tuple[ToolEntry, ...]:
        common: dict[str, Any] = dict(
            toolset=TOOLSET,
            effect=ToolEffect.READ,
            idempotency=ToolIdempotency.IDEMPOTENT,
            access=ToolAccess.NETWORK,
            content_trust=ContentTrust.UNTRUSTED,
            concurrency=ToolConcurrency.PARALLEL_SAFE,
            permission=ToolPermission.ALLOW,
            resource_arg="symbol",
            is_async=False,
            timeout_seconds=FETCH_TIMEOUT_SECONDS,
            contract_version="1",
            check_fn=self.available,
            max_result_size_chars=MAX_RESULT_CHARS,
        )
        schema = object_schema(
            {
                "symbol": {"type": "string", "minLength": 1},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_ITEMS},
            },
            ("symbol",),
        )
        return (
            ToolEntry(
                name="get_company_events",
                description=(
                    "List one listed company's corporate events, newest first: cash and "
                    "stock dividends with ex-right, record and payment dates, bonus "
                    "issues, shareholder meetings and insider or major-shareholder "
                    "deals. Use it for any question about dividends, meetings or insider "
                    "trading before searching the web, and quote each item with its date."
                ),
                schema=schema,
                handler=self.get_company_events,
                display_name="Đọc sự kiện doanh nghiệp",
                summarise=lambda args: f"Đọc sự kiện doanh nghiệp {str(args.get('symbol') or '?').upper()}",
                **common,
            ),
            ToolEntry(
                name="get_company_news",
                description=(
                    "List one listed company's recent news headlines and disclosures with "
                    "their publication dates. Use it to find what the company announced "
                    "lately; a headline is not the article, so open the source with "
                    "fetch_url before stating a figure that only the article gives."
                ),
                schema=schema,
                handler=self.get_company_news,
                display_name="Đọc tin doanh nghiệp",
                summarise=lambda args: f"Đọc tin doanh nghiệp {str(args.get('symbol') or '?').upper()}",
                **common,
            ),
        )

    def get_company_events(self, context: ToolContext, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        symbol, limit = self._request(arguments)
        records = self._read(symbol, "events")
        lines = event_lines(records, limit)
        return self._payload(context, symbol, records, lines, kind="events", heading="sự kiện doanh nghiệp")

    def get_company_news(self, context: ToolContext, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        symbol, limit = self._request(arguments)
        records = self._read(symbol, "news")
        lines = news_lines(records, limit)
        return self._payload(context, symbol, records, lines, kind="news", heading="tin doanh nghiệp")

    def _request(self, arguments: Mapping[str, Any]) -> tuple[str, int]:
        try:
            symbol = normalize_symbol(str(arguments.get("symbol") or ""))
        except ValueError as exc:
            raise MarketDataError(vnstock_provider.INVALID_REQUEST, str(exc)) from exc
        if is_index(symbol):
            raise MarketDataError(vnstock_provider.INVALID_REQUEST, f"{symbol} is an index, not a company")
        if not self.available():
            raise MarketDataError(
                vnstock_provider.PROVIDER_UNAVAILABLE, "company data is not enabled on this deployment"
            )
        wanted = arguments.get("limit")
        return symbol, max(1, min(MAX_ITEMS, int(wanted))) if wanted is not None else DEFAULT_ITEMS

    def _read(self, symbol: str, method: str) -> list[dict[str, Any]]:
        import_vnstock()

        def read() -> list[dict[str, Any]]:
            company = importlib.import_module("vnstock.explorer.vci.company").Company(symbol=symbol)
            return getattr(company, method)().to_dict(orient="records")

        return vnstock_provider.call(read, symbol=symbol)

    @staticmethod
    def _payload(
        context: ToolContext,
        symbol: str,
        records: Sequence[Mapping[str, Any]],
        lines: list[str],
        *,
        kind: str,
        heading: str,
    ) -> Mapping[str, Any]:
        if not lines:
            raise MarketDataError(vnstock_provider.NO_DATA, f"no dated {kind} for {symbol}")
        now = (context.now or datetime.now(tz=ICT)).astimezone(ICT)
        encoded = json.dumps(list(records), ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        newest = lines[0][:10]
        return {
            "symbol": symbol,
            "publisher": PUBLISHER,
            "source": f"vci-{kind}",
            "source_class": "store",
            "evidence_kind": "store_figure",
            "evidence_role": kind,
            "title": f"{symbol} · {heading}",
            "as_of": datetime.combine(date.fromisoformat(newest), datetime.min.time(), tzinfo=ICT).isoformat(),
            "retrieved_at": now.isoformat(),
            "content_sha256": hashlib.sha256(encoded).hexdigest(),
            "item_count": len(lines),
            "excerpt": "\n".join(
                [f"{symbol} · {heading} · nguồn {PUBLISHER} · mỗi dòng bắt đầu bằng ngày của mục đó", *lines]
            ),
        }


def register_company_tools(*, settings: Settings | None = None) -> tuple[ToolEntry, ...]:
    return tuple(register(entry) for entry in CompanyTools(settings=settings).entries())


__all__ = ["CompanyTools", "event_lines", "news_lines", "register_company_tools"]
