# TanStack Query v5: Smooth Loading Transitions

## 1. useSuspenseQuery vs useQuery

### When to Use Each

| Hook | Use Case |
|------|----------|
| `useSuspenseQuery` | Simple data fetching where loading/error handled by boundaries |
| `useQuery` | Complex UX requiring granular loading states, transitions |

### useSuspenseQuery Characteristics
- Data always defined (no `undefined` checks needed)
- Loading/error states handled by React Suspense + Error Boundaries
- **Limitation**: Does NOT support `placeholderData` option
- Multiple calls execute serially (waterfall), not parallel

```tsx
// useSuspenseQuery - data guaranteed defined
const { data } = useSuspenseQuery({ queryKey: ['post', id], queryFn })
// ^? data: Post (never undefined)
```

### Migration: useSuspenseQuery to useQuery

When you need smooth transitions with `keepPreviousData`:

```tsx
// Before: useSuspenseQuery (no placeholderData support)
const { data } = useSuspenseQuery({ queryKey, queryFn })

// After: useQuery with keepPreviousData
import { useQuery, keepPreviousData } from '@tanstack/react-query'

const { data, isPending, isPlaceholderData } = useQuery({
  queryKey,
  queryFn,
  placeholderData: keepPreviousData,
})
```

---

## 2. keepPreviousData Pattern

### How It Works

```tsx
import { useQuery, keepPreviousData } from '@tanstack/react-query'

const { data, isPending, isFetching, isPlaceholderData } = useQuery({
  queryKey: ['items', page],
  queryFn: () => fetchItems(page),
  placeholderData: keepPreviousData, // Shows previous data while fetching new
})
```

### State Flags Explained

| Flag | Meaning |
|------|---------|
| `isPending` | No data yet (first load only) |
| `isFetching` | Currently fetching (any fetch, including refetch) |
| `isPlaceholderData` | Showing previous/placeholder data while fetching new |

### Key Insight
- `isPending` = true only on **first load**d data)
- `isFetching` = true on **any fetch** (initial, refetch, key change)
- With `keepPreviousData`: `isPending` stays false after first load

---

## 3. Component Patterns for Smooth Transitions

### Pattern A: Opacity Fade During Loading

```tsx
function DataList({ category }) {
  const { data, isFetching, isPlaceholderData } = useQuery({
    queryKey: ['items', category],
    queryFn: () => fetchItems(category),
    placeholderData: keepPreviousData,
  })

  return (
    <div style={{
      opacity: isPlaceholderData ? 0.6 : 1,
      transition: 'opacity 200ms ease'
    }}>
      {data?.map(item => <Item key={item.id} {...item} />)}
      {isFetching && <LoadingSpinner position="corner" />}
    </div>
  )
}
```

### Pattern B: First Load vs Subsequent Loads

```tsx
function DataSection() {
  const { data, isPending, isFetching, isPlaceholderData } = useQuery({
    queryKey,
    queryFn,
    placeholderData: keepPreviousData,
  })

  // First load: show skeleton
  if (isPending) {
    return <Skeleton />
  }

  // Subsequent loads: show data with subtle indicator
  return (
    <div className={isPlaceholderData ? 'opacity-60' : ''}>
      {data.map(renderItem)}
      {isFetching && <RefetchIndicator />}
    </div>
  )
}
```

### Pattern C: Loading Overlay (Non-Blocking)

```tsx
function TableWithOverlay() {
  const { data, isFetching, isPlaceholderData } = useQuery({...})

  return (
    <div className="relative">
      <Table data={data} />
      {isFetching && (
        <div className="absolute inset-0 bg-white/50 flex items-center justify-center">
          <Spinner />
        </div>
      )}
    </div>
  )
}
```

---

## 4. Real-World Examples

### Tab Switching Without Flash

```tsx
function TabbedContent() {
  const [activeTab, setActiveTab] = useState('overview')

  const { data, isPlaceholderData, isFetching } = useQuery({
    queryKey: ['content', activeTab],
    queryFn: () => fetchContent(activeTab),
    placeholderData: keepPreviousData,
  })

  return (
    <div>
      <TabBar
        active={activeTab}
        onChange={setActiveTab}
        disabled={isPlaceholderData} // Prevent rapid switching
      />
      <div className={cn(
        'transition-opacity duration-200',
        isPlaceholderData && 'opacity-50'
      )}>
        <Content data={data} />
      </div>
      {isFetching && <LoadingBar />}
    </div>
  )
}
```

### Mefresh Button

```tsx
function RefreshableData() {
  const { data, isFetching, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
    placeholderData: keepPreviousData,
  })

  return (
    <div>
      <button
        onClick={() => refetch()}
        disabled={isFetching}
        className="flex items-center gap-2"
      >
        <RefreshIcon className={isFetching ? 'animate-spin' : ''} />
        {isFetching ? 'Refreshing...' : 'Refresh'}
      </button>
      <DataDisplay data={data} />
    </div>
  )
}
```

### Auto-Refetch with Subtle Indicator

```tsx
function LiveData() {
  const { data, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ['live-stats'],
    queryFn: fetchStats,
    refetchInterval: 30000, // Auto-refetch every 30s
    placeholderData: keepPreviousData,
  })

  return (
    <div>
      <div className="flex items-center gap-2 text-sm text-muted">
        {isFetching ? (
          <span className="animate-pulse">Updating...</span>
        ) : (
          <span>Updated {formatRelative(dataUpdatedAt)}</span>
        )}
      </div>
      <StatsDisplay data={data} />
    </div>
  )
}
```

---

## Best Practices Summary

1. **Use `useQuery` + `keepPreviousData`** for smooth transitions (not useSuspenseQuery)
2. **Check `isPending`** for first-load skeleton
3. **Check `isPlaceholderData`** for opacity/disabled states during transitions
4. **Check `isFetching`** for subtle loading indicators (spinners, progress bars)
5. **Disable navigation** while `isPlaceholderData` to prevent rapid state changes
6. **Use CSS transitions** for smooth opacity changes

## Unresolved Questions

- None identified for this research scope
