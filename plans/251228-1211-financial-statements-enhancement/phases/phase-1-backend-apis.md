# Phase 1: Backend APIs

## Context

- **Plan**: [plan.md](../plan.md)
- **Research**: [researcher-02-financial-health-scoring.md](../research/researcher-02-financial-health-scoring.md)
- **Existing**: [scout-existing-code-analysis.md](../scout/scout-existing-code-analysis.md)

## Overview

Create 4 new API endpoints for financial analysis: health score, trend metrics, FCF analysis, and sector peers.

## Key Insights

- vnstock `Finance.ratio()` returns 48 quarters of data - sufficient for all features
- VCI source provides: roe, roa, net_margin, current_ratio, de, dso, pe, pb, ccc
- Cash flow data from `Finance.cash_flow()` for CFO, CapEx
- ICB codes from `Listing().symbols_by_group()` for sector peers

## Requirements

### 1. Health Score Endpoint

`GET /api/v1/stocks/{symbol}/health-score`

Response:
```json
{
  "symbol": "VNM",
  "health_score": 75,
  "dimensions": {
    "profitability": { "score": 85, "metrics": { "roe": 0.18, "roa": 0.12, "net_margin": 0.15 } },
    "liquidity": { "score": 70, "metrics": { "current_ratio": 1.8, "quick_ratio": 1.2 } },
    "leverage": { "score": 80, "metrics": { "de": 0.45, "interest_coverage": 8.5 } },
    "efficiency": { "score": 65, "metrics": { "asset_turnover": 0.9, "dso": 45 } },
    "valuation": { "score": 75, "metrics": { "pe": 15.2, "pb": 3.1 } }
  },
  "f_score": 7,
  "f_score_details": {
    "positive_roa": true,
    "positive_cfo": true,
    "roa_improving": true,
    "accrual_quality": true,
    "leverage_decreasing": false,
    "liquidity_improving": true
  }
}
```

### 2. Trend Metrics Endpoint

`GET /api/v1/stocks/{symbol}/trend-metrics?periods=8`

Response:
```json
{
  "symbol": "VNM",
  "periods": ["Q1/2023", "Q2/2023", ...],
  "revenue": [12500, 13200, ...],
  "net_profit": [3200, 3500, ...],
  "gross_margin": [0.32, 0.33, ...],
  "net_margin": [0.15, 0.16, ...],
  "roe": [0.18, 0.19, ...],
  "roa": [0.12, 0.13, ...],
  "cfo": [4500, 4800, ...],
  "cfi": [-2000, -1800, ...],
  "cff": [-1500, -1200, ...]
}
```

### 3. FCF Analysis Endpoint

`GET /api/v1/stocks/{symbol}/fcf-analysis`

Response:
```json
{
  "symbol": "VNM",
  "period": "Q4/2024",
  "net_income": 3500000000,
  "cfo": 4800000000,
  "capex": -1200000000,
  "fcf": 3600000000,
  "fcf_margin": 0.27,
  "ccc": 45,
  "dso": 30,
  "dio": 60,
  "dpo": 45,
  "market_cap": 150000000000000,
  "fcf_yield": 0.024
}
```

### 4. Sector Peers Endpoint

`GET /api/v1/stocks/analytics/sector-peers?symbol=VNM&limit=5`

Response:
```json
{
  "symbol": "VNM",
  "icb_code": "3577",
  "icb_name": "Thuc pham",
  "peers": [
    { "symbol": "MSN", "roe": 0.12, "roa": 0.08, "pe": 18.5, "pb": 2.8, "market_cap": 120000 },
    { "symbol": "MCH", "roe": 0.15, "roa": 0.10, "pe": 14.2, "pb": 2.2, "market_cap": 80000 },
    ...
  ]
}
```

## Architecture

```
apps/api/src/stocks/
├── financial/
│   ├── router.py          # Add new endpoints
│   ├── service.py          # Existing, extend
│   └── health_scoring.py   # NEW: Scoring algorithms
├── analytics/
│   └── router.py           # Add sector-peers endpoint
└── schemas/
    └── financial.py        # Add new response models
```

## Related Files

| File | Action |
|------|--------|
| `/apps/api/src/stocks/financial/router.py` | Add 3 endpoints |
| `/apps/api/src/stocks/financial/service.py` | Add data fetching methods |
| `/apps/api/src/stocks/financial/health_scoring.py` | **NEW** - Scoring algorithms |
| `/apps/api/src/stocks/analytics/router.py` | Add sector-peers endpoint |
| `/apps/api/src/stocks/schemas/financial.py` | Add response schemas |

## Implementation Steps

### Step 1: Create Pydantic Schemas

**File: `/apps/api/src/stocks/schemas/financial.py`**

