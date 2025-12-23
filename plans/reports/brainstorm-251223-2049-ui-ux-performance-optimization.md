# Brainstorm: UI/UX Performance Optimization

**Date:** 2025-12-23
**Type:** UI/UX Enhancement
**Status:** Brainstorm Complete

---

## Problem Statement

User muốn cải thiện trải nghiệm UI/UX:
- Tăng độ mượt mà (smoothness)
- Cải thiện scrolling
- Loading không bị flicker
- Tránh giật khi load dữ liệu

---

## Current State Analysis

### Điểm mạnh hiện tại
1. **Skeleton Loading** - Có sẵn cho hầu hết components
2. **TanStack Query** - Đã config staleTime, gcTime
3. **CSS Transitions** - Sidebar đã có GPU acceleration
4. **Custom Scrollbar** - Đã style thin scrollbar

### Vấn đề phát hiện

| Issue | Severity | Root Cause |
|-------|----------|------------|
| Multiple aggressive polling (10s) | High | 4+ hooks cùng poll 10s → network overload |
| No React.memo on table rows | High | Re-render toàn bộ table khi parent update |
| No virtualization | Medium | 30-50 rows render full DOM |
| Charts không lazy load | Medium | Recharts bundle load ngay từ đầu |
| Inline functions in JSX | Medium | New function refs mỗi render |
| Flicker khi data thay đổi | High | Không có `placeholderData` trong queries |

---

## Proposed Solutions

### Priority 1: Fix Data Fetching Flicker (High Impact)

**Problem:** Khi refetch, `isLoading` toggle → hiện skeleton → flicker

**Solution: `placeholderData: keepPreviousData`**

```tsx
// Before
useQuery({
  queryKey: [...],
  queryFn: ...,
  refetchInterval: 10000,
})

// After
import { keepPreviousData } from "@tanstack/react-query"

useQuery({
  queryKey: [...],
  queryFn: ...,
  refetchInterval: 10000,
  placeholderData: keepPreviousData, // Keep old data while refetching
})
```

**Files cần update:**
- `use-market-indices.ts`
- `use-vn30-overview.ts`
- `use-stock-detail.ts`
- `use-fund-certificates.ts`
- `use-sector-performance.ts`
- `use-volume-spikes.ts`
- `use-financial-statements.ts`

**Impact:** Eliminates 90% flicker khi refetch

---

### Priority 2: Reduce Polling Aggression (High Impact)

**Current State:**
| Hook | staleTime | refetchInterval |
|------|-----------|-----------------|
| market-indices | 10s | 10s |
| vn30-overview | 10s | 10s |
| stock-detail | 10s | 10s |
| fund-certificates | 10s | 10s |

**Problem:** 4 hooks × 10s = ~24 requests/minute → browser busy, UI janky

**Solution: Stagger intervals + Increase for non-critical data**

| Hook | New staleTime | New Interval | Rationale |
|------|---------------|--------------|-----------|
| market-indices | 15s | 15s | Main dashboard, acceptable |
| vn30-overview | 30s | 30s | Less volatile |
| stock-detail | 15s | 15s | User-focused |
| fund-certificates | 60s | 60s | NAV changes slowly |
| sector-performance | 60s | 120s | Already reasonable |

**Thêm logic:** Pause polling khi tab không active
```tsx
refetchIntervalInBackground: false, // Stop polling when tab inactive
```

---

### Priority 3: Component Memoization (Medium Impact)

**Current:** Table row components không có React.memo

**Solution: Wrap heavy components với React.memo**

```tsx
// Table Row Component
const TableRow = React.memo(function TableRow({ stock }: Props) {
  // ... render
})

// Chart Components
const VolumeSpike = React.memo(function VolumeSpike({ data }: Props) {
  // ... render
})
```

**Files cần memo:**
- `vn30-overview-table.tsx` - Row component
- `financial-statements-table.tsx` - Row component
- `volume-spike-chart.tsx`
- `volume-spike-treemap.tsx`
- `stock-index-card.tsx`

