"""Filter and rank a set of listed tickers by market and reported figures.

The model turns "ngân hàng nào P/B dưới 1,5 và tăng giá hôm qua" into a
universe, a few filters and a sort; this tool does the reading and the
comparing, so no ranking in an answer rests on figures the model recalled.

**Two kinds of field, two costs.** Market fields — price, change, volume,
traded value, foreign net flow — come from KB's price board, one request for up
to fifty tickers. Reported fields need one read per ticker: P/B, P/E and
trailing ROE from KB (one request), NPL from Vietcap (two, and only when asked
for). The provider allows sixteen requests a minute in this process
(``vnstock_provider``), so reported figures are cached per ticker for half a
day and fetched in parallel, only while the quota has room *now* and only for
:data:`FUNDAMENTALS_BUDGET_SECONDS`. A ticker the tool could not cover is named
as not yet covered — never guessed, never silently dropped from a ranking — and
a read still in flight when the budget ends fills the cache for the next call.

**Every figure it prints is dated.** Market lines carry the session the board
reported; reported lines carry the quarter's end. The figure check reads them
like any other data tool's lines.
"""

from __future__ import annotations

import hashlib
import importlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout
import operator
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
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
from ..evidence.numbers import fold
from .financials import KbsFinancials, VciFinancials
from .market_data import ICT, INTERNAL_PROFILE, is_index
from .vnstock_provider import MarketDataError, TtlCache, import_vnstock

TOOLSET = "market_data"
TOOL_NAME = "screen_stocks"
MAX_UNIVERSE = 60
MAX_RESULTS = 30
BOARD_CHUNK = 50
FUNDAMENTALS_TTL_SECONDS = 12 * 3600
#: How long one screen may spend reading reported figures. Leaves the tool's
#: 20 s budget room for the price board and the listing.
FUNDAMENTALS_BUDGET_SECONDS = 9.0
FUNDAMENTAL_WORKERS = 4
LISTING_TTL_SECONDS = 24 * 3600

#: field → (label, unit, kind). ``market`` fields come from the price board,
#: ``reported`` ones from the latest quarter Vietcap publishes.
FIELDS: Mapping[str, tuple[str, str, str]] = {
    "price": ("giá", "đồng", "market"),
    "change_pct": ("thay đổi", "%", "market"),
    "volume": ("khối lượng", "cổ phiếu", "market"),
    "value_bn": ("giá trị giao dịch", "tỷ đồng", "market"),
    "foreign_net": ("khối ngoại mua ròng", "cổ phiếu", "market"),
    "pb": ("P/B", "lần", "reported"),
    "pe": ("P/E", "lần", "reported"),
    "roe": ("ROE 4 quý gần nhất", "%", "reported"),
    "npl": ("Tỷ lệ nợ xấu (NPL)", "%", "reported"),
}

#: How each reported field is named by the source that supplies it.
_KBS_NAMES = {
    "pb": ("(P/B)", "P/B"),
    "pe": ("(P/E)", "P/E"),
    "roe": ("ROE bình quân 4 quý gần nhất", "ROE Trailling"),
}
_VCI_NAMES = {"npl": ("Tỷ lệ nợ xấu (NPL)",)}

OPERATORS: Mapping[str, Callable[[float, float], bool]] = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}


@dataclass(frozen=True)
class Reported:
    label: str
    ended: date
    values: Mapping[str, float]


def _vn(value: float, unit: str) -> str:
    whole = float(value).is_integer() and abs(value) >= 1000
    text = f"{value:,.0f}" if whole else f"{value:,.2f}"
    text = text.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{text}%" if unit == "%" else f"{text} {unit}"


def _signed(value: float, unit: str) -> str:
    sign = "+" if value > 0 else ("-" if value < 0 else "")
    return sign + _vn(abs(value), unit)


