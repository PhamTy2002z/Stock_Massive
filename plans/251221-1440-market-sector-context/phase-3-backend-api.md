# Phase 3: Backend API

## Context

- **Plan**: `/plans/251221-1440-market-sector-context/plan.md`
- **Phase 1**: `/plans/251221-1440-market-sector-context/phase-1-database.md`
- **Phase 2**: `/plans/251221-1440-market-sector-context/phase-2-eod-pipeline.md`
- **Design**: `/plans/reports/brainstorm-251221-1432-market-sector-context.md` (Section 15)

## Overview

**Description**: Create REST API endpoint to serve precomputed market context data. Reads from database tables populated by EOD pipeline, returns normalized price series, correlation metrics, and sector context.

**Priority**: P1 (Blocking for Phase 4)

**Status**: Pending

**Effort**: 1-2 days

## Requirements

### Functional
1. Endpoint: `GET /stocks/{symbol}/market-context?period=3M`
2. Return normalized price series (base 100) for stock, VNINDEX, sector
3. Return current metrics (beta, correlation, RS)
4. Return sector context (rank, peers)
5. Return performance summary
6. Support periods: 1M, 3M, 6M, 1Y
7. Handle "Unclassified" sector gracefully (sector data = null)

### Non-Functional
1. Response time < 100ms (precomputed data)
2. Cache response (5 min during trading, 1 hour off-hours)
3. Validate symbol format
4. Error handling for missing data
5. OpenAPI documentation

## Architecture Decisions

### Response Contract

```typescript
interface MarketContextResponse {
  symbol: string
  period: "1M" | "3M" | "6M" | "1Y"

  // Normalized price series (base 100)
  chart_data: {
    date: string
    stock: number      // normalized price
    vnindex: number    // normalized price
    sector: number | null  // normalized price (null if Unclassified)
  }[]

  // Current metrics
  metrics: {
    beta_20d: number | null
    beta_60d: number | null
    correlation_20d: number | null
    correlation_60d: number | null
    rs_market_20d: number | null   // >1 = outperform
    rs_sector_20d: number | null
  }

  // Sector context
  sector: {
    icb_code: string
    icb_name: string
    rank: number           // stock rank in sector
    total: number          // total stocks in sector
    top_peers: {
      symbol: string
      change_pct: number
    }[]
  } | null  // null if Unclassified

  // Performance summary
  performance: {
    stock_return: number   // % change over period
    vnindex_return: number
    sector_return: number | null
    outperform_market: boolean
    outperform_sector: boolean | null
  }

  generated_at: string
}
```

### Period Mapping

| Period | Days | Description |
|--------|------|-------------|
| 1M | 30 | Last month |
| 3M | 90 | Last quarter |
| 6M | 180 | Last half year |
| 1Y | 365 | Last year |

### Caching Strategy
- Use `TradingHoursCache` pattern
- Key: `market_context:{symbol}:{period}`
- TTL: 5 min trading, 1 hour off-hours

## Related Code Files

**Existing**:
- `/apps/api/src/stocks/router.py` - Main router
- `/apps/api/src/stocks/schemas/price.py` - Price schemas
- `/apps/api/src/core/cache.py` - TradingHoursCache
- `/apps/api/src/stocks/market_context_repository.py` - Data access

**New**:
- `/apps/api/src/stocks/schemas/market_context.py` - Response schemas
- `/apps/api/src/stocks/market_context_api_service.py` - API business logic
- `/apps/api/src/stocks/market_context_router.py` - Update with GET endpoint

## Implementation Steps

### Step 1: Define Response Schemas (30 min)

Update `/apps/api/src/stocks/schemas/market_context.py`:

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class ChartDataPoint(BaseModel):
    """Single point in normalized price chart."""
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    stock: float = Field(..., description="Normalized stock price (base 100)")
    vnindex: float = Field(..., description="Normalized VNINDEX (base 100)")
    sector: Optional[float] = Field(None, description="Normalized sector benchmark (base 100)")

