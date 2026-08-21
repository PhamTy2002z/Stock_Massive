"""The six store-backed data tools introduced by A5 tickets #73 and #75."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.alpha.models import Analysis, WatchlistEntry
from src.core.database import sync_session_factory
from src.core.redis import get_redis
from src.stocks.models import ListingRoster, ProviderSnapshot
from src.stocks.providers import Capability, SnapshotStore, main_source
from src.stocks.signals import (
    ADTV_MONEY,
    FOREIGN_ROOM_PCT,
    registered_field,
    serve_field,
)
from src.stocks.signals.fundamentals import FUNDAMENTAL_STALE_DAYS
from src.stocks.shared import validate_symbol
from src.stocks.universe import Universe, build_universe

from .catalog import MAX_TOOL_RESULT_BYTES, ToolCatalog, ToolContext, ToolSpec, serialized_size
from .fields import REGISTERED_FIELD_VALUES_KEY, sanctioned_interpretation
from .scope import adtv_by_symbol, structured_universe_refusal

DATA_REFERENCE_TTL_SECONDS = 24 * 60 * 60
PRICE_SAMPLE_POINTS = 12

#: Every statement figure a FundamentalSnapshot can hold, in the order the
#: model reads them. The tool serves the stored value under the stored name —
#: no figure here is computed at serving time.
FUNDAMENTAL_FIGURES = (
    "revenue_vnd",
    "gross_profit_vnd",
    "operating_profit_vnd",
    "pre_tax_profit_vnd",
    "net_profit_after_tax_vnd",
    "parent_net_profit_vnd",
    "trailing_12_month_net_income_vnd",
    "parent_equity_vnd",
    "total_assets_vnd",
    "total_liabilities_vnd",
    "short_term_borrowings_vnd",
    "long_term_borrowings_vnd",
    "cash_and_equivalents_vnd",
    "cfo_vnd",
    "cfi_vnd",
    "cff_vnd",
)

SessionFactory = Callable[[], Session]
UniverseFactory = Callable[[Session], Universe]


#: The stored Analysis key `get_analysis` does not serve.
#:
#: The envelope is 86% of a real payload — ~15.4 KB of a ~17.9 KB row, against
#: a catalog budget of 4 KB — so a tool that returned it returned nothing at
#: all: `ToolResultTooLarge` every single time, and the loop never saw the
#: Analysis it was being asked about. Withholding it is what makes the tool
#: answer.
#:
#: Nothing is lost that the loop cannot get. `evidence` is every figure the
#: model was shown, and the figures are what the registered-field tools serve
#: directly and citably; what only this row holds is the *judgment* made from
#: them, which is served whole. `citedFieldIds` still names every field that
#: judgment rests on, so a reader can go and fetch any of them.
EVIDENCE_KEY = "evidence"

EVIDENCE_WITHHELD = (
    "evidence: the Analysis's evidence envelope is not served here because it "
    "does not fit the tool result budget. Read any figure it held with the "
    "field tools; citedFieldIds names the ones this judgment rests on."
)


def _object_schema(properties: Mapping[str, Any], required: Sequence[str] = ()) -> dict:
    return {
        "type": "object",
        "properties": dict(properties),
        "required": list(required),
        "additionalProperties": False,
    }


def availability(present: bool) -> dict[str, Any]:
    """Say whether a fixed slice could be rebuilt, in one shape.

    Shared by every replay path (``docs/adr/0012``) so that a caller branches on
    one key rather than on four different emptinesses — no rows, no value, no
    symbols, no window. The reason is stable and branchable; the surface writes
    the sentence.
    """
    return {
        "available": present,
        "unavailable_reason": None if present else "slice_unavailable",
    }


class StoreBackedTools:
    """Tool callables that own one short-lived store read apiece."""

    def __init__(
        self,
        *,
        session_factory: SessionFactory = sync_session_factory,
        redis: Any | None = None,
        universe_factory: UniverseFactory = build_universe,
    ) -> None:
        self._session_factory = session_factory
        self._redis = get_redis() if redis is None else redis
        self._universe_factory = universe_factory

    def catalog(self, *, trace_writer) -> ToolCatalog:
        return ToolCatalog(self.registrations(), trace_writer=trace_writer)

    def registrations(self) -> tuple[ToolSpec, ...]:
        symbol = {"type": "string", "description": "Vietnamese equity symbol."}
        return (
            ToolSpec(
                name="get_analysis",
                description=(
                    "Read the stored nightly Analysis for a symbol — its verdict, "
                    "thesis, per-axis readings and cited field ids — either at one "
                    "Trading Day or at the latest stored Trading Day. The evidence "
                    "envelope behind it is not included; read those figures with "
                    "the field tools."
                ),
                parameters=_object_schema(
                    {
                        "symbol": symbol,
                        "date": {"type": "string", "format": "date"},
                    },
                    ("symbol",),
                ),
                callable=self.get_analysis,
                # What this serves is a judgment, already reduced to fit once
                # (``EVIDENCE_WITHHELD``). Clipping prose leaves a sentence that
                # looks finished, which is the one shape a preview must not have.
                result_budget_bytes=MAX_TOOL_RESULT_BYTES,
            ),
            ToolSpec(
                name="get_price_series",
                description=(
                    "Summarize stored daily OHLCV without returning a raw series; "
                    "includes a fixed-date Data Reference for visualization."
                ),
                parameters=_object_schema(
                    {
                        "symbol": symbol,
                        "window_days": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 3650,
                        },
                    },
                    ("symbol", "window_days"),
                ),
                callable=self.get_price_series,
                registered_fields=(ADTV_MONEY.name,),
            ),
            ToolSpec(
                name="get_financials",
                description=(
                    "Read stored quarterly financial statements — revenue, profits, "
                    "balance-sheet totals, borrowings and net cash flows — grouped "
                    "per reporting period, each period stamped with its reporting "
                    "date, age and staleness. A figure absent from one period was "
                    "not reported for that period; a figure named in `unavailable` "
                    "is held for no stored period."
                ),
                parameters=_object_schema(
                    {
                        "symbol": symbol,
                        "periods": {"type": "integer", "minimum": 1, "maximum": 12},
                    },
                    ("symbol",),
                ),
                callable=self.get_financials,
                # The periods list *is* the answer — the flagged question this
                # tool was widened for asks for eight quarters — and it is also
                # what a quarterly-financials Widget binds to. Previewing it
                # would answer with three quarters and draw three.
                result_budget_bytes=MAX_TOOL_RESULT_BYTES,
            ),
            ToolSpec(
                name="get_company_profile",
                description=(
                    "Read stored company, ICB industry, share count and foreign-room "
                    "facts with their as-of dates."
                ),
                parameters=_object_schema({"symbol": symbol}, ("symbol",)),
                callable=self.get_company_profile,
                registered_fields=(FOREIGN_ROOM_PCT.name,),
            ),
            ToolSpec(
                name="screen_universe",
                description=(
                    "Filter and rank Universe symbols using stored market, valuation "
                    "and fundamental figures only."
                ),
                parameters=_object_schema(
                    {
                        "criteria": {
                            "type": "object",
                            "properties": {
                                "min_market_cap_vnd": {"type": "number"},
                                "min_adtv_vnd": {"type": "number"},
                                "max_provider_pe": {"type": "number"},
                                "max_provider_pb": {"type": "number"},
                                "min_ttm_net_income_vnd": {"type": "number"},
                            },
                            "additionalProperties": False,
                        },
                        "sort_by": {
                            "type": "string",
                            "enum": [
                                "market_cap_vnd",
                                "adtv_vnd",
                                "provider_pe",
                                "provider_pb",
                                "ttm_net_income_vnd",
                            ],
                        },
                        "order": {"type": "string", "enum": ["asc", "desc"]},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    }
                ),
                callable=self.screen_universe,
                # A screen is asked for its tail as much as its head. The top
                # three rows of a ranking answer a question nobody asked.
                result_budget_bytes=MAX_TOOL_RESULT_BYTES,
            ),
            ToolSpec(
                name="get_watchlist",
                description="Read the caller's Watchlist from the injected Tool Context.",
                parameters=_object_schema({}),
                callable=self.get_watchlist,
            ),
        )

    async def get_watchlist(
        self, context: ToolContext, _arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await asyncio.to_thread(self._get_watchlist, context.user_id)

    def _get_watchlist(self, user_id: int) -> Mapping[str, Any]:
        with self._session_factory() as session:
            rows = session.execute(
                select(WatchlistEntry)
                .where(WatchlistEntry.user_id == user_id)
                .order_by(WatchlistEntry.added_at.asc(), WatchlistEntry.id.asc())
            ).scalars()
            symbols = [row.symbol for row in rows]
            return {"symbols": symbols, "count": len(symbols)}

    async def get_analysis(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await asyncio.to_thread(self._get_analysis, context, dict(arguments))

    def _get_analysis(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        symbol = validate_symbol(str(arguments["symbol"]))
        requested = date.fromisoformat(str(arguments["date"])) if arguments.get("date") else None
        with self._session_factory() as session:
            refusal = self._refusal(session, symbol, context.trading_day)
            if refusal is not None:
                return refusal
            query = select(Analysis).where(Analysis.symbol == symbol)
            if requested is not None:
                query = query.where(Analysis.trading_day == requested)
            else:
                query = query.order_by(Analysis.trading_day.desc()).limit(1)
            row = session.execute(query).scalar_one_or_none()
            if row is None:
                return {
                    "analysis": None,
                    "message": (
                        f"No Analysis is stored for {symbol}"
                        + (f" on {requested.isoformat()}" if requested else "")
                        + "."
                    ),
                }
            payload = dict(row.payload)
            withheld = payload.pop(EVIDENCE_KEY, None) is not None
            return {
                # An Analysis is dated to the session it was produced for, and
                # that date belongs at the top for the same reason it does on
                # the price series: a citation into `analysis.payload` finds no
                # stamp of its own, and an undatable citation is refused.
                "as_of": row.trading_day.isoformat(),
                "analysis": {
                    "symbol": row.symbol,
                    "trading_day": row.trading_day.isoformat(),
                    "verdict": row.verdict,
                    "payload": payload,
                    "schema_version": row.schema_version,
                },
                # Said out loud rather than left as an absence, so a reader of
                # the trace can tell a withheld envelope from an Analysis that
                # never had one.
                **({"withheld": EVIDENCE_WITHHELD} if withheld else {}),
            }

    async def get_price_series(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await asyncio.to_thread(self._get_price_series, context, dict(arguments))

    def _get_price_series(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        symbol = validate_symbol(str(arguments["symbol"]))
        window_days = int(arguments["window_days"])
        if not 1 <= window_days <= 3650:
            raise ValueError("window_days must be between 1 and 3650")
        start = context.trading_day - timedelta(days=window_days - 1)
        with self._session_factory() as session:
            refusal = self._refusal(session, symbol, context.trading_day)
            if refusal is not None:
                return refusal
            series = SnapshotStore(session, redis=None).series(
                Capability.MARKET,
                symbol,
                start=start,
                end=context.trading_day,
            )
            rows = self._price_rows(series.snapshots)
            adtv = serve_field(
                session,
                symbol,
                ADTV_MONEY,
                end=context.trading_day,
                peers=self._universe_factory(session).symbols,
            )

        closes = [row["close_price"] for row in rows if row["close_price"] is not None]
        first_close = closes[0] if closes else None
        last_close = closes[-1] if closes else None
        change_pct = (
            ((last_close / first_close) - 1) * 100
            if first_close not in (None, 0) and last_close is not None
            else None
        )
        sample = [
            {"date": row["date"], "close_price": row["close_price"]}
            for row in self._decimated(rows)
        ]
        descriptor = self._data_reference(symbol, start, context.trading_day)
        self._cache_data_reference(descriptor, rows)
        return {
            "symbol": symbol,
            # The session every figure below stopped being current at, and the
            # reason it is a top-level key rather than something a reader infers
            # from `summary.end`: the Recommendation Validator stamps a stored
            # citation from `as_of` and refuses one it cannot date
            # (`grounding.py`, `missing_as_of`). Without it every figure in
            # `summary` — the last close, the change, the range — is a figure the
            # model may narrate and the Gate will then block, which ends the
            # Turn rather than the sentence. `screen_universe` has carried the
            # same key since it shipped; this tool was the one that did not.
            "as_of": rows[-1]["date"] if rows else None,
            "summary": {
                "sessions": len(rows),
                "start": rows[0]["date"] if rows else None,
                "end": rows[-1]["date"] if rows else None,
                "first_close_vnd": first_close,
                "last_close_vnd": last_close,
                "change_pct": change_pct,
                "lowest_vnd": min(
                    (row["low_price"] for row in rows if row["low_price"] is not None),
                    default=None,
                ),
                "highest_vnd": max(
                    (row["high_price"] for row in rows if row["high_price"] is not None),
                    default=None,
                ),
                "total_volume": sum(row["volume"] or 0 for row in rows),
                "average_daily_value_vnd": (
                    sum(row["total_value_vnd"] or 0 for row in rows) / len(rows)
                    if rows
                    else None
                ),
            },
            "sample": sample,
            "data_ref": descriptor,
            REGISTERED_FIELD_VALUES_KEY: {ADTV_MONEY.name: adtv},
        }

    async def resolve_data_ref(self, reference: Mapping[str, Any]) -> Mapping[str, Any]:
        return await asyncio.to_thread(self._resolve_data_ref, dict(reference))

    def _resolve_data_ref(self, reference: Mapping[str, Any]) -> Mapping[str, Any]:
        """The fixed slice a Data Reference names, from Redis or from the store.

        The 24-hour Redis entry is a hot cache and nothing more. Past it the
        same window is rebuilt from the store, which is sound because EOD data
        is settled — the reconstruction is that window, never today's.

        A window that no longer reconstructs answers ``available: False`` rather
        than an empty series (``docs/adr/0012``): an empty chart and a chart of
        nothing look identical to a reader and mean different things.
        """
        descriptor = {
            "symbol": validate_symbol(str(reference["symbol"])),
            "start": date.fromisoformat(str(reference["start"])).isoformat(),
            "end": date.fromisoformat(str(reference["end"])).isoformat(),
            "field": str(reference["field"]),
        }
        expected = self._reference_id(descriptor)
        if reference.get("id") != expected or descriptor["field"] != "ohlcv":
            raise ValueError("invalid Data Reference")
        cached = self._redis_get(self._reference_key(expected))
        if cached is not None:
            return json.loads(cached)
        with self._session_factory() as session:
            series = SnapshotStore(session, redis=None).series(
                Capability.MARKET,
                descriptor["symbol"],
                start=date.fromisoformat(descriptor["start"]),
                end=date.fromisoformat(descriptor["end"]),
            )
            rows = self._price_rows(series.snapshots)
        payload = {**descriptor, "series": rows, **availability(bool(rows))}
        self._redis_set(self._reference_key(expected), payload)
        return payload

    async def replay_screen(
        self,
        *,
        criteria: Mapping[str, Any],
        sort_by: str,
        order: str,
        limit: int,
        as_of: date,
    ) -> Mapping[str, Any]:
        """Re-run one screen at the day it was originally run.

        The seam a Widget descriptor replays through (``docs/adr/0012``). A
        stored ranking would put a copy of the Universe in every message that
        ever ordered it; the *question* is small, and against a settled store it
        answers the same way.
        """
        return await asyncio.to_thread(
            self._screen_universe,
            as_of,
            {
                "criteria": dict(criteria),
                "sort_by": sort_by,
                "order": order,
                "limit": limit,
            },
        )

    async def replay_field(
        self,
        *,
        symbols: Sequence[str],
        field_name: str,
        as_of: date,
    ) -> Mapping[str, Any]:
        """Recompute one registered field for several symbols, at a fixed day.

        The other half of Widget replay. A stored Widget keeps the field, the
        symbols and the day; this turns that back into values, and it computes
        them the same way the tool layer did — through the Signal Registry, at
        the day the answer was dated to, never at today's.
        """
        return await asyncio.to_thread(
            self._replay_field, tuple(symbols), field_name, as_of
        )

    def _replay_field(
        self, symbols: Sequence[str], field_name: str, as_of: date
    ) -> Mapping[str, Any]:
        declared = registered_field(field_name)
        points: list[dict[str, Any]] = []
        with self._session_factory() as session:
            peers = self._universe_factory(session).symbols
            for symbol in symbols:
                answer = serve_field(
                    session,
                    validate_symbol(symbol),
                    declared,
                    end=as_of,
                    peers=peers,
                )
                points.append(
                    {
                        "symbol": validate_symbol(symbol),
                        "value": answer.value,
                        "details": dict(answer.extras),
                        "refusal": (
                            answer.refusal.value if answer.refusal is not None else None
                        ),
                    }
                )
        present = any(point["value"] is not None for point in points)
        return {
            "field": declared.name,
            "unit": declared.unit.value,
            "sign": declared.sign.value,
            "interpretation": sanctioned_interpretation(declared),
            "as_of": as_of.isoformat(),
            "points": points,
            **availability(present),
        }

    async def replay_financials(
        self,
        *,
        symbol: str,
        period_ends: Sequence[str],
        figures: Sequence[str],
        trading_day: date,
    ) -> Mapping[str, Any]:
        """Re-read the stored statement figures one Widget's table was drawn from.

        The Widget half of ``get_financials`` (``docs/adr/0012``). The periods are
        named rather than counted, so a reopened Thread shows the quarters the
        answer was written about even after two more have been filed — asking for
        "the last four" a year later is how a historical record turns into a fresh
        query wearing an old date.

        ``trading_day`` is the read boundary and it is not the same date as the
        newest period: a June filing is written to the store in August, so
        bounding the read at the period end would drop the row this exists to
        return.
        """
        return await asyncio.to_thread(
            self._replay_financials,
            validate_symbol(symbol),
            tuple(period_ends),
            tuple(figures),
            trading_day,
        )

    def _replay_financials(
        self,
        symbol: str,
        period_ends: Sequence[str],
        figures: Sequence[str],
        trading_day: date,
    ) -> Mapping[str, Any]:
        wanted = set(period_ends)
        with self._session_factory() as session:
            stored = SnapshotStore(session, redis=None).series(
                Capability.FUNDAMENTAL,
                symbol,
                end=trading_day,
            ).snapshots
        rows: list[dict[str, Any]] = []
        for snapshot in stored:
            period_end = snapshot.period_end
            if period_end.isoformat() not in wanted:
                continue
            age = max(0, (trading_day - period_end).days)
            rows.append(
                {
                    "period_end": period_end.isoformat(),
                    "stale": age > FUNDAMENTAL_STALE_DAYS,
                    # Only the columns the table draws, and only where the store
                    # holds them: an absent line item is a company that filed
                    # without one, which is a different fact from a zero.
                    "figures": {
                        name: getattr(snapshot, name)
                        for name in figures
                        if getattr(snapshot, name, None) is not None
                    },
                }
            )
        # Newest first, which is the order a reader compares quarters in and the
        # order the tool served them to the model.
        rows.sort(key=lambda row: row["period_end"], reverse=True)
        return {
            "symbol": symbol,
            "unit": "vnd",
            "figures": list(figures),
            "periods": rows,
            **availability(any(row["figures"] for row in rows)),
        }

    async def get_financials(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await asyncio.to_thread(self._get_financials, context, dict(arguments))

    def _get_financials(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        symbol = validate_symbol(str(arguments["symbol"]))
        periods = int(arguments.get("periods", 4))
        if not 1 <= periods <= 12:
            raise ValueError("periods must be between 1 and 12")
        with self._session_factory() as session:
            refusal = self._refusal(session, symbol, context.trading_day)
            if refusal is not None:
                return refusal
            stored = SnapshotStore(session, redis=None).series(
                Capability.FUNDAMENTAL,
                symbol,
                end=context.trading_day,
            ).snapshots
        output = []
        for snapshot in reversed(stored[-periods:]):
            period_end = snapshot.period_end
            age = max(0, (context.trading_day - period_end).days)
            figures = {
                name: getattr(snapshot, name)
                for name in FUNDAMENTAL_FIGURES
                if getattr(snapshot, name) is not None
            }
            output.append(
                {
                    "period_end": period_end.isoformat(),
                    "age_days": age,
                    "stale": age > FUNDAMENTAL_STALE_DAYS,
                    "figures": figures,
                }
            )
        # A figure held for no stored period is named once here rather than
        # absent from every period silently — absence per period is ordinary
        # (a company can file without a cash flow statement), absence across
        # all of them is what the model must report as unavailable.
        unavailable = [
            name
            for name in FUNDAMENTAL_FIGURES
            if all(name not in item["figures"] for item in output)
        ]
        result = {
            "symbol": symbol,
            "periods": output,
            "unavailable": unavailable,
        }
        # Old periods are dropped before the catalog's byte cap refuses the
        # whole answer: four rich quarters beat an error, and the model is
        # told the window was shortened rather than left to read it as the
        # store's full depth.
        while output and serialized_size(result) > MAX_TOOL_RESULT_BYTES:
            output.pop()
            result["periods_truncated_to_fit"] = True
        return result

    async def get_company_profile(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await asyncio.to_thread(self._get_company_profile, context, dict(arguments))

    def _get_company_profile(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        symbol = validate_symbol(str(arguments["symbol"]))
        with self._session_factory() as session:
            refusal = self._refusal(session, symbol, context.trading_day)
            if refusal is not None:
                return refusal
            roster = session.execute(
                select(ListingRoster).where(ListingRoster.symbol == symbol)
            ).scalar_one_or_none()
            reference = SnapshotStore(session, redis=None).series(
                Capability.REFERENCE,
                symbol,
                end=context.trading_day,
                now=datetime.combine(context.trading_day, time.max, tzinfo=timezone.utc),
            )
            snapshot = reference.snapshots[-1] if reference.snapshots else None
            foreign_room = serve_field(
                session,
                symbol,
                FOREIGN_ROOM_PCT,
                end=context.trading_day,
                peers=self._universe_factory(session).symbols,
            )

        listing_as_of = roster.observed_at.date().isoformat() if roster is not None else None
        profile: dict[str, Any] = {
            "symbol": symbol,
            "company_name": roster.company_name if roster is not None else None,
            "exchange": roster.exchange if roster is not None else None,
            "listing_as_of": listing_as_of,
            "industry": {
                "code": roster.icb_code if roster is not None else None,
                "name": roster.icb_name if roster is not None else None,
                "as_of": listing_as_of,
                "available": bool(roster is not None and roster.icb_code),
            },
            "shares": [],
            "foreign_room": None,
            "unavailable": ["ownership_breakdown"],
            REGISTERED_FIELD_VALUES_KEY: {
                FOREIGN_ROOM_PCT.name: foreign_room
            },
        }
        if roster is None:
            profile["unavailable"].extend(
                ["company_name", "exchange", "industry"]
            )
        elif roster.icb_code is None:
            profile["unavailable"].append("industry")
        if snapshot is None:
            profile["unavailable"].extend(["share_counts", "foreign_room"])
            return profile
        as_of = snapshot.metadata.effective_at.date()
        age = max(0, (context.trading_day - as_of).days)
        profile["shares"] = [
            {
                "type": item.share_type.value,
                **self._stamped(item.value, as_of, age, reference.stale),
            }
            for item in snapshot.shares
        ]
        profile["foreign_room"] = {
            "current_shares": self._stamped(
                snapshot.current_foreign_room, as_of, age, reference.stale
            ),
            "total_shares": self._stamped(
                snapshot.total_foreign_room, as_of, age, reference.stale
            ),
        }
        if not snapshot.shares:
            profile["unavailable"].append("share_counts")
        if snapshot.current_foreign_room is None:
            profile["unavailable"].append("foreign_room.current_shares")
        if snapshot.total_foreign_room is None:
            profile["unavailable"].append("foreign_room.total_shares")
        return profile

    async def screen_universe(
        self, context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return await asyncio.to_thread(
            self._screen_universe, context.trading_day, dict(arguments)
        )

    def _screen_universe(
        self, trading_day: date, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Rank the Universe as it stood at the end of one Trading Day.

        Takes the day rather than the whole Tool Context because the day is the
        only thing it reads: a screen is the same ranking for every caller, so
        the replay path (``docs/adr/0012``) has no user to supply and should not
        have to invent one.
        """
        criteria = dict(arguments.get("criteria") or {})
        sort_by = str(arguments.get("sort_by", "adtv_vnd"))
        order = str(arguments.get("order", "desc"))
        limit = int(arguments.get("limit", 20))
        allowed = {
            "market_cap_vnd",
            "adtv_vnd",
            "provider_pe",
            "provider_pb",
            "ttm_net_income_vnd",
        }
        if sort_by not in allowed or order not in {"asc", "desc"} or not 1 <= limit <= 50:
            raise ValueError("invalid screen ordering or limit")
        with self._session_factory() as session:
            symbols = self._universe_factory(session).symbols
            market = self._latest_payloads(session, Capability.MARKET, symbols, trading_day)
            valuation = self._latest_payloads(
                session, Capability.VALUATION, symbols, trading_day
            )
            fundamental = self._latest_payloads(
                session, Capability.FUNDAMENTAL, symbols, trading_day
            )
            adtv = self._adtv(session, symbols, trading_day)
        rows = [
            {
                "symbol": symbol,
                "market_cap_vnd": market.get(symbol, {}).get("market_cap_vnd"),
                "adtv_vnd": adtv.get(symbol),
                "provider_pe": valuation.get(symbol, {}).get("provider_pe"),
                "provider_pb": valuation.get(symbol, {}).get("provider_pb"),
                "ttm_net_income_vnd": fundamental.get(symbol, {}).get(
                    "trailing_12_month_net_income_vnd"
                ),
            }
            for symbol in symbols
        ]
        rows = [row for row in rows if self._matches(row, criteria)]
        reverse = order == "desc"
        present = [row for row in rows if row[sort_by] is not None]
        missing = [row for row in rows if row[sort_by] is None]
        present.sort(key=lambda row: (row[sort_by], row["symbol"]), reverse=reverse)
        missing.sort(key=lambda row: row["symbol"])
        ranked = present + missing
        response: dict[str, Any] = {
            "matched_count": len(ranked),
            "returned_count": 0,
            "truncated": bool(ranked),
            "sort_by": sort_by,
            "order": order,
            # The day the ranking is *of*. A screen answered without one cannot
            # be cited, and cannot be replayed to the same slice a year later —
            # which is what ``docs/adr/0012`` asks a stored Widget descriptor to
            # do. Set before the budget loop below so its bytes are charged.
            "as_of": trading_day.isoformat(),
            "symbols": [],
        }
        for row in ranked[:limit]:
            candidate = {**response, "symbols": [*response["symbols"], row]}
            candidate["returned_count"] = len(candidate["symbols"])
            candidate["truncated"] = candidate["returned_count"] < len(ranked)
            if serialized_size(candidate) > MAX_TOOL_RESULT_BYTES:
                break
            response = candidate
        return response

    def _refusal(
        self, session: Session, symbol: str, trading_day: date
    ) -> Mapping[str, Any] | None:
        return structured_universe_refusal(
            session,
            self._universe_factory,
            symbol,
            trading_day,
        )

    @staticmethod
    def _latest_payloads(
        session: Session,
        capability: Capability,
        symbols: Sequence[str],
        end: date,
    ) -> dict[str, Mapping[str, Any]]:
        if not symbols:
            return {}
        cutoff = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc)
        rows = session.execute(
            select(ProviderSnapshot)
            .where(
                ProviderSnapshot.capability == capability.value,
                ProviderSnapshot.source == main_source(capability).value,
                ProviderSnapshot.symbol.in_(symbols),
                ProviderSnapshot.effective_at < cutoff,
            )
            .distinct(ProviderSnapshot.symbol)
            .order_by(
                ProviderSnapshot.symbol,
                ProviderSnapshot.effective_at.desc(),
                ProviderSnapshot.observed_at.desc(),
            )
        ).scalars()
        return {row.symbol: dict(row.payload) for row in rows}

    @staticmethod
    def _adtv(
        session: Session, symbols: Sequence[str], end: date | None
    ) -> dict[str, float]:
        return adtv_by_symbol(session, symbols, end)

    @staticmethod
    def _matches(row: Mapping[str, Any], criteria: Mapping[str, Any]) -> bool:
        checks = {
            "min_market_cap_vnd": ("market_cap_vnd", lambda actual, wanted: actual >= wanted),
            "min_adtv_vnd": ("adtv_vnd", lambda actual, wanted: actual >= wanted),
            "max_provider_pe": ("provider_pe", lambda actual, wanted: actual <= wanted),
            "max_provider_pb": ("provider_pb", lambda actual, wanted: actual <= wanted),
            "min_ttm_net_income_vnd": (
                "ttm_net_income_vnd",
                lambda actual, wanted: actual >= wanted,
            ),
        }
        unknown = set(criteria).difference(checks)
        if unknown:
            raise ValueError(f"unknown screen criteria: {', '.join(sorted(unknown))}")
        for name, wanted in criteria.items():
            field, comparison = checks[name]
            actual = row[field]
            if actual is None or not comparison(actual, wanted):
                return False
        return True

    @staticmethod
    def _stamped(value: Any, as_of: date, age_days: int, stale: bool) -> dict[str, Any]:
        return {
            "value": value,
            "as_of": as_of.isoformat(),
            "age_days": age_days,
            "stale": stale,
        }

    @staticmethod
    def _price_rows(snapshots: Sequence[Any]) -> list[dict[str, Any]]:
        return [
            {
                "date": snapshot.metadata.effective_at.date().isoformat(),
                "open_price": snapshot.open_price,
                "high_price": snapshot.high_price,
                "low_price": snapshot.low_price,
                "close_price": snapshot.last_price,
                "volume": snapshot.volume,
                "total_value_vnd": snapshot.total_value_vnd,
                "price_basis": snapshot.price_basis.value,
                "source": snapshot.metadata.source.value,
            }
            for snapshot in snapshots
        ]

    @staticmethod
    def _decimated(rows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        if len(rows) <= PRICE_SAMPLE_POINTS:
            return list(rows)
        positions = {
            round(index * (len(rows) - 1) / (PRICE_SAMPLE_POINTS - 1))
            for index in range(PRICE_SAMPLE_POINTS)
        }
        return [row for index, row in enumerate(rows) if index in positions]

    def _data_reference(self, symbol: str, start: date, end: date) -> dict[str, Any]:
        descriptor = {
            "symbol": symbol,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "field": "ohlcv",
        }
        return {"id": self._reference_id(descriptor), **descriptor}

    @staticmethod
    def _reference_id(descriptor: Mapping[str, Any]) -> str:
        encoded = json.dumps(descriptor, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()[:24]

    @staticmethod
    def _reference_key(reference_id: str) -> str:
        return f"alpha:data_ref:{reference_id}"

    def _cache_data_reference(
        self, reference: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]
    ) -> None:
        payload = {
            "symbol": reference["symbol"],
            "start": reference["start"],
            "end": reference["end"],
            "field": reference["field"],
            "series": list(rows),
            # The same shape the reconstruction produces, because the cache is a
            # copy of the store's answer rather than a second kind of answer: a
            # reader must not be able to tell a hit from a miss.
            **availability(bool(rows)),
        }
        self._redis_set(self._reference_key(str(reference["id"])), payload)

    def _redis_get(self, key: str) -> str | None:
        if self._redis is None:
            return None
        try:
            value = self._redis.get(key)
            if isinstance(value, bytes):
                return value.decode()
            return value
        except Exception:
            return None

    def _redis_set(self, key: str, payload: Mapping[str, Any]) -> None:
        if self._redis is None:
            return
        try:
            self._redis.set(
                key,
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                ex=DATA_REFERENCE_TTL_SECONDS,
            )
        except Exception:
            return
