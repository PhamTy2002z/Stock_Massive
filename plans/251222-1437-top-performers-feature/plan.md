---
title: "Top 50 Most Profitable Companies Feature"
description: "Dashboard displaying top 50 profitable companies from HOSE+HNX with scheduled batch job"
status: pending
priority: P2
effort: 8h
branch: main
tags: [feature, backend, frontend, analytics, scheduled-job]
created: 2025-12-22
---

# Top 50 Most Profitable Companies Feature

## Overview

Implement a dashboard at `/analytics/top-performers` showing top 50 most profitable companies from the most recent quarter. Uses scheduled batch job to fetch financial data from HOSE+HNX exchanges (excluding UPCOM), stores in PostgreSQL, serves via cached API endpoint.

## Architecture

```
Scheduled Job (weekly, 02:00 ICT)
        ↓
Fetch income_statement() for HOSE+HNX symbols (~700-800)
        ↓
Store in PostgreSQL (top_performers table)
        ↓
API endpoint → Redis cache → Frontend table
```

## Scope

- **Exchanges:** HOSE + HNX only (no UPCOM)
- **Estimated symbols:** ~700-800
- **Batch job time:** ~20-30 min weekly
- **Data:** Net profit, revenue, EPS, profit margin

## Phases

| # | Phase | Status | Effort | Link |
|---|-------|--------|--------|------|
| 1 | Database & Models | Pending | 1.5h | [phase-01](./phase-01-database-models.md) |
| 2 | Scheduled Batch Job | DONE (2025-12-22) | 2.5h | [phase-02-scheduled-batch-job.md](./phase-02-scheduled-batch-job.md) |
| 3 | API Endpoint | DONE (2025-12-22) | 1.5h | [phase-03-api-endpoint.md](./phase-03-api-endpoint.md) |
| 4 | Frontend UI | Pending | 2.5h | [phase-04-frontend-ui.md](./phase-04-frontend-ui.md) |

## Dependencies

- vnstock library (existing)
- Redis cache (existing)
- APScheduler (existing)
- TanStack Query (existing)

## Research Reports

- [Scheduled Jobs Pattern](./research/researcher-scheduled-jobs-report.md)
- [UI Patterns](./research/researcher-ui-patterns-report.md)
- [Brainstorm](../reports/brainstorm-251222-1428-top-performers-feature.md)

## Success Criteria

- Page loads in <500ms
- Data freshness <7 days
- 95%+ symbol coverage for HOSE+HNX
- Zero rate limit errors during batch job

---

## Validation Summary

**Validated:** 2025-12-22
**Questions asked:** 6

### Confirmed Decisions

| Decision | User Choice |
|----------|-------------|
| Schedule frequency | Weekly on Sunday 02:00 ICT |
| Primary ranking metric | Both Net Profit and Margin with UI toggle |
| Exchange scope | HOSE + HNX only (confirmed) |
| Manual trigger endpoint | Yes, add admin endpoint |
| Historical data | Latest quarter only |
| Initial data population | Manual trigger first run |

### Action Items

- [ ] **Phase 2:** Add POST `/api/v1/stocks/analytics/top-performers/collect` endpoint for manual trigger
- [ ] **Phase 4:** Add toggle in UI to switch ranking between Net Profit and Profit Margin
- [ ] **Phase 3:** Simplify DB query - no need to support historical periods