class MarketMetrics(BaseModel):
    """Market correlation and beta metrics."""
    beta_20d: Optional[float] = Field(None, description="20-day beta vs VNINDEX")
    beta_60d: Optional[float] = Field(None, description="60-day beta vs VNINDEX")
    correlation_20d: Optional[float] = Field(None, description="20-day correlation vs VNINDEX")
    correlation_60d: Optional[float] = Field(None, description="60-day correlation vs VNINDEX")
    rs_market_20d: Optional[float] = Field(None, description="20-day relative strength vs market")
    rs_sector_20d: Optional[float] = Field(None, description="20-day relative strength vs sector")

class TopPeer(BaseModel):
    """Top performing peer in sector."""
    symbol: str
    change_pct: float

class SectorContext(BaseModel):
    """Sector context information."""
    icb_code: str = Field(..., description="ICB Level 2 code")
    icb_name: str = Field(..., description="Sector name (Vietnamese)")
    rank: int = Field(..., description="Stock rank within sector")
    total: int = Field(..., description="Total stocks in sector")
    top_peers: List[TopPeer] = Field(default_factory=list, description="Top 3 peers")

class PerformanceSummary(BaseModel):
    """Performance comparison summary."""
    stock_return: float = Field(..., description="Stock return % over period")
    vnindex_return: float = Field(..., description="VNINDEX return % over period")
    sector_return: Optional[float] = Field(None, description="Sector return % over period")
    outperform_market: bool = Field(..., description="Stock outperformed market")
    outperform_sector: Optional[bool] = Field(None, description="Stock outperformed sector")

class MarketContextResponse(BaseModel):
    """Market context analysis response."""
    symbol: str = Field(..., description="Stock ticker symbol")
    period: str = Field(..., description="Analysis period (1M, 3M, 6M, 1Y)")
    chart_data: List[ChartDataPoint] = Field(..., description="Normalized price series")
    metrics: MarketMetrics = Field(..., description="Current market metrics")
    sector: Optional[SectorContext] = Field(None, description="Sector context (null if Unclassified)")
    performance: PerformanceSummary = Field(..., description="Performance summary")
    generated_at: str = Field(..., description="Response generation timestamp")

    model_config = {"from_attributes": True}
```

### Step 2: Create API Service Layer (2 hours)

Create `/apps/api/src/stocks/market_context_api_service.py`:

```python
import logging
from datetime import date, timedelta
from typing import Optional, List, Dict
from sqlalchemy.orm import Session

from .market_context_repository import MarketContextRepository
from .schemas.market_context import (
    MarketContextResponse, ChartDataPoint, MarketMetrics,
    SectorContext, PerformanceSummary, TopPeer
)
from vnstock import Listing

logger = logging.getLogger(__name__)

