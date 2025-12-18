# Dashboard Stock Index Cards Implementation

**Date:** 2024-12-18
**Priority:** High
**Status:** Done
**Completed:** 2025-12-18

## Overview

Implement stock market index cards for the dashboard page matching the provided screenshot design. Cards display VN-INDEX, VN30, HNX-INDEX, and UPCOM-INDEX with real-time data visualization.

## Phases

| Phase | Name | Status | File |
|-------|------|--------|------|
| 01 | Design System & Components | Done | [phase-01-design-system.md](./phase-01-design-system.md) |
| 02 | Implementation | Done | [phase-02-implementation.md](./phase-02-implementation.md) |

## Design Specifications (Extracted from Screenshot)

### Color Palette
- **Background:** `#F8FAFC` (slate-50)
- **Card Background:** `#FFFFFF` (white)
- **Card Border:** `#E2E8F0` (slate-200)
- **Text Primary:** `#0F172A` (slate-900)
- **Text Secondary:** `#64748B` (slate-500)
- **Positive/Green:** `#22C55E` (green-500)
- **Negative/Red:** `#EF4444` (red-500)
- **Chart Line Green:** `#22C55E`
- **Chart Line Red:** `#EF4444`

### Typography
- **Font Family:** DM Sans (Google Fonts)
- **Index Name:** 14px, font-medium, slate-500
- **Value:** 28px, font-semibold, slate-900
- **Change:** 14px, font-medium, green-500/red-500

### Spacing
- **Card Padding:** 20px (p-5)
- **Card Gap:** 16px (gap-4)
- **Border Radius:** 12px (rounded-xl)
- **Shadow:** `shadow-sm`

### Layout
- 4-column grid on desktop
- 2-column on tablet
- 1-column on mobile

## Components to Create

1. `card.tsx` - ShadCN Card component
2. `stock-index-card.tsx` - Stock index card with sparkline
3. `sparkline.tsx` - Mini chart component
4. `market-indices.tsx` - Container for all index cards

## Success Criteria

- [ ] Cards match screenshot design
- [ ] Responsive grid layout
- [ ] Sparkline charts render correctly
- [ ] Green/red colors for positive/negative changes
- [ ] Data fetched from API endpoints