def board_rows(frame_records: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """KB's price board as market fields per ticker, with the session date."""
    rows: dict[str, dict[str, Any]] = {}
    for record in frame_records:
        symbol = str(record.get("symbol") or "").upper()
        try:
            close = float(record.get("close_price"))
        except (TypeError, ValueError):
            continue
        if not symbol or close <= 0:
            continue
        stamp = record.get("time")
        try:
            session = datetime.fromtimestamp(float(stamp) / 1000, tz=ICT).date()
        except (TypeError, ValueError, OSError):
            session = None
        buy, sell = record.get("foreign_buy_volume"), record.get("foreign_sell_volume")
        rows[symbol] = {
            "session": session,
            "price": close,
            "change_pct": round(float(record.get("percent_change") or 0), 2),
            "volume": float(record.get("volume_accumulated") or 0),
            "value_bn": round(float(record.get("total_value") or 0) / 1e9, 2),
            "foreign_net": float(buy or 0) - float(sell or 0),
        }
    return rows


class ScreenerTools:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        ratios: Any | None = None,
        quality: Any | None = None,
        board: Callable[[list[str]], list[dict[str, Any]]] | None = None,
        listing: Callable[[str], list[str]] | None = None,
    ) -> None:
        self._settings_override = settings
        # Both read with no wait: the screen fills what quota there is now.
        keep = vnstock_provider.BACKGROUND_KEEP_FREE
        self._ratios = ratios or KbsFinancials(max_wait=0.0, keep_free=keep)
        self._quality = quality or VciFinancials(max_wait=0.0, keep_free=keep)
        self._board = board or _read_board
        self._listing = listing or _read_listing
        self._reported = TtlCache(FUNDAMENTALS_TTL_SECONDS)
        self._universes = TtlCache(LISTING_TTL_SECONDS)

    def available(self) -> bool:
        settings = self._settings_override or get_settings()
        return settings.deployment_profile == INTERNAL_PROFILE and settings.market_data_enabled

    def entries(self) -> tuple[ToolEntry, ...]:
        return (
            ToolEntry(
                name=TOOL_NAME,
                toolset=TOOLSET,
                description=(
                    "Filter and rank listed Vietnamese tickers. Give a universe — an index "
                    "group (VN30, VN100, HNX30, VNFIN…), an industry name in Vietnamese "
                    "(e.g. Ngân hàng), or an explicit ticker list, optionally narrowed by "
                    "industry (VN30 + Ngân hàng) — then filters and an "
                    "optional sort over: price, change_pct, volume, value_bn, foreign_net "
                    "(latest session) and pb, pe, roe, npl (latest reported quarter). Use "
                    "it for any 'which stocks…' question instead of listing from memory. "
                    "Tickers the tool could not read reported figures for yet are named "
                    "as not covered; say so rather than ranking them."
                ),
                schema=object_schema(
                    {
                        "universe": {"type": "string", "description": "Index group or industry name."},
                        "industry": {
                            "type": "string",
                            "description": "An ICB industry name to keep within the universe, e.g. Ngân hàng.",
                        },
                        "symbols": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_UNIVERSE},
                        "filters": {
                            "type": "array",
                            "maxItems": 6,
                            "items": object_schema(
                                {
                                    "field": {"type": "string", "enum": list(FIELDS)},
                                    "op": {"type": "string", "enum": list(OPERATORS)},
                                    "value": {"type": "number"},
                                },
                                ("field", "op", "value"),
                            ),
                        },
                        "sort_by": {"type": "string", "enum": list(FIELDS)},
                        "descending": {"type": "boolean"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": MAX_RESULTS},
                    },
                    (),
                ),
                handler=self.screen_stocks,
                display_name="Lọc cổ phiếu",
                summarise=lambda args: f"Lọc cổ phiếu · {args.get('universe') or ', '.join(args.get('symbols') or [])[:60]}",
                effect=ToolEffect.READ,
                idempotency=ToolIdempotency.IDEMPOTENT,
                access=ToolAccess.NETWORK,
                content_trust=ContentTrust.UNTRUSTED,
                concurrency=ToolConcurrency.SERIALIZED,
                permission=ToolPermission.ALLOW,
                is_async=False,
                timeout_seconds=20.0,
                contract_version="1",
                check_fn=self.available,
                max_result_size_chars=20_000,
            ),
        )

    def screen_stocks(self, context: ToolContext, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        if not self.available():
            raise MarketDataError(
                vnstock_provider.PROVIDER_UNAVAILABLE, "screening is not enabled on this deployment"
            )
        universe_name, symbols = self._universe(arguments)
        filters = self._filters(arguments.get("filters") or ())
        sort_by = arguments.get("sort_by")
        if sort_by is not None and sort_by not in FIELDS:
            raise MarketDataError(vnstock_provider.INVALID_REQUEST, f"sort_by must be one of {', '.join(FIELDS)}")
        limit = max(1, min(MAX_RESULTS, int(arguments.get("limit") or 10)))

        board: dict[str, dict[str, Any]] = {}
        for start in range(0, len(symbols), BOARD_CHUNK):
            chunk = symbols[start : start + BOARD_CHUNK]
            board.update(board_rows(self._board(chunk)))

        needed = {name for name, _, _ in filters} | ({sort_by} if sort_by else set())
        wanted = {name for name in needed if FIELDS[name][2] == "reported"}
        reported: dict[str, Reported] = {}
        uncovered: list[str] = []
        if wanted:
            reported = self._reported_within_budget(symbols, wanted)
            uncovered = [symbol for symbol in symbols if symbol not in reported]

        matched: list[tuple[str, dict[str, float]]] = []
        missing_market: list[str] = []
        for symbol in symbols:
            values: dict[str, float] = {}
            if symbol in board:
                values.update({k: v for k, v in board[symbol].items() if k != "session"})
            elif any(FIELDS[name][2] == "market" for name in needed):
                missing_market.append(symbol)
                continue
            if symbol in reported:
                values.update(reported[symbol].values)
            if any(name not in values for name in needed):
                continue
            if all(OPERATORS[op](values[name], value) for name, op, value in filters):
                matched.append((symbol, values))
        if sort_by:
            matched.sort(key=lambda item: item[1][sort_by], reverse=bool(arguments.get("descending", True)))
        matched = matched[:limit]

        now = (context.now or datetime.now(tz=ICT)).astimezone(ICT)
        lines = [f"Lọc cổ phiếu · {universe_name} · {len(symbols)} mã · mỗi dòng bắt đầu bằng ngày của số liệu"]
        condition = " và ".join(f"{FIELDS[name][0]} {op} {_vn(value, FIELDS[name][1])}" for name, op, value in filters)
        if condition:
            lines.append(f"Điều kiện: {condition}")
        market_lines: list[str] = []
        reported_lines: list[str] = []
        for symbol, _ in matched:
            if symbol in board:
                row = board[symbol]
                session = row["session"] or now.date()
                market_lines.append(
                    f"{session.isoformat()}: {symbol} · giá {_vn(row['price'], 'đồng')} · thay đổi "
                    f"{_signed(row['change_pct'], '%')} · khối lượng {_vn(row['volume'], 'cổ phiếu')} · "
                    f"giá trị {_vn(row['value_bn'], 'tỷ đồng')} · khối ngoại mua ròng {_signed(row['foreign_net'], 'cổ phiếu')}"
                )
            if symbol in reported:
                item = reported[symbol]
                figures = " · ".join(
                    f"{FIELDS[name][0]} {_vn(value, FIELDS[name][1])}" for name, value in item.values.items()
                )
                reported_lines.append(f"{item.ended.isoformat()}: {symbol} · {item.label} · {figures}")
        lines.extend(market_lines)
        lines.extend(reported_lines)
        if not matched:
            lines.append("Không có mã nào thỏa điều kiện trong số mã đã đọc được.")
        if uncovered:
            lines.append(
                "Chưa đọc được số liệu báo cáo (giới hạn lượt gọi nguồn, gọi lại sau khoảng một phút): "
                + ", ".join(uncovered)
            )
        if missing_market:
            lines.append("Bảng giá không có dữ liệu cho: " + ", ".join(missing_market))
        excerpt = "\n".join(lines)
        return {
            "universe": universe_name,
            "symbols": [symbol for symbol, _ in matched],
            "publisher": "KB Securities; Vietcap" if "npl" in wanted else "KB Securities",
            "source": "screener",
            "source_class": "store",
            "evidence_kind": "store_figure",
            "evidence_role": "market",
            "title": f"Lọc cổ phiếu · {universe_name}",
            "retrieved_at": now.isoformat(),
            "content_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
            "matched": len(matched),
            "not_covered": uncovered,
            "excerpt": excerpt,
            # Two sources for the figure check: sessions and quarters are dated
            # and held to "now" differently.
            "parts": [
                part
                for part in (
                    {
                        "excerpt": "\n".join(market_lines),
                        "evidence_role": "market",
                        "publisher": "KB Securities",
                        "title": f"Bảng giá · {universe_name}",
                    }
                    if market_lines
                    else None,
                    {
                        "excerpt": "\n".join(reported_lines),
                        "evidence_role": "statement",
                        "publisher": "KB Securities; Vietcap" if "npl" in wanted else "KB Securities",
                        "title": f"Chỉ số báo cáo · {universe_name}",
                    }
                    if reported_lines
                    else None,
                )
                if part is not None
            ],
        }

    # -- inputs -------------------------------------------------------------

    def _universe(self, arguments: Mapping[str, Any]) -> tuple[str, list[str]]:
        given = [str(item) for item in arguments.get("symbols") or () if str(item).strip()]
        if given:
            symbols = []
            for raw in given[:MAX_UNIVERSE]:
                try:
                    symbol = normalize_symbol(raw)
                except ValueError as exc:
                    raise MarketDataError(vnstock_provider.INVALID_REQUEST, str(exc)) from exc
                if not is_index(symbol) and symbol not in symbols:
                    symbols.append(symbol)
            return ", ".join(symbols), symbols
        name = str(arguments.get("universe") or "").strip()
        industry = str(arguments.get("industry") or "").strip()
        if not name and not industry:
            raise MarketDataError(vnstock_provider.INVALID_REQUEST, "give a universe or a list of symbols")
        members = self._members(name or industry)
        if name and industry:
            within = set(self._members(industry))
            members = [symbol for symbol in members if symbol in within]
            name = f"{name} · {industry}"
        if not members:
            raise MarketDataError(vnstock_provider.NO_DATA, f"no listed tickers found for {name or industry!r}")
        return name or industry, members[:MAX_UNIVERSE]

    def _members(self, name: str) -> list[str]:
        cached = self._universes.get(name.casefold())
        if cached is None:
            cached = [s for s in self._listing(name) if s and not is_index(s)]
            if cached:  # an empty answer is not remembered: it may be a bad moment
                self._universes.put(name.casefold(), cached)
        return list(cached)

    @staticmethod
    def _filters(raw: Sequence[Any]) -> list[tuple[str, str, float]]:
        filters = []
        for item in raw:
            if not isinstance(item, Mapping):
                continue
            name, op = str(item.get("field") or ""), str(item.get("op") or "")
            if name not in FIELDS or op not in OPERATORS:
                raise MarketDataError(vnstock_provider.INVALID_REQUEST, f"unknown filter {name} {op}")
            try:
                filters.append((name, op, float(item.get("value"))))
            except (TypeError, ValueError) as exc:
                raise MarketDataError(vnstock_provider.INVALID_REQUEST, f"filter {name} needs a number") from exc
        return filters

    def _reported_within_budget(self, symbols: Sequence[str], wanted: set[str]) -> dict[str, Reported]:
        """Reported fields per ticker: cache first, then parallel reads for a bounded time."""
        found: dict[str, Reported] = {}
        missing: list[str] = []
        for symbol in symbols:
            hit = self._reported.get(symbol)
            if hit is not None and wanted <= set(hit.values):
                found[symbol] = hit
            else:
                missing.append(symbol)
        if not missing:
            return found
        pool = ThreadPoolExecutor(max_workers=FUNDAMENTAL_WORKERS, thread_name_prefix="screen")
        futures = {pool.submit(self._read_reported, symbol, wanted): symbol for symbol in missing}
        try:
            for future in as_completed(futures, timeout=FUNDAMENTALS_BUDGET_SECONDS):
                result = future.result()
                if result is not None:
                    found[futures[future]] = result
        except FuturesTimeout:
            pass
        finally:
            # Reads still running finish into the cache; nothing waits for them.
            pool.shutdown(wait=False, cancel_futures=True)
        return found

    def _read_reported(self, symbol: str, wanted: set[str]) -> Reported | None:
        values: dict[str, float] = {}
        label, ended = "", None
        for source, names in ((self._ratios, _KBS_NAMES), (self._quality, _VCI_NAMES)):
            if not wanted & set(names):
                continue
            try:
                statement = source.ratios(symbol, quarterly=True, periods=1)
            except MarketDataError:
                return None
            if not statement.periods:
                return None
            period = statement.periods[0]
            label, ended = period.label.lower(), max(ended or period.ended, period.ended)
            for key, spellings in names.items():
                for figure in period.figures:
                    if any(figure.name == s or figure.name.endswith(s) for s in spellings):
                        values[key] = figure.value
                        break
        if ended is None or not wanted <= set(values):
            return None
        result = Reported(label=label, ended=ended, values=values)
        self._reported.put(symbol, result)
        return result


def _read_board(symbols: list[str]) -> list[dict[str, Any]]:
    import_vnstock()

    def read() -> list[dict[str, Any]]:
        trading = importlib.import_module("vnstock.explorer.kbs.trading").Trading()
        return trading.price_board(symbols).to_dict(orient="records")

    return vnstock_provider.call(read, symbol=",".join(symbols[:3]))


_GROUP_CODE = re.compile(r"^[A-Z][A-Z0-9]{1,11}$")


def _read_listing(name: str) -> list[str]:
    """An index group's members (``VN30``), or an industry's (``Ngân hàng``).

    KB's listing, not Vietcap's: Vietcap serves it from the trading host that
    timed out repeatedly on 2026-09-26. A name written like a code is a group;
    anything else is matched against KB's industry names with diacritics folded
    on both sides — the listing and a typed name do not reliably share one
    Unicode form.
    """
    import_vnstock()
    code = name.upper().replace(" ", "")

    def read() -> list[str]:
        listing = importlib.import_module("vnstock.explorer.kbs.listing").Listing()
        if _GROUP_CODE.match(code):
            return [str(item).upper() for item in list(listing.symbols_by_group(code))]
        frame = listing.symbols_by_industries()
        wanted = fold(name).strip()
        names = frame["industry_name"].astype(str).map(fold)
        found = frame[names.str.contains(wanted, regex=False)]["symbol"].astype(str).str.upper()
        return list(dict.fromkeys(found.tolist()))

    return vnstock_provider.call(read, symbol=name)


def register_screener_tools(*, settings: Settings | None = None) -> tuple[ToolEntry, ...]:
    return tuple(register(entry) for entry in ScreenerTools(settings=settings).entries())


__all__ = ["FIELDS", "ScreenerTools", "TOOL_NAME", "board_rows", "register_screener_tools"]
