---
title: "Volume Anomaly Detection"
description: "Detect unusual trading volume by time slot with bar chart visualization"
status: ✅ completed
effort: 8h
priority: high
branch: main
tags: [feature, volume-analysis, charting, intraday]
created: 2025-12-20
validated: 2025-12-20
completed: 2025-12-20
---

# Volume Anomaly Detection - Implementation Plan

## Overview

Implement historical volume anomaly detection feature for intraday trading analysis. Display 5-minute interval volume data with anomaly highlighting using time-series bar chart.

## Validated Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Endpoint | New `/volume-anomalies` | Clean separation, dedicated schema |
| Baseline | User selectable (10/20/30/60 days) | Flexibility for different analysis needs |
| UI Placement | New 4th tab "Khối Lượng" | Clear navigation, dedicated space |
| Chart Interaction | Tooltip on hover only | Simple, performant, sufficient for analysis |

## Objectives

- Detect volume anomalies using ratio-based algorithm (vs configurable baseline)
- Visualize 72 bars per session (09:00-14:55) with anomaly indicators
- Integrate into stock detail page as new 4th tab
- Support historical analysis (end-of-day, not real-time)

## Architecture

### Backend Changes
- Extend `IntradayCollector.analyze_volume()` to return full time-series (72 bars)
- Add anomaly detection logic (volume ratio thresholds: 1.5x, 2x, 3x)
- Update schemas to include anomaly flags and baseline data
- Endpoint already exists: `GET /{symbol}/volume-analysis`

### Frontend Changes
- Install Recharts library for bar chart visualization
- Create `VolumeAnomalyChart` component with shadcn/ui styling
- Add React Query hook `useVolumeAnalysis`
- Integrate as 4th tab in stock detail page OR panel in overview tab

## Phases

1. **Phase 01: Backend API** (3h) - Completed: 2025-12-20
   - Update schemas with anomaly fields
   - Enhance `analyze_volume()` method
   - Test endpoint with sample data

2. **Phase 02: Frontend Chart** (3h) - Completed: 2025-12-20
   - Install recharts dependency
   - Build chart component with anomaly highlighting
   - Add loading/error states

3. **Phase 03: Frontend Integration** (2h) - Completed: 2025-12-20
   - Create React Query hook
   - Add tab/panel to stock detail page
   - Wire up data flow and interactions

## Success Criteria

- [x] API returns 72 bars with anomaly flags for any symbol
- [x] Chart displays volume bars with color-coded anomalies
- [x] Chart shows baseline average line
- [x] Hover tooltips show volume, ratio, and time
- [x] Responsive design works on mobile/desktop
- [x] Loading states and error handling implemented
- [x] Integration follows existing code patterns

## Dependencies

- Existing: `StockIntradayBar` model, `IntradayCollector` service
- New: recharts library (~50KB gzipped)
- Related: Stock detail page, tab system

## References

- Research: researcher-01 (vnstock intraday), researcher-02 (anomaly algorithms)
- Backend: `D:\Stock_Massive\apps\api\src\stocks\intraday_collector.py`
- Frontend: `D:\Stock_Massive\apps\web\src\components\dashboard\stock-detail-tabs.tsx`
- Endpoint: `D:\Stock_Massive\apps\api\src\stocks\price\router.py` (line 106-123)

---

## Completion Summary

**Status:** ✅ Complete
**Completion Date:** 2025-12-20
**Total Effort:** ~8 hours

### Deliverables

**Backend (Phase 01):**
- ✅ Volume anomaly detection API endpoint `/stocks/{symbol}/volume-anomalies`
- ✅ Ratio-based anomaly algorithm (1.5x/2x/3x thresholds)
- ✅ Configurable baseline period (10/20/30/60 days)
- ✅ Full test coverage (test_volume_anomaly_api.py)
- Code review: plans/reports/code-reviewer-251220-1427-volume-anomaly-phase01.md

**Frontend Chart (Phase 02):**
- ✅ VolumeAnomalyChart component with Recharts
- ✅ Color-coded anomaly bars (normal/elevated/high/very_high)
- ✅ Baseline average line overlay
- ✅ Custom tooltips with volume details
- ✅ Loading skeleton and responsive design
- Code review: plans/reports/code-reviewer-251220-1443-volume-anomaly-phase02.md

**Frontend Integration (Phase 03):**
- ✅ React Query hook (useVolumeAnalysis)
- ✅ 4th tab "Khối Lượng" in stock detail page
- ✅ Baseline period selector (10/20/30/60 days)
- ✅ Refresh button with loading state
- ✅ Error handling with retry UI
- Code review: plans/reports/code-reviewer-251220-1454-volume-anomaly-phase03.md

### Quality Metrics

- **Code Quality:** A- (all phases)
- **Security:** ✅ 0 vulnerabilities
- **Performance:** ✅ Optimized (caching, memoization)
- **Test Coverage:** ✅ API tested, manual UI testing complete
- **Build Status:** ✅ TypeScript clean, production build successful

### Known Technical Debt

1. ⚠️ console.error in stock-search-bar.tsx (unrelated to this feature)
2. Consider: React.memo wrapper for VolumeTabContent
3. Consider: Extract magic number 12 to constant in chart

### Next Steps

1. ✅ Deploy to staging
2. Monitor user feedback on anomaly thresholds
3. Consider adding real-time updates (future enhancement)
