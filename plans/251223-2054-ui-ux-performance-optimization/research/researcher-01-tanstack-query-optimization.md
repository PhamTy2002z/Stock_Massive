# TanStack Query v5 Optimization Patterns

**Date**: 2024-12-23 | **Source**: TanStack Query v5 Official Docs

---

## 1. placeholderData vs keepPreviousData

**v5 Breaking Change**: `keepPreviousData` option REMOVED. Use `placeholderData` with helper.

```tsx
import { useQuery, keepPreviousData } from '@tanstack/react-query'

// CORRECT v5 pattern
const { data, isPlaceholderData } = useQuery({
  queryKey: ['projects', page],
  queryFn: () => fetchProjects(page),
  placeholderData: keepPreviousData,  // helper function
})

// Alternative: identity function
placeholderData: (previousData) => previousData
```

**Key difference**: `isPlaceholderData` replaces `isPreviousData`.

---

## 2. Preventing Flicker During Refetch

**Problem**: UI flickers when data transitions between loading/success states.

```tsx
// Solution: Combine placeholderData + isFetching indicator
const { data, isFetching, isPlaceholderData } = useQuery({
  queryKey: ['todos', filter],
  queryFn: fetchTodos,
  placeholderData: keepPreviousData,
  staleTime: 30_000,  // 30s - reduces unnecessary refetches
})

// UI: Show subtle loading, not full skeleton
return (
  <div style={{ opacity: isFetching ? 0.7 : 1 }}>
    {data?.map(item => <Item key={item.id} {...item} />)}
    {isFetching && <Spinner size="small" />}
  </div>
)
```

**Anti-pattern**: Avoid showing loading skeleton on refetch - use opacity/spinner instead.

---

## 3. refetchInterval Optimization

**Problem**: Aggressive polling wastes resources.

```tsx
// Dynamic interval based on state
const { data } = useQuery({
  queryKey: ['stocks'],
  queryFn: fetchStocks,
  refetchInterval: (query) => {
    // Faster polling on error for recovery
    if (query.state.status === 'error') return 5_000
    // Normal polling
    return 60_000  // 1 minute
  },
  staleTime: 30_000,  // Prevent refetch if data fresh
})
```

**Best practices**:
- Use `staleTime` to gate refetches (prevents network spam)
- Consider user activity - pause polling when idle
- For real-time data: WebSocket > polling

```tsx
// Conditional polling - only when tab visible
refetchInterval: document.hidden ? false : 30_000
```

---

## 4. refetchIntervalInBackground

**When to enable**: Data critical even when tab inactive (monitoring dashboards).
**When to disable** (default): Most apps - saves resources.

```tsx
// Enable for critical monitoring
const { data } = useQuery({
  queryKey: ['system-status'],
  queryFn: fetchSystemStatus,
  refetchInterval: 30_000,
  refetchIntervalInBackground: true,  // continues in background
})

// Disable (default) for standard apps
const { data } = useQuery({
  queryKey: ['user-data'],
  queryFn: fetchUser,
  refetchInterval: 60_000,
  refetchIntervalInBackground: false,  // pauses when tab hidden
})
```

---

## 5. Suspense Integration (useSuspenseQuery)

**v5 Pattern**: Use `useSuspenseQuery` for Suspense-enabled queries.

```tsx
import { useSuspenseQuery } from '@tanstack/react-query'
import { Suspense } from 'react'

function TodoList() {
  // Automatically suspends until data ready
  const { data } = useSuspenseQuery({
    queryKey: ['todos'],
    queryFn: fetchTodos,
  })

  // data is GUARANTEED non-null here
  return data.map(todo => <Todo key={todo.id} {...todo} />)
}

// Parent must have Suspense boundary
function App() {
  return (
    <Suspense fallback={<Skeleton />}>
      <TodoList />
    </Suspense>
  )
}
```

**Critical rules**:
- Data access MUST be inside Suspense boundary
- No `isPending` check needed - data guaranteed
- Error boundaries handle errors

---

## Quick Reference Table

| Pattern | Use Case | Key Option |
|---------|----------|------------|
| `keepPreviousData` | Pagination, filters | `placeholderData: keepPreviousData` |
| Flicker prevention | Any refetch | `staleTime` + opacity on `isFetching` |
| Smart polling | Live data | `refetchInterval: (query) => ...` |
| Background sync | Dashboards | `refetchIntervalInBackground: true` |
| Suspense | SSR, clean loading | `useSuspenseQuery` |

---

## Unresolved Questions

None - patterns are well-documented in v5.
