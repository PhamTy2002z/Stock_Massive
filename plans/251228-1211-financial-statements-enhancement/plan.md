---
title: "Financial Statements Enhancement"
description: "Add health scorecard, trend charts, peer comparison, and FCF analysis to Financial Statements page"
status: in-progress
priority: P1
effort: 16h
branch: main
tags: [financial, analytics, recharts, vnstock, vci]
created: 2024-12-28
---

# Financial Statements Enhancement

## Overview

Enhance the existing Financial Statements page (`/analytics/financial-statements`) with advanced visualization and analysis features using vnstock VCI data source.

**Current State:**
- Simple ranking table with net profit, revenue, margin, EPS
- Pre-collected weekly data from HOSE + HNX

**Target State:**
- Financial Health Scorecard with Radar chart (5 dimensions)
- Trend Analysis Charts (Revenue/Profit, Margins, ROE/ROA, Cash Flow)
- Peer Comparison with sector peers
- FCF & Cash Conversion analysis

## Research Summary

| Report | Key Findings |
|--------|--------------|
| [brainstorm-summary.md](research/brainstorm-summary.md) | 4 feature groups, VCI data 100% feasible |
| [researcher-01-recharts-financial-viz.md](research/researcher-01-recharts-financial-viz.md) | ComposedChart, RadarChart patterns |
| [researcher-02-financial-health-scoring.md](research/researcher-02-financial-health-scoring.md) | Piotroski F-Score + DuPont analysis |
| [scout-existing-code-analysis.md](scout/scout-existing-code-analysis.md) | Current code structure, extension points |

## Phases

| Phase | Title | Effort | Description |
|-------|-------|--------|-------------|
| 1 | [Backend APIs](phases/phase-1-backend-apis.md) | 5h | Health score, trend metrics, FCF, peer endpoints |
| 2 | [Health Scorecard UI](phases/phase-2-health-scorecard-ui.md) | 3h | Radar chart + score breakdown card |
| 3 | [Trend Charts](phases/phase-3-trend-charts.md) | 4h | 4 chart types: Revenue/Profit, Margins, ROE/ROA, Cash Flow |
| 4 | [Peer Comparison & FCF](phases/phase-4-peer-fcf.md) | 3h | Sector peers table, FCF waterfall |
| 5 | [Integration & Testing](phases/phase-5-integration-testing.md) | 1h | Page layout, E2E tests |

## Architecture

```
                          ┌─────────────────────────────────────┐
                          │   /analytics/financial-statements   │
                          │                                     │
┌─────────────────────────┼─────────────────────────────────────┼─────────────────────────┐
│                         │                                     │                         │
│  ┌───────────────────┐  │  ┌───────────────────────────────┐  │  ┌───────────────────┐  │
│  │ Health Scorecard  │  │  │     Trend Charts Tabs         │  │  │  Peer Comparison  │  │
│  │  (Radar + Score)  │  │  │ Revenue|Margin|ROE|Cash Flow  │  │  │  (Heatmap Table)  │  │
│  └───────────────────┘  │  └───────────────────────────────┘  │  └───────────────────┘  │
│                         │                                     │                         │
│  ┌───────────────────┐  │                                     │  ┌───────────────────┐  │
│  │  FCF Waterfall    │  │                                     │  │  Existing Table   │  │
│  │  + CCC Display    │  │                                     │  │  (Rankings)       │  │
│  └───────────────────┘  │                                     │  └───────────────────┘  │
│                         │                                     │                         │
└─────────────────────────┴─────────────────────────────────────┴─────────────────────────┘

API Endpoints:
- GET /api/v1/stocks/{symbol}/health-score      → HealthScoreResponse
- GET /api/v1/stocks/{symbol}/trend-metrics     → TrendMetricsResponse
- GET /api/v1/stocks/{symbol}/fcf-analysis      → FCFAnalysisResponse
- GET /api/v1/stocks/analytics/sector-peers     → SectorPeersResponse
```

## Data Flow

1. User selects stock from ranking table
2. Stock detail panel opens (slide-over or modal)
3. Panel fetches 4 endpoints in parallel
4. Charts render with cached data (TTL: 1h trading, 24h off-hours)

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Scoring algorithm | Simplified Piotroski (6 criteria) | Binary criteria, works well for VN market |
| Trend periods | 8 quarters | Balance between data richness and API calls |
| Peer selection | Top 5 by market cap in same ICB3 | Relevant, not overwhelming |
| FCF calculation | CFO - CapEx | Standard definition, data available |
| **Color palette** | **Orange accent per Design Guidelines** | **Consistent with project design system** |

## Design Guidelines Compliance

All UI components follow `/docs/design-guidelines.md`:

| Guideline | Implementation |
|-----------|----------------|
| **Color**: Orange accent | Primary colors use `--accent-orange`, not hardcoded colors |
| **KPI Requirements** | All cards show time range, benchmark, delta vs prior |
| **Feedback State** | Last Updated timestamp + Refresh button |
| **Loading State** | Skeleton loading mandatory |
| **Error State** | Clear message + Retry button |
| **Drill-down Pattern** | Row click opens Sheet with detail |

## Rate Limit Strategy

- **Caching**: 1h during trading, 24h off-hours
- **Batch fetching**: Single API call for 8-quarter trend data
- **Stale-while-revalidate**: Show cached data while fetching fresh

## Success Criteria

- [ ] Health scorecard renders with 5-dimension radar chart
- [ ] Trend charts show 8 quarters of data
- [ ] Peer comparison shows top 5 sector peers
- [ ] FCF waterfall displays Net Income -> CFO -> FCF
- [ ] All charts responsive (mobile-friendly)
- [ ] API response time < 500ms (cached)

## Risks

| Risk | Mitigation |
|------|------------|
| VCI rate limiting | Aggressive caching, 150ms delay between calls |
| CCC null for banks | Handle gracefully, show "N/A" |
| Large data payload | Limit to 8 quarters, compress responses |

## Validation Summary

**Validated:** 2025-12-28
**Questions asked:** 6

### Confirmed Decisions
- **UI Pattern:** Sheet (slide-over) - Panel trượt từ phải khi click row
- **Score Weights:** Default (Profitability 30%, Liquidity/Leverage 20%, Efficiency/Valuation 15%)
- **Trend Periods:** 8 quarters - cân bằng data richness và performance
- **Peer Count:** Top 5 công ty cùng ngành ICB3
- **Bank CCC:** Show "N/A - Không áp dụng cho ngân hàng/tài chính"
- **FCF Waterfall:** Simple (4 bars) - Net Income → CFO → CapEx → FCF

### Action Items
- [x] All decisions confirmed, no plan changes required
