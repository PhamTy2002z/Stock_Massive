# Phase 2: Component Fixes

**Status**: Pending
**Estimated**: 20 min
**Depends on**: Phase 1

## Context

- [Plan Overview](./plan.md)
- [Component Analysis](./research/researcher-02-component-analysis.md)

## Overview

Fix 2 components with hardcoded colors that won't auto-update with CSS variables.

## Requirements

- Replace hardcoded hex colors with CSS variables
- Add dark: variants where needed
- Maintain visual consistency with new palette

---

## Fix 1: sparkline.tsx

**File**: `apps/web/src/components/dashboard/sparkline.tsx`
**Issue**: Hardcoded hex colors `#22C55E` (green) and `#EF4444` (red)

### Current Code (line ~48)
```tsx
const strokeColor = positive ? "#22C55E" : "#EF4444"
```

### Solution A: Use chart CSS variables (Recommended)

Update globals.css to add semantic chart colors, then reference them:

```tsx
const strokeColor = positive
  ? "hsl(var(--chart-1))"  // green - already defined as 142 70% 45%
  : "hsl(var(--chart-2))"  // red - already defined as 0 84% 60%
```

### Solution B: Use Tailwind colors via CSS

```tsx
const strokeColor = positive
  ? "rgb(34 197 94)"   // green-500
  : "rgb(239 68 68)"   // red-500
```

**Recommendation**: Solution A - leverages existing CSS variables

---

## Fix 2: fund-certificates.tsx

**File**: `apps/web/src/components/dashboard/fund-certificates.tsx`
**Issue**: Uses `emerald-500`, `red-500` without dark variants

### Current Code (lines ~86-87, 99-100, 104-105)

Look for patterns like:
```tsx
text-emerald-500
text-red-500
bg-emerald-500/10
bg-red-500/10
```

### Fix

Add dark variants for better contrast on darker backgrounds:

```tsx
// Text colors
text-emerald-500 dark:text-emerald-400
text-red-500 dark:text-red-400

// Background colors
bg-emerald-500/10 dark:bg-emerald-400/10
bg-red-500/10 dark:bg-red-400/10
```

---

## Todo

- [ ] Update sparkline.tsx to use CSS variables
- [ ] Add dark: variants to fund-certificates.tsx
- [ ] Test both components in dark mode
- [ ] Verify colors match design intent

## Success Criteria

1. No hardcoded hex colors in sparkline.tsx
2. fund-certificates.tsx has proper dark: variants
3. Both components render correctly in dark mode
4. Colors have sufficient contrast on new backgrounds
