"""Schemas module with backward compatibility re-exports."""

# Common
from .common import ErrorResponse, HistoryParams

# Price domain
from .price import (
    StockPrice,
    IntradayTick,
    PriceBoardItem,
    MarketIndexItem,
    IntradayBarCreate,
    IntradayBar,
    IntradayCollectionResult,
    VolumeTimePeriod,
    VolumeAnalysisResponse,
)

# Company domain
from .company import (
    CompanyOverview,
    StockSymbol,
    StockDetail,
    ShareholderItem,
    ShareholdersResponse,
    OfficerItem,
    OfficersResponse,
    InsiderDealItem,
    InsiderDealsResponse,
)

# Financial domain
from .financial import (
    FinancialRatio,
    IncomeStatementItem,
    IncomeStatementRow,
    IncomeStatementResponse,
    BalanceSheetItem,
    BalanceSheetRow,
    BalanceSheetResponse,
    CashFlowRow,
    CashFlowResponse,
)

# Market domain
from .market import (
    SectorPerformanceItem,
    SectorPerformanceResponse,
    FundCertificateItem,
    FundCertificatesResponse,
)

__all__ = [
    # Common
    "ErrorResponse",
    "HistoryParams",
    # Price
    "StockPrice",
    "IntradayTick",
    "PriceBoardItem",
    "MarketIndexItem",
    "IntradayBarCreate",
    "IntradayBar",
    "IntradayCollectionResult",
    "VolumeTimePeriod",
    "VolumeAnalysisResponse",
    # Company
    "CompanyOverview",
    "StockSymbol",
    "StockDetail",
    "ShareholderItem",
    "ShareholdersResponse",
    "OfficerItem",
    "OfficersResponse",
    "InsiderDealItem",
    "InsiderDealsResponse",
    # Financial
    "FinancialRatio",
    "IncomeStatementItem",
    "IncomeStatementRow",
    "IncomeStatementResponse",
    "BalanceSheetItem",
    "BalanceSheetRow",
    "BalanceSheetResponse",
    "CashFlowRow",
    "CashFlowResponse",
    # Market
    "SectorPerformanceItem",
    "SectorPerformanceResponse",
    "FundCertificateItem",
    "FundCertificatesResponse",
]
