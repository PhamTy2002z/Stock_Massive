# Code Standards - Stock Massive

Updated: 2026-01-03

## General Principles

- **YAGNI**: Don't build features until needed
- **KISS**: Prefer simple solutions
- **DRY**: Extract common patterns, avoid duplication

---

## Frontend (TypeScript/React)

### File Naming

- Components: `kebab-case.tsx` (e.g., `stock-chart.tsx`)
- Hooks: `use-kebab-case.ts` (e.g., `use-chart-data.ts`)
- Types: `kebab-case.types.ts`
- Utils: `kebab-case.ts`

### Directory Structure

```
components/
├── ui/                    # 25+ ShadCN base components
├── dashboard/             # 35+ feature-specific components
├── layout/                # 6 layout components (+ job-progress-bar, notification-panel)
└── providers/             # 2 context providers
```

### Component Structure

```tsx
// 1. Imports
"use client" // Only when needed

import { useState } from 'react'
import { cn } from "@/lib/utils"

// 2. Types
interface Props {
  symbol: string
  className?: string
}

// 3. Component
export function StockChart({ symbol, className }: Props) {
  // hooks first
  const [data, setData] = useState(null)

  // handlers
  const handleClick = () => {}

  // render
  return (
    <div className={cn("base-classes", className)}>
      {symbol}
    </div>
  )
}
```

### Best Practices

- Use `"use client"` only when needed (hooks, event handlers)
- Prefer Server Components by default
- Extract reusable logic to hooks
- Use `cn()` for conditional class merging
- Follow Modern + Clean design guidelines (see `design-guidelines.md`)

### State Management

- **Local State**: useState for component-level state
- **URL State**: Search params for shareable state (stock symbol)
- **Server State**: TanStack Query v5.90 for data fetching, caching, synchronization
- **Theme State**: next-themes provider
- **Toast Notifications**: Sonner for user feedback

### Loading & Error States

```tsx
// Always handle loading states
if (isLoading) return <StockDetailSkeleton />

// Always handle error states
if (error) return <StockDetailError message={error.message} onRetry={refetch} />

// Empty states
if (!data) return <StockDetailEmpty />
```

### Smooth Loading Pattern (Dashboard Sections)

Use `useQuery` with `keepPreviousData` for smooth section loading without skeleton flash on refetch:

```tsx
// Hook pattern
export function useMarketData() {
  const query = useQuery({
    queryKey: queryKeys.marketData,
    queryFn: fetchMarketData,
    placeholderData: keepPreviousData,
    staleTime: 15 * 1000,
    refetchInterval: 15 * 1000,
  })

  return {
    data: query.data,
    isPending: query.isPending,        // true on first load only
    isFetching: query.isFetching,      // true during any fetch
    isPlaceholderData: query.isPlaceholderData,  // true when showing stale data
    refetch: query.refetch,
  }
}

// Component pattern
function DashboardSection() {
  const { data, isPending, isFetching, isPlaceholderData } = useMarketData()

  // First load - show skeleton
  if (isPending) return <SectionSkeleton />

  return (
    <div className="relative">
      {/* 60% opacity during refetch */}
      <div className={cn(
        "transition-opacity duration-200",
        isPlaceholderData && "opacity-60"
      )}>
        <Content data={data} />
      </div>
      {/* Loading spinner overlay in top-right */}
      {isFetching && !isPending && (
        <div className="absolute top-2 right-2 bg-background/80 backdrop-blur-sm rounded-full p-1.5">
          <RefreshCw className="h-3 w-3 animate-spin text-muted-foreground" />
        </div>
      )}
    </div>
  )
}
```

**Key states:**
- `isPending`: First load (no cached data) - show skeleton
- `isPlaceholderData`: Refetching with stale data - show 60% opacity
- `isFetching && !isPending`: Background refetch - show spinner overlay

**Prefetch optimization (for tabbed sections):**
- Use `usePrefetchAdjacentPeriods` hook to prefetch adjacent tabs on mount
- Add hover-based prefetch with 200ms delay on tab triggers
- Ensures instant tab switching by pre-warming query cache

### Custom Hooks (28 total)

- `use-stock-detail`, `use-market-indices`, `use-vn30-overview`
- `use-sector-performance`, `use-fund-certificates`, `use-market-overview`
- `use-income-statement`, `use-balance-sheet`, `use-cash-flow`
- `use-shareholders`, `use-volume-analysis`
- `use-volume-spikes`, `use-financial-statements`
- `use-health-score`, `use-trend-metrics`, `use-sector-peers`, `use-fcf-analysis`
- `use-jobs-status` (job progress polling)
- `use-sector-historical-performance` (sector historical data)
- `use-foreign-trading`, `use-foreign-snapshot`, `use-prop-trading`
- `use-price-depth`, `use-trading-stats`, `use-order-stats`, `use-intraday-order-stats`
- `use-ratio-summary`, `use-mobile`

---

## Backend (Python/FastAPI)

### File Naming

- Modules: `snake_case.py`
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`

### Module Structure

```python
# router.py - HTTP endpoints
# service.py - Business logic
# repository.py - Data access (if needed)
# schemas.py or schemas/ - Pydantic models
# models.py - SQLAlchemy models
# jobs.py - Scheduled tasks
# jobs_router.py - Job status API endpoints
# intraday_collector.py - Intraday data collection + volume anomaly
# financial_statements_collector.py - Weekly financial data collection
```

### Router Pattern

```python
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/stocks", tags=["stocks"])

