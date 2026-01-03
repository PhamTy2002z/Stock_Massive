# Brainstorm Report: Stock Screener Feature

**Date:** 2026-01-03
**Session:** Feature brainstorming for analysis & decision-making tools

---

## Problem Statement

User wants to add features to Stock_Massive project that support **investment analysis and decision-making** (not trading). The project uses vnstock library with **VCI source only** (TCBS discontinued). Rate limit handling is critical.

---

## Requirements

1. Features must support analysis & decision-making
2. Use VCI data source exclusively
3. Handle rate limits properly
4. Leverage existing codebase infrastructure

---

## Current State Analysis

### Existing Infrastructure
- **vnstock wrapper** with rate limit protection (exponential backoff, max 3 retries)
- **Redis caching** (Upstash, trading-hours-aware TTL)
- **API rate limiting** (100/60s standard, 20/60s heavy)
- **Background jobs** (APScheduler, 17:00 ICT collection)
- **Financial APIs**: ratios, health-score, trend-metrics, sector-peers

### VCI Capabilities (from Context7)
```python
# Financial Data
finance.ratio(period='year/quarter', lang='vi/en')
finance.income_statement(period='year/quarter')
finance.balance_sheet(period='year/quarter')
finance.cash_flow(period='year/quarter')

# Company Data
company.overview()
company.shareholders()
company.news()
company.events()
company.reports()
company.ratio_summary()
```

---

## Evaluated Options

### Option 1: Stock Screener (SELECTED)
**Description:** Filter stocks by financial criteria (P/E, ROE, Growth, etc.)

**Filter Criteria:**
- Valuation: P/E, P/B, EV/EBITDA
- Profitability: ROE, ROA, Net Margin, Gross Margin
- Growth: Revenue growth, Profit growth (YoY)
- Liquidity: Current Ratio, Quick Ratio
- Leverage: Debt/Equity, Debt/Asset
- Dividend: Dividend Yield

**Rate Limit Strategy:**
- Pre-compute ratio data for all stocks (background job)
- Store in PostgreSQL, query locally
- Refresh daily after trading hours (17:00 ICT)

**Pros:**
- Very high value for decision-making
- Leverages existing FinancialService
- Pre-compute eliminates real-time rate limit concerns
- Reference model exists (FinancialStatement)

**Cons:**
- Requires new background job for data collection
- Initial collection takes time (~1500 stocks)

---

### Option 2: Company News/Events (Not Selected)
**Description:** Display news, events, reports from VCI

**Pros:** VCI supports natively, simple implementation
**Cons:** Lower priority vs screener for analysis

---

### Option 3: Valuation Calculator (Not Selected)
**Description:** DCF, Graham Number, PEG Ratio tools

**Pros:** High value, uses existing APIs
**Cons:** Requires complex UI, user input assumptions

---

### Option 4: Financial Comparison (Not Selected)
**Description:** Compare 2-5 stocks side-by-side

**Pros:** Uses existing APIs, radar chart available
**Cons:** UI complexity, lower priority

---

## Final Recommendation: Stock Screener

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Stock Screener Flow                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ Background   │───▶│  PostgreSQL  │◀───│  Screener    │  │
│  │ Job (17:00)  │    │  StockRatio  │    │  API         │  │
│  └──────────────┘    │  Table       │    └──────────────┘  │
│         │            └──────────────┘           │          │
│         ▼                                       ▼          │
│  ┌──────────────┐                      ┌──────────────┐    │
│  │ VCI API      │                      │  Frontend    │    │
│  │ (rate limit  │                      │  Screener UI │    │
│  │  protected)  │                      └──────────────┘    │
│  └──────────────┘                                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Database Model (New)

```python
class StockRatio(Base):
    __tablename__ = "stock_ratios"

    id: int (PK)
    symbol: str (indexed)
    year: int
    quarter: int
    exchange: str
    company_name: str
    icb_code: str
    icb_name: str

    # Valuation
    pe: float
    pb: float
    ps: float
    ev_ebitda: float

    # Profitability
    roe: float
    roa: float
    gross_margin: float
    net_margin: float

    # Growth (YoY)
    revenue_growth: float
    profit_growth: float

    # Liquidity
    current_ratio: float
    quick_ratio: float

    # Leverage
    debt_to_equity: float
    debt_to_asset: float

    # Other
    dividend_yield: float
    market_cap: float
    eps: float
    bvps: float

    updated_at: datetime
```

### API Endpoints (New)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/stocks/screener` | GET | Filter stocks by criteria |
| `/api/v1/stocks/screener/filters` | GET | Get available filter options |

### Query Parameters for Screener

```
GET /api/v1/stocks/screener?
  pe_min=5&pe_max=15&
  roe_min=15&
  exchange=HOSE&
  sort_by=roe&
  sort_order=desc&
  limit=50
```

### Frontend Components (New)

1. **ScreenerPage** (`/screener`)
2. **ScreenerFilters** - Filter panel with sliders/inputs
3. **ScreenerResults** - TanStack Table with results
4. **ScreenerPresets** - Save/load filter presets

---

## Rate Limit Mitigation

| Strategy | Implementation |
|----------|---------------|
| Pre-compute | Background job collects all ratios daily |
| Batch Processing | Process 50 stocks/batch with 2s delay |
| Adaptive Delay | Use `get_adaptive_delay()` from vnstock_wrapper |
| Error Recovery | Skip failed stocks, retry next run |
| Progress Tracking | Use existing job_status_store |

---

## Success Metrics

1. Screener returns results in <500ms (from DB)
2. Daily data refresh completes within 30 minutes
3. Zero rate limit errors during collection
4. Filter combinations work correctly

---

## Implementation Considerations

### Risks
- Initial data collection may take 30-60 minutes
- VCI API changes could break collection
- Some stocks may have incomplete data

### Mitigations
- Run initial collection during off-hours
- Add data validation and null handling
- Log and skip problematic stocks

---

## Next Steps

1. Create implementation plan with `/plan` command
2. Implement database model and migration
3. Build background job for data collection
4. Create screener API endpoints
5. Build frontend UI

---

## Unresolved Questions

None - ready to proceed with implementation planning.
