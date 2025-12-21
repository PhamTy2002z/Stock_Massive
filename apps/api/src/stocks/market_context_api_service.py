"""Service layer for market context API endpoints."""
import logging
from datetime import date, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session
from vnstock import Listing

from .market_context_repository import MarketContextRepository
from .schemas.market_context import (
    ChartDataPoint,
    MarketContextResponse,
    MarketMetrics,
    PerformanceSummary,
    SectorContext,
    TopPeer,
)

logger = logging.getLogger(__name__)


class MarketContextAPIService:
    """Service for market context API endpoints."""

    PERIOD_DAYS = {
        "1M": 30,
        "3M": 90,
        "6M": 180,
        "1Y": 365,
    }

    def __init__(self, db: Session):
        self.db = db
        self.repo = MarketContextRepository(db)

    def get_market_context(self, symbol: str, period: str) -> MarketContextResponse:
        """Get market context analysis for symbol."""
        symbol = symbol.upper()

        # Validate period
        if period not in self.PERIOD_DAYS:
            raise ValueError(f"Invalid period: {period}. Must be one of {list(self.PERIOD_DAYS.keys())}")

        # Validate symbol
        self._validate_symbol(symbol)

        # Calculate date range
        end_date = date.today()
        start_date = end_date - timedelta(days=self.PERIOD_DAYS[period])

        # Get stock info (for sector classification)
        stock_info = self._get_stock_info(symbol)

        # Fetch data from precomputed tables
        stock_returns = self.repo.get_daily_returns(symbol, start_date, end_date)
        vnindex_returns = self.repo.get_daily_returns("VNINDEX", start_date, end_date)
        latest_metric = self.repo.get_latest_metric(symbol)

        if not stock_returns:
            raise ValueError(f"No data available for {symbol}. EOD pipeline may not have run yet.")

        if not vnindex_returns:
            raise ValueError("No VNINDEX data available. EOD pipeline may not have run yet.")

        # Get sector data if available
        sector_returns = None
        sector_context = None
        if stock_info and stock_info.get("icb_code2"):
            icb_code = stock_info["icb_code2"]
            sector_returns = self.repo.get_sector_benchmark(icb_code, start_date, end_date)
            sector_context = self._build_sector_context(
                symbol,
                icb_code,
                stock_info.get("icb_name2"),
                latest_metric,
            )

        # Build response components
        chart_data = self._build_chart_data(stock_returns, vnindex_returns, sector_returns)
        metrics = self._build_metrics(latest_metric)
        performance = self._build_performance_summary(stock_returns, vnindex_returns, sector_returns)

        return MarketContextResponse(
            symbol=symbol,
            period=period,
            chart_data=chart_data,
            metrics=metrics,
            sector=sector_context,
            performance=performance,
            generated_at=date.today().isoformat(),
        )

    def _validate_symbol(self, symbol: str) -> None:
        """Validate symbol format and existence."""
        if not symbol or len(symbol) > 10:
            raise ValueError("Invalid symbol format")

        # Allow VNINDEX without validation
        if symbol == "VNINDEX":
            return

        try:
            listing = Listing()
            all_symbols = listing.all_symbols()
            if all_symbols is not None and not all_symbols.empty:
                if symbol not in all_symbols["symbol"].values:
                    raise ValueError(f"Symbol {symbol} not found")
        except ValueError:
            raise
        except Exception as e:
            logger.warning(f"Symbol validation failed for {symbol}: {e}")
            # Don't fail if vnstock API fails, let DB query handle it

    def _get_stock_info(self, symbol: str) -> Optional[Dict]:
        """Get stock ICB classification."""
        try:
            listing = Listing()
            symbols_df = listing.symbols_by_industries()

            if symbols_df is None or symbols_df.empty:
                return None

            stock_row = symbols_df[symbols_df["symbol"] == symbol]

            if stock_row.empty:
                return None

            row = stock_row.iloc[0]
            return {
                "icb_code2": row.get("icb_code2"),
                "icb_name2": row.get("icb_name2"),
            }
        except Exception as e:
            logger.warning(f"Failed to get stock info for {symbol}: {e}")
            return None

    def _build_chart_data(
        self,
        stock_returns: List,
        vnindex_returns: List,
        sector_returns: Optional[List],
    ) -> List[ChartDataPoint]:
        """Build normalized price chart data (base 100)."""
        # Create date-aligned dictionary
        data_dict: Dict = {}

        # Add stock data
        for r in stock_returns:
            data_dict[r.date] = {
                "date": r.date.isoformat(),
                "stock_price": r.close_price,
            }

        # Add VNINDEX data
        for r in vnindex_returns:
            if r.date in data_dict:
                data_dict[r.date]["vnindex_price"] = r.close_price

        # Add sector data if available
        if sector_returns:
            for r in sector_returns:
                if r.date in data_dict:
                    data_dict[r.date]["sector_return"] = r.mcap_weighted_return

        # Sort by date
        sorted_dates = sorted(data_dict.keys())

        if not sorted_dates:
            return []

        # Get base prices for normalization
        stock_base = data_dict[sorted_dates[0]]["stock_price"]
        vnindex_base = data_dict[sorted_dates[0]].get("vnindex_price", stock_base)

        # Validate bases to prevent division by zero
        if not stock_base or stock_base == 0:
            stock_base = 1.0
        if not vnindex_base or vnindex_base == 0:
            vnindex_base = 1.0

        # Build normalized chart data
        chart_data = []
        sector_cumulative = 100.0

        for date_key in sorted_dates:
            point = data_dict[date_key]

            # Normalize stock price
            stock_normalized = (point["stock_price"] / stock_base) * 100

            # Normalize VNINDEX price
            vnindex_price = point.get("vnindex_price", vnindex_base)
            vnindex_normalized = (vnindex_price / vnindex_base) * 100 if vnindex_base else 100.0

            # Sector: apply daily return to cumulative
            sector_normalized = None
            if "sector_return" in point and point["sector_return"] is not None:
                sector_cumulative *= 1 + point["sector_return"]
                sector_normalized = round(sector_cumulative, 2)

            chart_data.append(
                ChartDataPoint(
                    date=point["date"],
                    stock=round(stock_normalized, 2),
                    vnindex=round(vnindex_normalized, 2),
                    sector=sector_normalized,
                )
            )

        return chart_data

    def _build_metrics(self, latest_metric) -> MarketMetrics:
        """Build metrics from latest database record."""
        if not latest_metric:
            return MarketMetrics()

        return MarketMetrics(
            beta_20d=float(latest_metric.beta_20d) if latest_metric.beta_20d else None,
            beta_60d=float(latest_metric.beta_60d) if latest_metric.beta_60d else None,
            correlation_20d=float(latest_metric.corr_20d) if latest_metric.corr_20d else None,
            correlation_60d=float(latest_metric.corr_60d) if latest_metric.corr_60d else None,
            rs_market_20d=float(latest_metric.rs_market_20d) if latest_metric.rs_market_20d else None,
            rs_sector_20d=float(latest_metric.rs_sector_20d) if latest_metric.rs_sector_20d else None,
        )

    def _build_sector_context(
        self,
        symbol: str,
        icb_code: str,
        icb_name: Optional[str],
        latest_metric,
    ) -> Optional[SectorContext]:
        """Build sector context with rank and peers."""
        if not latest_metric:
            return None

        sector_rank = latest_metric.sector_rank
        sector_total = latest_metric.sector_total

        if not sector_rank or not sector_total:
            return None

        # Top peers placeholder - would need price board data
        top_peers: List[TopPeer] = []

        return SectorContext(
            icb_code=icb_code,
            icb_name=icb_name or "Unknown",
            rank=sector_rank,
            total=sector_total,
            top_peers=top_peers,
        )

    def _build_performance_summary(
        self,
        stock_returns: List,
        vnindex_returns: List,
        sector_returns: Optional[List],
    ) -> PerformanceSummary:
        """Build performance comparison summary."""
        # Calculate cumulative returns
        stock_return = self._calculate_cumulative_return([r.return_1d for r in stock_returns if r.return_1d])
        vnindex_return = self._calculate_cumulative_return([r.return_1d for r in vnindex_returns if r.return_1d])

        sector_return = None
        if sector_returns:
            sector_return = self._calculate_cumulative_return(
                [r.mcap_weighted_return for r in sector_returns if r.mcap_weighted_return]
            )

        return PerformanceSummary(
            stock_return=round(stock_return * 100, 2),
            vnindex_return=round(vnindex_return * 100, 2),
            sector_return=round(sector_return * 100, 2) if sector_return is not None else None,
            outperform_market=stock_return > vnindex_return,
            outperform_sector=(stock_return > sector_return) if sector_return is not None else None,
        )

    @staticmethod
    def _calculate_cumulative_return(returns: List[float]) -> float:
        """Calculate cumulative return from daily returns."""
        cumulative = 1.0
        for r in returns:
            if r is not None:
                cumulative *= 1 + r
        return cumulative - 1.0
