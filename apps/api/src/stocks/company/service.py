"""Company domain service for company information and stakeholders."""

import logging
from functools import lru_cache
from typing import Optional

import pandas as pd
from src.core.vnstock_client import Company, Market, Trading, Vnstock
from src.core.vnstock_client import VnstockUnavailable, VnstockUnsupported

from ..market import MarketService
from ..schemas.company import (
    CompanyOverview,
    StockDetail,
    ShareholderItem,
    ShareholdersResponse,
    OfficerItem,
    OfficersResponse,
    InsiderDealItem,
    InsiderDealsResponse,
    NewsItem,
    NewsResponse,
    DividendItem,
    DividendsResponse,
    RatioSummaryResponse,
)
from ..shared import (
    StockServiceError,
    market_cap_billions,
    safe_float,
    validate_symbol,
)

logger = logging.getLogger(__name__)

# Only KBS implements Company.insider_trading in vnstock 4.x.
INSIDER_TRADING_SOURCE = "KBS"


def row_id(row: pd.Series, fallback: str) -> str:
    """Stable row id: vnstock 4.x dropped the `id` column, so fall back to a
    deterministic per-row value instead of returning "" for every row."""
    raw = row.get("id")
    if raw is None or (not isinstance(raw, str) and pd.isna(raw)):
        return fallback
    text = str(raw).strip()
    return text if text and text.lower() != "nan" else fallback


