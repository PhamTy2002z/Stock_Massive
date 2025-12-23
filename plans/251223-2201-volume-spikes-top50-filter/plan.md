---
title: "Volume Spikes Top 50 Profitable Filter"
description: "Add tab to filter volume spikes by top 50 most profitable companies"
status: pending
priority: P2
effort: 3h
branch: main
tags: [analytics, volume-spikes, financial-statements, frontend, backend]
created: 2025-12-23
---

# Volume Spikes - Top 50 Profitable Companies Filter

## Overview

Filter volume spikes to only show stocks from Top 50 most profitable companies (based on financial statements). Makes the volume spikes page more useful by filtering out "garbage" penny stocks.

## Problem Statement

Current `/analytics/volume-spikes` shows ALL stocks with unusual volume. Most are low-quality companies. User wants primary view to show only Top 50 profitable companies with volume spikes.

## Solution Summary

**Approach:** Backend filter parameter (Option A from brainstorm)

1. Add `top_profitable_only: bool` param to `/volume-spikes` endpoint
2. Query `FinancialStatement` table for top 50 symbols
3. Filter spikes to only include those symbols
4. Add Data Source Tabs (Top 50 LN | Tất cả) in frontend
5. Default to "Top 50 LN" tab

## UI Design

```
┌─────────────────────────────────────────────────┐
│ Khối lượng đột biến - Top 50 Lợi nhuận          │
│ 2024-12-23 • 12 cổ phiếu                    [↻] │
├─────────────────────────────────────────────────┤
│ [ Top 50 LN ✓ ] [ Tất cả ]  ← DATA SOURCE TABS  │
├─────────────────────────────────────────────────┤
│ Ngưỡng: [≥1.5x ▼]           ← FILTERS          │
├─────────────────────────────────────────────────┤
│ Summary Cards                                   │
├─────────────────────────────────────────────────┤
│ [ Cột ngang | Tròn | Phân cấp | KL vs Giá ]    │
├─────────────────────────────────────────────────┤
│ Industry groups                                 │
└─────────────────────────────────────────────────┘
```

## Implementation Phases

| Phase | Description | Status | Effort |
|-------|-------------|--------|--------|
| [Phase 01](./phase-01-backend-filter.md) | Backend: Add `top_profitable_only` filter | pending | 1h |
| [Phase 02](./phase-02-frontend-tabs.md) | Frontend: Data source tabs + hook updates | pending | 1.5h |
| [Phase 03](./phase-03-testing.md) | Testing + edge cases | pending | 0.5h |

## Key Files

**Backend:**
- `apps/api/src/stocks/analytics/router.py` - Add parameter
- `apps/api/src/stocks/analytics/service.py` - Filter logic
- `apps/api/src/stocks/schemas/analytics.py` - (no changes needed)

**Frontend:**
- `apps/web/src/lib/api.ts` - Add param to API call
- `apps/web/src/hooks/use-volume-spikes.ts` - Update hook
- `apps/web/src/components/dashboard/volume-spike-dashboard.tsx` - Add tabs

## Success Criteria

1. Default tab shows only Top 50 profitable companies with volume spikes
2. "Tất cả" tab shows current behavior (all stocks)
3. Exchange filter hidden in Top 50 mode
4. Empty state handles case when no Top 50 stocks have spikes
5. Cache works correctly with new parameter

## Validation Summary

**Validated:** 2025-12-23
**Questions asked:** 5

### Confirmed Decisions
| Decision | User Choice |
|----------|-------------|
| Top 50 ranking criteria | Net Profit only (use existing `rank` column) |
| Empty state behavior | Show empty state + link to "Tất cả" tab |
| UPCOM in Top 50 mode | Exclude UPCOM |
| Tab placement | Above filters (separate tabs) |
| Cache strategy | Separate cache keys per mode |

### Action Items
- [x] Plan already aligns with all confirmed decisions
- [x] No changes needed

## References

- Brainstorm Report: `plans/reports/brainstorm-251223-2153-volume-spikes-top50-filter.md`
- Codebase Summary: `docs/codebase-summary.md`
- System Architecture: `docs/system-architecture.md`
