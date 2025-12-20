---
title: "Volume Anomaly Detection"
description: "Detect unusual trading volume by time slot with bar chart visualization"
status: in-progress
effort: 8h
priority: high
branch: main
tags: [feature, volume-analysis, charting, intraday]
created: 2025-12-20
validated: 2025-12-20
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

3. **Phase 03: Frontend Integration** (2h)
   - Create React Query hook
   - Add tab/panel to stock detail page
   - Wire up data flow and interactions

## Success Criteria

- [ ] API returns 72 bars with anomaly flags for any symbol
- [ ] Chart displays volume bars with color-coded anomalies
- [ ] Chart shows baseline average line
- [ ] Hover tooltips show volume, ratio, and time
- [ ] Responsive design works on mobile/desktop
- [ ] Loading states and error handling implemented
- [ ] Integration follows existing code patterns

## Dependencies

- Existing: `StockIntradayBar` model, `IntradayCollector` service
- New: recharts library (~50KB gzipped)
- Related: Stock detail page, tab system

## References

- Research: researcher-01 (vnstock intraday), researcher-02 (anomaly algorithms)
- Backend: `D:\Stock_Massive\apps\api\src\stocks\intraday_collector.py`
- Frontend: `D:\Stock_Massive\apps\web\src\components\dashboard\stock-detail-tabs.tsx`
- Endpoint: `D:\Stock_Massive\apps\api\src\stocks\price\router.py` (line 106-123)
