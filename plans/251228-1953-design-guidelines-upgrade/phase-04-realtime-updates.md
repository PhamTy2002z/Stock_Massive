# Phase 04: Real-time Update Patterns

## Context Links
- Parent plan: [plan.md](./plan.md)
- Brainstorming: `plans/reports/brainstorm-251228-1941-design-guidelines-upgrade.md`

## Overview
- **Priority:** P2 (Enhanced UX)
- **Effort:** 3h
- **Status:** Pending
- **Description:** Document real-time update patterns including visual change indicators, stale data handling, and optimistic updates.

## Key Insights
- Already have TanStack Query polling (10s for market indices)
- WebSocket optional - can use polling fallback
- Flash animations help users perceive changes quickly
- Stale data indicator builds trust

## Requirements

### Functional
- Document update strategy (polling vs WebSocket vs hybrid)
- Define flash animation for price changes
- Define stale data indicator component
- Document optimistic updates with TanStack Query

### Non-Functional
- Animations respect prefers-reduced-motion
- Flash animations < 1s duration
- Stale threshold configurable

## Architecture

```
apps/web/src/
├── app/globals.css              # Flash animations
├── components/
│   ├── price-cell.tsx           # Flash on change
│   └── data-freshness.tsx       # Live/stale indicator
└── hooks/
    └── use-previous-value.ts    # Track previous for comparison
```

## Related Code Files

| File | Action | Description |
|------|--------|-------------|
| `docs/design-guidelines.md` | Modify | Add "Real-time Update Patterns" section |
| `apps/web/src/app/globals.css` | Modify | Add flash animations |

## Implementation Steps

### Step 1: Document Update Strategy (20min)
1. Define three levels:
   - Critical (market indices): 5-10s polling, WebSocket optional
   - Important (volume spikes): 30s polling
   - Static (company info): manual refresh
2. Create strategy table

### Step 2: Add Flash Animations CSS (20min)
1. Add to globals.css:
   ```css
   @keyframes flash-green {
     0% { background-color: hsl(var(--stock-up) / 0.3); }
     100% { background-color: transparent; }
   }
   @keyframes flash-red {
     0% { background-color: hsl(var(--stock-down) / 0.3); }
     100% { background-color: transparent; }
   }
   .animate-flash-green { animation: flash-green 1s ease-out; }
   .animate-flash-red { animation: flash-red 1s ease-out; }

   @media (prefers-reduced-motion: reduce) {
     .animate-flash-green, .animate-flash-red {
       animation: none;
     }
   }
   ```

### Step 3: Document PriceCell Pattern (30min)
1. Component that tracks previous value
2. Triggers flash animation on change
3. Uses cn() for conditional classes
4. Include full code example

### Step 4: Document Stale Data Indicator (30min)
1. Shows "Live" or "Data may be stale"
2. Color changes (green dot vs yellow dot)
3. Shows time since last update
4. Include full code example

### Step 5: Document Optimistic Updates (30min)
1. TanStack Query mutation with onMutate
2. Cancel outgoing queries
3. Snapshot previous value
4. Optimistic update with setQueryData
5. Rollback on error
6. Include watchlist example

### Step 6: Add to Design Guidelines (30min)
1. Add "Real-time Update Patterns" section
2. Structure:
   - Update strategy table
   - Flash animations (CSS + component)
   - Stale data indicator
   - Optimistic updates pattern
   - TanStack Query configuration

## Todo List
- [ ] Document update strategy levels
- [ ] Add flash animations to CSS
- [ ] Document PriceCell with flash pattern
- [ ] Document DataFreshnessIndicator pattern
- [ ] Document optimistic updates with TanStack Query
- [ ] Add section to design-guidelines.md

## Success Criteria
- [ ] Update strategy documented
- [ ] Flash animations defined in CSS
- [ ] Component patterns with code examples
- [ ] Optimistic update pattern documented

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Too many animations = distracting | Medium | Use subtle colors, short duration |
| WebSocket not available | Low | Polling fallback works well |

## Security Considerations
- None specific to this phase

## Next Steps
- After docs: Implement PriceCell and DataFreshnessIndicator
- Consider: WebSocket backend for critical data
