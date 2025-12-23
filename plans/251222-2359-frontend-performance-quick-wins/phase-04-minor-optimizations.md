# Phase 4: Minor Optimizations

## Context
- **Research:** [React Performance - Common Re-render Causes](./research/researcher-01-react-performance.md#3-common-re-render-causes--fixes)
- **Priority:** P3 - LOW IMPACT
- **Effort:** 10 minutes
- **Status:** pending

## Overview
Small optimizations that individually have minimal impact but collectively improve code quality and prevent potential performance issues.

## Requirements
- Move Supabase client creation outside component
- Fix any other low-hanging optimization opportunities
- Maintain all existing functionality

## Implementation Steps

### 1. Fix Supabase Client Creation in dashboard-header.tsx
**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/layout/dashboard-header.tsx`

**Problem:** `createClient()` called on every render (line 32), creating new instance unnecessarily.

**Before (lines 29-32):**
```typescript
export function DashboardHeader({ onStockSelect }: DashboardHeaderProps) {
  const router = useRouter()
  const [user, setUser] = useState<SupabaseUser | null>(null)
  const supabase = createClient()
```

**After:**
```typescript
export function DashboardHeader({ onStockSelect }: DashboardHeaderProps) {
  const router = useRouter()
  const [user, setUser] = useState<SupabaseUser | null>(null)
  const supabase = useMemo(() => createClient(), [])
```

**Add useMemo import (line 3):**
```diff
- import { useEffect, useState } from "react"
+ import { useEffect, useState, useMemo } from "react"
```

## Code Changes Summary

### dashboard-header.tsx

**Import change (line 3):**
```diff
  "use client"

- import { useEffect, useState } from "react"
+ import { useEffect, useState, useMemo } from "react"
  import { useRouter } from "next/navigation"
```

**Component change (line 32):**
```diff
  export function DashboardHeader({ onStockSelect }: DashboardHeaderProps) {
    const router = useRouter()
    const [user, setUser] = useState<SupabaseUser | null>(null)
-   const supabase = createClient()
+   const supabase = useMemo(() => createClient(), [])

    useEffect(() => {
      // Get initial user
```

## Success Criteria
- [ ] Supabase client created once per component lifecycle
- [ ] Auth functionality works identically
- [ ] No console warnings
- [ ] Sign in/out works correctly

## Testing
1. Navigate to any dashboard page
2. Verify header renders correctly
3. Test sign in functionality
4. Test sign out functionality
5. Verify user avatar/name displays
6. Check React DevTools - supabase should be stable reference
7. No console errors or warnings

## Risk Assessment
**Risk Level:** MINIMAL

- **Breaking Changes:** None - same client, stable reference
- **User Impact:** None - invisible optimization
- **Rollback:** Trivial - remove useMemo wrapper
- **Dependencies:** None - React built-in
- **Auth Impact:** None - client behavior unchanged

## Performance Impact
- **Re-renders:** Prevents unnecessary client recreation
- **Memory:** Negligible improvement
- **Auth Performance:** No measurable change
- **Code Quality:** Better - follows React best practices

## Additional Opportunities (Future)

### 1. Optimize Icon Imports
If bundle analysis shows large icon library size:

```typescript
// Current (loads all icons)
import { Bell, HelpCircle, LogIn, ... } from "lucide-react"

// Optimized (tree-shakeable)
// Add to next.config.js:
experimental: {
  optimizePackageImports: ['lucide-react'],
}
```

### 2. Memoize User Display Values
If profiling shows frequent recalculation:

```typescript
const userDisplayInfo = useMemo(() => ({
  name: user?.user_metadata?.full_name || user?.email?.split("@")[0] || "User",
  email: user?.email || "",
  avatar: user?.user_metadata?.avatar_url || "",
  initials: (user?.user_metadata?.full_name || user?.email?.split("@")[0] || "User")
    .slice(0, 2).toUpperCase(),
}), [user])
```

### 3. Debounce Search Input
If search causes performance issues:

```typescript
import { useDebouncedCallback } from 'use-debounce'

const debouncedSearch = useDebouncedCallback(
  (value) => performSearch(value),
  300
)
```

## Notes
- These optimizations are preventive rather than reactive
- Profile before implementing additional optimizations
- Focus on user-facing performance first
- Code quality improvements have long-term value
- Don't over-optimize without measurements
