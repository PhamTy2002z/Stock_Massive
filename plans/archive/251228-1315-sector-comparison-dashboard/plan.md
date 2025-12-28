---
title: "Sector Comparison Dashboard"
description: "So sánh cổ phiếu với peers cùng ngành ICB - P/E, P/B, ROE, ROA với premium/discount visualization"
status: done
priority: P1
effort: 6h
branch: main
tags: [analytics, frontend, backend, institutional]
created: 2025-12-28
---

# Sector Comparison Dashboard

## Overview

Thêm chức năng so sánh cổ phiếu với peers cùng ngành ICB Level 3, hiển thị các chỉ số P/E, P/B, ROE, ROA và premium/discount vs sector median.

**Target Users:** Institutional investors
**Data Source:** VCI only (TCBS discontinued)

## Phases

| # | Phase | Status | Effort | Link |
|---|-------|--------|--------|------|
| 1 | Backend Enhancement | Done (2025-12-28) | 2h | [phase-1](./phases/phase-1-backend-enhancement.md) |
| 2 | Frontend UI Components | Done (2025-12-28) | 2.5h | [phase-2](./phases/phase-2-frontend-components.md) |
| 3 | Integration & Testing | Done (2025-12-28) | 1.5h | [phase-3](./phases/phase-3-integration-testing.md) |

## Dependencies

- Backend: Existing `sector_peers` endpoint + `TradingHoursCache`
- Frontend: ShadCN/UI components, TanStack Query hooks
- Research: [UI Patterns](./research/researcher-01-ui-patterns.md), [Rate Limit Strategy](./research/researcher-02-rate-limit-caching.md)

## Key Decisions

1. **VCI Rate Limit:** 60 req/min - cache 4h trading, 24h off-hours
2. **UI Pattern:** Horizontal scroll table with sticky first column
3. **Color Coding:** 5-level diverging palette (green→gray→red)
4. **Peer Limit:** 10 peers max per request

## Success Criteria

- [ ] API response < 2s with cache
- [ ] Cache hit ratio > 80% during trading hours
- [ ] Mobile responsive (horizontal scroll)
- [ ] WCAG AA color contrast

## Related Files

**Backend:**
- `apps/api/src/stocks/financial/service.py` - get_sector_peers()
- `apps/api/src/stocks/schemas/financial.py` - SectorPeersResponse

**Frontend:**
- `apps/web/src/components/dashboard/advanced-tab/` - New subtab location

---

## Validation Summary

**Validated:** 2025-12-28
**Questions asked:** 5

### Confirmed Decisions

| Decision | User Choice |
|----------|-------------|
| Premium metric in "vs Sector" column | P/E only |
| Number of peers displayed | 10 peers |
| Mobile UX pattern | Horizontal scroll |
| Additional metrics | None (keep P/E, P/B, ROE, ROA) |
| Cache TTL | 4h trading, 24h off-hours |

### Action Items

- [x] All decisions align with plan - no changes needed
- [x] Plan ready for implementation
