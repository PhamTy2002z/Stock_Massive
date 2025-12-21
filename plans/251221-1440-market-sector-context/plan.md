---
title: "Market & Sector Context"
description: "Stock vs market/sector trend analysis for Deep Dive"
status: pending
priority: P2
effort: 5-7 days
branch: main
tags: [deep-dive, analytics, market-context]
created: 2025-12-21
---

# Market & Sector Context Implementation Plan

## Overview

Add "Market Context" tab to Deep Dive page analyzing if stock moves with/against market and sector trends. Uses daily OHLCV, correlation analysis (5D/20D/60D windows), and market-cap weighted sector benchmarks.

## Context

- **Research Reports**:
  - `/plans/251221-1440-market-sector-context/research/researcher-vnstock-api.md`
  - `/plans/251221-1440-market-sector-context/research/researcher-backend-analysis.md`
  - `/plans/reports/brainstorm-251221-1432-market-sector-context.md`
- **Codebase Docs**: `/docs/codebase-summary.md`, `/docs/system-architecture.md`, `/docs/code-standards.md`

## Key Design Decisions (Finalized)

1. **Daily OHLCV only** - No intraday (reduces API calls, sufficient for context)
2. **Missing sector** → "Unclassified" → Market comparison only
3. **Correlation** - Daily returns (simple/log), windows: 5D/20D/60D
4. **Sector benchmark** - Market-cap weighted avg (no external sector index)
5. **Cache strategy** - EOD batch pipeline → precomputed tables → zero runtime calc

## Architecture

```
EOD Pipeline (15:30 ICT) → Precomputed Tables → API (< 100ms) → Frontend
```

## Implementation Phases

### Phase 1: Database Schema & Models ✅ DONE
- Create 3 precomputed tables: `stock_daily_returns`, `stock_market_metrics`, `sector_daily_benchmark`
- Add SQLAlchemy models
- Alembic migration
- **File**: `phase-1-database.md`

### Phase 2: EOD Pipeline (2 days)
- Batch job for computing metrics (correlation, beta, RS, sector benchmarks)
- APScheduler integration (15:30 ICT daily)
- vnstock data fetching
- **File**: `phase-2-eod-pipeline.md`

### Phase 3: Backend API (1-2 days)
- New endpoint: `GET /stocks/{symbol}/market-context?period=3M`
- Read from precomputed tables
- Response contract with chart data + metrics
- **File**: `phase-3-backend-api.md`

### Phase 4: Frontend Components (2-3 days)
- New "Market Context" tab in Deep Dive
- Relative performance chart (Recharts)
- Correlation/sector cards
- Period selector (1M/3M/6M/1Y)
- **File**: `phase-4-frontend.md`

## Success Criteria

- [ ] EOD pipeline runs daily without errors
- [ ] API response time < 100ms (precomputed data)
- [ ] Chart renders 3 lines (stock, VNINDEX, sector)
- [ ] Correlation metrics accurate (validated against manual calc)
- [ ] Handles "Unclassified" sector gracefully
- [ ] Mobile responsive

## Dependencies

- Existing: vnstock API, PostgreSQL, APScheduler, Recharts
- New: None (uses existing stack)

## Risks

| Risk | Mitigation |
|------|------------|
| vnstock rate limits | Batch requests, cache raw OHLCV |
| Missing sector data | Fallback to market-only comparison |
| Pipeline failure | Alerting, retry logic, manual trigger endpoint |
| Large data payload | Limit to 1Y max, paginate if needed |

## Effort Estimate

- Phase 1: 1 day
- Phase 2: 2 days
- Phase 3: 1-2 days
- Phase 4: 2-3 days
- **Total**: 5-7 days

## Related Files

- Backend: `/apps/api/src/stocks/`
- Frontend: `/apps/web/src/app/analytics/deep-dive/`
- Docs: `/docs/system-architecture.md`

---

## Validation Summary

**Validated:** 2025-12-21
**Questions asked:** 6

### Confirmed Decisions

| Decision | User Choice |
|----------|-------------|
| Data granularity | Daily OHLCV only (no intraday) |
| Pipeline frequency | EOD only at 15:30 ICT |
| Correlation windows | 5D, 20D, 60D |
| Initial backfill | 90 days |
| Sector peers display | Top 3 peers |
| Default period | 3M |

### Action Items

- [x] All recommended options confirmed - no plan changes needed
