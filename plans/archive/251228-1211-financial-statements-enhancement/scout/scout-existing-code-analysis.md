# Existing Code Analysis - Financial Statements

## Current Implementation

### Frontend
| File | Purpose |
|------|---------|
| `apps/web/src/app/analytics/financial-statements/page.tsx` | Simple page wrapper, renders FinancialStatementsTable |
| `apps/web/src/components/dashboard/financial-statements-table.tsx` | Ranking table with sorting, pagination, filters (exchange) |
| `apps/web/src/hooks/use-financial-statements.ts` | TanStack Query hook for fetching data |
| `apps/web/src/lib/api.ts` | API client with `fetchFinancialStatements()` |

### Backend
| File | Purpose |
|------|---------|
| `apps/api/src/stocks/analytics/router.py` | `/analytics/financial-statements` endpoint |
| `apps/api/src/stocks/analytics/service.py` | Query database for ranked financial data |
| `apps/api/src/stocks/financial/service.py` | Wrapper for vnstock Finance module |
| `apps/api/src/stocks/financial/router.py` | Per-stock financial endpoints |
| `apps/api/src/stocks/schemas/financial.py` | Pydantic models for financial data |
| `apps/api/src/stocks/schemas/analytics.py` | FinancialStatementItem schema |

## Data Flow
```
User → Page → FinancialStatementsTable → useFinancialStatements hook
    → API /analytics/financial-statements → AnalyticsService
    → PostgreSQL financial_statements table (pre-collected weekly)
```

## Key Schemas

### FinancialStatementItem (current)
```python
symbol: str
company_name: Optional[str]
exchange: str
net_profit: Optional[float]
revenue: Optional[float]
profit_margin: Optional[float]  # calculated
eps: Optional[float]
rank: int
```

### vnstock Finance.ratio() fields available
- Profitability: roe, roa, net_profit_margin, gross_margin
- Liquidity: current_ratio, quick_ratio, cash_ratio
- Leverage: de (D/E), interest_coverage
- Efficiency: at (asset turnover), dso, dpo, ccc
- Valuation: pe, pb, ps, eps, bvps, ev_per_ebitda

## Gaps to Fill

1. **No health score calculation** - need scoring service
2. **No trend data** - need historical ratios endpoint
3. **No peer comparison** - need sector-based query
4. **No FCF metrics** - need cash flow calculation
5. **No detailed single-stock view** - need stock detail panel
6. **Charts** - only table exists, no Recharts visualizations

## Extension Points

### Backend
- Add new endpoints in `analytics/router.py`:
  - `GET /{symbol}/health-score`
  - `GET /{symbol}/trend-metrics`
  - `GET /{symbol}/fcf-analysis`
  - `GET /sector/{code}/peers`

### Frontend
- Add new components in `components/dashboard/`:
  - `financial-health-radar.tsx`
  - `financial-trend-charts.tsx`
  - `fcf-analysis-widget.tsx`
  - `peer-comparison-table.tsx`
  - `stock-detail-panel.tsx` (reuse pattern from stock-detail-*)
