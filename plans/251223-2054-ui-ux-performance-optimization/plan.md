---
title: "UI/UX Performance Optimization"
description: "Eliminate flicker, reduce polling, memoize components, smooth scrolling"
status: pending
priority: P1
effort: 4h
branch: main
tags: [frontend, performance, ui-ux, tanstack-query]
created: 2025-12-23
---

# UI/UX Performance Optimization

## Problem Summary

| Issue | Impact | Root Cause |
|-------|--------|------------|
| Flicker during refetch | High | No `placeholderData` in queries |
| Aggressive polling | High | 4+ hooks polling 10s = 24 req/min |
| No component memoization | Medium | Table rows re-render on parent update |
| Scrolling not smooth | Low | Missing CSS optimizations |

## Phases Overview

| Phase | Description | Effort | Status |
|-------|-------------|--------|--------|
| [Phase 1](./phase-01-fix-flicker-tanstack-query.md) | Add `placeholderData: keepPreviousData` to all hooks | 1h | pending |
| [Phase 2](./phase-02-optimize-polling-intervals.md) | Reduce polling intervals, disable background refetch | 30min | pending |
| [Phase 3](./phase-03-component-memoization.md) | React.memo table rows + useCallback handlers | 1.5h | pending |
| [Phase 4](./phase-04-css-smooth-scrolling.md) | Smooth scrolling + GPU acceleration CSS | 30min | pending |
| [Phase 5](./phase-05-lazy-load-charts.md) | (Optional) Lazy load Recharts components | 30min | pending |

## Files to Modify

**Hooks (7 files):**
- `apps/web/src/hooks/use-market-indices.ts`
- `apps/web/src/hooks/use-vn30-overview.ts`
- `apps/web/src/hooks/use-stock-detail.ts`
- `apps/web/src/hooks/use-fund-certificates.ts`
- `apps/web/src/hooks/use-sector-performance.ts`
- `apps/web/src/hooks/use-volume-spikes.ts`
- `apps/web/src/hooks/use-financial-statements.ts`

**Components (5 files):**
- `apps/web/src/components/dashboard/vn30-overview-table.tsx`
- `apps/web/src/components/dashboard/financial-statements-table.tsx`
- `apps/web/src/components/dashboard/volume-spike-chart.tsx`
- `apps/web/src/components/dashboard/volume-spike-treemap.tsx`
- `apps/web/src/components/dashboard/stock-index-card.tsx`

**CSS (1 file):**
- `apps/web/src/app/globals.css`

## Success Metrics

- [ ] No visible flicker when data refreshes
- [ ] Smooth scrolling in tables
- [ ] Network requests reduced 50%+
- [ ] React DevTools shows stable component identity

## Dependencies

- TanStack Query v5.90 (already installed)
- React 18+ (already installed)

## Research References

- [TanStack Query Optimization](./research/researcher-01-tanstack-query-optimization.md)
- [React Performance Patterns](./research/researcher-02-react-performance-patterns.md)