class MarketContextAPIService:
    """Service for market context API endpoints."""

    PERIOD_DAYS = {
        "1M": 30,
        "3M": 90,
        "6M": 180,
        "1Y": 365
    }

    def __init__(self, db: Session):
        self.db = db
        self.repo = MarketContextRepository(db)
        self.listing = Listing()

    def get_market_context(self, symbol: str, period: str) -> MarketContextResponse:
        """Get market context analysis for symbol."""
        symbol = symbol.upper()

        # Validate period
        if period not in self.PERIOD_DAYS:
            raise ValueError(f"Invalid period: {period}. Must be one of {list(self.PERIOD_DAYS.keys())}")

        # Calculate date range
        end_date = date.today()
        start_date = end_date - timedelta(days=self.PERIOD_DAYS[period])

        # Get stock info (for sector classification)
        stock_info = self._get_stock_info(symbol)

        # Fetch data
        stock_returns = self.repo.get_daily_returns(symbol, start_date, end_date)
        vnindex_returns = self.repo.get_daily_returns('VNINDEX', start_date, end_date)
        latest_metric = self.repo.get_latest_metric(symbol)

        if not stock_returns or not vnindex_returns:
            raise ValueError(f"Insufficient data for {symbol}")

        # Get sector data if available
        sector_returns = None
        sector_context = None
        if stock_info and stock_info.get('icb_code2'):
            icb_code = stock_info['icb_code2']
            sector_returns = self.repo.get_sector_benchmark(icb_code, start_date, end_date)
            sector_context = self._build_sector_context(symbol, icb_code, stock_info.get('icb_name2'))

        # Build chart data
        chart_data = self._build_chart_data(stock_returns, vnindex_returns, sector_returns)

        # Build metrics
        metrics = self._build_metrics(latest_metric)

        # Build performance summary
        performance = self._build_performance_summary(
            stock_returns, vnindex_returns, sector_returns
        )

        return MarketContextResponse(
            symbol=symbol,
            period=period,
            chart_data=chart_data,
            metrics=metrics,
            sector=sector_context,
            performance=performance,
            generated_at=date.today().isoformat()
        )

    def _get_stock_info(self, symbol: str) -> Optional[Dict]:
        """Get stock ICB classification."""
        try:
            symbols_df = self.listing.symbols_by_industries()
            stock_row = symbols_df[symbols_df['ticker'] == symbol]

            if stock_row.empty:
                return None

            return {
                'icb_code2': stock_row.iloc[0].get('icb_code2'),
                'icb_name2': stock_row.iloc[0].get('icb_name2')
            }
        except Exception as e:
            logger.warning(f"Failed to get stock info for {symbol}: {e}")
            return None

    def _build_chart_data(self, stock_returns, vnindex_returns, sector_returns) -> List[ChartDataPoint]:
        """Build normalized price chart data."""
        # Create date-aligned dictionary
        data_dict = {}

        # Add stock data
        for r in stock_returns:
            data_dict[r.date] = {
                'date': r.date.isoformat(),
                'stock_price': r.close_price
            }

        # Add VNINDEX data
        for r in vnindex_returns:
            if r.date in data_dict:
                data_dict[r.date]['vnindex_price'] = r.close_price

        # Add sector data if available
        if sector_returns:
            for r in sector_returns:
                if r.date in data_dict:
                    # Reconstruct price from returns (cumulative)
                    data_dict[r.date]['sector_return'] = r.mcap_weighted_return

        # Sort by date
        sorted_dates = sorted(data_dict.keys())

        # Normalize to base 100
        chart_data = []
        stock_base = data_dict[sorted_dates[0]]['stock_price']
        vnindex_base = data_dict[sorted_dates[0]].get('vnindex_price')

        # Calculate sector base (cumulative returns)
        sector_base = 100.0
        sector_cumulative = 100.0

        for date_key in sorted_dates:
            point = data_dict[date_key]

            stock_normalized = (point['stock_price'] / stock_base) * 100
            vnindex_normalized = (point.get('vnindex_price', vnindex_base) / vnindex_base) * 100 if vnindex_base else None

            # Sector: apply daily return to cumulative
            sector_normalized = None
            if 'sector_return' in point:
                sector_cumulative *= (1 + point['sector_return'])
                sector_normalized = sector_cumulative

            chart_data.append(ChartDataPoint(
                date=point['date'],
                stock=round(stock_normalized, 2),
                vnindex=round(vnindex_normalized, 2) if vnindex_normalized else 100.0,
                sector=round(sector_normalized, 2) if sector_normalized else None
            ))

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
            rs_sector_20d=float(latest_metric.rs_sector_20d) if latest_metric.rs_sector_20d else None
        )

    def _build_sector_context(self, symbol: str, icb_code: str, icb_name: str) -> Optional[SectorContext]:
        """Build sector context with rank and peers."""
        try:
            # Get latest metric for rank
            latest_metric = self.repo.get_latest_metric(symbol)

            if not latest_metric or not latest_metric.sector_rank:
                return None

            # Get top peers (simplified - would need price board data)
            top_peers = []  # TODO: Fetch from price board

            return SectorContext(
                icb_code=icb_code,
                icb_name=icb_name or "Unknown",
                rank=latest_metric.sector_rank,
                total=latest_metric.sector_total or 0,
                top_peers=top_peers
            )
        except Exception as e:
            logger.warning(f"Failed to build sector context: {e}")
            return None

    def _build_performance_summary(self, stock_returns, vnindex_returns, sector_returns) -> PerformanceSummary:
        """Build performance comparison summary."""
        # Calculate cumulative returns
        stock_return = self._calculate_cumulative_return([r.return_1d for r in stock_returns if r.return_1d])
        vnindex_return = self._calculate_cumulative_return([r.return_1d for r in vnindex_returns if r.return_1d])

        sector_return = None
        if sector_returns:
            sector_return = self._calculate_cumulative_return([r.mcap_weighted_return for r in sector_returns])

        return PerformanceSummary(
            stock_return=round(stock_return * 100, 2),
            vnindex_return=round(vnindex_return * 100, 2),
            sector_return=round(sector_return * 100, 2) if sector_return else None,
            outperform_market=stock_return > vnindex_return,
            outperform_sector=(stock_return > sector_return) if sector_return else None
        )

    @staticmethod
    def _calculate_cumulative_return(returns: List[float]) -> float:
        """Calculate cumulative return from daily returns."""
        cumulative = 1.0
        for r in returns:
            if r is not None:
                cumulative *= (1 + r)
        return cumulative - 1.0
