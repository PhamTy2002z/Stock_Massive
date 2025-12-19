"""Company domain service for company information and stakeholders."""

import logging
from typing import Optional

import pandas as pd
from vnstock import Vnstock

from ..schemas.company import (
    CompanyOverview,
    StockDetail,
    ShareholderItem,
    ShareholdersResponse,
    OfficerItem,
    OfficersResponse,
    InsiderDealItem,
    InsiderDealsResponse,
)
from ..shared import StockServiceError, validate_symbol, safe_float

logger = logging.getLogger(__name__)


class CompanyService:
    """Service for company-related data: overview, shareholders, officers, insider deals."""

    def __init__(self, source: str = "VCI"):
        """Initialize company service with data source."""
        self.source = source

    def get_company_overview(self, symbol: str) -> CompanyOverview:
        """Get company overview information."""
        symbol = validate_symbol(symbol)
        try:
            stock = Vnstock().stock(symbol=symbol, source=self.source)
            overview = stock.company.overview()

            if overview is None or (isinstance(overview, pd.DataFrame) and overview.empty):
                return CompanyOverview(symbol=symbol.upper())

            return self._to_company_overview(symbol, overview)
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
            for _, row in df.iterrows():
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
                        id=str(row.get("id", "")),
                        name=str(row.get("share_holder", "")),
                        shares=float(row.get("quantity", 0)),
                        ownership_pct=float(row.get("share_own_percent", 0)) * 100,
                        update_date=update_date,
                    ))
                except Exception as e:
                    logger.warning(f"Skipping shareholder row due to error: {e}")
                    continue

            return ShareholdersResponse(
                symbol=symbol,
                shareholders=shareholders,
                total_count=len(shareholders),
            )
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
            for _, row in df.iterrows():
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
                        id=str(row.get("id", "")),
                        name=str(row.get("officer_name", "")),
                        position=str(row.get("officer_position", "")),
                        position_short=row.get("position_short_name"),
                        shares=safe_float(row.get("quantity")),
                        ownership_pct=safe_float(row.get("officer_own_percent")) * 100 if row.get("officer_own_percent") else None,
                        update_date=update_date,
                        status=row.get("type"),
                    ))
                except Exception as e:
                    logger.warning(f"Skipping officer row due to error: {e}")
                    continue

            return OfficersResponse(
                symbol=symbol,
                officers=officers,
                total_count=len(officers),
            )
        except Exception as e:
            logger.error(f"Error fetching officers for {symbol}: {e}")
            raise StockServiceError(f"Failed to fetch officers for {symbol}: {e}")

    def get_insider_deals(self, symbol: str) -> InsiderDealsResponse:
        """Get insider trading deals for a stock."""
        symbol = validate_symbol(symbol)
        try:
            stock = Vnstock().stock(symbol=symbol, source=self.source)
            df = stock.company.insider_deals()

            if df is None or df.empty:
                return InsiderDealsResponse(symbol=symbol, deals=[], total_count=0)

            deals = []
            for _, row in df.iterrows():
                try:
                    announce_date = row.get("deal_announce_date")
                    if announce_date is not None and pd.notna(announce_date):
                        if hasattr(announce_date, "strftime"):
                            announce_date = announce_date.strftime("%Y-%m-%d")
                        else:
                            announce_date = str(announce_date)
                    else:
                        announce_date = None

                    deals.append(InsiderDealItem(
                        id=str(row.get("id", "")),
                        name=str(row.get("deal_owner_name", "")),
                        position=row.get("deal_position"),
                        deal_type=row.get("deal_action"),
                        shares=safe_float(row.get("deal_quantity")),
                        price=safe_float(row.get("deal_price")),
                        announce_date=announce_date,
                        relation=row.get("deal_relation"),
                    ))
                except Exception as e:
                    logger.warning(f"Skipping insider deal row due to error: {e}")
                    continue

            return InsiderDealsResponse(
                symbol=symbol,
                deals=deals,
                total_count=len(deals),
            )
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
            short_name=row.get("short_name"),
            exchange=row.get("exchange"),
            industry=row.get("icb_name3") or row.get("icb_name2"),
            issue_share=safe_float(row.get("issue_share")),
            outstanding_share=safe_float(row.get("outstanding_share")),
            description=row.get("company_profile"),
            website=row.get("website"),
            employees=row.get("no_employees"),
            established_year=row.get("established_year"),
        )
