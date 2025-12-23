"""Financial statements data collector - fetches quarterly financials for HOSE+HNX."""

import logging
import time
from datetime import datetime
from typing import Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from vnstock import Finance, Listing

from src.core.config import get_settings
from src.core.vnstock_wrapper import (
    VnstockRateLimitError,
    get_adaptive_delay,
    safe_vnstock_call,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class FinancialStatementsCollector:
    """Collects quarterly financial data for financial statements ranking."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.base_delay = settings.financial_statements_delay

    async def collect(self) -> dict:
        """Main collection method. Returns summary dict."""
        start_time = time.time()

        # 1. Get HOSE+HNX symbols
        symbols_data = self._get_symbols()
        if not symbols_data:
            return {"success": 0, "failed": 0, "error": "Failed to fetch symbols"}

        logger.info(f"Fetching financials for {len(symbols_data)} symbols")

        # 2. Collect financial data with incremental saving
        batch_results = []
        total_stored = 0
        failed = 0
        rate_limited = 0
        batch_size = 100  # Save every 100 records

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
                    data["rank"] = 0  # Temporary, will update later
                    batch_results.append(data)
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

            # Save batch every 100 records to avoid data loss
            if len(batch_results) >= batch_size:
                stored = await self._store_batch(batch_results)
                total_stored += stored
                logger.info(f"Saved batch: {stored} records (total: {total_stored})")
                batch_results = []

            # Delay between calls
            delay = get_adaptive_delay(self.base_delay)
            time.sleep(delay)

        # 3. Save remaining batch
        if batch_results:
            stored = await self._store_batch(batch_results)
            total_stored += stored
            logger.info(f"Saved final batch: {stored} records")

        # 4. Update ranks based on net_profit
        await self._update_ranks()

        elapsed = time.time() - start_time
        logger.info(
            f"Collection complete: {total_stored} stored, {failed} failed, "
            f"{rate_limited} rate limited in {elapsed:.1f}s"
        )

        return {
            "success": total_stored,
            "failed": failed,
            "rate_limited": rate_limited,
            "total_symbols": len(symbols_data),
            "elapsed_seconds": round(elapsed, 1),
        }

    def _get_symbols(self) -> list:
        """Get HOSE+HNX symbols via VCI Listing API."""

        def _fetch():
            listing = Listing(source="VCI")
            # Get both exchanges
            hose = listing.symbols_by_exchange(exchange="HOSE")
            hnx = listing.symbols_by_exchange(exchange="HNX")
            # Combine and filter for stocks only (type=STOCK)
            combined = pd.concat([hose, hnx], ignore_index=True)
            stocks = combined[combined["type"] == "STOCK"]
            # Rename columns to match expected format
            stocks = stocks.rename(columns={
                "organ_short_name": "short_name",
                "organ_name": "organ_name"
            })
            return stocks.to_dict("records")

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

            # VCI column names (may vary by symbol type: bank vs non-bank)
            net_profit = (
                latest.get("Net Profit For the Year") or
                latest.get("Attributable to parent company") or
                latest.get("Attribute to parent company (Bn. VND)") or
                latest.get("postTaxProfit") or
                latest.get("Net profit")
            )
            revenue = (
                latest.get("Revenue (Bn. VND)") or
                latest.get("Total operating revenue") or
                latest.get("revenue") or
                latest.get("Net Revenue")
            )
            eps = (
                latest.get("EPS_basis") or
                latest.get("earningPerShare") or
                latest.get("EPS")
            )

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

    async def _store_batch(self, batch: list) -> int:
        """Store a batch of results to database with upsert."""
        if not batch:
            return 0

        try:
            for item in batch:
                stmt = text("""
                    INSERT INTO financial_statements
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
                        updated_at = NOW()
                """)
                await self.db.execute(stmt, item)

            await self.db.commit()
            return len(batch)

        except Exception as e:
            logger.error(f"Failed to store batch: {e}")
            await self.db.rollback()
            return 0

    async def _update_ranks(self) -> None:
        """Update ranks based on net_profit for latest quarter."""
        try:
            # Get the latest year/quarter in the data
            latest_period = await self.db.execute(text("""
                SELECT year, quarter FROM financial_statements
                ORDER BY year DESC, quarter DESC
                LIMIT 1
            """))
            row = latest_period.fetchone()
            if not row:
                return

            year, quarter = row

            # Update ranks for the latest quarter using window function
            await self.db.execute(text("""
                UPDATE financial_statements tp
                SET rank = ranked.new_rank
                FROM (
                    SELECT symbol, year, quarter,
                           ROW_NUMBER() OVER (ORDER BY net_profit DESC NULLS LAST) as new_rank
                    FROM financial_statements
                    WHERE year = :year AND quarter = :quarter
                ) ranked
                WHERE tp.symbol = ranked.symbol
                  AND tp.year = ranked.year
                  AND tp.quarter = ranked.quarter
            """), {"year": year, "quarter": quarter})

            await self.db.commit()
            logger.info(f"Updated ranks for Q{quarter}-{year}")

        except Exception as e:
            logger.error(f"Failed to update ranks: {e}")
            await self.db.rollback()
