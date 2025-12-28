# Phase 02: Data Density Modes

## Context Links
- Parent plan: [plan.md](./plan.md)
- Brainstorming: `plans/reports/brainstorm-251228-1941-design-guidelines-upgrade.md`

## Overview
- **Priority:** P1 (Core UX for pro users)
- **Effort:** 3h
- **Status:** Pending
- **Description:** Add density modes (compact/comfortable/spacious) documentation and implementation pattern. Pro-first: default to compact.

## Key Insights
- Pro traders need high data density to see more stocks at once
- Retail investors prefer spacious layouts for readability
- CSS variables approach = simpler, no component refactoring
- React Context approach = more flexible, can affect non-CSS things

## Requirements

### Functional
- Document 3 density modes with specific values
- Define CSS variables for density
- Create DensityProvider pattern
- Define useDensity hook pattern
- Document density-aware component pattern

### Non-Functional
- Mode switch should be instant (no loading)
- Persist preference to localStorage
- Support keyboard toggle

## Architecture

```
providers/
└── density-provider.tsx    # New provider

lib/
└── density-config.ts       # New config file

components/layout/
└── density-toggle.tsx      # New toggle component
```

## Related Code Files

| File | Action | Description |
|------|--------|-------------|
| `docs/design-guidelines.md` | Modify | Add "Data Density Modes" section |
| `apps/web/src/app/globals.css` | Modify | Add density CSS variables |
| `apps/web/src/components/providers/density-provider.tsx` | Create | Context provider |
| `apps/web/src/lib/density-config.ts` | Create | Density configurations |
| `apps/web/src/components/layout/density-toggle.tsx` | Create | Toggle UI component |

## Implementation Steps

### Step 1: Add Density CSS Variables (20min)
1. Open `apps/web/src/app/globals.css`
2. Add CSS custom properties:
   ```css
   [data-density="compact"] {
     --density-gap-card: 0.5rem;
     --density-padding-card: 0.5rem;
     --density-text-kpi: 1.25rem;
     --density-chart-height: 8rem;
     --density-row-height: 2rem;
   }
   [data-density="comfortable"] {
     --density-gap-card: 1rem;
     --density-padding-card: 1rem;
     --density-text-kpi: 1.5rem;
     --density-chart-height: 12rem;
     --density-row-height: 2.5rem;
   }
   [data-density="spacious"] {
     --density-gap-card: 1.5rem;
     --density-padding-card: 1.5rem;
     --density-text-kpi: 1.875rem;
     --density-chart-height: 16rem;
     --density-row-height: 3rem;
   }
   ```

### Step 2: Create Density Config (20min)
1. Create `apps/web/src/lib/density-config.ts`
2. Define TypeScript types and Tailwind class mappings
3. Export `densityConfigs` object

### Step 3: Create Density Provider (30min)
1. Create `apps/web/src/components/providers/density-provider.tsx`
2. Implement:
   - DensityContext with mode and setMode
   - localStorage persistence
   - data-density attribute on wrapper
3. Export `useDensity` hook

### Step 4: Create Density Toggle (20min)
1. Create `apps/web/src/components/layout/density-toggle.tsx`
2. Use ToggleGroup from ShadCN
3. Icons: LayoutGrid (compact), LayoutList (comfortable), Square (spacious)
4. Add a11y labels

### Step 5: Write Documentation Section (60min)
1. Add "Data Density Modes" section to design-guidelines.md
2. Include:
   - Mode definitions table
   - CSS variables reference
   - Provider setup code
   - useDensity hook usage
   - Density-aware component pattern
   - Toggle integration example

### Step 6: Document Migration Guide (30min)
1. Add subsection on updating existing components
2. Pattern: `className={cn("base", config.spacing.card)}`
3. Recommend gradual adoption

## Todo List
- [ ] Add density CSS variables to globals.css
- [ ] Create density-config.ts with types and configs
- [ ] Create density-provider.tsx with context and hook
- [ ] Create density-toggle.tsx component
- [ ] Write documentation section with examples
- [ ] Add migration guide for existing components

## Success Criteria
- [ ] 3 density modes defined with CSS variables
- [ ] Provider and hook patterns documented
- [ ] Toggle component pattern documented
- [ ] Code examples for density-aware components

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| All components need updates | High | Document pattern, gradual adoption |
| CSS variables not flexible enough | Low | Provider can add non-CSS config |

## Security Considerations
- None specific to this phase

## Next Steps
- After docs: Create actual provider/toggle components
- Gradually update dashboard components to use density
