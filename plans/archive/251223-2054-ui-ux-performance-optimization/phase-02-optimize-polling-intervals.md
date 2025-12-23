# Phase 2: Optimize Polling Intervals

**Parent Plan:** [plan.md](./plan.md)
**Dependencies:** Phase 1 (for context, but can run independently)

---

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-23 |
| Priority | P1 |
| Effort | 30min |
| Status | completed |

**Goal:** Reduce network load by increasing polling intervals for less volatile data.

---

## Requirements

1. Stagger polling intervals to prevent request bursts
2. Increase intervals for slow-changing data (fund certificates, sector performance)
3. Keep faster intervals for user-focused real-time data

---

## Current vs Proposed Intervals

| Hook | Current staleTime | Current Interval | New staleTime | New Interval | Requests/min |
|------|-------------------|------------------|---------------|--------------|--------------|
| market-indices | 10s | 10s | 15s | 15s | 6 -> 4 |
| vn30-overview | 10s | 10s | 30s | 30s | 6 -> 2 |
| stock-detail | 10s | 10s | 15s | 15s | 6 -> 4 |
| fund-certificates | 10s | 10s | 60s | 60s | 6 -> 1 |
| sector-performance | 60s | 60s | 60s | 120s | 1 -> 0.5 |
| volume-spikes | 2min | 3min | 2min | 3min | no change |
| financial-statements | 1min | 5min | 1min | 5min | no change |

**Total reduction:** ~24 req/min -> ~12 req/min (50% reduction)

---

## Related Files

All hooks already modified in Phase 1 - intervals are part of those changes.

---

## Implementation Steps

Already included in Phase 1 code. This phase is a documentation/verification checkpoint.

### Verify intervals in each hook:

| Hook | staleTime | refetchInterval |
|------|-----------|-----------------|
| use-market-indices.ts | `15 * 1000` | `15 * 1000` |
| use-vn30-overview.ts | `30 * 1000` | `30 * 1000` |
| use-stock-detail.ts | `15 * 1000` | `15 * 1000` |
| use-fund-certificates.ts | `60 * 1000` | `60 * 1000` |
| use-sector-performance.ts | `60 * 1000` | `120 * 1000` |
| use-volume-spikes.ts | `2 * 60 * 1000` | `3 * 60 * 1000` |
| use-financial-statements.ts | `60 * 1000` | `5 * 60 * 1000` |

---

## Success Criteria

- [x] Network tab shows ~50% fewer requests per minute
- [x] Dashboard data still updates regularly
- [x] No visible staleness for user-focused data (indices, stock detail)

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Data feels stale | Low | Keep 15s for main indices |
| User complaints | Low | Add manual refresh button (already exists) |

---

## Rationale

**Fast polling (15s):** Market indices, stock detail - users expect real-time feel
**Medium polling (30s):** VN30 overview - 30 stocks, less volatile aggregate
**Slow polling (60s+):** Fund NAV, sector stats - change slowly, heavy compute
