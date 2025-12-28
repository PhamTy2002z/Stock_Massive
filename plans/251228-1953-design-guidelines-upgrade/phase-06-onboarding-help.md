# Phase 06: Onboarding & Contextual Help

## Context Links
- Parent plan: [plan.md](./plan.md)
- Brainstorming: `plans/reports/brainstorm-251228-1941-design-guidelines-upgrade.md`

## Overview
- **Priority:** P3 (After core features)
- **Effort:** 2h
- **Status:** Pending
- **Description:** Document first-time user onboarding, contextual tooltips, and feature discovery patterns.

## Key Insights
- `driver.js` is lightweight (5kb), no React dependency
- First-time tour should be skippable
- Help tooltips should be non-intrusive
- Feature discovery dots encourage exploration

## Requirements

### Functional
- Document onboarding tour pattern (driver.js)
- Define contextual help tooltip pattern
- Define feature discovery hint pattern
- Document enhanced empty states

### Non-Functional
- Onboarding tour skippable
- Tour state persisted to localStorage
- Tooltips accessible (keyboard, screen reader)

## Architecture

```
apps/web/src/
├── components/
│   ├── onboarding-tour.tsx      # First-time tour
│   ├── help-tooltip.tsx         # ? icon with tooltip
│   ├── feature-hint.tsx         # Discovery dot
│   └── empty-state.tsx          # Enhanced empty state
└── hooks/
    ├── use-onboarding.ts        # Tour completion state
    └── use-feature-discovery.ts # Discovered features
```

## Related Code Files

| File | Action | Description |
|------|--------|-------------|
| `docs/design-guidelines.md` | Modify | Add "Onboarding & Contextual Help" section |
| `apps/web/package.json` | Modify | Add `driver.js` dependency |

## Implementation Steps

### Step 1: Document Onboarding Tour (30min)
1. Recommend `driver.js` library
2. Define tour steps structure:
   ```ts
   const onboardingSteps = [
     {
       element: "#market-indices",
       popover: {
         title: "Market Overview",
         description: "Real-time indices. Click for details.",
         side: "bottom"
       }
     },
     // more steps...
   ]
   ```
3. Tour trigger (first-time user detection)
4. Skip and completion handling
5. Include full code example

### Step 2: Document Help Tooltip (20min)
1. HelpTooltip component pattern
2. Uses ShadCN Tooltip
3. Optional "Learn more" link
4. Include code example:
   ```tsx
   <HelpTooltip
     content="P/E ratio explanation..."
     learnMoreUrl="/docs/pe-ratio"
   />
   ```

### Step 3: Document Feature Hint (20min)
1. FeatureHint wrapper component
2. Shows pulsing dot for undiscovered features
3. Marks as discovered on click
4. localStorage persistence
5. Include code example

### Step 4: Document Empty State (20min)
1. Enhanced empty state pattern
2. Icon, title, description, CTA
3. Contextual guidance
4. Include code example:
   ```tsx
   <EmptyState
     icon={Star}
     title="No stocks in watchlist"
     description="Add stocks to track..."
     action={{
       label: "Search Stocks",
       onClick: openCommandPalette
     }}
   />
   ```

### Step 5: Document useOnboarding Hook (15min)
1. Check localStorage for completion
2. Mark completed on tour finish
3. Reset option for testing

### Step 6: Add to Design Guidelines (35min)
1. Add "Onboarding & Contextual Help" section
2. Structure:
   - Onboarding tour with driver.js
   - Help tooltip pattern
   - Feature discovery hints
   - Enhanced empty states
   - Hooks for state management
   - Best practices

## Todo List
- [ ] Document onboarding tour with driver.js
- [ ] Document HelpTooltip component
- [ ] Document FeatureHint component
- [ ] Document EmptyState component
- [ ] Document useOnboarding hook
- [ ] Document useFeatureDiscovery hook
- [ ] Add section to design-guidelines.md

## Success Criteria
- [ ] Onboarding tour pattern documented
- [ ] Help tooltip pattern documented
- [ ] Feature hint pattern documented
- [ ] Empty state pattern documented
- [ ] All with code examples

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tour is annoying | Medium | Make skippable, only show once |
| Too many hints clutter UI | Low | Limit to 3-4 key features |

## Security Considerations
- None specific to this phase

## Next Steps
- After docs: Install driver.js
- Implement OnboardingTour for home page
- Add help tooltips to complex metrics
