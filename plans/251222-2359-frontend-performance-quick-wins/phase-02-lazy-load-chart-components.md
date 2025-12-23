# Phase 2: Lazy Load Chart Components

## Context
- **Research:** [Next.js Dynamic Imports](./research/researcher-02-nextjs-optimization.md#1-dynamic-imports-with-nextdynamic)
- **Priority:** P1 - HIGH IMPACT
- **Effort:** 15 minutes
- **Status:** pending

## Overview
Recharts library (~400KB) loads immediately on volume spike dashboard even though charts are below the fold and may not be viewed. Using `next/dynamic` with `ssr: false` defers loading until needed, significantly reducing initial bundle size.

**Problem:** All chart components imported statically at top of file, included in initial bundle.

**Solution:** Convert to dynamic imports with loading skeletons for better UX.

## Requirements
- Lazy load all 4 chart components (bar, pie, treemap, composed)
- Add loading skeletons matching existing design system
- Disable SSR for charts (client-only rendering)
- Maintain tab switching functionality
- No layout shift during load

## Implementation Steps

### 1. Add Dynamic Imports
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/volume-spike-dashboard.tsx`

**Before (lines 38-41):**
```typescript
import { VolumeSpikeChart, VolumeSpikeChartSkeleton } from "./volume-spike-chart"
import { VolumeSpikePieChart } from "./volume-spike-pie-chart"
import { VolumeSpikeTreemap } from "./volume-spike-treemap"
import { VolumeSpikeComposedChart } from "./volume-spike-composed-chart"
```

**After:**
```typescript
import dynamic from "next/dynamic"
import { VolumeSpikeChartSkeleton } from "./volume-spike-chart"

// Lazy load chart components (Recharts ~400KB)
const VolumeSpikeChart = dynamic(
  () => import("./volume-spike-chart").then((mod) => ({ default: mod.VolumeSpikeChart })),
  {
    ssr: false,
    loading: () => <VolumeSpikeChartSkeleton />,
  }
)

const VolumeSpikePieChart = dynamic(
  () => import("./volume-spike-pie-chart").then((mod) => ({ default: mod.VolumeSpikePieChart })),
  {
    ssr: false,
    loading: () => (
      <div className="h-[400px] rounded-lg border border-border/50 bg-card/50 animate-pulse" />
    ),
  }
)

const VolumeSpikeTreemap = dynamic(
  () => import("./volume-spike-treemap").then((mod) => ({ default: mod.VolumeSpikeTreemap })),
  {
    ssr: false,
    loading: () => (
      <div className="h-[500px] rounded-lg border border-border/50 bg-card/50 animate-pulse" />
    ),
  }
)

const VolumeSpikeComposedChart = dynamic(
  () => import("./volume-spike-composed-chart").then((mod) => ({ default: mod.VolumeSpikeComposedChart })),
  {
    ssr: false,
    loading: () => (
      <div className="h-[400px] rounded-lg border border-border/50 bg-card/50 animate-pulse" />
    ),
  }
)
```

### 2. Update Import Statement
Add `next/dynamic` import at top of file (after line 4):

```typescript
import { useState, useMemo, useEffect } from "react"
import { useRouter } from "next/navigation"
import dynamic from "next/dynamic"  // ADD THIS LINE
import { cn } from "@/lib/utils"
```

## Code Changes Summary

### Complete Diff for volume-spike-dashboard.tsx

**Lines 1-5 (add dynamic import):**
```diff
  "use client"

  import { useState, useMemo, useEffect } from "react"
  import { useRouter } from "next/navigation"
+ import dynamic from "next/dynamic"
  import { cn } from "@/lib/utils"
```

**Lines 38-45 (replace static imports):**
```diff
  import { useVolumeSpikes } from "@/hooks/use-volume-spikes"
  import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
- import { VolumeSpikeChart, VolumeSpikeChartSkeleton } from "./volume-spike-chart"
- import { VolumeSpikePieChart } from "./volume-spike-pie-chart"
- import { VolumeSpikeTreemap } from "./volume-spike-treemap"
- import { VolumeSpikeComposedChart } from "./volume-spike-composed-chart"
+ import { VolumeSpikeChartSkeleton } from "./volume-spike-chart"
+
+ // Lazy load chart components (Recharts ~400KB)
+ const VolumeSpikeChart = dynamic(
+   () => import("./volume-spike-chart").then((mod) => ({ default: mod.VolumeSpikeChart })),
+   {
+     ssr: false,
+     loading: () => <VolumeSpikeChartSkeleton />,
+   }
+ )
+
+ const VolumeSpikePieChart = dynamic(
+   () => import("./volume-spike-pie-chart").then((mod) => ({ default: mod.VolumeSpikePieChart })),
+   {
+     ssr: false,
+     loading: () => (
+       <div className="h-[400px] rounded-lg border border-border/50 bg-card/50 animate-pulse" />
+     ),
+   }
+ )
+
+ const VolumeSpikeTreemap = dynamic(
+   () => import("./volume-spike-treemap").then((mod) => ({ default: mod.VolumeSpikeTreemap })),
+   {
+     ssr: false,
+     loading: () => (
+       <div className="h-[500px] rounded-lg border border-border/50 bg-card/50 animate-pulse" />
+     ),
+   }
+ )
+
+ const VolumeSpikeComposedChart = dynamic(
+   () => import("./volume-spike-composed-chart").then((mod) => ({ default: mod.VolumeSpikeComposedChart })),
+   {
+     ssr: false,
+     loading: () => (
+       <div className="h-[400px] rounded-lg border border-border/50 bg-card/50 animate-pulse" />
+     ),
+   }
+ )
  import type {
    IndustryVolumeSpikeGroup,
    VolumeSpikeAnomalyLevel,
```

## Success Criteria
- [ ] Charts load dynamically when tab is selected
- [ ] Loading skeletons display during chart load
- [ ] Initial bundle size reduced by ~400KB
- [ ] No SSR errors in console
- [ ] Tab switching works smoothly
- [ ] No layout shift when charts load
- [ ] All 4 chart types render correctly

## Testing
1. Clear browser cache
2. Open DevTools Network tab
3. Navigate to volume spike dashboard
4. Verify Recharts NOT in initial bundle
5. Click each chart tab (bar, pie, treemap, composed)
6. Verify loading skeleton appears briefly
7. Verify chart loads and renders correctly
8. Check bundle size in Network tab (should be ~400KB smaller)
9. Test tab switching performance

## Risk Assessment
**Risk Level:** LOW

- **Breaking Changes:** None - same components, different loading
- **User Impact:** Positive - faster initial load, brief skeleton on first chart view
- **Rollback:** Simple - revert to static imports
- **Dependencies:** Requires `next/dynamic` (already in Next.js)
- **SSR Impact:** Charts already client-only (Recharts requires window)

## Performance Impact
- **Initial Bundle:** -400KB (~30% reduction for this page)
- **Time to Interactive:** Improved by 200-400ms on 3G
- **First Contentful Paint:** Improved (less JS to parse)
- **Chart Load Time:** +50-100ms first view (acceptable tradeoff)
- **Subsequent Views:** No impact (cached)

## Notes
- VolumeSpikeChartSkeleton already exists, reuse for bar chart
- Other charts use simple animated div skeletons
- Heights match actual chart heights to prevent layout shift
- `ssr: false` required because Recharts uses browser APIs
