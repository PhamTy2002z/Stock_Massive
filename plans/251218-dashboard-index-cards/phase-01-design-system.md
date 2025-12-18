# Phase 01: Design System & Components

**Status:** Done
**Completed:** 2025-12-18
**Priority:** High

## Context

Create base components following ShadCN patterns and extracted design specifications.

## Requirements

### 1. Card Component (ShadCN)
- Base card with variants
- Follows existing CSS variable pattern
- File: `apps/web/src/components/ui/card.tsx`

### 2. Stock Index Card Component
- Displays: index name, value, change, percentage, sparkline
- Props: symbol, name, value, change, changePercent, data[]
- File: `apps/web/src/components/dashboard/stock-index-card.tsx`

### 3. Sparkline Component
- Lightweight SVG-based mini chart
- No external library (keep bundle small)
- Props: data[], color, width, height
- File: `apps/web/src/components/ui/sparkline.tsx`

## Implementation Steps

1. Add ShadCN Card component
2. Create Sparkline SVG component
3. Create StockIndexCard component
4. Add Google Font (DM Sans) to layout

## Related Files

- `apps/web/src/app/globals.css`
- `apps/web/src/app/layout.tsx`
- `apps/web/tailwind.config.js`
