---
title: "Deep Dive Tab Improvements"
description: "Add Money Flow tab, News & Events tab, and UI improvements to analytics deep-dive page"
status: pending
priority: P2
effort: 12h
branch: main
tags: [frontend, backend, api, analytics]
created: 2025-12-24
---

# Deep Dive Tab Improvements

## Overview

Enhance `/analytics/deep-dive` page with new tabs and UI improvements:
- **Tab "Dòng Tiền"**: Foreign + Proprietary trading (VCI source)
- **Tab "Tin Tức & Sự Kiện"**: News + Dividends + Insider Deals
- **UI**: Quick Stats Bar, Sticky Tabs, Mobile dropdown overflow

## Context

- **Brainstorm**: [brainstorm-251224-2348-deep-dive-tab-improvements.md](../reports/brainstorm-251224-2348-deep-dive-tab-improvements.md)
- **Research**:
  - [researcher-01-vnstock-money-flow-apis.md](./research/researcher-01-vnstock-money-flow-apis.md)
  - [researcher-02-vnstock-news-events-apis.md](./research/researcher-02-vnstock-news-events-apis.md)

## Key Decisions

| Decision | Choice |
|----------|--------|
| Money Flow | Gộp Foreign + Prop Trading trong 1 tab |
| News Tab | Full (News + Dividends + Insider Deals) |
| Mobile Tabs | Dropdown overflow (4 visible + More) |
| Data Depth | 30 days |
| Sticky | Quick Stats Bar + Tabs Bar |
| Fetch | Lazy Load on tab switch |

## Phases

| # | Phase | Status | Effort | Link |
|---|-------|--------|--------|------|
| 1 | Backend: Trading & News APIs | Pending | 3h | [phase-01](./phase-01-backend-trading-news-apis.md) |
| 2 | Frontend: Money Flow Tab | Pending | 3h | [phase-02](./phase-02-frontend-money-flow-tab.md) |
| 3 | Frontend: News & Events Tab | Pending | 3h | [phase-03](./phase-03-frontend-news-events-tab.md) |
| 4 | UI: Sticky Elements & Mobile | Pending | 3h | [phase-04](./phase-04-ui-sticky-mobile.md) |

## Dependencies

- vnstock >= 3.0.0 (VCI source)
- Existing rate limit infrastructure (100/60s standard)
- Redis cache (Upstash)
- Recharts for charts

## Validation Summary

**Validated:** 2025-12-25
**Questions asked:** 4

### Confirmed Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Order-stats endpoint | Backend only, frontend deferred | Build API now, add UI later if needed |
| VCI API error handling | Graceful degradation | Return cached stale data on API failure |
| Phase execution order | Sequential as planned | Backend → Money Flow → News → UI |
| Testing approach | Manual only | No unit tests for this iteration |

### Action Items

- [ ] Ensure `order-stats` endpoint in Phase 01 is built but not exposed in frontend
- [ ] Implement stale-while-revalidate caching pattern for VCI API failures
- [ ] Document manual testing checklist for QA

## Success Criteria

- [ ] All 5 new endpoints working with proper caching
- [ ] Money Flow tab with charts rendering correctly
- [ ] News tab with 3 sections (news, dividends, insider deals)
- [ ] Sticky elements working on scroll
- [ ] Mobile dropdown overflow for 6 tabs
- [ ] P95 load time < 2s for all tabs