Add new response models:

```python
# Health Score Response
class HealthScoreDimension(BaseModel):
    score: int = Field(..., ge=0, le=100)
    metrics: dict[str, Optional[float]]

class FScoreDetails(BaseModel):
    positive_roa: bool
    positive_cfo: bool
    roa_improving: bool
    accrual_quality: bool
    leverage_decreasing: bool
    liquidity_improving: bool

class HealthScoreResponse(BaseModel):
    symbol: str
    health_score: int = Field(..., ge=0, le=100)
    dimensions: dict[str, HealthScoreDimension]
    f_score: int = Field(..., ge=0, le=9)
    f_score_details: FScoreDetails

# Trend Metrics Response
class TrendMetricsResponse(BaseModel):
    symbol: str
    periods: list[str]
    revenue: list[Optional[float]]
    net_profit: list[Optional[float]]
    gross_margin: list[Optional[float]]
    net_margin: list[Optional[float]]
    roe: list[Optional[float]]
    roa: list[Optional[float]]
    cfo: list[Optional[float]]
    cfi: list[Optional[float]]
    cff: list[Optional[float]]

# FCF Analysis Response
class FCFAnalysisResponse(BaseModel):
    symbol: str
    period: str
    net_income: Optional[float]
    cfo: Optional[float]
    capex: Optional[float]
    fcf: Optional[float]
    fcf_margin: Optional[float]
    ccc: Optional[float]
    dso: Optional[float]
    dio: Optional[float]
    dpo: Optional[float]
    market_cap: Optional[float]
    fcf_yield: Optional[float]

# Sector Peers Response
class PeerMetrics(BaseModel):
    symbol: str
    company_name: Optional[str]
    roe: Optional[float]
    roa: Optional[float]
    pe: Optional[float]
    pb: Optional[float]
    market_cap: Optional[float]

class SectorPeersResponse(BaseModel):
    symbol: str
    icb_code: str
    icb_name: str
    peers: list[PeerMetrics]
```

### Step 2: Create Health Scoring Module

**File: `/apps/api/src/stocks/financial/health_scoring.py`** (NEW)

```python
"""Financial health scoring algorithms."""

from typing import Optional
from dataclasses import dataclass

# Benchmark thresholds for Vietnam market
BENCHMARKS = {
    "roe": {"good": 0.15, "excellent": 0.20},
    "roa": {"good": 0.08, "excellent": 0.12},
    "net_margin": {"good": 0.10, "excellent": 0.15},
    "current_ratio": {"good": 1.5, "excellent": 2.0},
    "de": {"good": 1.0, "excellent": 0.5},  # Lower is better
    "pe": {"good": 15, "excellent": 10},  # Lower is better
}

def normalize_score(value: float, benchmark: dict, inverse: bool = False) -> int:
    """Normalize metric to 0-100 score."""
    if value is None:
        return 50  # Neutral

    good = benchmark["good"]
    excellent = benchmark["excellent"]

    if inverse:
        # Lower is better (D/E, P/E)
        if value <= excellent:
            return 100
        elif value <= good:
            return 70 + int(30 * (good - value) / (good - excellent))
        else:
            return max(0, 70 - int(70 * (value - good) / good))
    else:
        # Higher is better (ROE, ROA)
        if value >= excellent:
            return 100
        elif value >= good:
            return 70 + int(30 * (value - good) / (excellent - good))
        else:
            return max(0, int(70 * value / good))

def calculate_dimension_score(metrics: dict, dimension: str) -> int:
    """Calculate score for a dimension from multiple metrics."""
    if dimension == "profitability":
        scores = [
            normalize_score(metrics.get("roe"), BENCHMARKS["roe"]),
            normalize_score(metrics.get("roa"), BENCHMARKS["roa"]),
            normalize_score(metrics.get("net_margin"), BENCHMARKS["net_margin"]),
        ]
    elif dimension == "liquidity":
        scores = [
            normalize_score(metrics.get("current_ratio"), BENCHMARKS["current_ratio"]),
        ]
    elif dimension == "leverage":
        scores = [
            normalize_score(metrics.get("de"), BENCHMARKS["de"], inverse=True),
        ]
    elif dimension == "valuation":
        scores = [
            normalize_score(metrics.get("pe"), BENCHMARKS["pe"], inverse=True),
        ]
    else:
        scores = [50]  # Default neutral

    return int(sum(scores) / len(scores)) if scores else 50

def calculate_f_score(current: dict, prior: dict) -> tuple[int, dict]:
    """Calculate simplified Piotroski F-Score (6 criteria)."""
    details = {
        "positive_roa": (current.get("roa") or 0) > 0,
        "positive_cfo": (current.get("cfo") or 0) > 0,
        "roa_improving": (current.get("roa") or 0) > (prior.get("roa") or 0),
        "accrual_quality": (current.get("cfo") or 0) > (current.get("net_income") or 0),
        "leverage_decreasing": (current.get("de") or 1) < (prior.get("de") or 1),
        "liquidity_improving": (current.get("current_ratio") or 0) > (prior.get("current_ratio") or 0),
    }
    score = sum(1 for v in details.values() if v)
    return score, details

def calculate_health_score(dimensions: dict[str, int]) -> int:
    """Calculate overall health score from dimension scores."""
    weights = {
        "profitability": 0.3,
        "liquidity": 0.2,
        "leverage": 0.2,
        "efficiency": 0.15,
        "valuation": 0.15,
    }
    return int(sum(dimensions.get(k, 50) * v for k, v in weights.items()))
```

