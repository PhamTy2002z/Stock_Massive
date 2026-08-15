"""The six A5 data tools through the same catalog the model receives."""

from __future__ import annotations

import ast
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import delete

from src.agent.tools.data import StoreBackedTools
from src.alpha.models import Analysis, WatchlistEntry
from src.auth.models import User
from src.core.database import Base, get_sync_db, sync_engine, sync_session_factory
from src.stocks.models import ListingRoster, ProviderSnapshot
from src.stocks.providers import (
    Capability,
    FundamentalSnapshot,
    MarketSnapshot,
    PriceBasis,
    ProviderSource,
    ReferenceSnapshot,
    ShareCount,
    ShareType,
    SnapshotMetadata,
    SnapshotStore,
    ValuationSnapshot,
)
from src.stocks.universe import Universe

DAY = date(2026, 8, 14)
MEMBERS = ("U73A", "U73B", "U73C", "U73D")
OUTSIDE = "X73A"
ALL_SYMBOLS = (*MEMBERS, OUTSIDE)


class MemoryRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.expires: dict[str, datetime] = {}
        self.now = datetime(2026, 8, 15, tzinfo=timezone.utc)

    def get(self, key: str):
        if key in self.expires and self.expires[key] <= self.now:
            self.values.pop(key, None)
            self.expires.pop(key, None)
        return self.values.get(key)

    def set(self, key: str, value: str, ex: int | None = None):
        self.values[key] = value
        if ex is not None:
            self.expires[key] = self.now + timedelta(seconds=ex)
        return True

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


