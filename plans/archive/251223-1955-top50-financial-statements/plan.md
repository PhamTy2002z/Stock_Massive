---
title: "Top 50 Financial Statements Feature Completion"
description: "Complete exchange filter UI and fix HSX/HOSE naming for Top 50 profits display"
status: completed
priority: P1
effort: 2h
branch: main
tags: [frontend, analytics, feature]
created: 2025-12-23
---

# Top 50 Financial Statements Feature Completion

## Overview

Complete the "Top 50 companies with highest profits from HOSE & HNX (by quarter)" feature at `/analytics/financial-statements`. Backend is ready, data collected. Frontend needs exchange filter UI and HSX/HOSE naming fix.

## Current State

- Data: 1135 Q3/2025 records (396 HSX + 303 HNX + 434 UPCOM)
- Backend: API supports `exchange` filter parameter
- Frontend: Hook/API client support exchange, **UI filter missing**
- Issue: DB stores `HSX` but UI expects `HOSE`

## Phases

| # | Phase | Status | Effort | Link |
|---|-------|--------|--------|------|
| 1 | Backend - HSX/HOSE Normalization | Complete | 30m | [phase-01](./phase-01-backend-exchange-normalization.md) |
| 2 | Frontend - Exchange Filter UI | Complete | 1h | [phase-02-frontend-exchange-filter.md](./phase-02-frontend-exchange-filter.md) |
| 3 | Testing & Verification | Complete | 30m | [phase-03](./phase-03-testing-verification.md) |

## Dependencies

- PostgreSQL database with `financial_statements` table populated
- Redis cache configured (will auto-invalidate)
- Existing ShadCN Select component

## Success Criteria

- [x] Filter dropdown shows: All | HOSE | HNX (no UPCOM)
- [x] Selecting HOSE filters to HSX data correctly
- [x] Default shows Top 50 HOSE+HNX only (excludes UPCOM)
- [x] Exchange badge displays "HOSE" not "HSX"
- [x] Table shows 50 records by default

---

## Validation Summary

**Validated:** 2025-12-23
**Questions asked:** 6

### Confirmed Decisions

| Decision | User Choice |
|----------|-------------|
| Default filter on page load | HOSE+HNX only (exclude UPCOM) |
| UPCOM in dropdown | Exclude - only show All/HOSE/HNX |
| Exchange badge display | Show "HOSE" (not "HSX") |
| Year/quarter selector | Latest quarter only (defer future) |
| Cache strategy | Keep current (1h trading, 24h off-hours) |
| Default records limit | 50 records |

### Action Items

- [x] Plan already aligns with user choices - no changes needed
- [x] Remove period selector from success criteria (deferred)
