---
title: "Overview Page UX Enhancement"
description: "Add Market Breadth, Top Movers, Foreign Flow widgets with collapsible grid layout"
status: in_progress
priority: P2
effort: 8h
branch: main
tags: [frontend, backend, api, ux]
created: 2025-12-28
---

# Overview Page UX Enhancement

## Overview

Enhance the Overview page with 4 new data widgets (Market Breadth, Top Movers, Foreign Flow, Top Volume) using a single aggregate API endpoint and collapsible grid layout. Target: Day traders + Swing traders.

## Phases

| # | Phase | Status | Effort | Link |
|---|-------|--------|--------|------|
| 1 | Backend API | Done | 3h | [phase-01](./phase-01-backend-api.md) |
| 2 | Frontend Components | Done | 3h | [phase-02](./phase-02-frontend-components.md) |
| 3 | Integration & Polish | Pending | 2h | [phase-03](./phase-03-integration-polish.md) |

## Dependencies

- vnstock >= 3.0.0 (VCI source only, TCBS deprecated)
- Existing TradingHoursCache infrastructure
- ShadCN/UI Collapsible component (already exists)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     FRONTEND                            │
│  useMarketOverview() → 1 API call → 10s auto-refresh    │
└───────────────────────────┬─────────────────────────────┘
                            │ GET /api/v1/stocks/market-overview
                            ▼
┌─────────────────────────────────────────────────────────┐
│                     BACKEND                             │
│  MarketOverviewService → Sequential VCI calls (100ms)   │
│  TradingHoursCache → 10s trading / 5min off-hours       │
└─────────────────────────────────────────────────────────┘
```

## Key Decisions

1. **Single Aggregate Endpoint** - Safe rate limit, simple frontend
2. **VCI Source Only** - TCBS deprecated per user requirement
3. **Collapsible Sections** - localStorage persistence
4. **10s Refresh All** - Consistent with existing market indices

## Success Criteria

- [ ] Initial load time < 2s
- [ ] API response time < 500ms (cached)
- [ ] 0% rate limit errors
- [ ] All 4 widgets render correctly
- [ ] Collapsed state persists across sessions

## Related Reports

- [Brainstorm Report](../reports/brainstorm-251228-2011-overview-ux-enhancement.md)

## Validation Summary

**Validated:** 2025-12-28
**Questions asked:** 6

### Confirmed Decisions

| Decision | User Choice |
|----------|-------------|
| Market Breadth scope | VN30 only (faster, representative) |
| VCI call delay | 100ms between calls |
| Error handling | Partial response (graceful degradation) |
| Collapsible default | All expanded |
| Keyboard shortcuts | Not needed (keep simple) |
| Test coverage | Backend only |

### Action Items

- [x] Plan already uses VN30 for breadth - confirmed correct
- [x] Plan already uses 100ms delay - confirmed correct
- [x] Plan already returns partial data on error - confirmed correct
- [ ] Remove keyboard shortcuts mention from Key Decisions section