class CompanyService:
    """Service for company-related data: overview, shareholders, officers, insider deals."""

    def __init__(self, source: str = "VCI"):
        """Initialize company service with data source."""
        self.source = source
        self._market = MarketService(source)

    def get_company_overview(self, symbol: str) -> CompanyOverview:
        """Get company overview information."""
        symbol = validate_symbol(symbol)
        try:
            stock = Vnstock().stock(symbol=symbol, source=self.source)
            overview = stock.company.overview()

            if overview is None or (isinstance(overview, pd.DataFrame) and overview.empty):
                return CompanyOverview(symbol=symbol.upper())

            return self._to_company_overview(symbol, overview)
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching company overview for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch company overview for {symbol}: {e}")

    def get_shareholders(self, symbol: str) -> ShareholdersResponse:
        """Get major shareholders for a stock."""
        symbol = validate_symbol(symbol)
        try:
            stock = Vnstock().stock(symbol=symbol, source=self.source)
            df = stock.company.shareholders()

            if df is None or df.empty:
                return ShareholdersResponse(symbol=symbol, shareholders=[], total_count=0)

            shareholders = []
            for i, (_, row) in enumerate(df.iterrows()):
                try:
                    update_date = row.get("update_date")
                    if update_date is not None and pd.notna(update_date):
                        if hasattr(update_date, "strftime"):
                            update_date = update_date.strftime("%Y-%m-%d")
                        else:
                            update_date = str(update_date)
                    else:
                        update_date = None

                    shareholders.append(ShareholderItem(
                        id=row_id(row, f"{symbol}-shareholder-{i}"),
                        name=str(row.get("share_holder", "")),
                        shares=float(row.get("quantity", 0)),
                        ownership_pct=float(row.get("share_own_percent", 0)) * 100,
                        update_date=update_date,
                    ))
                except (VnstockUnavailable, VnstockUnsupported):
                    # Upstream quota/capability problems carry their own meaning;
                    # don't flatten them into a generic service error.
                    raise
                except Exception as e:
                    logger.warning(f"Skipping shareholder row due to error: {e}")
                    continue

            return ShareholdersResponse(
                symbol=symbol,
                shareholders=shareholders,
                total_count=len(shareholders),
            )
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching shareholders for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch shareholders for {symbol}: {e}")

    def get_officers(self, symbol: str, filter_by: str = "working") -> OfficersResponse:
        """Get company officers/management for a stock."""
        symbol = validate_symbol(symbol)
        try:
            stock = Vnstock().stock(symbol=symbol, source=self.source)
            df = stock.company.officers(filter_by=filter_by)

            if df is None or df.empty:
                return OfficersResponse(symbol=symbol, officers=[], total_count=0)

            officers = []
            for i, (_, row) in enumerate(df.iterrows()):
                try:
                    update_date = row.get("update_date")
                    if update_date is not None and pd.notna(update_date):
                        if hasattr(update_date, "strftime"):
                            update_date = update_date.strftime("%Y-%m-%d")
                        else:
                            update_date = str(update_date)
                    else:
                        update_date = None

                    officers.append(OfficerItem(
                        id=row_id(row, f"{symbol}-officer-{i}"),
                        name=str(row.get("officer_name", "")),
                        position=str(row.get("officer_position", "")),
                        position_short=row.get("position_short_name"),
                        shares=safe_float(row.get("quantity")),
                        ownership_pct=safe_float(row.get("officer_own_percent")) * 100 if row.get("officer_own_percent") else None,
                        update_date=update_date,
                        status=row.get("type"),
                    ))
                except (VnstockUnavailable, VnstockUnsupported):
                    # Upstream quota/capability problems carry their own meaning;
                    # don't flatten them into a generic service error.
                    raise
                except Exception as e:
                    logger.warning(f"Skipping officer row due to error: {e}")
                    continue

            return OfficersResponse(
                symbol=symbol,
                officers=officers,
                total_count=len(officers),
            )
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching officers for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch officers for {symbol}: {e}")

    def get_insider_deals(self, symbol: str) -> InsiderDealsResponse:
        """Get insider trading deals for a stock."""
        symbol = validate_symbol(symbol)
        try:
            # vnstock 4.x renamed this to Company.insider_trading and only the
            # KBS provider implements it — VCI raises NotImplementedError, and
            # the legacy `stock.company.insider_deals` attribute is gone.
            df = Company(symbol=symbol, source=INSIDER_TRADING_SOURCE).insider_trading()

            if df is None or df.empty:
                return InsiderDealsResponse(symbol=symbol, deals=[], total_count=0)

            deals = []
            for i, (_, row) in enumerate(df.iterrows()):
                try:
                    announce_date = row.get("deal_announce_date")
                    if announce_date is not None and pd.notna(announce_date):
                        if hasattr(announce_date, "strftime"):
                            announce_date = announce_date.strftime("%Y-%m-%d")
                        else:
                            announce_date = str(announce_date)
                    else:
                        announce_date = None

                    # Field names must match InsiderDealItem: pydantic drops
                    # unknown keywords, and `action`/`quantity` are required, so
                    # a near-miss made every row fail validation and get skipped
                    # — the endpoint always answered with an empty list.
                    deals.append(InsiderDealItem(
                        announce_date=announce_date or "",
                        action=str(row.get("deal_action") or ""),
                        quantity=safe_float(row.get("deal_quantity")) or 0.0,
                        price=safe_float(row.get("deal_price")),
                        ratio=safe_float(row.get("deal_ratio")),
                    ))
                except (VnstockUnavailable, VnstockUnsupported):
                    # Upstream quota/capability problems carry their own meaning;
                    # don't flatten them into a generic service error.
                    raise
                except Exception as e:
                    logger.warning(f"Skipping insider deal row due to error: {e}")
                    continue

            return InsiderDealsResponse(
                symbol=symbol,
                deals=deals,
                total_count=len(deals),
            )
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching insider deals for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch insider deals for {symbol}: {e}")

    # --- Converter methods ---

    def _to_company_overview(self, symbol: str, overview) -> CompanyOverview:
        """Convert overview data to CompanyOverview."""
        if isinstance(overview, pd.DataFrame):
            row = overview.iloc[0].to_dict() if len(overview) > 0 else {}
        else:
            row = overview if isinstance(overview, dict) else {}

        return CompanyOverview(
            symbol=symbol.upper(),
            company_name=row.get("organ_name") or row.get("short_name"),
            exchange=row.get("exchange"),
            # vnstock 4.x overview carries `sector`; keep the 3.x names as a
            # fallback so older payloads still resolve.
            industry=row.get("sector") or row.get("icb_name3") or row.get("icb_name2"),
            description=row.get("company_profile"),
            website=row.get("website"),
            employees=row.get("no_employees"),
            established_year=row.get("established_year"),
        )

    # --- News & Dividends methods ---

    def get_company_news(self, symbol: str) -> NewsResponse:
        """Get company news and announcements."""
        symbol = validate_symbol(symbol)
        try:
            stock = Vnstock().stock(symbol=symbol, source=self.source)
            df = stock.company.news()

            if df is None or df.empty:
                return NewsResponse(symbol=symbol, items=[], total_count=0)

            items = []
            for _, row in df.iterrows():
                try:
                    # Parse publish date
                    pub_date = row.get("publish_date")
                    if pub_date is not None and pd.notna(pub_date):
                        if hasattr(pub_date, "strftime"):
                            pub_date_str = pub_date.strftime("%Y-%m-%d %H:%M")
                        else:
                            pub_date_str = str(pub_date)
                    else:
                        pub_date_str = ""

                    items.append(
                        NewsItem(
                            id=int(row.get("id", 0) or 0),
                            title=str(row.get("title", "")),
                            source=row.get("source"),
                            published_at=pub_date_str,
                            price=safe_float(row.get("price")),
                            price_change_pct=safe_float(row.get("price_change_ratio")),
                        )
                    )
                except (VnstockUnavailable, VnstockUnsupported):
                    # Upstream quota/capability problems carry their own meaning;
                    # don't flatten them into a generic service error.
                    raise
                except Exception as e:
                    logger.warning(f"Skipping news row due to error: {e}")
                    continue

            return NewsResponse(
                symbol=symbol,
                items=items,
                total_count=len(items),
            )
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching company news for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch company news for {symbol}: {e}")

    def get_company_dividends(self, symbol: str) -> DividendsResponse:
        """Get dividend history for a stock."""
        symbol = validate_symbol(symbol)
        try:
            stock = Vnstock().stock(symbol=symbol, source=self.source)
            df = stock.company.dividends()

            if df is None or df.empty:
                return DividendsResponse(symbol=symbol, items=[], total_count=0)

            items = []
            for _, row in df.iterrows():
                try:
                    # Parse exercise date (format: DD/MM/YY)
                    ex_date = row.get("exercise_date")
                    if ex_date is not None:
                        ex_date_str = str(ex_date)
                    else:
                        ex_date_str = ""

                    # Get dividend percentage and convert to percentage format
                    div_pct = safe_float(row.get("cash_dividend_percentage")) or 0
                    # API returns decimal (0.181 = 18.1%), convert to percentage
                    div_pct_display = div_pct * 100

                    items.append(
                        DividendItem(
                            exercise_date=ex_date_str,
                            year=int(row.get("cash_year", 0) or 0),
                            dividend_pct=div_pct_display,
                            method=str(row.get("issue_method", "cash")),
                        )
                    )
                except (VnstockUnavailable, VnstockUnsupported):
                    # Upstream quota/capability problems carry their own meaning;
                    # don't flatten them into a generic service error.
                    raise
                except Exception as e:
                    logger.warning(f"Skipping dividend row due to error: {e}")
                    continue

            return DividendsResponse(
                symbol=symbol,
                items=items,
                total_count=len(items),
            )
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching company dividends for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch company dividends for {symbol}: {e}")

    # --- Advanced Deep Dive methods ---

    def get_ratio_summary(self, symbol: str) -> RatioSummaryResponse:
        """Get financial ratios summary for advanced tab."""
        symbol = validate_symbol(symbol)
        try:
            stock = Vnstock().stock(symbol=symbol, source=self.source)
            df = stock.company.ratio_summary()

            if df is None or (isinstance(df, pd.DataFrame) and df.empty):
                return RatioSummaryResponse(symbol=symbol.upper())

            if isinstance(df, pd.DataFrame):
                row = df.iloc[0].to_dict() if len(df) > 0 else {}
            else:
                row = df if isinstance(df, dict) else {}

            return RatioSummaryResponse(
                symbol=symbol.upper(),
                pe=safe_float(row.get("pe") or row.get("price_to_earning")),
                pb=safe_float(row.get("pb") or row.get("price_to_book")),
                ps=safe_float(row.get("ps")),
                roe=safe_float(row.get("roe")),
                roa=safe_float(row.get("roa")),
                roic=safe_float(row.get("roic")),
                current_ratio=safe_float(row.get("current_ratio")),
                debt_to_equity=safe_float(row.get("debt_to_equity") or row.get("de")),
            )
        except (VnstockUnavailable, VnstockUnsupported):
            # Upstream quota/capability problems carry their own meaning;
            # don't flatten them into a generic service error.
            raise
        except Exception as e:
            logger.error(f"Error fetching ratio summary for {symbol}: {e}")
            raise StockServiceError(f"Failed to get ratio summary for {symbol}: {e}")

    # --- Composite stock detail ---

    def get_stock_detail(self, symbol: str) -> StockDetail:
        """Get comprehensive stock detail data.

        Combines price board, company overview, and financial ratios.
        """
        symbol = validate_symbol(symbol)
        result: dict = {"symbol": symbol.upper()}
        listed_shares: Optional[float] = None

        # 1. Get price board data
        try:
            # vnstock 4.x defaults Trading to KBS, whose price_board rejects
            # drop_levels; 3.x defaulted to VCI. Pass the configured source.
            trading = Trading(source=self.source)
            price_df = trading.price_board(
                symbols_list=[symbol],
                flatten_columns=True,
                drop_levels=[0],
            )

            if price_df is not None and not price_df.empty:
                row = price_df.iloc[0]
                listed_shares = safe_float(row.get("listed_share"))
                result.update({
                    "price": safe_float(row.get("match_price")),
                    "ceiling": safe_float(row.get("ceiling")),
                    "floor": safe_float(row.get("floor")),
                    "ref_price": safe_float(row.get("ref_price")),
                    "high_price": safe_float(row.get("highest")),
                    "low_price": safe_float(row.get("lowest")),
                    "volume": int(row.get("accumulated_volume", 0)) if pd.notna(row.get("accumulated_volume")) else None,
                    "trading_value": safe_float(row.get("accumulated_value")),
                    "exchange": row.get("exchange"),
                })

                organ_name = row.get("organ_name")
                if organ_name and pd.notna(organ_name):
                    result["company_name"] = str(organ_name)

                if result.get("price") and result.get("ref_price"):
                    change = result["price"] - result["ref_price"]
                    change_pct = (change / result["ref_price"]) * 100
                    result["change"] = round(change, 2)
                    result["change_pct"] = round(change_pct, 2)

        except Exception as e:
            logger.warning(f"Error fetching price board for {symbol}: {e}")

        # 2. Get company overview
        try:
            stock = Vnstock().stock(symbol=symbol, source=self.source)
            overview = stock.company.overview()

            if overview is not None and not (isinstance(overview, pd.DataFrame) and overview.empty):
                if isinstance(overview, pd.DataFrame):
                    row = overview.iloc[0].to_dict() if len(overview) > 0 else {}
                else:
                    row = overview if isinstance(overview, dict) else {}

                if not result.get("company_name"):
                    company_name = row.get("organ_name") or row.get("short_name") or row.get("company_name")
                    if company_name:
                        result["company_name"] = company_name

                if not result.get("exchange"):
                    result["exchange"] = row.get("exchange")

                result.update({
                    # vnstock 4.x overview carries `sector` (and icb_code_lv2/lv4)
                    # instead of the 3.x icb_name3/icb_name2, so this used to be
                    # null for every symbol. Read from the same payload rather
                    # than adding upstream calls to a hot path.
                    "industry": row.get("sector") or row.get("industry"),
                    "issue_share": safe_float(row.get("issue_share")),
                    "outstanding_shares": safe_float(row.get("outstanding_share")) or safe_float(row.get("issue_share")),
                    "description": row.get("company_profile") or row.get("description"),
                    "website": row.get("website"),
                    "employees": row.get("no_employees"),
                    "established_year": row.get("established_year"),
                })

                outstanding_shares = safe_float(row.get("outstanding_share"))
                issue_shares = safe_float(row.get("issue_share"))
                market_cap = market_cap_billions(
                    result.get("price"),
                    outstanding_shares or listed_shares or issue_shares,
                )
                if market_cap is not None:
                    result["market_cap"] = round(market_cap, 2)

        except Exception as e:
            logger.warning(f"Error fetching company overview for {symbol}: {e}")

        # 3. Get financial ratios (summary)
        try:
            stock = Vnstock().stock(symbol=symbol, source=self.source)
            ratios = stock.company.ratio_summary()

            if ratios is not None and not (isinstance(ratios, pd.DataFrame) and ratios.empty):
                if isinstance(ratios, pd.DataFrame):
                    row = ratios.iloc[0].to_dict() if len(ratios) > 0 else {}
                else:
                    row = ratios if isinstance(ratios, dict) else {}

                result.update({
                    "eps": safe_float(row.get("eps") or row.get("eps_ttm")),
                    "pe": safe_float(row.get("pe") or row.get("price_to_earning")),
                    "pb": safe_float(row.get("pb") or row.get("price_to_book")),
                    "roe": safe_float(row.get("roe")),
                    "roa": safe_float(row.get("roa")),
                })
                # Dividend yield from ratio_summary (decimal -> percentage)
                div_val = safe_float(row.get("dividend"))
                if div_val is not None:
                    result["dividend_yield"] = div_val * 100

        except Exception as e:
            logger.warning(f"Error fetching financial ratios for {symbol}: {e}")

        # 4. Calculate 52-week metrics from the supported vnstock 4 OHLCV API.
        try:
            result.update(self._get_52_week_metrics(symbol))
        except Exception as e:
            logger.warning(f"Error fetching 52-week metrics for {symbol}: {e}")

        # 5. Calculate VN30 rank by market cap
        try:
            result["vn30_rank"] = self._get_vn30_rank(symbol, result.get("market_cap"))
        except Exception as e:
            logger.warning(f"Error calculating VN30 rank for {symbol}: {e}")

        return StockDetail(**result)

    def _get_52_week_metrics(self, symbol: str) -> dict:
        """Calculate true 52-week range and average volume from daily bars."""
        frame = Market().equity(symbol).ohlcv(count=260, source=self.source)
        if frame is None or frame.empty:
            return {}

        high = safe_float(pd.to_numeric(frame["high"], errors="coerce").max())
        low = safe_float(pd.to_numeric(frame["low"], errors="coerce").min())
        average_volume = safe_float(
            pd.to_numeric(frame["volume"], errors="coerce").mean()
        )
        return {
            "high_52_week": high,
            "low_52_week": low,
            "avg_volume_52_week": (
                int(round(average_volume)) if average_volume is not None else None
            ),
        }

    def _get_vn30_rank(self, symbol: str, current_market_cap: Optional[float] = None) -> Optional[int]:
        """Calculate VN30 rank by market cap for a symbol.

        Returns rank (1-30) if symbol is in VN30, None otherwise.
        """
        symbol = symbol.upper()

        # Get VN30 symbols list
        vn30_symbols = self._market.list_symbols_by_group("VN30")
        if not vn30_symbols or symbol not in vn30_symbols:
            return None

        # Get price board for all VN30 symbols to calculate market caps
        try:
            # vnstock 4.x defaults Trading to KBS, whose price_board rejects
            # drop_levels; 3.x defaulted to VCI. Pass the configured source.
            trading = Trading(source=self.source)
            price_df = trading.price_board(
                symbols_list=vn30_symbols,
                flatten_columns=True,
                drop_levels=[0],
            )

            if price_df is None or price_df.empty:
                return None

            # Calculate market cap for each VN30 stock
            # market_cap = match_price * listed_share / 1e9 (billion VND)
            market_caps = []
            for _, row in price_df.iterrows():
                sym = row.get("symbol", "").upper()
                price = safe_float(row.get("match_price"))
                listed_share = safe_float(row.get("listed_share"))

                if price and listed_share:
                    cap = (price * listed_share) / 1e9
                else:
                    cap = 0

                market_caps.append({"symbol": sym, "market_cap": cap})

            # Sort by market cap descending
            market_caps.sort(key=lambda x: x["market_cap"], reverse=True)

            # Find rank for the requested symbol
            for rank, item in enumerate(market_caps, start=1):
                if item["symbol"] == symbol:
                    return rank

            return None
        except Exception as e:
            logger.warning(f"Error fetching VN30 price board: {e}")
            return None


@lru_cache(maxsize=1)
def get_company_service(source: str = "VCI") -> CompanyService:
    """Get or create company service instance (thread-safe singleton)."""
    return CompanyService(source=source)
