# Phase 5: Lazy Load Charts (Optional)

**Parent Plan:** [plan.md](./plan.md)
**Dependencies:** None (independent, optional enhancement)

---

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-23 |
| Priority | P3 |
| Effort | 30min |
| Status | completed |

**Goal:** Reduce initial bundle size by lazy loading Recharts components.

---

## Requirements

1. Use `next/dynamic` for chart components (SSR: false for Recharts)
2. Add skeleton fallbacks during chart load
3. Wrap lazy components in Suspense boundaries

---

## Related Files

| File | Action |
|------|--------|
| Pages/components importing charts | Add dynamic imports |
| `apps/web/src/components/dashboard/volume-spike-chart.tsx` | Target for lazy load |
| `apps/web/src/components/dashboard/volume-spike-treemap.tsx` | Target for lazy load |

---

## Implementation Steps

### Step 1: Create Lazy Chart Exports

Create `apps/web/src/components/dashboard/charts-lazy.tsx`:

```tsx
"use client"

import dynamic from "next/dynamic"
import { Skeleton } from "@/components/ui/skeleton"

// Chart loading skeleton
function ChartSkeleton({ className }: { className?: string }) {
  return (
    <div className={className}>
      <Skeleton className="h-full w-full min-h-[300px] rounded-lg" />
    </div>
  )
}

// Lazy load VolumeSpikeChart (contains Recharts)
export const LazyVolumeSpikeChart = dynamic(
  () => import("./volume-spike-chart").then((mod) => ({
    default: mod.VolumeSpikeChart
  })),
  {
    ssr: false, // Recharts doesn't support SSR
    loading: () => <ChartSkeleton className="h-[400px]" />,
  }
)

// Lazy load VolumeSpikeTreemap
export const LazyVolumeSpikeTreemap = dynamic(
  () => import("./volume-spike-treemap").then((mod) => ({
    default: mod.VolumeSpikeTreemap
  })),
  {
    ssr: false,
    loading: () => <ChartSkeleton className="h-[350px]" />,
  }
)

// Lazy load ComposedChart component if exists
export const LazyVolumeSpikeComposed = dynamic(
  () => import("./volume-spike-composed").then((mod) => ({
    default: mod.VolumeSpikeComposed
  })),
  {
    ssr: false,
    loading: () => <ChartSkeleton className="h-[400px]" />,
  }
)
```

### Step 2: Update Import in Parent Components

In pages/components that use these charts:

**Before:**
```tsx
import { VolumeSpikeChart } from "@/components/dashboard/volume-spike-chart"
import { VolumeSpikeTreemap } from "@/components/dashboard/volume-spike-treemap"
```

**After:**
```tsx
import {
  LazyVolumeSpikeChart,
  LazyVolumeSpikeTreemap
} from "@/components/dashboard/charts-lazy"

// Usage
<LazyVolumeSpikeChart data={data} className="h-[400px]" />
<LazyVolumeSpikeTreemap data={data} className="h-[350px]" />
```

### Step 3: Alternative - Direct Dynamic Import

If you don't want a separate file, use inline dynamic:

```tsx
"use client"

import dynamic from "next/dynamic"
import { Skeleton } from "@/components/ui/skeleton"

const VolumeSpikeChart = dynamic(
  () => import("@/components/dashboard/volume-spike-chart")
    .then((m) => m.VolumeSpikeChart),
  {
    ssr: false,
    loading: () => <Skeleton className="h-[400px] rounded-lg" />
  }
)

// Use normally in JSX
<VolumeSpikeChart data={chartData} />
```

---

## Bundle Size Impact

| Component | Approx Size | Load Timing |
|-----------|-------------|-------------|
| Recharts core | ~150KB gzipped | Now: on demand |
| VolumeSpikeChart | ~10KB | Lazy |
| VolumeSpikeTreemap | ~8KB | Lazy |

**Expected improvement:** Initial JS bundle reduced by ~150KB+

---

## Success Criteria

- [x] Chart components load on demand
- [x] Skeleton shown during chart load
- [x] No SSR errors (charts render client-side only)
- [x] Network tab shows chart chunk loaded separately
- [x] TypeScript compiles without errors

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Flash of skeleton on navigation | Medium | Pre-fetch on hover if needed |
| Increased perceived latency | Low | Skeleton makes load feel intentional |
| Hydration mismatch | Low | Using ssr: false prevents this |

---

## Testing Checklist

1. Build production bundle: `pnpm build`
2. Analyze bundle: `pnpm build && npx @next/bundle-analyzer`
3. Open Network tab, navigate to page with charts
4. Verify chart chunk loads separately from main bundle
5. Verify skeleton appears briefly then chart renders

---

## When to Skip This Phase

Skip if:
- Charts are above-the-fold and need immediate render
- Bundle size is already acceptable (<500KB gzipped)
- User always lands on pages with charts (no savings)

Implement if:
- Landing page doesn't have charts
- Multiple chart-heavy pages exist
- Mobile performance is critical
