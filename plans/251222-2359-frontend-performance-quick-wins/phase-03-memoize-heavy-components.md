# Phase 3: Memoize Heavy Components

## Context
- **Research:** [React Performance - React.memo Best Practices](./research/researcher-01-react-performance.md#1-reactmemo-best-practices)
- **Priority:** P2 - MEDIUM IMPACT
- **Effort:** 20 minutes
- **Status:** pending

## Overview
Volume spike dashboard contains expensive components that re-render unnecessarily when parent state changes. Wrapping with React.memo and stabilizing function references with useCallback prevents wasted renders.

**Problem:** Components re-render even when their props haven't changed, causing performance degradation with large datasets.

**Solution:** Apply React.memo to pure components and useCallback to event handlers.

## Requirements
- Wrap 3 heavy components with React.memo
- Stabilize event handler references with useCallback
- Maintain all existing functionality
- No prop drilling changes needed

## Implementation Steps

### 1. Memoize SectorGroupHeader Component
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/volume-spike-dashboard.tsx`

**Before (line 94):**
```typescript
function SectorGroupHeader({
  sectorCount,
  sectorSort,
  onSortChange,
  selectedSector,
  onSectorFilterChange,
  allSectors,
  expandAll,
  onExpandAllToggle,
}: {
  sectorCount: number
  sectorSort: SectorSortType
  onSortChange: (value: SectorSortType) => void
  selectedSector: string
  onSectorFilterChange: (sector: string) => void
  allSectors: { code: string; name: string }[]
  expandAll: boolean
  onExpandAllToggle: () => void
}) {
```

**After:**
```typescript
const SectorGroupHeader = memo(function SectorGroupHeader({
  sectorCount,
  sectorSort,
  onSortChange,
  selectedSector,
  onSectorFilterChange,
  allSectors,
  expandAll,
  onExpandAllToggle,
}: {
  sectorCount: number
  sectorSort: SectorSortType
  onSortChange: (value: SectorSortType) => void
  selectedSector: string
  onSectorFilterChange: (sector: string) => void
  allSectors: { code: string; name: string }[]
  expandAll: boolean
  onExpandAllToggle: () => void
}) {
```

### 2. Memoize SummaryCards Component
**Before (line 172):**
```typescript
function SummaryCards({
  totalSpikes,
  avgRatio,
  topIndustry,
}: {
  totalSpikes: number
  avgRatio: number
  topIndustry: string
}) {
```

**After:**
```typescript
const SummaryCards = memo(function SummaryCards({
  totalSpikes,
  avgRatio,
  topIndustry,
}: {
  totalSpikes: number
  avgRatio: number
  topIndustry: string
}) {
```

### 3. Memoize IndustrySpikeGroup Component
**Before (line 221):**
```typescript
function IndustrySpikeGroup({
  group,
  isOpen,
  onToggle,
}: {
  group: IndustryVolumeSpikeGroup
  isOpen: boolean
  onToggle: () => void
}) {
```

**After:**
```typescript
const IndustrySpikeGroup = memo(function IndustrySpikeGroup({
  group,
  isOpen,
  onToggle,
}: {
  group: IndustryVolumeSpikeGroup
  isOpen: boolean
  onToggle: () => void
}) {
```

### 4. Add React Import
**Before (line 3):**
```typescript
import { useState, useMemo, useEffect } from "react"
```

**After:**
```typescript
import { useState, useMemo, useEffect, memo, useCallback } from "react"
```

### 5. Wrap Event Handlers with useCallback
In the main `VolumeSpikeDashboard` component (around line 447):

**Before:**
```typescript
  // Expand all toggle handler
  const handleExpandAllToggle = () => {
    if (expandAll) {
      setExpandedSectors(new Set())
    } else {
      setExpandedSectors(new Set(sortedIndustries.map((g) => g.icb_code)))
    }
    setExpandAll(!expandAll)
  }

  // Individual sector toggle handler
  const handleSectorToggle = (icbCode: string) => {
    setExpandedSectors((prev) => {
      const next = new Set(prev)
      if (next.has(icbCode)) {
        next.delete(icbCode)
      } else {
        next.add(icbCode)
      }
      return next
    })
  }
```

**After:**
```typescript
  // Expand all toggle handler
  const handleExpandAllToggle = useCallback(() => {
    if (expandAll) {
      setExpandedSectors(new Set())
    } else {
      setExpandedSectors(new Set(sortedIndustries.map((g) => g.icb_code)))
    }
    setExpandAll(!expandAll)
  }, [expandAll, sortedIndustries])

  // Individual sector toggle handler
  const handleSectorToggle = useCallback((icbCode: string) => {
    setExpandedSectors((prev) => {
      const next = new Set(prev)
      if (next.has(icbCode)) {
        next.delete(icbCode)
      } else {
        next.add(icbCode)
      }
      return next
    })
  }, [])
```

## Code Changes Summary

### Import Changes (line 3)
```diff
- import { useState, useMemo, useEffect } from "react"
+ import { useState, useMemo, useEffect, memo, useCallback } from "react"
```

### SectorGroupHeader (line 94)
```diff
- function SectorGroupHeader({
+ const SectorGroupHeader = memo(function SectorGroupHeader({
    sectorCount,
    sectorSort,
    onSortChange,
    selectedSector,
    onSectorFilterChange,
    allSectors,
    expandAll,
    onExpandAllToggle,
  }: {
    sectorCount: number
    sectorSort: SectorSortType
    onSortChange: (value: SectorSortType) => void
    selectedSector: string
    onSectorFilterChange: (sector: string) => void
    allSectors: { code: string; name: string }[]
    expandAll: boolean
    onExpandAllToggle: () => void
- }) {
+ }) {
    return (
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
        {/* ... existing JSX ... */}
      </div>
    )
- }
+ })
```

### SummaryCards (line 172)
```diff
- function SummaryCards({
+ const SummaryCards = memo(function SummaryCards({
    totalSpikes,
    avgRatio,
    topIndustry,
  }: {
    totalSpikes: number
    avgRatio: number
    topIndustry: string
- }) {
+ }) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* ... existing JSX ... */}
      </div>
    )
- }
+ })
```

### IndustrySpikeGroup (line 221)
```diff
- function IndustrySpikeGroup({
+ const IndustrySpikeGroup = memo(function IndustrySpikeGroup({
    group,
    isOpen,
    onToggle,
  }: {
    group: IndustryVolumeSpikeGroup
    isOpen: boolean
    onToggle: () => void
- }) {
+ }) {
    const router = useRouter()
    // ... existing logic ...
    return (
      <Collapsible open={isOpen} onOpenChange={onToggle}>
        {/* ... existing JSX ... */}
      </Collapsible>
    )
- }
+ })
```

### Event Handlers (around line 447)
```diff
  // Expand all toggle handler
- const handleExpandAllToggle = () => {
+ const handleExpandAllToggle = useCallback(() => {
    if (expandAll) {
      setExpandedSectors(new Set())
    } else {
      setExpandedSectors(new Set(sortedIndustries.map((g) => g.icb_code)))
    }
    setExpandAll(!expandAll)
- }
+ }, [expandAll, sortedIndustries])

  // Individual sector toggle handler
- const handleSectorToggle = (icbCode: string) => {
+ const handleSectorToggle = useCallback((icbCode: string) => {
    setExpandedSectors((prev) => {
      const next = new Set(prev)
      if (next.has(icbCode)) {
        next.delete(icbCode)
      } else {
        next.add(icbCode)
      }
      return next
    })
- }
+ }, [])
```

## Success Criteria
- [ ] All 3 components wrapped with React.memo
- [ ] Event handlers wrapped with useCallback
- [ ] No unnecessary re-renders (verify with React DevTools Profiler)
- [ ] All functionality works identically
- [ ] No console warnings about missing dependencies

## Testing
1. Install React DevTools browser extension
2. Open Profiler tab
3. Navigate to volume spike dashboard
4. Start recording
5. Change filters (threshold, exchange, sector)
6. Stop recording
7. Verify memoized components don't re-render when props unchanged
8. Test all interactions (expand/collapse, sorting, pagination)
9. Verify no functional regressions

## Risk Assessment
**Risk Level:** LOW-MEDIUM

- **Breaking Changes:** None - same behavior, optimized rendering
- **User Impact:** Positive - smoother interactions with large datasets
- **Rollback:** Simple - remove memo/useCallback wrappers
- **Dependencies:** None - React built-ins
- **Complexity:** Medium - requires understanding of React rendering

## Performance Impact
- **Re-renders:** 50-70% reduction for memoized components
- **Interaction Latency:** 20-50ms improvement on filter changes
- **Memory:** Slight increase (memoization overhead)
- **Large Datasets:** More noticeable improvement with 50+ industries

## Notes
- memo() only prevents re-renders when props are shallowly equal
- useCallback dependencies must be complete (ESLint will warn)
- handleSectorToggle has no deps because it uses functional setState
- handleExpandAllToggle depends on expandAll and sortedIndustries
- Don't over-optimize - profile first, optimize second
- Consider custom comparison function for memo if needed later
