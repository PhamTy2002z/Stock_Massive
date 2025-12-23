# Phase 4: CSS Smooth Scrolling

**Parent Plan:** [plan.md](./plan.md)
**Dependencies:** None (independent)

---

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-23 |
| Priority | P2 |
| Effort | 30min |
| Status | completed |

**Goal:** Improve scrolling smoothness and prevent scroll-related jank.

---

## Requirements

1. Add smooth scrolling behavior globally
2. Add GPU acceleration for scroll containers
3. Add `overscroll-behavior` to prevent scroll chaining
4. Add touch scrolling optimization for mobile

---

## Related Files

| File | Action |
|------|--------|
| `apps/web/src/app/globals.css` | Add CSS utilities |

---

## Implementation Steps

### Step 1: Add Smooth Scrolling CSS to `globals.css`

Add the following at the end of the `@layer utilities` block in `globals.css`:

```css
@layer utilities {
  /* ... existing utilities ... */

  /* Smooth scroll behavior - global */
  html {
    scroll-behavior: smooth;
  }

  /* GPU-accelerated scroll containers */
  .scroll-gpu {
    transform: translateZ(0);
    -webkit-overflow-scrolling: touch;
    will-change: scroll-position;
  }

  /* Prevent scroll chaining to parent */
  .overscroll-contain {
    overscroll-behavior: contain;
  }

  /* Combined scroll optimization class */
  .scroll-smooth-container {
    overflow-y: auto;
    scroll-behavior: smooth;
    overscroll-behavior: contain;
    -webkit-overflow-scrolling: touch;
    transform: translateZ(0);
  }

  /* Reduce tap highlight on mobile */
  .tap-transparent {
    -webkit-tap-highlight-color: transparent;
  }

  /* Content containment for performance */
  .contain-content {
    contain: content;
  }

  .contain-layout {
    contain: layout style paint;
  }

  /* Price change transitions - cheap animation */
  .price-transition {
    transition: color 0.2s ease-out, opacity 0.2s ease-out;
  }

  /* Table container optimizations */
  .table-scroll-container {
    overflow-x: auto;
    overscroll-behavior-x: contain;
    -webkit-overflow-scrolling: touch;
    transform: translateZ(0);
  }

  /* Data fetching opacity indicator */
  .fetching-opacity {
    transition: opacity 0.15s ease-out;
  }

  .fetching-opacity[data-fetching="true"] {
    opacity: 0.7;
  }
}
```

### Step 2: Apply Classes to Table Containers (Optional Enhancement)

In table components, update scroll container classes:

**Before:**
```tsx
<div className="overflow-x-auto scrollbar-thin">
```

**After:**
```tsx
<div className="overflow-x-auto scrollbar-thin table-scroll-container">
```

### Step 3: Apply Fetching Indicator (Optional Enhancement)

In components using data hooks:

```tsx
<div
  className="fetching-opacity"
  data-fetching={isFetching && !isLoading}
>
  {/* content */}
</div>
```

---

## Full CSS Addition

Add this complete block to the end of `globals.css`:

```css
/* Performance Optimizations - Phase 4 */
@layer utilities {
  /* Global smooth scroll */
  html {
    scroll-behavior: smooth;
  }

  /* GPU-accelerated scroll containers */
  .scroll-gpu {
    transform: translateZ(0);
    -webkit-overflow-scrolling: touch;
  }

  /* Prevent scroll chaining */
  .overscroll-contain {
    overscroll-behavior: contain;
  }

  /* Table scroll container optimization */
  .table-scroll-container {
    overscroll-behavior-x: contain;
    -webkit-overflow-scrolling: touch;
    transform: translateZ(0);
  }

  /* Content containment */
  .contain-content {
    contain: content;
  }

  /* Fetching state opacity */
  .fetching-opacity {
    transition: opacity 0.15s ease-out;
  }

  .fetching-opacity[data-fetching="true"] {
    opacity: 0.7;
  }
}
```

---

## Success Criteria

- [x] Smooth scrolling enabled globally
- [x] Table horizontal scroll feels smooth on mobile
- [x] No scroll "bounce" to parent containers
- [x] CSS compiles without errors

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `will-change` overuse | Low | Only on scroll containers, not elements |
| Smooth scroll breaks anchor links | Low | Only affects programmatic scroll |
| Performance regression | Very Low | GPU acceleration is net positive |

---

## Testing Checklist

1. Open dashboard on mobile device/emulator
2. Scroll tables horizontally - verify smoothness
3. Scroll page vertically - verify no jank
4. Verify no "bounce" when reaching scroll limits