@router.get("/{symbol}/detail", response_model=StockDetail)
async def get_stock_detail(symbol: str) -> StockDetail:
    """Get comprehensive stock detail data.

    - **symbol**: Stock ticker (e.g., VCB, ACB, TCB)
    """
    try:
        service = get_service()
        return service.get_stock_detail(symbol)
    except StockServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

### Service Pattern

```python
class StockService:
    """Service layer wrapping vnstock library."""

    def __init__(self):
        self.stock = Vnstock().stock(symbol="VN30", source="VCI")

    def get_stock_detail(self, symbol: str) -> StockDetail:
        """Get comprehensive stock detail."""
        self.stock.symbol = symbol.upper()
        # Fetch and combine data
        return StockDetail(...)
```

### Schema Pattern

```python
from pydantic import BaseModel, Field
from typing import Optional

class StockDetail(BaseModel):
    """Comprehensive stock detail response."""

    symbol: str = Field(..., description="Stock ticker symbol")
    price: float = Field(..., description="Current price")
    change: float = Field(..., description="Price change")
    change_percent: float = Field(..., description="Change percentage")
    volume: Optional[int] = Field(None, description="Trading volume")

    model_config = {"from_attributes": True}
```

### Schema Files (6 total)

- `schemas/analytics.py` - FinancialStatementItem, VolumeSpikeItem
- `schemas/common.py` - Shared types
- `schemas/company.py` - Company, shareholders, officers
- `schemas/financial.py` - Income, balance sheet, cash flow
- `schemas/market.py` - VN30Overview, sectors, fund certificates
- `schemas/price.py` - OHLCV, intraday, volume

### Best Practices

- Type hints on all functions
- Use `async` for I/O operations
- Use `sync_to_async` for synchronous library calls (e.g., vnstock)
- Use dependency injection
- Validate all inputs with Pydantic
- Handle vnstock exceptions gracefully

---

## Git Conventions

### Branch Naming

- `feature/short-description`
- `fix/issue-description`
- `refactor/what-changed`

### Commit Messages

```
type(scope): short description

- feat: new feature
- fix: bug fix
- refactor: code change (no feature/fix)
- docs: documentation
- test: tests
- chore: maintenance
```

Examples:
```
feat(analytics): add volume spikes dashboard with treemap
fix(api): correct rate limit handling in vnstock_wrapper
refactor(frontend): rename top performers to financial statements
docs: update project documentation for December 2025
```

---

## Testing

### Frontend

- Unit: Vitest for utilities/hooks
- Component: React Testing Library
- E2E: Playwright (if needed)

### Backend (9 test files, 18+ tests)

- Unit: pytest
- Integration: pytest + TestClient
- Coverage target: 80%+

```python
# Test example
def test_get_stock_detail():
    response = client.get("/api/v1/stocks/VCB/detail")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "VCB"
```

---

## API Design

### Endpoint Naming

- Use plural nouns: `/stocks`, `/users`
- Use kebab-case for multi-word: `/price-board`, `/volume-spikes`
- Nest resources logically: `/stocks/{symbol}/financials/ratios`
- Analytics under `/analytics/`: `/analytics/volume-spikes`, `/analytics/financial-statements`

### Query Parameters

```python
# Use Query with validation
@router.get("/analytics/financial-statements")
async def get_financial_statements(
    limit: int = Query(50, ge=1, le=100, description="Max results"),
    exchange: Optional[str] = Query(None, description="HOSE, HNX, or UPCOM"),
    year: Optional[int] = Query(None, description="Fiscal year"),
    quarter: Optional[int] = Query(None, ge=1, le=4, description="Quarter 1-4"),
) -> FinancialStatementsResponse:
```

### Response Format

- Always return JSON
- Use consistent field naming (snake_case)
- Include pagination for list endpoints

### Error Handling

```python
# Standard error response
{
    "detail": "Error message",
    "code": "ERROR_CODE"  # Optional
}

# HTTP status codes
# 200 - Success
# 400 - Bad request (validation error)
# 404 - Not found
# 502 - External service error (vnstock)
```

---

## vnstock Integration

### Service Pattern

```python
# stocks/service.py
_stock_service: Optional[StockService] = None

def get_stock_service() -> StockService:
    """Get singleton StockService instance."""
    global _stock_service
    if _stock_service is None:
        _stock_service = StockService()
    return _stock_service

class StockService:
    def __init__(self):
        self.stock = Vnstock().stock(symbol="VN30", source="VCI")

    def get_history(self, symbol: str, start: date, end: date, interval: str):
        self.stock.symbol = symbol.upper()
        df = self.stock.quote.history(start=str(start), end=str(end), interval=interval)
        return [StockPrice(**row) for row in df.to_dict("records")]
```

### Rate Limit Protection

```python
# core/vnstock_wrapper.py
# Wraps vnstock calls with rate limit handling
# Provides graceful degradation on rate limit errors
```

### Data Source

- Primary: VCI (Vietnam)
- Always handle vnstock exceptions gracefully
- Use Redis caching for frequently accessed data

---

## Design Standards

All UI development must follow the **Modern + Clean** design style documented in `design-guidelines.md`:

- HSL color system with CSS variables
- Dark/light theme support
- Skeleton loading patterns
- Consistent component patterns (ShadCN/UI)
- Mobile-first responsive design

---

## Code Review Checklist

- [ ] Follows naming conventions
- [ ] Type hints/TypeScript types complete
- [ ] Error handling implemented
- [ ] Loading states handled
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No console.log/print statements
- [ ] Follows design guidelines
