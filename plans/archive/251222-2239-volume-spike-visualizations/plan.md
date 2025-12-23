---
title: Volume Spike Dashboard Visualizations Enhancement
description: Add pie chart, treemap, composed chart visualizations and improve ICB sector UI/UX
status: completed
priority: high
effort: medium
branch: feat/volume-spike-visualizations
tags: [frontend, visualization, recharts, ui-ux, volume-spikes]
created: 2025-12-22
---

# Volume Spike Dashboard Visualizations Enhancement

## Overview

Enhance Volume Spikes dashboard with multiple chart types (pie, treemap, composed) and improve ICB sector UI/UX with filtering, sorting, expand/collapse controls.

## Context

- **Current**: Single horizontal bar chart showing top 10 industries
- **Tech**: Next.js 15, Recharts, ShadCN/UI, TailwindCSS
- **Data**: `IndustryVolumeSpikeGroup` with ICB sectors, spike counts, stocks
- **Files**:
  - `/apps/web/src/components/dashboard/volume-spike-dashboard.tsx`
  - `/apps/web/src/components/dashboard/volume-spike-chart.tsx`

## Research Reports

1. `research/researcher-01-chart-types.md` - Chart type analysis
2. `research/researcher-02-icb-ui-ux.md` - ICB sector UX improvements

## Goals

1. Add pie chart for top 10 stocks by spike ratio
2. Add treemap for industry hierarchy visualization
3. Add composed chart for volume vs price correlation
4. Improve ICB sector filtering, sorting, expand/collapse
5. Maintain existing patterns (dynamic colors, custom tooltips, responsive)

## Implementation Phases

### Phase 1: Pie Chart Component (Priority 1)
- Create `volume-spike-pie-chart.tsx`
- Top 10 stocks across all industries by spike_ratio
- Custom tooltip with stock details
- Color palette matching anomaly levels
- **Effort**: Low | **Value**: High

### Phase 2: ICB Sector UI Improvements (Priority 2)
- Add sector filter dropdown
- Add sort selector (spike_count, avg_spike_ratio, alphabetical)
- Add "Expand All / Collapse All" toggle
- Add sector count in header
- Color-code collapsed headers by avg_spike_ratio
- **Effort**: Medium | **Value**: High

### Phase 3: Advanced Charts (Priority 3)
- Create `volume-spike-treemap.tsx` for industry hierarchy
- Create `volume-spike-composed-chart.tsx` for volume vs price
- Add chart selector/tabs for switching views
- **Effort**: Medium | **Value**: Medium

## Success Criteria

- All charts render correctly with real data
- Responsive on mobile/desktop
- Consistent with existing design system
- No performance degradation
- Accessible (keyboard nav, ARIA labels)

## Risks

- Treemap may not work well on mobile (mitigation: hide on small screens)
- Too many charts may overwhelm users (mitigation: use tabs/selector)
- Data transformation complexity (mitigation: use useMemo)

## Validation Summary

**Validated:** 2025-12-22
**Questions asked:** 6

### Confirmed Decisions
- **Chart Layout**: Grid layout - Hiển thị Bar + Pie song song (2 cột)
- **Pie Chart Data**: Top 10 CP toàn thị trường (không theo ngành filter)
- **Phase 3 Scope**: Đầy đủ - Implement cả Treemap + Composed chart
- **ICB Filter**: Single-select dropdown (chọn 1 ngành tại 1 thời điểm)
- **Chart Organization**: Tabs phía trên để switch giữa 4 loại chart
- **Color Scheme**: Dùng anomaly colors (red/orange/yellow) cho nhất quán

### Action Items
- [x] Phase 1: Grid layout 2 cột cho Bar + Pie chart
- [x] Phase 2: Single-select sector filter (không multi-select)
- [x] Phase 3: Implement Tabs component cho 4 chart types
- [x] Phase 3: Treemap ẩn trên mobile, hiện trên desktop

## Next Steps

1. Create feature branch: `feat/volume-spike-visualizations`
2. Implement Phase 1 (pie chart + grid layout)
3. Implement Phase 2 (ICB UI with single-select filter)
4. Implement Phase 3 (treemap + composed chart + tabs)
5. Testing & refinement
