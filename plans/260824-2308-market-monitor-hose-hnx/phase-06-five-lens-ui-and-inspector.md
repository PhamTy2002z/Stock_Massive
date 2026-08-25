---
phase: 6
title: "Build five lenses and inspector integration"
status: completed
priority: P1
effort: "2.5d"
dependencies: [4, 5]
---

# Phase 6: Build five lenses and inspector integration

## Overview

Implement the complete Market Monitor inside the established Analyst's
Instrument Panel visual system.

## Requirements

- All five lenses, presets, drill-down transitions, and symbol inspector.
- Dense, Vietnamese-first, comparison-friendly display.
- No color-only meaning; honest evidence and coverage labels.
- Responsive loading, empty, stale, partial, disconnected, error, and recovery.

## Architecture

`BoardView` becomes a thin coordinator. Each lens owns one query hook and its
composition. Shared primitives render coverage, metadata, figures,
distributions, trends, tables, and state notices. Inspector stays the detail
destination.

## Related code files

- Create: `apps/web/src/components/market-monitor/overview-lens.tsx`
- Create: `breadth-lens.tsx`, `flow-lens.tsx`, `sector-lens.tsx`, `stocks-lens.tsx`
- Create: `apps/web/src/components/market-monitor/monitor-primitives.tsx`
- Create: `apps/web/src/hooks/use-market-monitor.ts`
- Modify: `apps/web/src/lib/api.ts`, `query-keys.ts`, `query-config.ts`
- Modify: `apps/web/src/components/shell/view-board.tsx`, `inspector.tsx`
- Create/update matching Vitest and Playwright files

## Implementation steps

1. Read Impeccable craft-floor immediately before UI editing.
2. Add strict API types, fetchers, query keys, and one hook per lens.
3. Build shared provenance, coverage, visualization, and state primitives.
4. Build Tổng quan with pulse, breadth, sector, flow, and contextual links.
5. Build Độ rộng, Dòng tiền, and Ngành with textual chart equivalents.
6. Build Cổ phiếu presets, bounded table controls, sticky columns, and mobile rows.
7. Extend inspector with trend, flow, valuation, source, and as-of evidence.
8. Inspect desktop/mobile once, batch-fix, and confirm once.

## Success criteria

- [x] First viewport answers direction, breadth, leadership, and freshness.
- [x] Summary blocks drill into the right lens with context preserved.
- [x] Presets avoid an unreadable mega-table.
- [x] Mobile uses a compact selector and bottom-sheet detail.
- [x] Material states and keyboard paths have tests.

## Risk assessment

Do not recreate a long dashboard inside Tổng quan. Cap it at one curated block
per question and route depth into lenses. Use SVG/CSS; avoid a new chart library.