**Impact:** Reduce re-renders by ~60-70%

---

### Priority 4: Lazy Load Heavy Components (Medium Impact)

**Current:** All Recharts components load immediately

**Solution: React.lazy + Suspense for charts**

```tsx
// Before
import { VolumeSpikeChart } from "@/components/dashboard/volume-spike-chart"

// After
import { Suspense, lazy } from "react"
const VolumeSpikeChart = lazy(() =>
  import("@/components/dashboard/volume-spike-chart")
    .then(m => ({ default: m.VolumeSpikeChart }))
)

// Usage
<Suspense fallback={<VolumeSpikeChartSkeleton />}>
  <VolumeSpikeChart data={data} />
</Suspense>
```

**Components to lazy load:**
- All volume-spike-*.tsx charts
- sector-performance.tsx (có biểu đồ)
- Bất kỳ component nào chứa Recharts

**Impact:** Faster initial page load, better TTI

---

### Priority 5: Smooth Scrolling CSS (Low Effort)

**Add to globals.css:**

```css
/* Smooth scroll behavior */
html {
  scroll-behavior: smooth;
}

/* GPU-accelerated scrolling for tables */
.table-container {
  -webkit-overflow-scrolling: touch;
  transform: translateZ(0);
}

/* Reduce scroll jank */
* {
  -webkit-tap-highlight-color: transparent;
}
```

---

### Priority 6: Extract Inline Handlers (Low-Medium Impact)

**Current:**
```tsx
{currentData.map((stock) => (
  <tr onClick={() => handleRowClick(stock.symbol)}>
```

**Solution:**
```tsx
const handleClick = useCallback((symbol: string) => () => {
  handleRowClick(symbol)
}, [handleRowClick])

// Or memoize the row component
```

---

### Priority 7: Virtual Scrolling (Optional - Future)

**When needed:** Khi table có > 100 rows

**Libraries:**
- `@tanstack/react-virtual` (recommended - same ecosystem)
- `react-window` (lighter)

**Current tables có ~30-50 rows → chưa cần thiết lắm**

---

## Implementation Approach

### Phase 1: Quick Wins (1-2 hours)
1. Add `placeholderData: keepPreviousData` to all hooks
2. Update CSS smooth scrolling
3. Set `refetchIntervalInBackground: false`

### Phase 2: Polling Optimization
1. Stagger refetch intervals
2. Test network requests reduction

### Phase 3: Component Memoization
1. Add React.memo to table rows
2. Add React.memo to chart components
3. Extract inline handlers

### Phase 4: Lazy Loading (Optional)
1. Lazy load chart components
2. Test bundle size reduction

---

## Trade-offs

| Approach | Pros | Cons |
|----------|------|------|
| keepPreviousData | No flicker, seamless updates | Stale data shown briefly |
| Longer intervals | Less network load | Slightly older data |
| React.memo | Less re-renders | Memory overhead, complexity |
| Lazy loading | Faster initial load | Delay on first chart render |

---

## Recommended Priority Order

1. **placeholderData: keepPreviousData** - Highest ROI, fixes flicker immediately
2. **refetchIntervalInBackground: false** - Stop wasteful background requests
3. **Increase polling intervals** - Reduce network load
4. **React.memo table rows** - Stop unnecessary re-renders
5. **Lazy load charts** - Improve initial load time

---

## Success Metrics

- [ ] No visible flicker khi data refresh
- [ ] Smooth scrolling trong tables
- [ ] Network requests giảm 50%+
- [ ] Lighthouse Performance Score >= 90

---

## Unresolved Questions

1. Có muốn implement virtual scrolling cho tables không? (hiện ~30 rows, có thể chưa cần)
2. Có muốn thêm optimistic updates cho user actions không?
3. Backend có support WebSocket để real-time update thay vì polling không?