```

### Step 3: Create API Endpoint (30 min)

Update `/apps/api/src/stocks/market_context_router.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.core.cache import TradingHoursCache
from .market_context_api_service import MarketContextAPIService
from .schemas.market_context import MarketContextResponse
import json

router = APIRouter(prefix="/stocks", tags=["market-context"])

# Cache instance
market_context_cache = TradingHoursCache(
    namespace="market_context",
    ttl_trading_hours=300,  # 5 minutes
    ttl_off_hours=3600      # 1 hour
)

@router.get("/{symbol}/market-context", response_model=MarketContextResponse)
async def get_market_context(
    symbol: str = Path(..., description="Stock ticker symbol"),
    period: str = Query("3M", description="Analysis period", regex="^(1M|3M|6M|1Y)$"),
    db: Session = Depends(get_db)
):
    """Get market context analysis for stock.

    Analyzes if stock is moving with or against market and sector trends.

    - **symbol**: Stock ticker (e.g., VCB, ACB, FPT)
    - **period**: Analysis period (1M, 3M, 6M, 1Y)

    Returns:
    - Normalized price chart (stock vs VNINDEX vs sector)
    - Correlation and beta metrics
    - Sector rank and peers
    - Performance summary
    """
    symbol = symbol.upper()
    cache_key = f"{symbol}:{period}"

    # Check cache
    cached = market_context_cache.get(cache_key)
    if cached:
        return MarketContextResponse(**json.loads(cached))

    try:
        service = MarketContextAPIService(db)
        result = service.get_market_context(symbol, period)

        # Cache result
        market_context_cache.set(cache_key, result.model_dump_json())

        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch market context: {str(e)}")
```

Add to main router in `/apps/api/src/stocks/router.py`:

```python
from .market_context_router import router as market_context_router

# Add after other routers
router.include_router(market_context_router)
```

### Step 4: Add Input Validation (20 min)

Add validation helper in `/apps/api/src/stocks/market_context_api_service.py`:

```python
def _validate_symbol(self, symbol: str):
    """Validate symbol format and existence."""
    if not symbol or len(symbol) > 10:
        raise ValueError("Invalid symbol format")

    # Check if symbol exists
    all_symbols = self.listing.all_symbols()
    if symbol not in all_symbols['ticker'].values:
        raise ValueError(f"Symbol {symbol} not found")
```

### Step 5: Write API Tests (1 hour)

Create `/apps/api/tests/test_market_context_api.py`:

```python
import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_get_market_context_success():
    """Test successful market context retrieval."""
    response = client.get("/api/v1/stocks/VCB/market-context?period=3M")

    assert response.status_code == 200
    data = response.json()

    assert data['symbol'] == 'VCB'
    assert data['period'] == '3M'
    assert len(data['chart_data']) > 0
    assert 'metrics' in data
    assert 'performance' in data

def test_get_market_context_invalid_period():
    """Test invalid period parameter."""
    response = client.get("/api/v1/stocks/VCB/market-context?period=2M")

    assert response.status_code == 422  # Validation error