def metadata(day: date, source: ProviderSource, *, schema_version: int = 1):
    stamp = datetime.combine(day, time(15, 0), tzinfo=timezone.utc)
    return SnapshotMetadata(
        source=source,
        effective_at=stamp,
        observed_at=stamp,
        schema_version=schema_version,
    )


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture
def stored_world():
    email = f"tools-{uuid.uuid4().hex}@example.com"
    with get_sync_db() as session:
        user = User(email=email, hashed_password="x")
        session.add(user)
        session.flush()
        user_id = user.id
        session.add(WatchlistEntry(user_id=user_id, symbol=MEMBERS[0]))
        for index, symbol in enumerate(ALL_SYMBOLS):
            session.add(
                ListingRoster(
                    symbol=symbol,
                    exchange="HOSE",
                    is_listed=True,
                    company_name=f"Company {symbol}",
                    icb_code="10" if symbol != MEMBERS[3] else "20",
                    icb_name="Banks" if symbol != MEMBERS[3] else "Retail",
                    source="vnstock",
                    observed_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
                )
            )

        for offset in range(3):
            session_day = DAY - timedelta(days=2 - offset)
            SnapshotStore(session, redis=None).save(
                Capability.MARKET,
                MarketSnapshot(
                    symbol=MEMBERS[0],
                    metadata=metadata(
                        session_day, ProviderSource.FIINQUANT, schema_version=2
                    ),
                    price_basis=PriceBasis.RAW,
                    open_price=100 + offset,
                    high_price=105 + offset,
                    low_price=98 + offset,
                    last_price=102 + offset,
                    volume=1_000 + offset,
                    total_value_vnd=1_000_000 + offset,
                    market_cap_vnd=10_000_000_000,
                ),
            )
        # A historical Turn must not rank suggestions with a later session.
        SnapshotStore(session, redis=None).save(
            Capability.MARKET,
            MarketSnapshot(
                symbol=MEMBERS[0],
                metadata=metadata(
                    DAY + timedelta(days=1),
                    ProviderSource.FIINQUANT,
                    schema_version=2,
                ),
                price_basis=PriceBasis.RAW,
                last_price=110,
                total_value_vnd=9_000_000_000,
                market_cap_vnd=10_000_000_000,
            ),
        )
        for index, symbol in enumerate(MEMBERS[1:], start=2):
            SnapshotStore(session, redis=None).save(
                Capability.MARKET,
                MarketSnapshot(
                    symbol=symbol,
                    metadata=metadata(DAY, ProviderSource.FIINQUANT, schema_version=2),
                    price_basis=PriceBasis.RAW,
                    last_price=100,
                    total_value_vnd=index * 10_000_000,
                    market_cap_vnd=index * 100_000_000_000,
                ),
            )
        SnapshotStore(session, redis=None).save(
            Capability.VALUATION,
            ValuationSnapshot(
                symbol=MEMBERS[0],
                metadata=metadata(DAY, ProviderSource.FIINQUANT),
                provider_pe=12.5,
                provider_pb=1.8,
            ),
        )
        for period, profit in (
            (date(2026, 3, 31), 9_000_000_000),
            (date(2026, 6, 30), 12_000_000_000),
        ):
            SnapshotStore(session, redis=None).save(
                Capability.FUNDAMENTAL,
                FundamentalSnapshot(
                    symbol=MEMBERS[0],
                    metadata=metadata(period, ProviderSource.VNSTOCK),
                    period_end=period,
                    trailing_12_month_net_income_vnd=profit,
                    parent_equity_vnd=30_000_000_000,
                ),
            )
        SnapshotStore(session, redis=None).save(
            Capability.REFERENCE,
            ReferenceSnapshot(
                symbol=MEMBERS[0],
                metadata=metadata(date(2026, 8, 1), ProviderSource.VNSTOCK),
                shares=(ShareCount(share_type=ShareType.LISTED, value=1_000_000),),
                current_foreign_room=200_000,
                total_foreign_room=500_000,
            ),
        )
        SnapshotStore(session, redis=None).save(
            Capability.REFERENCE,
            ReferenceSnapshot(
                symbol=MEMBERS[1],
                metadata=metadata(date(2026, 8, 1), ProviderSource.VNSTOCK),
            ),
        )
        session.add_all(
            [
                Analysis(
                    symbol=MEMBERS[0],
                    trading_day=date(2026, 8, 13),
                    verdict="hold",
                    payload={"version": "old"},
                    schema_version=1,
                ),
                Analysis(
                    symbol=MEMBERS[0],
                    trading_day=DAY,
                    verdict="watch",
                    payload={"version": "new"},
                    schema_version=99,
                ),
            ]
        )

    redis = MemoryRedis()
    tools = StoreBackedTools(
        session_factory=sync_session_factory,
        redis=redis,
        universe_factory=lambda _session: Universe(explicit=MEMBERS),
    )
    yield user_id, tools, redis

    with get_sync_db() as session:
        session.execute(delete(Analysis).where(Analysis.symbol.in_(ALL_SYMBOLS)))
        session.execute(delete(WatchlistEntry).where(WatchlistEntry.user_id == user_id))
        session.execute(delete(ProviderSnapshot).where(ProviderSnapshot.symbol.in_(ALL_SYMBOLS)))
        session.execute(delete(ListingRoster).where(ListingRoster.symbol.in_(ALL_SYMBOLS)))
        session.execute(delete(User).where(User.id == user_id))


def context(user_id: int):
    from src.agent.tools import ToolContext

    return ToolContext(user_id=user_id, trading_day=DAY, active_symbol=MEMBERS[0])


@pytest.mark.asyncio
async def test_watchlist_identity_is_out_of_band_and_analysis_reads_old_versions(stored_world):
    user_id, tools, _ = stored_world
    catalog = tools.catalog(trace_writer=lambda _trace: None)

    watchlist = await catalog.dispatch("get_watchlist", {}, context(user_id))
    latest = await catalog.dispatch(
        "get_analysis", {"symbol": MEMBERS[0]}, context(user_id)
    )
    exact = await catalog.dispatch(
        "get_analysis",
        {"symbol": MEMBERS[0], "date": "2026-08-13"},
        context(user_id),
    )

    schema = next(item for item in catalog.tool_schemas if item.name == "get_watchlist")
    assert schema.parameters["properties"] == {}
    assert watchlist["symbols"] == [MEMBERS[0]]
    assert latest["analysis"]["schema_version"] == 99
    assert latest["analysis"]["payload"] == {"version": "new"}
    assert exact["analysis"]["payload"] == {"version": "old"}


