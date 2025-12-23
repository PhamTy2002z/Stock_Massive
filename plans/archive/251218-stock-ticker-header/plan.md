# Stock Ticker Header Implementation

**Date**: 2025-12-18
**Status**: ✅ Completed
**Priority**: High

## Overview

Implement stock ticker header component displaying selected stock symbol with price info, placed below "Chỉ số thị trường" section.

## Design Specifications (from screenshot)

### Typography
- **Stock Symbol**: 24px, font-bold, text-foreground (e.g., "VNM")
- **Company Name**: 14px, font-normal, text-muted-foreground
- **Price**: 28px, font-semibold, tabular-nums
- **Change**: 14px, font-medium, green-500/red-500

### Colors
- Background: card (hsl(var(--card)))
- Border: border (hsl(var(--border)))
- Positive: #22c55e (green-500)
- Negative: #ef4444 (red-500)

### Layout
- Card with rounded-xl border
- Padding: 20px (p-5)
- Flex row layout
- Gap between sections: 16px

### Component Structure
```
[Stock Symbol + Company Name] | [Price + Change] | [Volume Info]
```

## Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 01 | Create stock-ticker-header component | ✅ Completed |
| 02 | Integrate into dashboard page | ✅ Completed |

## Files to Create/Modify

- `apps/web/src/components/dashboard/stock-ticker-header.tsx` (new)
- `apps/web/src/app/page.tsx` (modify)

## Completion Notes
- Component implemented at `apps/web/src/components/dashboard/stock-ticker-header.tsx`
- Features: price flash animation, Vietnamese number formatting, responsive layout
- Exported via `apps/web/src/components/dashboard/index.ts`
