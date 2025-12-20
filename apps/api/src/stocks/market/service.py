"""Market domain service for listings and market-wide data."""

import logging
from typing import Optional

import pandas as pd
from vnstock import Listing, Trading, Vnstock

from ..schemas.company import StockSymbol
from ..schemas.market import (
    SectorPerformanceItem,
    SectorPerformanceResponse,
    FundCertificateItem,
    FundCertificatesResponse,
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

            if exchange:
                symbols_series = listing.symbols_by_exchange(exchange.upper())
                if symbols_series is None or (hasattr(symbols_series, "empty") and symbols_series.empty):
                    return []
                symbols_list = symbols_series.tolist() if hasattr(symbols_series, "tolist") else list(symbols_series)
                return [StockSymbol(symbol=s, exchange=exchange.upper()) for s in symbols_list]

            df = listing.all_symbols()

            if df is None or df.empty:
                return []

            return self._df_to_stock_symbols(df)
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
        except Exception as e:
            logger.error(f"Error searching symbols for '{query}': {e}")
            raise StockServiceError(f"Failed to search symbols: {e}")

    def get_sector_performance(self) -> SectorPerformanceResponse:
        """Get market-cap weighted sector performance (ICB Level 2)."""
        try:
            listing = Listing()
            trading = Trading()

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

            # Ensure unique symbols in all_symbols_df before merge
            # Select ICB columns that exist in the DataFrame
            icb_cols = ["symbol"]
            for col in ["icb_name2", "icb_name3", "icb_code2"]:
                if col in all_symbols_df.columns:
                    icb_cols.append(col)
            symbols_for_merge = all_symbols_df[icb_cols].drop_duplicates(subset=["symbol"], keep="first")

            # Merge with symbol data
            merged = price_df.merge(
                symbols_for_merge,
                on="symbol",
                how="left",
            )

            # Calculate sector performance
            sector_col = "icb_name2"  # ICB Level 2
            if sector_col not in merged.columns:
                return SectorPerformanceResponse(sectors=[], generated_at=pd.Timestamp.now(), total_sectors=0)

            sectors = []
            total_market_cap = 0

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

                # Simple average change for now (market cap data not always available)
                changes = (valid_rows["match_price"] - valid_rows["ref_price"]) / valid_rows["ref_price"] * 100
                avg_change = changes.mean()

                # Estimate trading value from accumulated_value (unit: million VND)
                sector_value = valid_rows["accumulated_value"].sum() if "accumulated_value" in valid_rows.columns else 0

                # Get ICB code if available
                icb_code = ""
                if "icb_code2" in group.columns:
                    icb_code = str(group["icb_code2"].iloc[0]) if pd.notna(group["icb_code2"].iloc[0]) else ""

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
                    # accumulated_value is in million VND, divide by 1000 to get billion (tỷ)
                    total_market_cap=round(float(sector_value) / 1000, 2) if sector_value else 0.0,
                    stock_count=len(valid_rows),
                    top_gainers=top_gainers,
                    top_losers=top_losers,
                ))

                total_market_cap += sector_value if sector_value else 0

            # Sort by change_pct descending
            sectors.sort(key=lambda x: x.change_pct or 0, reverse=True)

            return SectorPerformanceResponse(
                sectors=sectors,
                generated_at=session_date,
                total_sectors=len(sectors),
            )
        except Exception as e:
            logger.error(f"Error fetching sector performance: {e}")
            raise StockServiceError(f"Failed to fetch sector performance: {e}")

    def get_fund_certificates(self, fund_type: Optional[str] = None) -> FundCertificatesResponse:
        """Get fund certificates (ETFs and open-end funds)."""
        # Curated list of fund symbols to display
        FUND_SYMBOLS = ["E1VFVN30", "VFMVF1", "VEOF", "VCBF-TBF", "VNDAF", "SSI-SCA"]

        try:
            etf_symbols = FUND_SYMBOLS

            if not etf_symbols:
                return FundCertificatesResponse(funds=[], generated_at=pd.Timestamp.now(), total_count=0)

            # Get price data for ETFs
            trading = Trading()
            price_df = trading.price_board(
                symbols_list=etf_symbols,
                flatten_columns=True,
                drop_levels=[0],
            )

            if price_df is None or price_df.empty:
                return FundCertificatesResponse(funds=[], generated_at=pd.Timestamp.now(), total_count=0)

            funds = []
            for _, row in price_df.iterrows():
                try:
                    match_price = safe_float(row.get("match_price"))
                    ref_price = safe_float(row.get("ref_price"))

                    change = None
                    change_pct = None
                    if match_price and ref_price and ref_price > 0:
                        change = match_price - ref_price
                        change_pct = (change / ref_price) * 100

                    funds.append(FundCertificateItem(
                        symbol=str(row.get("symbol", "")),
                        short_name=row.get("organ_name") or str(row.get("symbol", "")),
                        fund_type="ETF",
                        nav=match_price,
                        price=match_price,
                        change_pct=round(change_pct, 2) if change_pct else None,
                    ))
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
        except Exception as e:
            logger.error(f"Error fetching fund certificates: {e}")
            raise StockServiceError(f"Failed to fetch fund certificates: {e}")

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
            except Exception as e:
                logger.warning(f"Skipping symbol row due to error: {e}")
                continue
        return symbols
