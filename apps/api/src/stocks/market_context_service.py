"""Service for computing market context metrics (EOD pipeline)."""
import logging
import time
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential
from vnstock import Listing, Quote, Trading

from .market_context_repository import MarketContextRepository

logger = logging.getLogger(__name__)

# Pipeline configuration
API_DELAY_SECONDS = 0.3  # 300ms delay between API calls to avoid rate limits
BATCH_COMMIT_SIZE = 100  # Commit every N symbols to avoid long transactions
LOOKBACK_DAYS = 90  # Days of history for rolling metrics
INITIAL_DELAY_SECONDS = 2  # Initial delay before starting to let rate limit reset


class MarketContextService:
    """Service for computing and storing market context metrics."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = MarketContextRepository(db)

    def run_eod_pipeline(self, target_date: Optional[date] = None) -> dict:
        """Run end-of-day pipeline for market context metrics.

        Args:
            target_date: Date to compute metrics for (default: today)

        Returns:
            Dictionary with pipeline results and statistics
        """
        if target_date is None:
            target_date = date.today()

        pipeline_start = time.time()
        results = {
            "target_date": str(target_date),
            "steps": {},
            "errors": [],
        }

        logger.info(f"Starting EOD pipeline for {target_date}")

        try:
            # Step 1: Fetch and store daily returns
            step_start = time.time()
            returns_result = self._fetch_and_store_daily_returns(target_date)
            results["steps"]["daily_returns"] = {
                "duration_seconds": round(time.time() - step_start, 2),
                **returns_result,
            }

            # Step 2: Compute rolling metrics
            step_start = time.time()
            metrics_result = self._compute_rolling_metrics(target_date)
            results["steps"]["rolling_metrics"] = {
                "duration_seconds": round(time.time() - step_start, 2),
                **metrics_result,
            }

            # Step 3: Compute sector benchmarks
            step_start = time.time()
            sector_result = self._compute_sector_benchmarks(target_date)
            results["steps"]["sector_benchmarks"] = {
                "duration_seconds": round(time.time() - step_start, 2),
                **sector_result,
            }

            # Step 4: Compute sector ranks
            step_start = time.time()
            ranks_result = self._compute_sector_ranks(target_date)
            results["steps"]["sector_ranks"] = {
                "duration_seconds": round(time.time() - step_start, 2),
                **ranks_result,
            }

            results["total_duration_seconds"] = round(time.time() - pipeline_start, 2)
            results["status"] = "success"
            logger.info(f"EOD pipeline completed for {target_date} in {results['total_duration_seconds']}s")

        except Exception as e:
            results["status"] = "failed"
            results["errors"].append(str(e))
            results["total_duration_seconds"] = round(time.time() - pipeline_start, 2)
            logger.error(f"EOD pipeline failed: {e}", exc_info=True)
            raise

        return results

    def _fetch_and_store_daily_returns(self, target_date: date) -> dict:
        """Fetch OHLCV and compute daily returns for all symbols."""
        logger.info(f"Fetching OHLCV data for {target_date}")

        # Initial delay to avoid rate limit issues
        time.sleep(INITIAL_DELAY_SECONDS)

        try:
            listing = Listing()
            all_symbols_df = listing.all_symbols()
        except Exception as e:
            logger.error(f"Failed to fetch symbol list (rate limit?): {e}")
            return {"success_count": 0, "error_count": 0, "symbols_processed": 0, "error": str(e)}

        if all_symbols_df is None or all_symbols_df.empty:
            logger.error("Failed to fetch symbol list")
            return {"success_count": 0, "error_count": 0, "symbols_processed": 0}

        symbols = all_symbols_df["symbol"].tolist()
        symbols.append("VNINDEX")  # Add market index

        # Date range: need previous days for return calculation
        start_date = target_date - timedelta(days=10)  # Buffer for weekends/holidays
        end_date = target_date

        success_count = 0
        error_count = 0

        for symbol in symbols:
            try:
                df = self._fetch_history_with_retry(symbol, start_date, end_date)

                if df is None or df.empty:
                    logger.debug(f"No data for {symbol}")
                    continue

                # Sort by date and compute returns
                df = df.sort_values("time")
                df["date"] = pd.to_datetime(df["time"]).dt.date
                df["return_1d"] = df["close"].pct_change()
                df["return_1d_log"] = np.log(df["close"] / df["close"].shift(1))

                # Store only target date
                target_row = df[df["date"] == target_date]
                if not target_row.empty:
                    row = target_row.iloc[0]
                    self.repo.upsert_daily_return(
                        symbol=symbol,
                        target_date=target_date,
                        close_price=float(row["close"]),
                        return_1d=float(row["return_1d"]) if pd.notna(row["return_1d"]) else None,
                        return_1d_log=float(row["return_1d_log"]) if pd.notna(row["return_1d_log"]) else None,
                    )
                    success_count += 1

                # Rate limiting: delay between API calls
                time.sleep(API_DELAY_SECONDS)

                # Progress logging every 100 symbols
                if (success_count + error_count) % 100 == 0:
                    logger.info(f"Progress: {success_count + error_count}/{len(symbols)} symbols processed")

            except Exception as e:
                logger.warning(f"Failed to fetch {symbol}: {e}")
                error_count += 1
                continue

        logger.info(f"Daily returns: {success_count} success, {error_count} errors")
        return {
            "success_count": success_count,
            "error_count": error_count,
            "symbols_processed": len(symbols),
        }

    def _compute_rolling_metrics(self, target_date: date) -> dict:
        """Compute rolling correlation, beta, RS for all stocks vs VNINDEX."""
        logger.info(f"Computing rolling metrics for {target_date}")

        time.sleep(INITIAL_DELAY_SECONDS)

        try:
            listing = Listing()
            all_symbols_df = listing.all_symbols()
        except Exception as e:
            logger.error(f"Failed to fetch symbol list for metrics: {e}")
            return {"success_count": 0, "error_count": 0, "symbols_processed": 0, "error": str(e)}

        if all_symbols_df is None or all_symbols_df.empty:
            return {"success_count": 0, "error_count": 0, "symbols_processed": 0}

        symbols = all_symbols_df["symbol"].tolist()

        # Fetch VNINDEX returns for correlation (90 days lookback)
        vnindex_returns = self._get_returns_series("VNINDEX", target_date, lookback_days=90)

        if vnindex_returns is None or len(vnindex_returns) < 5:
            logger.error("Insufficient VNINDEX data for metrics computation")
            return {"success_count": 0, "error_count": 0, "symbols_processed": len(symbols)}

        success_count = 0
        error_count = 0

        for symbol in symbols:
            try:
                stock_returns = self._get_returns_series(symbol, target_date, lookback_days=90)

                if stock_returns is None or len(stock_returns) < 5:
                    continue

                # Align dates between stock and market
                aligned = pd.DataFrame({
                    "stock": stock_returns,
                    "market": vnindex_returns,
                }).dropna()

                if len(aligned) < 5:
                    continue

                metrics = {}

                # 5D window
                if len(aligned) >= 5:
                    window_5d = aligned.tail(5)
                    metrics["corr_5d"] = self._pearson_correlation(
                        window_5d["stock"].values,
                        window_5d["market"].values,
                    )

                # 20D window
                if len(aligned) >= 20:
                    window_20d = aligned.tail(20)
                    metrics["corr_20d"] = self._pearson_correlation(
                        window_20d["stock"].values,
                        window_20d["market"].values,
                    )
                    metrics["beta_20d"] = self._calculate_beta(
                        window_20d["stock"].values,
                        window_20d["market"].values,
                    )
                    metrics["rs_market_20d"] = self._calculate_relative_strength(
                        window_20d["stock"].values,
                        window_20d["market"].values,
                    )

                # 60D window
                if len(aligned) >= 60:
                    window_60d = aligned.tail(60)
                    metrics["corr_60d"] = self._pearson_correlation(
                        window_60d["stock"].values,
                        window_60d["market"].values,
                    )
                    metrics["beta_60d"] = self._calculate_beta(
                        window_60d["stock"].values,
                        window_60d["market"].values,
                    )

                # Store metrics if any computed
                if metrics:
                    self.repo.upsert_market_metric(symbol, target_date, **metrics)
                    success_count += 1

            except Exception as e:
                logger.warning(f"Failed to compute metrics for {symbol}: {e}")
                error_count += 1
                continue

        logger.info(f"Rolling metrics: {success_count} success, {error_count} errors")
        return {
            "success_count": success_count,
            "error_count": error_count,
            "symbols_processed": len(symbols),
        }

    def _compute_sector_benchmarks(self, target_date: date) -> dict:
        """Compute market-cap weighted sector benchmarks."""
        logger.info(f"Computing sector benchmarks for {target_date}")

        time.sleep(INITIAL_DELAY_SECONDS)

        try:
            listing = Listing()
            trading = Trading()
        except Exception as e:
            logger.error(f"Failed to initialize vnstock for benchmarks: {e}")
            return {"sectors_computed": 0, "error_count": 0, "error": str(e)}

        # Get symbols with ICB classification
        try:
            symbols_df = listing.symbols_by_industries()
        except Exception as e:
            logger.error(f"Failed to fetch industries: {e}")
            return {"sectors_computed": 0, "error_count": 0, "error": str(e)}

        if symbols_df is None or symbols_df.empty:
            return {"sectors_computed": 0, "error_count": 0}

        # Get price board for market cap calculation (batch)
        symbols_list = symbols_df["symbol"].tolist()
        batch_size = 100
        all_price_data = []

        for i in range(0, len(symbols_list), batch_size):
            batch = symbols_list[i : i + batch_size]
            try:
                batch_df = trading.price_board(
                    symbols_list=batch,
                    flatten_columns=True,
                    drop_levels=[0],
                )
                if batch_df is not None and not batch_df.empty:
                    batch_df = batch_df.loc[:, ~batch_df.columns.duplicated()]
                    all_price_data.append(batch_df)
            except Exception as e:
                logger.warning(f"Error fetching price batch {i}: {e}")
                continue

        if not all_price_data:
            return {"sectors_computed": 0, "error_count": 0}

        price_df = pd.concat(all_price_data, ignore_index=True)
        price_df = price_df.drop_duplicates(subset=["symbol"], keep="first")

        # Merge with ICB data
        icb_cols = ["symbol"]
        for col in ["icb_code2", "icb_name2"]:
            if col in symbols_df.columns:
                icb_cols.append(col)

        symbols_for_merge = symbols_df[icb_cols].drop_duplicates(subset=["symbol"], keep="first")
        merged = price_df.merge(symbols_for_merge, on="symbol", how="left")

        # Get daily returns from database
        returns_dict = {}
        for symbol in merged["symbol"].unique():
            ret = self.repo.get_daily_return(symbol, target_date)
            if ret and ret.return_1d is not None:
                returns_dict[symbol] = float(ret.return_1d)

        merged["return_1d"] = merged["symbol"].map(returns_dict)

        # Filter valid rows
        required_cols = ["return_1d", "match_price", "listed_share"]
        for col in required_cols:
            if col not in merged.columns:
                merged[col] = None

        merged = merged.dropna(subset=["return_1d", "match_price", "listed_share"])

        if merged.empty or "icb_code2" not in merged.columns:
            return {"sectors_computed": 0, "error_count": 0}

        # Calculate market cap
        merged["market_cap"] = merged["match_price"] * merged["listed_share"]

        # Group by ICB Level 2
        sectors_computed = 0
        error_count = 0

        for icb_code, group in merged.groupby("icb_code2"):
            if pd.isna(icb_code) or not icb_code:
                continue

            try:
                total_mcap = group["market_cap"].sum()
                if total_mcap <= 0:
                    continue

                weighted_return = (group["return_1d"] * group["market_cap"]).sum() / total_mcap

                self.repo.upsert_sector_benchmark(
                    icb_code=str(icb_code),
                    target_date=target_date,
                    mcap_weighted_return=float(weighted_return),
                    total_mcap=int(total_mcap),
                    stock_count=len(group),
                )
                sectors_computed += 1

            except Exception as e:
                logger.warning(f"Failed to compute benchmark for sector {icb_code}: {e}")
                error_count += 1
                continue

        logger.info(f"Sector benchmarks: {sectors_computed} computed, {error_count} errors")
        return {"sectors_computed": sectors_computed, "error_count": error_count}

    def _compute_sector_ranks(self, target_date: date) -> dict:
        """Compute stock rank within sector based on daily return."""
        logger.info(f"Computing sector ranks for {target_date}")

        time.sleep(INITIAL_DELAY_SECONDS)

        try:
            listing = Listing()
            symbols_df = listing.symbols_by_industries()
        except Exception as e:
            logger.error(f"Failed to fetch industries for ranks: {e}")
            return {"sectors_processed": 0, "stocks_ranked": 0, "error": str(e)}

        if symbols_df is None or symbols_df.empty or "icb_code2" not in symbols_df.columns:
            return {"sectors_processed": 0, "stocks_ranked": 0}

        sectors_processed = 0
        stocks_ranked = 0

        for icb_code, group in symbols_df.groupby("icb_code2"):
            if pd.isna(icb_code) or not icb_code:
                continue

            try:
                # Get returns for all stocks in sector
                stock_returns = []
                for symbol in group["symbol"]:
                    ret = self.repo.get_daily_return(symbol, target_date)
                    if ret and ret.return_1d is not None:
                        stock_returns.append((symbol, float(ret.return_1d)))

                if not stock_returns:
                    continue

                # Sort by return descending
                stock_returns.sort(key=lambda x: x[1], reverse=True)
                sector_total = len(stock_returns)

                # Assign ranks
                for rank, (symbol, _) in enumerate(stock_returns, start=1):
                    self.repo.upsert_market_metric(
                        symbol,
                        target_date,
                        sector_rank=rank,
                        sector_total=sector_total,
                    )
                    stocks_ranked += 1

                sectors_processed += 1

            except Exception as e:
                logger.warning(f"Failed to compute ranks for sector {icb_code}: {e}")
                continue

        logger.info(f"Sector ranks: {sectors_processed} sectors, {stocks_ranked} stocks ranked")
        return {"sectors_processed": sectors_processed, "stocks_ranked": stocks_ranked}

    def _get_returns_series(
        self, symbol: str, end_date: date, lookback_days: int
    ) -> Optional[pd.Series]:
        """Get returns series for symbol from database."""
        start_date = end_date - timedelta(days=lookback_days)
        returns = self.repo.get_daily_returns(symbol, start_date, end_date)

        if not returns:
            return None

        df = pd.DataFrame([
            {"date": r.date, "return_1d": r.return_1d}
            for r in returns
        ])

        df = df.dropna(subset=["return_1d"])
        if df.empty:
            return None

        df = df.set_index("date")
        return df["return_1d"]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _fetch_history_with_retry(
        self, symbol: str, start_date: date, end_date: date
    ) -> Optional[pd.DataFrame]:
        """Fetch history with retry logic for API failures."""
        quote = Quote(symbol=symbol, source="VCI")
        return quote.history(
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            interval="1D",
        )

    @staticmethod
    def _pearson_correlation(x: np.ndarray, y: np.ndarray) -> Optional[float]:
        """Calculate Pearson correlation coefficient."""
        try:
            if len(x) < 2 or len(y) < 2:
                return None
            corr = np.corrcoef(x, y)[0, 1]
            return float(corr) if not np.isnan(corr) else None
        except Exception:
            return None

    @staticmethod
    def _calculate_beta(
        stock_returns: np.ndarray, market_returns: np.ndarray
    ) -> Optional[float]:
        """Calculate beta (covariance / variance of market)."""
        try:
            if len(stock_returns) < 2 or len(market_returns) < 2:
                return None
            cov = np.cov(stock_returns, market_returns)[0, 1]
            var = np.var(market_returns, ddof=1)
            if var == 0:
                return None
            return float(cov / var)
        except Exception:
            return None

    @staticmethod
    def _calculate_relative_strength(
        stock_returns: np.ndarray, market_returns: np.ndarray
    ) -> Optional[float]:
        """Calculate relative strength (cumulative return ratio)."""
        try:
            stock_cum = (1 + stock_returns).prod() - 1
            market_cum = (1 + market_returns).prod() - 1
            if market_cum == 0:
                return None
            return float(stock_cum / market_cum)
        except Exception:
            return None
