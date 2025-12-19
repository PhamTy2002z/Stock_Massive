---
title: "Hybrid SSR + TanStack Query Migration"
description: "Migrate frontend from CSR to hybrid SSR with TanStack Query for better performance"
status: in-progress
priority: P1
effort: 6h
branch: main
tags: [frontend, ssr, tanstack-query, performance]
created: 2024-12-19
---

# Hybrid SSR + TanStack Query Migration Plan

## Overview

Migrate Stock_Massive frontend from 95% client-side rendering (useState/useEffect) to hybrid SSR architecture with TanStack Query v5. Clean migration without backward compatibility.

**Current**: Next.js 14.2 with custom hooks using useState/useEffect
**Target**: Server Components + TanStack Query + client islands
**Scope**: 7 data-fetching hooks, main dashboard page, API layer

## Phases

### Phase 1: TanStack Query Setup
**Status**: done (2024-12-19)
**File**: [phase-01-tanstack-query-setup.md](./phase-01-tanstack-query-setup.md)
**Effort**: 1h
Install TanStack Query v5, create QueryClientProvider, setup query key factory

**Completed:**
- Installed @tanstack/react-query v5.90.12 + devtools
- Created QueryProvider component w/ SSR-safe config
- Created query key factory w/ all endpoints
- Updated root layout.tsx w/ QueryProvider
- Build + type-check passed

**Files Changed:**
- NEW: `src/components/providers/query-provider.tsx`
- NEW: `src/lib/query-keys.ts`
- MOD: `src/app/layout.tsx`
- MOD: `package.json`

### Phase 2: Hooks Migration
**Status**: pending
**File**: [phase-02-hooks-migration.md](./phase-02-hooks-migration.md)
**Effort**: 2.5h
Convert 7 custom hooks to TanStack Query hooks with proper error/loading states

### Phase 3: SSR Integration
**Status**: pending
**File**: [phase-03-ssr-integration.md](./phase-03-ssr-integration.md)
**Effort**: 2h
Convert page.tsx to Server Component, add prefetching, create client islands

### Phase 4: Cleanup & Testing
**Status**: pending
**File**: [phase-04-cleanup-testing.md](./phase-04-cleanup-testing.md)
**Effort**: 0.5h
Remove old hooks, verify all flows, performance check

## Success Criteria

- TanStack Query v5 installed and configured
- All 7 hooks migrated to useQuery/useMutation
- page.tsx is Server Component with prefetched data
- Market indices + sector performance load server-side
- Client islands handle interactive features
- Loading/error states preserved
- No console errors, all features functional
- Initial page load faster (FCP/LCP improved)

## Dependencies

- Research reports completed
- Next.js 14.2+ (App Router)
- FastAPI backend unchanged
- ShadCN UI components unchanged

## Risks

- Hydration mismatches (mitigated by HydrationBoundary)
- Query key collisions (mitigated by key factory)
- Breaking existing components (mitigated by incremental migration)

---

## Validation Summary

**Validated:** 2024-12-19
**Questions asked:** 6

### Confirmed Decisions

| Decision | User Choice |
|----------|-------------|
| Caching Strategy | **Relaxed** - 5min staleTime for all queries (less API load) |
| SSR Prefetch Scope | **All three** - Market indices + sector performance + default stock |
| React Query DevTools | **Yes** - Enable in development |
| Old Hooks | **Replace completely** - Delete after migration |
| ISR Revalidate | **60 seconds** - Balance freshness vs server load |
| Phase Approach | **Approved** - 4 phases as planned |

### Action Items (Plan Adjustments)

- [ ] Update staleTime values in phase-02 to 5 minutes (relaxed strategy)
- [ ] Confirm ISR revalidate: 60 in phase-03 api-server.ts
- [ ] Ensure old hooks are deleted in phase-04 cleanup

### Recommendation

**Proceed to implementation** - All key decisions confirmed, no blockers identified.
