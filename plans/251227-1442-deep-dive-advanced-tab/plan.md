---
title: "Deep Dive Advanced Tab"
description: "Add Advanced tab with Order Flow, Technical, Money Flow sub-tabs"
status: in_progress
priority: P2
effort: 8h
branch: main
tags: [frontend, backend, deep-dive, analytics]
created: 2025-12-27
---

# Deep Dive Advanced Tab

## Overview
Add "Advanced" tab to Deep Dive page with 3 nested sub-tabs: Order Flow, Technical, Money Flow. Provides professional-grade analytics using VCI data source.

## Architecture
```
Advanced Tab (Lazy Load)
├── Order Flow Sub-tab (Priority)
│   ├── OrderStatsTable (30D)
│   └── PriceDepthWidget (real-time)
├── Technical Sub-tab
│   ├── RatioSummaryCard
│   └── TradingStatsCard
└── Money Flow Sub-tab
    ├── ForeignFlowChart (30D)
    └── PropFlowChart (30D)
```

## Backend Status
| Endpoint | Status | Action |
|----------|--------|--------|
| order-stats | Exists | Use existing |
| foreign-trading | Exists | Use existing |
| prop-trading | Exists | Use existing |
| price-depth | Missing | Create new |
| ratio-summary | Missing | Create new |
| trading-stats | Missing | Create new |

## Frontend Scope
- 1 main tab container
- 3 sub-tabs (lazy loaded)
- 6 hooks (API integration)
- 8 widget components

## Phases

| Phase | File | Effort | Dependencies |
|-------|------|--------|--------------|
| 1 | phase-01-backend-new-endpoints.md | 2h | None |
| 2 | phase-02-frontend-hooks-api.md | 1.5h | Phase 1 |
| 3 | phase-03-frontend-components.md | 3h | Phase 2 |
| 4 | phase-04-integration-testing.md | 1.5h | Phase 3 |

## Success Criteria
- [x] 3 new backend endpoints returning valid data
- [x] 6 frontend hooks with loading/error states
- [ ] Advanced tab with 3 sub-tabs rendering correctly
- [ ] P95 load time <1.5s per sub-tab
- [ ] API tests passing
- [ ] Rate limit errors <0.1%

## Technical Notes
- Data depth: 30 days default
- Cache TTL: price-depth 30s, others 15min
- Lazy load sub-tabs to minimize API calls
- VCI source only (TCBS deprecated)

## Related Files
- Backend: `apps/api/src/stocks/price/`, `apps/api/src/stocks/company/`
- Frontend: `apps/web/src/components/dashboard/`
- Schemas: `apps/api/src/stocks/schemas/`

## Validation Summary

**Validated:** 2025-12-27
**Questions asked:** 4

### Confirmed Decisions
| Decision | Choice | Rationale |
|----------|--------|-----------|
| price-depth caching | 30s trading / 5min off-hours | Matches real-time needs without overwhelming VCI |
| API column handling | Assume & handle errors | More resilient to VCI changes |
| Sub-tab loading | Lazy load on tab switch | Minimizes initial API calls |
| Advanced tab position | Tab 5 (cuối) | Non-disruptive to existing users |

### Action Items
- [x] Plan approved - no changes needed
