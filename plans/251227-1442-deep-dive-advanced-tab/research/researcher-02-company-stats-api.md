# Research: Vnstock VCI Company Stats APIs

**Date:** 2025-12-27
**APIs:** `company.ratio_summary()` & `company.trading_stats()`
**Purpose:** Deep Dive Advanced Tab implementation

---

## 1. API Overview

### 1.1 `company.ratio_summary()`
**Purpose:** Financial ratios (P/E, P/B, ROE, ROA, etc.)
**Source:** VCI data provider
**Usage:**
```python
from vnstock import Vnstock
stock = Vnstock().stock(symbol='VNM', source='VCI')
df = stock.company.ratio_summary()
```

**Current Implementation:** Already used in `apps/api/src/stocks/service.py:208`

### 1.2 `company.trading_stats()`
**Purpose:** Trading statistics (volume, turnover, transactions)
**Source:** VCI data provider
**Usage:**
```python
df = stock.company.trading_stats()
```

**Current Implementation:** Already used in `apps/api/src/stocks/service.py:234`

---

## 2. Data Structure Analysis

### 2.1 `ratio_summary()` Response
Based on existing codebase usage, returns DataFrame with columns:
- **Valuation ratios:** P/E, P/B, P/S
- **Profitability:** ROE, ROA, ROIC
- **Liquidity:** Current ratio, Quick ratio
- **Leverage:** Debt/Equity, Debt/Assets
- **Efficiency:** Asset turnover, Inventory turnover

**Format:** pandas DataFrame → convert to dict/list for API response

### 2.2 `trading_stats()` Response
Expected columns:
- **Volume metrics:** Total volume, Average volume
- **Turnover:** Total value, Average value
- **Transactions:** Number of trades
- **Price movement:** High, Low, Average price
- **Time period:** Daily/Weekly/Monthly aggregates

---

## 3. VCI Source Compatibility

✅ **Both APIs work with VCI source**
- Already implemented in `StockService` class
- Used in `get_stock_detail()` method
- Proven functional in production code

**Evidence:**
```python
# apps/api/src/stocks/service.py:208
ratios = stock.company.ratio_summary()

# apps/api/src/stocks/service.py:234
trading_stats = stock.company.trading_stats()
```

---

## 4. Proposed Pydantic Schemas

### 4.1 RatioSummaryResponse
```python
from pydantic import BaseModel, Field
from typing import Optional

class RatioSummaryResponse(BaseModel):
    # Valuation
    pe: Optional[float] = Field(None, description="Price-to-Earnings ratio")
    pb: Optional[float] = Field(None, description="Price-to-Book ratio")
    ps: Optional[float] = Field(None, description="Price-to-Sales ratio")

    # Profitability
    roe: Optional[float] = Field(None, description="Return on Equity %")
    roa: Optional[float] = Field(None, description="Return on Assets %")
    roic: Optional[float] = Field(None, description="Return on Invested Capital %")

    # Liquidity
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None

    # Leverage
    debt_to_equity: Optional[float] = None
    debt_to_assets: Optional[float] = None
```

### 4.2 TradingStatsResponse
```python
class TradingStatsResponse(BaseModel):
    # Volume
    total_volume: Optional[int] = Field(None, description="Total trading volume")
    avg_volume: Optional[float] = Field(None, description="Average volume")

    # Value
    total_value: Optional[float] = Field(None, description="Total turnover (VND)")
    avg_value: Optional[float] = Field(None, description="Average turnover")

    # Transactions
    total_transactions: Optional[int] = None

    # Price
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    avg_price: Optional[float] = None
```

---

## 5. Implementation Notes

**Already Available:**
- Both APIs already integrated in `StockService`
- No new vnstock integration needed
- Only need to expose via new endpoints

**Required Actions:**
1. Extract existing logic from `get_stock_detail()`
2. Create dedicated endpoints:
   - `GET /stocks/{symbol}/ratio-summary`
   - `GET /stocks/{symbol}/trading-stats`
3. Apply Pydantic schemas for validation
4. Add error handling for missing data

**Performance:**
- APIs return DataFrames (fast)
- Consider caching (TTL: 1 hour for ratios, 5 min for trading stats)
- Use async endpoints for non-blocking

---

## Unresolved Questions

1. **Trading stats time range:** Does API support date range params? Default period?
2. **Ratio summary frequency:** Update frequency from VCI? Daily/Quarterly?
3. **Field mapping:** Need actual API call to confirm exact column names