def test_get_market_context_invalid_symbol():
    """Test invalid symbol."""
    response = client.get("/api/v1/stocks/INVALID/market-context?period=3M")

    assert response.status_code == 400

def test_get_market_context_unclassified_sector():
    """Test stock with no sector classification."""
    # Use a stock known to have no ICB classification
    response = client.get("/api/v1/stocks/XXX/market-context?period=1M")

    if response.status_code == 200:
        data = response.json()
        assert data['sector'] is None
        assert data['performance']['sector_return'] is None

def test_chart_data_normalization():
    """Test chart data is normalized to base 100."""
    response = client.get("/api/v1/stocks/VCB/market-context?period=1M")

    assert response.status_code == 200
    data = response.json()

    # First point should be close to 100
    first_point = data['chart_data'][0]
    assert 99 <= first_point['stock'] <= 101
    assert 99 <= first_point['vnindex'] <= 101

def test_performance_summary_logic():
    """Test performance summary calculations."""
    response = client.get("/api/v1/stocks/VCB/market-context?period=3M")

    assert response.status_code == 200
    data = response.json()

    perf = data['performance']
    assert isinstance(perf['stock_return'], float)
    assert isinstance(perf['vnindex_return'], float)
    assert isinstance(perf['outperform_market'], bool)

    # Logic check
    if perf['stock_return'] > perf['vnindex_return']:
        assert perf['outperform_market'] is True
```

### Step 6: Update OpenAPI Documentation (15 min)

Add examples to endpoint docstring:

```python
@router.get("/{symbol}/market-context", response_model=MarketContextResponse)
async def get_market_context(...):
    """
    ...

    Example Response:
    ```json
    {
      "symbol": "VCB",
      "period": "3M",
      "chart_data": [
        {"date": "2024-09-21", "stock": 100.0, "vnindex": 100.0, "sector": 100.0},
        {"date": "2024-09-22", "stock": 102.5, "vnindex": 101.2, "sector": 101.8}
      ],
      "metrics": {
        "beta_20d": 1.15,
        "correlation_20d": 0.82,
        "rs_market_20d": 1.08
      },
      "sector": {
        "icb_code": "8355",
        "icb_name": "Ngân hàng",
        "rank": 3,
        "total": 27
      },
      "performance": {
        "stock_return": 12.5,
        "vnindex_return": 8.3,
        "outperform_market": true
      }
    }
    ```
    """
```

## Success Criteria

- [ ] Endpoint returns 200 for valid requests
- [ ] Response matches schema contract
- [ ] Chart data normalized to base 100
- [ ] Handles "Unclassified" sector (sector = null)
- [ ] Response time < 100ms (cached)
- [ ] Cache invalidation works correctly
- [ ] OpenAPI docs generated correctly
- [ ] All API tests pass
- [ ] Error messages are clear and actionable

## Testing Checklist

- [ ] Test all periods (1M, 3M, 6M, 1Y)
- [ ] Test valid symbols (VCB, FPT, ACB)
- [ ] Test invalid symbols
- [ ] Test stocks with/without sector classification
- [ ] Test cache hit/miss scenarios
- [ ] Test during/outside trading hours (cache TTL)
- [ ] Load test (100 concurrent requests)
- [ ] Verify response size (< 50KB)

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Missing precomputed data | High | Graceful error, suggest running EOD pipeline |
| Large response payload | Medium | Limit chart data points, pagination if needed |
| Cache stampede | Low | Use cache locking, stagger requests |
| Incorrect calculations | High | Unit tests, validate against manual calc |

## Performance Targets

- Response time: < 100ms (cached), < 500ms (uncached)
- Response size: < 50KB
- Concurrent requests: 100 req/s
- Cache hit rate: > 80%

## Dependencies

- Phase 1 completed (database tables)
- Phase 2 completed (EOD pipeline running)
- TradingHoursCache implemented
- FastAPI, Pydantic installed

## Next Phase

Phase 4: Frontend Components - Build UI to consume this API