### Step 3: Extend Financial Service

**File: `/apps/api/src/stocks/financial/service.py`**

Add methods:

```python
def get_ratio_history(self, symbol: str, periods: int = 8) -> list[dict]:
    """Get historical ratio data for trend analysis."""
    symbol = validate_symbol(symbol)
    finance = Finance(symbol=symbol, source=self.source)
    df = finance.ratio(period="quarter", lang="en", dropna=True)

    if df is None or df.empty:
        return []

    return df.head(periods).to_dict("records")

def get_cash_flow_history(self, symbol: str, periods: int = 8) -> list[dict]:
    """Get historical cash flow data."""
    symbol = validate_symbol(symbol)
    finance = Finance(symbol=symbol, source=self.source)
    df = finance.cash_flow(period="quarter", lang="en", dropna=True)

    if df is None or df.empty:
        return []

    return df.head(periods).to_dict("records")
```

### Step 4: Add Router Endpoints

**File: `/apps/api/src/stocks/financial/router.py`**

Add 3 new endpoints:

```python
@router.get("/{symbol}/health-score", response_model=HealthScoreResponse)
async def get_health_score(symbol: str) -> HealthScoreResponse:
    """Get financial health scorecard for a stock."""
    # Implementation using health_scoring module
    pass

@router.get("/{symbol}/trend-metrics", response_model=TrendMetricsResponse)
async def get_trend_metrics(
    symbol: str,
    periods: int = Query(8, ge=4, le=16)
) -> TrendMetricsResponse:
    """Get trend metrics for charts."""
    pass

@router.get("/{symbol}/fcf-analysis", response_model=FCFAnalysisResponse)
async def get_fcf_analysis(symbol: str) -> FCFAnalysisResponse:
    """Get FCF and cash conversion analysis."""
    pass
```

### Step 5: Add Sector Peers Endpoint

**File: `/apps/api/src/stocks/analytics/router.py`**

```python
@router.get("/sector-peers", response_model=SectorPeersResponse)
async def get_sector_peers(
    symbol: str = Query(..., description="Target stock symbol"),
    limit: int = Query(5, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
) -> SectorPeersResponse:
    """Get peer companies in same ICB sector."""
    # Use Listing().symbols_by_group() to find peers
    pass
```

### Step 6: Add Caching

Apply `TradingHoursCache` to all new endpoints:

```python
health_score_cache = TradingHoursCache(
    key_prefix="stock:health_score:",
    ttl_trading=3600,      # 1 hour
    ttl_off_hours=86400,   # 24 hours
)
```

## Todo

- [x] Create `HealthScoreResponse`, `TrendMetricsResponse`, `FCFAnalysisResponse`, `SectorPeersResponse` schemas
- [x] Create `health_scoring.py` module with scoring algorithms
- [x] Add `get_ratio_history()`, `get_cash_flow_history()` to FinancialService
- [x] Implement `/health-score` endpoint
- [x] Implement `/trend-metrics` endpoint
- [x] Implement `/fcf-analysis` endpoint
- [x] Implement `/sector-peers` endpoint
- [x] Add caching to all endpoints
- [x] Write unit tests for scoring algorithms (28/28 passed)

## Success Criteria

- [x] All 4 endpoints return valid responses
- [x] Health score range: 0-100
- [x] F-Score range: 0-9
- [x] Trend metrics return 8 periods of data
- [x] Sector peers return top 5 by market cap
- [x] API response time < 500ms (cached) - verified

## Phase Status: COMPLETED (2024-12-28)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| VCI rate limit | Medium | High | Aggressive caching, batch calls |
| Missing ratio data | Low | Medium | Return null, handle gracefully |
| CCC null for banks | High | Low | Check industry, return N/A |

## Security Considerations

- Validate symbol input (alphanumeric only)
- Rate limit endpoints (standard: 100/60s)
- No sensitive data exposed
