# Research: Real-time Updates, Dashboard Customization & Onboarding

**Date:** 2025-12-28
**Researcher:** researcher subagent
**Focus:** Stock dashboard real-time patterns, drag-drop grids, onboarding tours

---

## 1. Real-time Updates for Stock Data

### 1.1 Transport Protocols Comparison

| Approach | Pros | Cons | Best For |
|----------|------|------|----------|
| **WebSocket** | • Bidirectional, lowest latency<br>• Single connection for all data<br>• Native browser support | • Complex reconnection logic<br>• Server complexity<br>• Infrastructure cost | High-frequency trading, tick-by-tick updates |
| **SSE (Server-Sent Events)** | • Auto-reconnection<br>• Simple HTTP-based<br>• Event ID for resume | • Unidirectional only<br>• HTTP/1.1 connection limits (6 per domain) | Price feeds, market status updates |
| **Polling (TanStack Query)** | • Simple implementation<br>• Works anywhere<br>• Built-in cache/refetch | • Higher latency (1-30s)<br>• Unnecessary requests | Dashboard metrics, delayed quotes |

**Recommendation:**
- **Primary:** SSE for price feeds (1-5s updates)
- **Fallback:** Polling with `refetchInterval` (10-30s)
- **Future:** WebSocket only if sub-second updates required

### 1.2 TanStack Query Patterns

#### Optimistic Updates
```typescript
const mutation = useMutation({
  mutationFn: updateOrder,
  onMutate: async (newOrder) => {
    await queryClient.cancelQueries({ queryKey: ['orders'] })
    const previous = queryClient.getQueryData(['orders'])

    queryClient.setQueryData(['orders'], (old) => [...old, newOrder])
    return { previous }
  },
  onError: (err, newOrder, context) => {
    queryClient.setQueryData(['orders'], context.previous)
  },
  onSettled: () => {
    queryClient.invalidateQueries({ queryKey: ['orders'] })
  }
})
```

#### Stale Data Indicators
```typescript
const { data, isStale, dataUpdatedAt } = useQuery({
  queryKey: ['stockPrice', symbol],
  queryFn: fetchPrice,
  staleTime: 5000, // 5s
  refetchInterval: 10000 // Poll every 10s
})

// Visual indicator
{isStale && <Badge color="yellow">Stale ({Date.now() - dataUpdatedAt}ms)</Badge>}
```

#### Real-time Integration
```typescript
useEffect(() => {
  const eventSource = new EventSource(`/api/stocks/${symbol}/stream`)

  eventSource.onmessage = (event) => {
    const newData = JSON.parse(event.data)
    queryClient.setQueryData(['stockPrice', symbol], newData)
  }

  return () => eventSource.close()
}, [symbol])
```

### 1.3 Flash Animation for Price Changes

**Recommended:** CSS-only approach for performance

```css
@keyframes flash-green {
  0% { background-color: rgb(34 197 94 / 0.3); }
  100% { background-color: transparent; }
}

@keyframes flash-red {
  0% { background-color: rgb(239 68 68 / 0.3); }
  100% { background-color: transparent; }
}

.price-flash-up {
  animation: flash-green 600ms ease-out;
}

.price-flash-red {
  animation: flash-red 600ms ease-out;
}
```

**React Hook:**
```typescript
const usePriceFlash = (price: number) => {
  const [flash, setFlash] = useState<'up' | 'down' | null>(null)
  const prevPrice = useRef(price)

  useEffect(() => {
    if (price > prevPrice.current) setFlash('up')
    else if (price < prevPrice.current) setFlash('down')

    prevPrice.current = price
    const timer = setTimeout(() => setFlash(null), 600)
    return () => clearTimeout(timer)
  }, [price])

  return flash
}
```

---

## 2. Dashboard Customization

### 2.1 Drag-Drop Grid Libraries

#### **react-grid-layout** ⭐ RECOMMENDED

**Pros:**
- Production-proven (AWS CloudFront, Grafana, Kibana, Monday)
- Full TypeScript v2.0+ with React Hooks API
- Responsive breakpoints with separate layouts
- Pluggable compaction (O(n log n) fast algorithm)
- Tree-shakeable, modular architecture
- Static widgets + bounded dragging/resizing

**Cons:**
- Only grid-based (no free-form placement)
- Learning curve for advanced customization

**Bundle Size:** ~50KB minified
**TypeScript:** Native (no @types needed)

**Use Case:** Dashboard with responsive grid widgets, fixed layouts per breakpoint

```typescript
import { useGridLayout } from 'react-grid-layout/hooks'

const { layout, handlers } = useGridLayout({
  gridConfig: { cols: 12, rowHeight: 60 },
  dragConfig: { handle: '.drag-handle' },
  resizeConfig: { minW: 2, minH: 2 }
})
```

#### **gridstack.js**

**Pros:**
- jQuery-free modern version
- Sub-grid support (nested grids)
- Auto-positioning algorithm

**Cons:**
- React wrapper not first-class
- Heavier bundle (~100KB)
- TypeScript support limited

**Use Case:** Complex nested dashboard requirements

#### **react-beautiful-dnd**

**Pros:**
- Beautiful animations, accessibility-first
- Keyboard navigation, screen reader support

**Cons:**
- List/column layouts only (NOT grid)
- Maintenance mode (no new features)
- No responsive breakpoints

**Use Case:** Kanban boards, reorderable lists (NOT dashboards)

---

### 2.2 Saved Views Persistence

