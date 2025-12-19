# Dark Mode UI Update Plan

**Created**: 2025-12-19
**Status**: Pending
**Scope**: Update website to dark mode with specific color palette

## Task Summary

Update entire website UI to dark mode using:
- **Background/Header**: #181C1A (HSL: 150 8% 10%)
- **Sidebar/Frames**: #0F0F0F (HSL: 0 0% 6%)
- **Text**: White (HSL: 0 0% 100%)

## Research Reports

- [CSS Variables Analysis](./research/researcher-01-css-variables.md)
- [Component Analysis](./research/researcher-02-component-analysis.md)

## Phases

| # | Phase | Status | File |
|---|-------|--------|------|
| 1 | CSS Variables Update | pending | [phase-01-css-variables.md](./phase-01-css-variables.md) |
| 2 | Component Fixes | pending | [phase-02-component-fixes.md](./phase-02-component-fixes.md) |
| 3 | Verification | pending | [phase-03-verification.md](./phase-03-verification.md) |

## Success Criteria

1. All dark mode CSS variables updated to new color palette
2. No hardcoded colors in components - all use CSS variables or dark: variants
3. WCAG AA contrast ratios maintained (min 4.5:1 for text)
4. Visual consistency across all pages and components
5. No regressions in light mode

## Estimated Effort

- Phase 1: ~15 min (CSS variable updates)
- Phase 2: ~20 min (component fixes)
- Phase 3: ~15 min (verification)
- **Total**: ~50 min

## Key Files

- `apps/web/src/app/globals.css` - CSS variables
- `apps/web/src/components/dashboard/sparkline.tsx` - hardcoded colors
- `apps/web/src/components/dashboard/fund-certificates.tsx` - needs dark variants
