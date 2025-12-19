# Phase 3: Verification

**Status**: Blocked
**Estimated**: 15 min
**Depends on**: Phase 1 ✓, Phase 2 (incomplete)
**Blocker**: Phase 2 has 2 critical fixes needed before verification can proceed

## Context

- [Plan Overview](./plan.md)

## Overview

Verify dark mode implementation across all pages and components.

## Requirements

- All pages display correctly in dark mode
- WCAG AA contrast ratios met
- No visual regressions in light mode
- Consistent appearance across browsers

---

## Visual Testing Checklist

### Pages

- [ ] Dashboard (main page)
- [ ] Stock detail pages
- [ ] Any other routes

### Layout Components

- [ ] Header - background #181C1A
- [ ] Sidebar - background #0F0F0F
- [ ] Main content area - background #181C1A

### UI Components

- [ ] Cards - proper background and text colors
- [ ] Buttons - primary, secondary, destructive variants
- [ ] Inputs - visible borders and focus states
- [ ] Dropdowns/Selects - proper backgrounds
- [ ] Popovers - correct background color
- [ ] Skeleton loaders - visible on new backgrounds

### Dashboard Components

- [ ] Sparkline charts - green/red colors visible
- [ ] Fund certificates - text colors readable
- [ ] Sector performance - existing dark variants work
- [ ] All data tables - text readable

### Interactive States

- [ ] Hover states visible
- [ ] Focus rings visible (--ring color)
- [ ] Active/selected states clear
- [ ] Disabled states distinguishable

---

## Accessibility Verification

### Contrast Ratios (use browser DevTools or axe)

| Element | Background | Foreground | Min Ratio |
|---------|------------|------------|-----------|
| Body text | #181C1A | #FFFFFF | 4.5:1 |
| Muted text | #181C1A | 65% white | 4.5:1 |
| Sidebar text | #0F0F0F | #FFFFFF | 4.5:1 |
| Borders | #181C1A | 15% white | visible |

### Checks

- [ ] Run Lighthouse accessibility audit
- [ ] Check with browser color contrast tools
- [ ] Test keyboard navigation visibility

---

## Browser Testing

- [ ] Chrome (primary)
- [ ] Firefox
- [ ] Edge
- [ ] Safari (if available)

---

## Regression Testing

### Light Mode

- [ ] Toggle to light mode
- [ ] Verify all pages render correctly
- [ ] No dark mode styles bleeding through

### Theme Switching

- [ ] Toggle dark/light multiple times
- [ ] No flash of wrong colors
- [ ] Persists across page refresh

---

## Todo

- [ ] Complete visual testing checklist
- [ ] Run accessibility checks
- [ ] Test in multiple browsers
- [ ] Verify light mode not affected
- [ ] Document any issues found

## Success Criteria

1. All checklist items pass
2. WCAG AA contrast ratios met (4.5:1 minimum)
3. No visual regressions in light mode
4. Consistent across Chrome, Firefox, Edge
5. Theme switching works smoothly