| Strategy | Pros | Cons | Recommended For |
|----------|------|------|-----------------|
| **localStorage** | • Zero latency<br>• Works offline<br>• No API calls | • 5-10MB limit<br>• Not synced across devices<br>• Cleared by user | Single-device power users |
| **Backend DB** | • Cross-device sync<br>• Unlimited storage<br>• Shareable views | • API latency<br>• Server dependency | Multi-device, team sharing |
| **Hybrid** | • Best of both<br>• localStorage as cache | • Sync complexity | Production apps |

**Recommended Pattern (Hybrid):**
```typescript
const usePersistedLayout = (userId: string) => {
  const { data: serverLayout } = useQuery({
    queryKey: ['layout', userId],
    queryFn: fetchLayout,
    staleTime: Infinity
  })

  const [localLayout, setLocalLayout] = useLocalStorage(
    `layout:${userId}`,
    serverLayout
  )

  const mutation = useMutation({
    mutationFn: saveLayout,
    onMutate: async (newLayout) => {
      setLocalLayout(newLayout) // Instant local update
      return newLayout
    }
  })

  return { layout: localLayout, save: mutation.mutate }
}
```

### 2.3 Widget Registry Pattern

```typescript
// widgets/registry.ts
export const WIDGET_REGISTRY = {
  'price-chart': {
    component: lazy(() => import('./PriceChart')),
    defaultSize: { w: 6, h: 4 },
    minSize: { w: 3, h: 2 },
    title: 'Price Chart',
    icon: TrendingUpIcon
  },
  'order-book': {
    component: lazy(() => import('./OrderBook')),
    defaultSize: { w: 4, h: 6 },
    minSize: { w: 2, h: 3 },
    title: 'Order Book',
    icon: ListIcon
  }
} as const

type WidgetType = keyof typeof WIDGET_REGISTRY
```

---

## 3. Onboarding & Help

### 3.1 Onboarding Tour Libraries

#### **driver.js** ⭐ RECOMMENDED

**Pros:**
- Zero dependencies, vanilla JS (2KB gzipped)
- Framework-agnostic (works with React, Vue, Angular)
- Keyboard navigation, screen reader support
- Popover positioning engine (auto-adjust)
- Highlight elements without DOM manipulation

**Cons:**
- No React hooks wrapper (need to create own)
- Minimal built-in analytics

**Bundle Size:** 2KB gzipped
**TypeScript:** Full support

**Use Case:** Lightweight, accessible product tours

```typescript
import { driver } from 'driver.js'

const tourDriver = driver({
  showProgress: true,
  steps: [
    { element: '#dashboard', popover: { title: 'Dashboard', description: '...' } },
    { element: '#add-widget', popover: { title: 'Add Widget', description: '...' } }
  ]
})

tourDriver.drive()
```

#### **react-joyride**

**Pros:**
- React-first with hooks API
- Callback system for step tracking
- Beacon/tooltip modes
- Continuous/controlled tours

**Cons:**
- Heavier bundle (~15KB)
- Styling customization complex
- Popper.js dependency

**Bundle Size:** 15KB
**TypeScript:** Yes

**Use Case:** React apps needing step analytics

#### **shepherd.js**

**Pros:**
- Tour lifecycle hooks (before/after each step)
- Tether.js positioning (robust)
- Browser back/forward support

**Cons:**
- Heaviest bundle (~25KB)
- Tether.js adds 10KB more
- Complex API

**Bundle Size:** 25KB
**TypeScript:** Limited

**Use Case:** Complex multi-page tours

### 3.2 Contextual Help Patterns

**Tooltip Library:** `@radix-ui/react-tooltip` (shadcn/ui)
- Accessible, keyboard navigation
- Delay control, portal rendering
- No popover conflicts

**Feature Discovery (Dot Indicators):**
```typescript
const useFeatureDiscovery = (featureKey: string) => {
  const [dismissed, setDismissed] = useLocalStorage(`feature:${featureKey}`, false)

  return {
    showIndicator: !dismissed,
    dismiss: () => setDismissed(true)
  }
}

// UI
{showIndicator && <Badge className="animate-pulse">New</Badge>}
```

**Help Panel Pattern:**
```typescript
// Contextual help sidebar
const HelpPanel = ({ context }: { context: string }) => {
  const helpContent = HELP_CONTENT[context]

  return (
    <Sheet>
      <SheetTrigger><HelpCircleIcon /></SheetTrigger>
      <SheetContent>
        <SheetHeader>{helpContent.title}</SheetHeader>
        <div dangerouslySetInnerHTML={{ __html: helpContent.html }} />
        <Button onClick={() => startTour(context)}>Show Tour</Button>
      </SheetContent>
    </Sheet>
  )
}
```

---

## Recommendations Summary

1. **Real-time:** SSE + TanStack Query with `refetchInterval` fallback
2. **Flash animations:** CSS keyframes + `usePriceFlash` hook
3. **Grid library:** `react-grid-layout` v2.0+ (TypeScript, production-proven)
4. **Persistence:** Hybrid (localStorage cache + backend sync)
5. **Onboarding:** `driver.js` (2KB, accessible) + `@radix-ui/react-tooltip`

---

## Unresolved Questions

1. **Real-time backend:** Which SSE library on backend (Node.js/Go)? Need infrastructure research.
2. **Widget state:** Should widget internal state persist (chart zoom level, filters)?
3. **Tour triggers:** Auto-start on first visit or manual "Take Tour" button?
4. **Help content:** CMS for help content or hardcoded markdown?
