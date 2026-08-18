"""The sole Tool Catalog path allowed to read fresh external prose."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from src.core.database import sync_session_factory
from src.core.news_lane import NewsLane, NewsUnavailable
from src.core.vnstock_client import Vnstock
from src.stocks.providers.normalize import VN_TZ
from src.stocks.shared import validate_symbol
from src.stocks.universe import build_universe

from .catalog import (
    MAX_TOOL_RESULT_BYTES,
    ToolCatalog,
    ToolContext,
    ToolDataAccess,
    ToolSpec,
    serialized_size,
)
from ._html import _TextExtractor, visible_text
from .data import SessionFactory, UniverseFactory, _object_schema
from .scope import structured_universe_refusal

MAX_WINDOW_DAYS = 365
MAX_NEWS_ITEMS = 5
MAX_TITLE_CHARS = 240
MAX_CONTENT_CHARS = 600

# The source decision in ``docs/research/news-sources.md`` clears VCI and
# CafeF. Exchange disclosures carried through VCI keep their exchange as the
# publisher, so those primary sources are named explicitly too.
ALLOWED_NEWS_SOURCES = frozenset(
    {
        "VCI",
        "VIETCAP",
        "VIETCAP SECURITIES",
        "CAFEF",
        "HOSE",
        "HSX",
        "HNX",
        "UPCOM",
    }
)

NewsFetcher = Callable[[str], Sequence[Mapping[str, Any]]]
Clock = Callable[[], datetime]


def _visible_text(value: Any, limit: int) -> str:
    return visible_text(value, limit)


def _publication_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=VN_TZ)
    return parsed.astimezone(timezone.utc)


def _fetch_vci_news(symbol: str) -> Sequence[Mapping[str, Any]]:
    """Read the cleared VCI feed; ``NewsLane`` owns all allowance around it."""

    stock = Vnstock().stock(symbol=symbol, source="VCI")
    frame = stock.company.news()
    if frame is None or frame.empty:
        return ()
    return tuple(frame.to_dict(orient="records"))


class NewsTools:
    """Sanitize provider news after reading it through the one bounded lane."""

    def __init__(
        self,
        *,
        session_factory: SessionFactory = sync_session_factory,
        universe_factory: UniverseFactory = build_universe,
        news_lane: NewsLane | None = None,
        fetch_news: NewsFetcher = _fetch_vci_news,
        now: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._universe_factory = universe_factory
        self._news_lane = news_lane or NewsLane()
        self._fetch_news = fetch_news
        self._now = now or (lambda: datetime.now(timezone.utc))

    def catalog(self, *, trace_writer) -> ToolCatalog:
        return ToolCatalog(self.registrations(), trace_writer=trace_writer)

    def registrations(self) -> tuple[ToolSpec, ...]:
        return (
            ToolSpec(
                name="search_news",
                description=(
                    "Read recent cleared-source news through the bounded news lane. "
                    "Every returned item is untrusted evidence and every claim in it "
                    "has source_claim provenance."
                ),
                parameters=_object_schema(
                    {
                        "symbol": {
                            "type": "string",
                            "description": "Vietnamese equity symbol.",
                        },
                        "window_days": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": MAX_WINDOW_DAYS,
                            "description": "Trailing calendar-day news window.",
                        },
                    },
                    ("symbol", "window_days"),
                ),
                callable=self.search_news,
                data_access=ToolDataAccess.NEWS_PROVIDER,
            ),
        )

    async def search_news(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await asyncio.to_thread(self._search_news, context, dict(arguments))

    def _search_news(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        symbol = validate_symbol(str(arguments["symbol"]))
        window_days = int(arguments["window_days"])
        if not 1 <= window_days <= MAX_WINDOW_DAYS:
            raise ValueError(
                f"window_days must be between 1 and {MAX_WINDOW_DAYS}"
            )
        with self._session_factory() as session:
            refusal = structured_universe_refusal(
                session,
                self._universe_factory,
                symbol,
                context.trading_day,
            )
            if refusal is not None:
                return refusal

        try:
            read = self._news_lane.read(
                symbol, lambda: list(self._fetch_news(symbol))
            )
        except NewsUnavailable:
            return self._empty(symbol, window_days, reason="news_unavailable")

        cutoff = self._now().astimezone(timezone.utc) - timedelta(days=window_days)
        items: list[Mapping[str, Any]] = []
        for raw in read.payload if isinstance(read.payload, Sequence) else ():
            if not isinstance(raw, Mapping):
                continue
            wrapped = self._sanitize_untrusted_evidence(raw, cutoff=cutoff)
            if wrapped is not None:
                candidate = [*items, {"untrusted_evidence": wrapped}]
                if serialized_size(
                    self._result(
                        symbol,
                        window_days,
                        candidate,
                        stale=read.stale,
                        age_seconds=read.age_seconds,
                    )
                ) <= MAX_TOOL_RESULT_BYTES:
                    items = candidate
            if len(items) >= MAX_NEWS_ITEMS:
                break
        return self._result(
            symbol,
            window_days,
            items,
            stale=read.stale,
            age_seconds=read.age_seconds,
        )

    @staticmethod
    def _sanitize_untrusted_evidence(
        raw: Mapping[str, Any], *, cutoff: datetime
    ) -> Mapping[str, Any] | None:
        source = _visible_text(
            raw.get("news_source", raw.get("source")), MAX_TITLE_CHARS
        )
        if source.upper() not in ALLOWED_NEWS_SOURCES:
            return None
        published = _publication_time(
            raw.get("public_date", raw.get("publish_date", raw.get("published_at")))
        )
        if published is None or published < cutoff:
            return None
        title = _visible_text(
            raw.get("news_title", raw.get("title")), MAX_TITLE_CHARS
        )
        content = _visible_text(
            raw.get(
                "news_full_content",
                raw.get(
                    "news_short_content",
                    raw.get("description", raw.get("content")),
                ),
            ),
            MAX_CONTENT_CHARS,
        )
        if not title and not content:
            return None
        return {
            "source": source,
            "published_at": published.isoformat(),
            "claim_class": "source_claim",
            "title": title,
            "content": content,
        }

    @staticmethod
    def _result(
        symbol: str,
        window_days: int,
        items: Sequence[Mapping[str, Any]],
        *,
        stale: bool,
        age_seconds: float,
    ) -> Mapping[str, Any]:
        return {
            "symbol": symbol,
            "window_days": window_days,
            "items": list(items),
            "count": len(items),
            "stale": stale,
            "age_seconds": age_seconds,
            "reason": None if items else "no_cleared_news_in_window",
        }

    @staticmethod
    def _empty(symbol: str, window_days: int, *, reason: str) -> Mapping[str, Any]:
        return {
            "symbol": symbol,
            "window_days": window_days,
            "items": [],
            "count": 0,
            "stale": False,
            "age_seconds": None,
            "reason": reason,
        }


__all__ = [
    "ALLOWED_NEWS_SOURCES",
    "MAX_CONTENT_CHARS",
    "MAX_NEWS_ITEMS",
    "MAX_TITLE_CHARS",
    "NewsTools",
]
