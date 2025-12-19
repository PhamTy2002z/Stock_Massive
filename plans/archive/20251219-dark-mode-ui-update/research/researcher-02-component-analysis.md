# Component Dark Mode Analysis

**Date**: 2025-12-19
**Scope**: apps/web/src/components/{ui,dashboard,layout}

---

## Summary

Most components use CSS variables (via ShadCN/UI) and will auto-update with theme changes. Few components have hardcoded colors requiring manual fixes.

---

## 1. Components with Hardcoded Colors (NEED FIXES)

### sparkline.tsx
- **Line 48**: `const strokeColor = positive ? "#22C55E" : "#EF4444"`
- Hardcoded hex colors for green/red
- **Fix**: Use CSS variables or Tailwind color classes

### fund-certificates.tsx
- **Lines 86-87, 99-100, 104-105**: Uses `emerald-500`, `red-500` directly
- Colors work in both modes but may need dark variants for better contrast
- **Fix**: Add `dark:emerald-400`, `dark:red-400` variants

---

## 2. Components with dark: Variants (ALREADY HANDLED)

### sector-performance.tsx
- Line 54: `text-green-600 dark:text-green-400`
- Line 91: `text-red-600 dark:text-red-400`
- Line 132: `text-green-600 dark:text-green-400` / `text-red-600 dark:text-red-400`
- **Status**: Properly implemented

### alert.tsx
- Line 13: `dark:border-destructive`
- **Status**: Properly implemented

---

## 3. Components Using CSS Variables (AUTO-UPDATE)

These use ShadCN semantic tokens - no changes needed:

| Component | CSS Variables Used |
|-----------|-------------------|
| card.tsx | `text-muted-foreground` |
| skeleton.tsx | `bg-primary/10` |
| sidebar.tsx | `bg-sidebar`, `text-sidebar-foreground`, `bg-sidebar-border` |
| sheet.tsx | `text-foreground`, `text-muted-foreground`, `bg-secondary` |
| select.tsx | `bg-muted` |
| dropdown-menu.tsx | `bg-muted` |
| fund-certificates.tsx | `bg-card`, `text-foreground`, `text-muted-foreground`, `border`, `bg-muted/50` |

---

## 4. Action Items

| Priority | Component | Issue | Fix |
|----------|-----------|-------|-----|
| HIGH | sparkline.tsx | Hardcoded hex colors | Replace with CSS vars or add theme-aware logic |
| LOW | fund-certificates.tsx | No dark variants on accent colors | Add `dark:` variants for emerald/red |

---

## 5. Recommendations

1. **sparkline.tsx**: Create CSS variables `--chart-positive` and `--chart-negative` in globals.css, or pass colors as props
2. **fund-certificates.tsx**: Consider adding dark variants: `emerald-500 dark:emerald-400` for better dark mode contrast
3. All other UI components rely on ShadCN CSS variables - will auto-update when theme variables change

---

## Unresolved Questions

1. Should sparkline colors match the exact brand palette or use standard Tailwind green/red?
2. Is the current emerald-500/red-500 contrast acceptable in dark mode, or should we use lighter variants?