@pytest.mark.asyncio
async def test_price_series_is_summarized_and_data_ref_reconstructs_after_ttl(stored_world):
    user_id, tools, redis = stored_world
    result = await tools.catalog(trace_writer=lambda _trace: None).dispatch(
        "get_price_series",
        {"symbol": MEMBERS[0], "window_days": 10},
        context(user_id),
    )

    assert result["summary"]["sessions"] == 3
    assert "liquidity_profile.adtv_vnd" in result["registered_fields"]
    assert all(set(point) == {"date", "close_price"} for point in result["sample"])
    first = await tools.resolve_data_ref(result["data_ref"])
    redis.advance(24 * 60 * 60 + 1)
    rebuilt = await tools.resolve_data_ref(result["data_ref"])
    assert rebuilt == first
    assert len(rebuilt["series"]) == 3
    assert set(rebuilt["series"][0]) > {"date", "close_price"}


@pytest.mark.asyncio
async def test_financials_and_profile_stamp_staleness_and_unavailable_fields(stored_world):
    user_id, tools, _ = stored_world
    catalog = tools.catalog(trace_writer=lambda _trace: None)

    financials = await catalog.dispatch(
        "get_financials", {"symbol": MEMBERS[0], "periods": 2}, context(user_id)
    )
    profile = await catalog.dispatch(
        "get_company_profile", {"symbol": MEMBERS[0]}, context(user_id)
    )
    missing_profile = await catalog.dispatch(
        "get_company_profile", {"symbol": MEMBERS[1]}, context(user_id)
    )

    assert financials["periods"][0]["trailing_12_month_net_income_vnd"]["as_of"]
    assert financials["periods"][0]["trailing_12_month_net_income_vnd"]["age_days"]
    assert "income_statement_line_items" in financials["unavailable"]
    assert profile["industry"]["code"] == "10"
    assert "company_profile.foreign_room_pct" in profile["registered_fields"]
    assert profile["foreign_room"]["current_shares"]["as_of"] == "2026-08-01"
    assert "ownership_breakdown" in profile["unavailable"]
    assert "share_counts" in missing_profile["unavailable"]
    assert "foreign_room.current_shares" in missing_profile["unavailable"]
    assert "foreign_room.total_shares" in missing_profile["unavailable"]


@pytest.mark.asyncio
async def test_universe_refusal_suggests_same_industry_by_descending_adtv(stored_world):
    user_id, tools, _ = stored_world

    refused = await tools.catalog(trace_writer=lambda _trace: None).dispatch(
        "get_company_profile", {"symbol": OUTSIDE}, context(user_id)
    )

    assert refused == {
        "reason": "not_in_universe",
        "suggestions": [MEMBERS[2], MEMBERS[1], MEMBERS[0]],
    }


@pytest.mark.asyncio
async def test_screen_ranks_stored_metrics_and_reports_truncation(stored_world):
    user_id, tools, _ = stored_world

    result = await tools.catalog(trace_writer=lambda _trace: None).dispatch(
        "screen_universe",
        {"criteria": {}, "sort_by": "market_cap_vnd", "order": "desc", "limit": 2},
        context(user_id),
    )

    assert result["matched_count"] == 4
    assert result["returned_count"] == 2
    assert result["truncated"] is True
    assert [row["symbol"] for row in result["symbols"]] == [MEMBERS[3], MEMBERS[2]]
    assert all("market_cap_vnd" in row for row in result["symbols"])


def test_tool_package_has_no_provider_or_legacy_live_read_path():
    package = Path(__file__).parents[1] / "src" / "agent" / "tools"
    forbidden_modules = {
        "src.core.vnstock_client",
        "src.core.vnstock_wrapper",
        "src.stocks.company.service",
        "src.stocks.financial.service",
        "src.stocks.providers.fiinquant",
        "src.stocks.providers.vnstock_provider",
    }

    imported: set[str] = set()
    # Ticket #76 adds the one named Provider Source exception. The proof still
    # applies unchanged to every other tool module; only search_news may import
    # the guarded vnstock boundary.
    for path in package.glob("*.py"):
        if path.name == "news.py":
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

    assert not imported.intersection(forbidden_modules)

    news_tree = ast.parse((package / "news.py").read_text(), filename="news.py")
    news_imports = {
        node.module
        for node in ast.walk(news_tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert news_imports.intersection(forbidden_modules) == {"src.core.vnstock_client"}
