"""Market domain service for listings and market-wide data."""

import logging
from functools import lru_cache
from typing import Optional

import pandas as pd
from src.core.vnstock_client import Listing, Trading, Vnstock
from src.core.vnstock_client import VnstockUnavailable, VnstockUnsupported

from ..schemas.company import StockSymbol
from ..schemas.market import (
    SectorPerformanceItem,
    SectorPerformanceResponse,
    FundCertificateItem,
    FundCertificatesResponse,
    VN30OverviewItem,
    VN30OverviewResponse,
)
from ..shared import StockServiceError, safe_float

logger = logging.getLogger(__name__)


class MarketService:
    """Service for market-wide data: listings, sectors, funds."""

    def __init__(self, source: str = "VCI"):
        """Initialize market service with data source."""
        self.source = source

    def list_symbols(self, exchange: Optional[str] = None) -> list[StockSymbol]:
        """List all stock symbols."""
        try:
            listing = Listing()

            # vnstock 4.x returns a DataFrame here and takes no exchange
            # argument; filtering happens on the `exchange` column. The previous
            # `list(...)` over that DataFrame yielded its *column names*, so this
            # endpoint was reporting "symbol", "organ_name", ... as tickers.
            df = listing.symbols_by_exchange()

            if df is None or df.empty:
                return []

            if exchange:
                wanted = exchange.upper()
                df = df[df["exchange"].str.upper() == wanted]
                if df.empty:
                    return []

            return self._df_to_stock_symbols(df)
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching symbols: {e}")
            raise StockServiceError(f"Failed to fetch symbols: {e}")

    def list_symbols_by_group(self, group: str) -> list[str]:
        """List symbols by group (e.g., VN30, HNX30)."""
        try:
            listing = Listing()
            symbols = listing.symbols_by_group(group.upper())

            if symbols is None:
                return []

            return symbols.tolist() if hasattr(symbols, "tolist") else list(symbols)
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching symbols for group {group}: {e}")
            raise StockServiceError(f"Failed to fetch symbols for group {group}: {e}")

    def search_symbols(self, query: str, limit: int = 20) -> list[StockSymbol]:
        """Search stock symbols by ticker or company name."""
        if not query or len(query.strip()) < 1:
            return []

        query = query.strip().upper()

        try:
            listing = Listing()
            df = listing.all_symbols()

            if df is None or df.empty:
                return []

            mask = df["symbol"].str.upper().str.contains(query, na=False)
            if "organ_name" in df.columns:
                mask |= df["organ_name"].str.upper().str.contains(query, na=False)

            filtered = df[mask].head(limit)

            return self._df_to_stock_symbols(filtered)
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error searching symbols for '{query}': {e}")
            raise StockServiceError(f"Failed to search symbols: {e}")

    def get_sector_performance(self) -> SectorPerformanceResponse:
        """Get market-cap weighted sector performance (ICB Level 2)."""
        try:
            listing = Listing()
            # vnstock 4.x defaults Trading to KBS, whose price_board rejects
            # drop_levels; 3.x defaulted to VCI. Pass the configured source.
            trading = Trading(source=self.source)

            # Get all symbols with ICB classification (symbols_by_industries has ICB data)
            all_symbols_df = listing.symbols_by_industries()
            if all_symbols_df is None or all_symbols_df.empty:
                return SectorPerformanceResponse(sectors=[], generated_at=pd.Timestamp.now(), total_sectors=0)

            # Get price board for all symbols
            symbols_list = all_symbols_df["symbol"].tolist()

            # Process in batches to avoid API limits
            batch_size = 100
            all_price_data = []

            for i in range(0, len(symbols_list), batch_size):
                batch = symbols_list[i:i + batch_size]
                try:
                    batch_price_df = trading.price_board(
                        symbols_list=batch,
                        flatten_columns=True,
                        drop_levels=[0],
                    )
                    if batch_price_df is not None and not batch_price_df.empty:
                        # Remove duplicate columns (vnstock returns duplicates like _sending_time)
                        batch_price_df = batch_price_df.loc[:, ~batch_price_df.columns.duplicated()]
                        # Reset index to avoid reindexing errors during concat
                        batch_price_df = batch_price_df.reset_index(drop=True)
                        all_price_data.append(batch_price_df)
                except (VnstockUnavailable, VnstockUnsupported):
                    # Upstream quota/capability problems carry their own meaning;
                    # don't flatten them into a generic service error.
                    raise
                except Exception as e:
                    logger.warning(f"Error fetching price batch {i}: {e}")
                    continue

            if not all_price_data:
                return SectorPerformanceResponse(sectors=[], generated_at=pd.Timestamp.now(), total_sectors=0)

            # Concatenate with ignore_index to avoid index conflicts
            price_df = pd.concat(all_price_data, ignore_index=True, copy=False)
            # Remove duplicate symbols to avoid reindexing errors
            price_df = price_df.drop_duplicates(subset=["symbol"], keep="first")

            # Extract actual trading session date from data
            session_date = pd.Timestamp.now()
            if "trading_date" in price_df.columns and price_df["trading_date"].notna().any():
                trading_date_val = price_df["trading_date"].dropna().iloc[0]
                if trading_date_val:
                    try:
                        session_date = pd.to_datetime(trading_date_val)
                    except Exception:
                        pass

            # Ensure unique symbols before merge. vnstock 4.x names these
            # industry_code / industry_name (3.x used icb_code2 / icb_name2).
            symbols_for_merge = (
                all_symbols_df[["symbol", "industry_code", "industry_name"]]
                .drop_duplicates(subset=["symbol"], keep="first")
                .rename(columns={"industry_code": "icb_code", "industry_name": "icb_name"})
            )

            # Merge with symbol data
            merged = price_df.merge(
                symbols_for_merge,
                on="symbol",
                how="left",
            )

            # Calculate sector performance
            sector_col = "icb_name"

            sectors = []

            for sector_name, group in merged.groupby(sector_col):
                if pd.isna(sector_name) or not sector_name:
                    continue

                # Calculate market cap weighted change
                # Filter: match_price > 0 to exclude non-trading stocks
                valid_rows = group[
                    group["match_price"].notna() &
                    group["ref_price"].notna() &
                    (group["match_price"] > 0) &
                    (group["ref_price"] > 0)
                ]

                if valid_rows.empty:
                    continue

                # Calculate change percentage for each stock
                changes = (valid_rows["match_price"] - valid_rows["ref_price"]) / valid_rows["ref_price"] * 100

                # Market-cap weighted average change
                # Market cap = match_price * listed_share
                if "listed_share" in valid_rows.columns:
                    market_caps = valid_rows["match_price"] * valid_rows["listed_share"]
                    total_cap = market_caps.sum()
                    if total_cap > 0:
                        avg_change = (changes * market_caps).sum() / total_cap
                    else:
                        avg_change = changes.mean()
                else:
                    # Fallback to simple average if listed_share not available
                    avg_change = changes.mean()

                # Calculate actual market cap (match_price * listed_share)
                # listed_share is in shares, match_price is in VND
                # Result in billion VND (tỷ đồng)
                if "listed_share" in valid_rows.columns:
                    # market_cap = price * shares / 1e9 (convert to billion VND)
                    sector_market_cap = (valid_rows["match_price"] * valid_rows["listed_share"]).sum() / 1e9
                else:
                    # Fallback to accumulated_value (trading value in million VND)
                    sector_market_cap = valid_rows["accumulated_value"].sum() / 1000 if "accumulated_value" in valid_rows.columns else 0

                # Get ICB code if available
                icb_code = ""
                if "icb_code" in group.columns and pd.notna(group["icb_code"].iloc[0]):
                    icb_code = str(group["icb_code"].iloc[0])

                # Get top gainers and losers using argsort for robust indexing
                changes_series = (valid_rows["match_price"] - valid_rows["ref_price"]) / valid_rows["ref_price"] * 100
                symbols_list = valid_rows["symbol"].tolist()
                changes_list = changes_series.tolist()
                # Sort by change descending
                sorted_pairs = sorted(zip(symbols_list, changes_list), key=lambda x: x[1], reverse=True)
                top_gainers = [s for s, _ in sorted_pairs[:3]]
                top_losers = [s for s, _ in sorted_pairs[-3:]]

                sectors.append(SectorPerformanceItem(
                    icb_code=icb_code,
                    icb_name=str(sector_name),
                    change_pct=round(float(avg_change), 2),
                    total_market_cap=round(float(sector_market_cap), 2),
                    stock_count=len(valid_rows),
                    top_gainers=top_gainers,
                    top_losers=top_losers,
                ))

            # Sort by change_pct descending
            sectors.sort(key=lambda x: x.change_pct or 0, reverse=True)

            return SectorPerformanceResponse(
                sectors=sectors,
                generated_at=session_date,
                total_sectors=len(sectors),
            )
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching sector performance: {e}")
            raise StockServiceError(f"Failed to fetch sector performance: {e}")

    def get_fund_certificates(self, fund_type: Optional[str] = None) -> FundCertificatesResponse:
        """Get fund certificates (open-end funds from fmarket)."""
        # Curated list of fund symbols to display
        FUND_SYMBOLS = ["MAGEF", "UVEEF", "DCDS", "VDEF", "KDEF", "TBLF", "BVFED"]

        try:
            from vnstock.explorer.fmarket.fund import Fund

            fund_api = Fund()
            df = fund_api.listing()

            if df is None or df.empty:
                return FundCertificatesResponse(funds=[], generated_at=pd.Timestamp.now(), total_count=0)

            # Filter for specific funds and maintain order
            filtered = df[df["short_name"].isin(FUND_SYMBOLS)]

            if filtered.empty:
                return FundCertificatesResponse(funds=[], generated_at=pd.Timestamp.now(), total_count=0)

            # Sort by FUND_SYMBOLS order
            filtered = filtered.set_index("short_name").loc[
                [s for s in FUND_SYMBOLS if s in filtered["short_name"].values]
            ].reset_index()

            funds = []
            for _, row in filtered.iterrows():
                try:
                    nav = safe_float(row.get("nav"))
                    change_pct = safe_float(row.get("nav_change_previous"))

                    # Map fund_type from Vietnamese to English
                    vn_fund_type = row.get("fund_type", "")
                    if "cổ phiếu" in str(vn_fund_type).lower():
                        mapped_type = "STOCK"
                    elif "trái phiếu" in str(vn_fund_type).lower():
                        mapped_type = "BOND"
                    elif "cân bằng" in str(vn_fund_type).lower():
                        mapped_type = "BALANCED"
                    else:
                        mapped_type = "STOCK"

                    funds.append(FundCertificateItem(
                        symbol=str(row.get("short_name", "")),
                        short_name=str(row.get("name", "")),
                        fund_type=mapped_type,
                        nav=round(nav, 2) if nav else None,
                        price=round(nav, 2) if nav else None,
                        change_pct=round(change_pct, 2) if change_pct is not None else None,
                    ))
                except (VnstockUnavailable, VnstockUnsupported):
                    # Upstream quota/capability problems carry their own meaning;
                    # don't flatten them into a generic service error.
                    raise
                except Exception as e:
                    logger.warning(f"Skipping fund row due to error: {e}")
                    continue

            # Filter by fund_type if specified
            if fund_type:
                funds = [f for f in funds if f.fund_type and f.fund_type.upper() == fund_type.upper()]

            return FundCertificatesResponse(
                funds=funds,
                generated_at=pd.Timestamp.now(),
                total_count=len(funds),
            )
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching fund certificates: {e}")
            raise StockServiceError(f"Failed to fetch fund certificates: {e}")

    def get_vn30_overview(self) -> VN30OverviewResponse:
        """Get VN30 index stocks with real-time price data."""
        try:
            listing = Listing()
            # vnstock 4.x defaults Trading to KBS, whose price_board rejects
            # drop_levels; 3.x defaulted to VCI. Pass the configured source.
            trading = Trading(source=self.source)

            # Step 1: Get VN30 symbols
            vn30_symbols = listing.symbols_by_group("VN30")
            if vn30_symbols is None or (hasattr(vn30_symbols, "empty") and vn30_symbols.empty):
                return VN30OverviewResponse(
                    stocks=[], generated_at=pd.Timestamp.now(), total_count=0
                )

            symbols_list = vn30_symbols.tolist() if hasattr(vn30_symbols, "tolist") else list(vn30_symbols)

            # Step 2: Get price board data for all VN30 stocks (batch call)
            price_df = trading.price_board(
                symbols_list=symbols_list,
                flatten_columns=True,
                drop_levels=[0],
            )

            if price_df is None or price_df.empty:
                return VN30OverviewResponse(
                    stocks=[], generated_at=pd.Timestamp.now(), total_count=0
                )

            # Remove duplicate columns and symbols
            price_df = price_df.loc[:, ~price_df.columns.duplicated()]
            price_df = price_df.drop_duplicates(subset=["symbol"], keep="first")

            # Step 3: Get company names (use all_symbols for efficiency)
            all_symbols_df = listing.all_symbols()
            company_names = {}
            if all_symbols_df is not None and not all_symbols_df.empty:
                for _, row in all_symbols_df.iterrows():
                    symbol = row.get("symbol")
                    name = row.get("organ_name") or row.get("organName")
                    if symbol and name:
                        company_names[symbol] = name

            # Step 4: Build response items
            stocks = []
            for _, row in price_df.iterrows():
                symbol = str(row.get("symbol", ""))
                if not symbol:
                    continue

                # Extract price data
                match_price = safe_float(row.get("match_price"))
                ref_price = safe_float(row.get("ref_price"))

                # Calculate change percentage
                change_pct = None
                if match_price and ref_price and ref_price > 0:
                    change_pct = ((match_price - ref_price) / ref_price) * 100

                # Calculate market cap (price * listed_share / 1e9 for billion VND)
                market_cap = None
                listed_share = safe_float(row.get("listed_share"))
                if match_price and listed_share:
                    market_cap = (match_price * listed_share) / 1e9

                stocks.append(VN30OverviewItem(
                    symbol=symbol,
                    company_name=company_names.get(symbol, symbol),
                    price=round(match_price, 2) if match_price else None,
                    change_pct=round(change_pct, 2) if change_pct is not None else None,
                    volume=safe_float(row.get("accumulated_volume")),
                    market_cap=round(market_cap, 2) if market_cap else None,
                ))

            # Sort by market cap descending (largest first)
            stocks.sort(key=lambda x: x.market_cap or 0, reverse=True)

            return VN30OverviewResponse(
                stocks=stocks,
                generated_at=pd.Timestamp.now(),
                total_count=len(stocks),
            )

        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching VN30 overview: {e}")
            raise StockServiceError(f"Failed to fetch VN30 overview: {e}")

    # --- Converter methods ---

    def _df_to_stock_symbols(self, df: pd.DataFrame) -> list[StockSymbol]:
        """Convert DataFrame to list of StockSymbol."""
        symbols = []
        for row in df.to_dict("records"):
            try:
                symbols.append(
                    StockSymbol(
                        symbol=str(row.get("symbol", row.get("ticker", ""))),
                        exchange=row.get("exchange"),
                        organ_name=row.get("organ_name") or row.get("organName"),
                        organ_type_code=row.get("organ_type_code"),
                    )
                )
            except (VnstockUnavailable, VnstockUnsupported):
                # Upstream quota/capability problems carry their own meaning;
                # don't flatten them into a generic service error.
                raise
            except Exception as e:
                logger.warning(f"Skipping symbol row due to error: {e}")
                continue
        return symbols


@lru_cache(maxsize=1)
def get_market_service(source: str = "VCI") -> MarketService:
    """Get or create market service instance (thread-safe singleton)."""
    return MarketService(source=source)
