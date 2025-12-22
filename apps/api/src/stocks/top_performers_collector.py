"""Top performers data collector - fetches quarterly financials for HOSE+HNX."""

import logging
import time
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from vnstock import Finance, Screener

from src.core.config import get_settings
from src.core.vnstock_wrapper import (
    VnstockRateLimitError,
    get_adaptive_delay,
    safe_vnstock_call,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class TopPerformersCollector:
    """Collects quarterly financial data for top performers ranking."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.base_delay = settings.top_performers_delay

    async def collect(self) -> dict:
        """Main collection method. Returns summary dict."""
        start_time = time.time()

        # 1. Get HOSE+HNX symbols
        symbols_data = self._get_symbols()
        if not symbols_data:
            return {"success": 0, "failed": 0, "error": "Failed to fetch symbols"}

        logger.info(f"Fetching financials for {len(symbols_data)} symbols")

        # 2. Collect financial data
        results = []
        failed = 0
        rate_limited = 0

        for i, row in enumerate(symbols_data):
            symbol = row["symbol"]
            exchange = row.get("exchange", "UNKNOWN")
            company_name = row.get("short_name", row.get("organ_name", ""))

            try:
                data = self._get_quarterly_financials(symbol)
                if data:
                    data["symbol"] = symbol
                    data["exchange"] = exchange
                    data["company_name"] = company_name
                    results.append(data)
                else:
                    failed += 1

            except VnstockRateLimitError:
                rate_limited += 1
                logger.warning(f"Rate limited on {symbol}, skipping")

            except Exception as e:
                failed += 1
                logger.debug(f"Error for {symbol}: {e}")

            # Progress log every 50 symbols
            if (i + 1) % 50 == 0:
                logger.info(f"Progress: {i+1}/{len(symbols_data)} symbols processed")

            # Delay between calls
            delay = get_adaptive_delay(self.base_delay)
            time.sleep(delay)

        # 3. Rank by net_profit
        results.sort(key=lambda x: x.get("net_profit") or 0, reverse=True)
        for rank, item in enumerate(results, 1):
            item["rank"] = rank

        # 4. Store in database
        stored = await self._store_results(results)

        elapsed = time.time() - start_time
        logger.info(
            f"Collection complete: {stored} stored, {failed} failed, "
            f"{rate_limited} rate limited in {elapsed:.1f}s"
        )

        return {
            "success": stored,
            "failed": failed,
            "rate_limited": rate_limited,
            "total_symbols": len(symbols_data),
            "elapsed_seconds": round(elapsed, 1),
        }

    def _get_symbols(self) -> list:
        """Get HOSE+HNX symbols via Screener."""

        def _fetch():
            screener = Screener(source="tcbs")
            df = screener.stock(params={"exchangeName": "HOSE,HNX"}, limit=1000)
            return df.to_dict("records")

        try:
            return safe_vnstock_call(_fetch, max_retries=3) or []
        except Exception as e:
            logger.error(f"Failed to fetch symbols: {e}")
            return []

    def _get_quarterly_financials(self, symbol: str) -> Optional[dict]:
        """Get latest quarterly income statement for symbol."""

        def _fetch():
            finance = Finance(symbol=symbol, source="VCI")
            df = finance.income_statement(period="quarter", lang="en", dropna=True)
            if df is None or df.empty:
                return None

            # Get latest quarter (first row after sort)
            latest = df.iloc[0].to_dict()

            # Extract year/quarter from period column
            year = latest.get("yearReport") or datetime.now().year
            quarter = latest.get("lengthReport") or 4

            net_profit = latest.get("postTaxProfit") or latest.get("Net profit")
            revenue = latest.get("revenue") or latest.get("Net Revenue")
            eps = latest.get("earningPerShare") or latest.get("EPS")

            profit_margin = None
            if net_profit and revenue and revenue != 0:
                profit_margin = round((net_profit / revenue) * 100, 2)

            return {
                "year": int(year),
                "quarter": int(quarter),
                "net_profit": int(net_profit) if net_profit else None,
                "revenue": int(revenue) if revenue else None,
                "profit_margin": profit_margin,
                "eps": float(eps) if eps else None,
            }

        return safe_vnstock_call(_fetch, max_retries=2, base_delay=2.0)

    async def _store_results(self, results: list) -> int:
        """Bulk upsert results to database."""
        if not results:
            return 0

        try:
            for item in results:
                stmt = text("""
                    INSERT INTO top_performers
                    (symbol, company_name, exchange, year, quarter, net_profit,
                     revenue, profit_margin, eps, rank, updated_at)
                    VALUES (:symbol, :company_name, :exchange, :year, :quarter,
                            :net_profit, :revenue, :profit_margin, :eps, :rank, NOW())
                    ON CONFLICT (symbol, year, quarter)
                    DO UPDATE SET
                        company_name = EXCLUDED.company_name,
                        exchange = EXCLUDED.exchange,
                        net_profit = EXCLUDED.net_profit,
                        revenue = EXCLUDED.revenue,
                        profit_margin = EXCLUDED.profit_margin,
                        eps = EXCLUDED.eps,
                        rank = EXCLUDED.rank,
                        updated_at = NOW()
                """)
                await self.db.execute(stmt, item)

            await self.db.commit()
            return len(results)

        except Exception as e:
            logger.error(f"Failed to store results: {e}")
            await self.db.rollback()
            return 0
