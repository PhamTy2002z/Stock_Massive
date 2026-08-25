---
phase: 5
title: "Add workspace navigation and URL state"
status: completed
priority: P1
effort: "1.5d"
dependencies: [1]
---

# Phase 5: Add workspace navigation and URL state

## Overview

Make Bảng giá a navigable workspace instead of one long page while preserving
the app's single-surface shell, draft, sidebar, and inspector.

## Requirements

- `view=board`, five lens values, exchange/horizon/filter/sort URL state.
- Deep links, back/forward, invalid-query defaults, and scroll restoration.
- No full reload or loss of unrelated shell state.
- Accessible desktop tablist and compact mobile selector.

## Architecture

URL owns durable/shareable board state; the shell reducer owns transient chrome.
One typed parser/serializer synchronizes them. Lens changes push history;
high-frequency filter edits replace. Scroll stays in keyed memory.

## Related code files

- Create: `apps/web/src/lib/market-monitor/url-state.ts`
- Create: `apps/web/src/lib/market-monitor/url-state.test.ts`
- Create: `apps/web/src/components/market-monitor/monitor-navigation.tsx`
- Create: matching navigation tests
- Modify: `apps/web/src/components/shell/app-shell.tsx`
- Modify: `apps/web/src/components/shell/shell-state.tsx`
- Modify: `apps/web/src/components/shell/view-board.tsx`

## Implementation steps

1. Write parser, serializer, and history transition tests.
2. Sync deep-linked board view without hydration mismatch.
3. Build sticky lens tablist and shared exchange/horizon/as-of context bar.
4. Preserve filters, sort, inspector, and per-lens scroll.
5. Add mobile view selection without another sidebar/hamburger.
6. Test keyboard, focus, history, invalid URLs, and reload.

## Success criteria

- [x] Direct links open the requested lens and filters.
- [x] Back/forward restores state without closing unrelated context.
- [x] Desktop and mobile expose identical views accessibly.
- [x] Existing shell/chat/news/inspector tests stay green.

## Risk assessment

Two state owners can loop. Keep synchronization in one adapter and prove
canonical equivalent state creates no navigation.
