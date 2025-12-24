# React Hydration Mismatch Investigation Report

**Date:** 2025-12-24
**Investigator:** Debugger
**Scope:** apps/web/src/ (Next.js frontend)

---

## Executive Summary

Tìm thấy **4 vấn đề hydration mismatch tiềm ẩn**, với 2 issues nghiêm trọng cần fix ngay.

| Severity | Issue | Location |
|----------|-------|----------|
| **HIGH** | Math.random() trong render | sidebar.tsx:682 |
| **HIGH** | useIsMobile returns !!undefined on SSR | use-mobile.tsx:18 |
| **MEDIUM** | formatDistanceToNow time-sensitive | notification-panel.tsx:57 |
| **LOW** | toLocaleString usage (stable with locale) | Multiple files |

---

## Issue 1: Math.random() in SidebarMenuSkeleton [HIGH]

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/ui/sidebar.tsx`
**Line:** 680-683

```tsx
const SidebarMenuSkeleton = React.forwardRef<...>(({ ... }, ref) => {
  // Random width between 50 to 90%.
  const width = React.useMemo(() => {
    return `${Math.floor(Math.random() * 40) + 50}%`  // <-- HYDRATION MISMATCH
  }, [])
  ...
})
```

**Problem:** `Math.random()` generates different values on server vs client. React.useMemo only runs once per environment - returns different cached values causing hydration error.

**Fix:**
```tsx
// Option 1: Use fixed widths array
const SKELETON_WIDTHS = ['50%', '60%', '70%', '80%', '90%']
const width = SKELETON_WIDTHS[index % SKELETON_WIDTHS.length]

// Option 2: Generate random width only on client with useEffect
const [width, setWidth] = useState('70%') // default
useEffect(() => {
  setWidth(`${Math.floor(Math.random() * 40) + 50}%`)
}, [])

// Option 3: Use CSS random animation (no JS)
// className="animate-skeleton-width"
```

---

## Issue 2: useIsMobile SSR/Client Mismatch [HIGH]

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-mobile.tsx`
**Lines:** 6, 18

```tsx
export function useIsMobile() {
  const [isMobile, setIsMobile] = React.useState<boolean | undefined>(undefined)

  React.useEffect(() => {
    // Only runs on client
    setIsMobile(window.innerWidth < MOBILE_BREAKPOINT)
  }, [])

  return !!isMobile  // <-- SSR: !!undefined = false, Client: true/false
}
```

**Problem:**
- SSR: `isMobile = undefined` → returns `false`
- Client hydration: Updates to actual value → potential UI mismatch if mobile

**Impact:** Components using `useIsMobile()` may render differently on server vs client, especially `SidebarProvider` which uses this hook.

**Fix:**
```tsx
export function useIsMobile() {
  const [isMobile, setIsMobile] = React.useState<boolean | undefined>(undefined)

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)
    const onChange = () => setIsMobile(mql.matches)
    mql.addEventListener("change", onChange)
    setIsMobile(mql.matches)
    return () => mql.removeEventListener("change", onChange)
  }, [])

  // Return undefined during SSR to allow parent to handle
  // OR suppress hydration warning in consuming components
  return isMobile
}

// Usage in components - handle undefined state:
const isMobile = useIsMobile()
if (isMobile === undefined) return <Skeleton /> // or null during SSR
```

---

## Issue 3: formatDistanceToNow Time-Sensitive [MEDIUM]

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/layout/notification-panel.tsx`
**Line:** 57-60

```tsx
{job.completedAt && formatDistanceToNow(new Date(job.completedAt), {
  addSuffix: true,
  locale: vi,
})}
```

**Problem:** If SSR time differs from client time (even by seconds), output differs.
Example: SSR "5 giây trước" vs Client hydration "6 giây trước"

**Risk Level:** MEDIUM - Only causes mismatch if SSR/client timing differs significantly (rare in practice).

**Fix:**
```tsx
// Option 1: Suppress hydration warning for this span
<span suppressHydrationWarning>
  {job.completedAt && formatDistanceToNow(...)}
</span>

// Option 2: Only render on client
const [mounted, setMounted] = useState(false)
useEffect(() => setMounted(true), [])
if (!mounted) return null
```

---

## Issue 4: toLocaleString Usage [LOW]

**Files:** Multiple dashboard components
**Examples:**
- stock-detail-panel.tsx:15
- stock-ticker-header.tsx:39, 44
- financial-statements-table.tsx:38, 48
- vn30-overview-table.tsx:21, 30, 39, 47
- volume-spike-dashboard.tsx:77

```tsx
return value.toLocaleString("vi-VN", { maximumFractionDigits: 1 })
```

**Analysis:** With explicit locale ("vi-VN"), this is STABLE. Only causes mismatch if:
- Server and client have different ICU data versions
- Server doesn't have vi-VN locale installed

**Risk Level:** LOW - Modern Node.js includes full ICU by default.

**Recommendation:** No action needed unless errors observed. If issues occur:
```tsx
// Use Intl.NumberFormat for consistency
const formatter = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 1 })
return formatter.format(value)
```

---

## Recently Modified Files Analysis

| File | Hydration Risk | Notes |
|------|---------------|-------|
| dashboard-header.tsx | LOW | Client state via useEffect is safe |
| dashboard-layout.tsx | Check | Need to verify usage of useIsMobile |
| notification-panel.tsx (NEW) | MEDIUM | formatDistanceToNow issue |
| job-progress-bar.tsx (NEW) | LOW | No time-sensitive renders |
| progress.tsx (NEW) | NONE | Pure UI component |
| use-jobs-status.ts (NEW) | NONE | Only TanStack Query hooks |

---

## Recommendations

### Immediate Actions (P0)

1. **Fix sidebar.tsx Math.random()** - Replace with deterministic widths
2. **Fix use-mobile.tsx** - Handle undefined state properly or use suppressHydrationWarning

### Short-term (P1)

3. **Add suppressHydrationWarning** to notification-panel.tsx time display
4. **Audit components using useIsMobile()** - Ensure they handle undefined state

### Best Practices Going Forward

- Never use `Math.random()`, `Date.now()`, or `new Date()` in render paths
- Always handle `undefined` state for client-only hooks
- Use `suppressHydrationWarning` sparingly for intentionally dynamic content
- Consider `next/dynamic` with `ssr: false` for client-only components

---

## Files to Review

```
/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/ui/sidebar.tsx
/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-mobile.tsx
/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/layout/notification-panel.tsx
```

---

## Unresolved Questions

1. Is `SidebarMenuSkeleton` actually rendered during SSR? If only used in loading states, issue may not manifest.
2. Are there error logs in production showing actual hydration errors?
3. Does the server environment have vi-VN locale data installed?
