# React 18+ Performance Optimization Patterns

**Date**: 2024-12-23 | **ID**: researcher-251223-2054

## 1. React.memo - Prevent Unnecessary Re-renders

Use when: component receives same props frequently, renders expensive UI, parent re-renders often.
Avoid when: props change frequently, component is simple/cheap.

```tsx
// Good: Expensive list item with stable props
const StockRow = React.memo(({ symbol, price, change }: StockRowProps) => (
  <tr><td>{symbol}</td><td>{price}</td><td>{change}</td></tr>
));

// With custom comparison (shallow by default)
const ChartCard = React.memo(({ data, config }: ChartProps) => (
  <Chart data={data} config={config} />
), (prev, next) => prev.data.length === next.data.length && prev.config.id === next.config.id);
```

## 2. useMemo/useCallback - Stabilize References

**useMemo**: Cache expensive computations or object/array references.
**useCallback**: Cache function references passed to memoized children.

```tsx
function StockDashboard({ stocks }: { stocks: Stock[] }) {
  // useMemo: expensive filter/sort
  const topGainers = useMemo(
    () => stocks.filter(s => s.change > 0).sort((a, b) => b.change - a.change).slice(0, 10),
    [stocks]
  );

  // useCallback: stable handler for memoized child
  const handleRowClick = useCallback((symbol: string) => {
    router.push(`/stock/${symbol}`);
  }, [router]);

  return <StockTable data={topGainers} onRowClick={handleRowClick} />;
}
```

**Rules**:
- Don't wrap primitives (strings, numbers) - already stable
- Dependencies must be stable or memoized themselves
- Measure before optimizing - profiler first

## 3. Lazy Loading Components

Use React.lazy + Suspense for code-splitting heavy components (charts, modals, analytics).

```tsx
// Lazy load chart library (reduces initial bundle)
const StockChart = lazy(() => import('@/components/charts/stock-chart'));
const VolumeHeatmap = lazy(() => import('@/components/charts/volume-heatmap'));

function AnalyticsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96" />}>
      <StockChart symbol="AAPL" />
    </Suspense>
  );
}

// Named exports require wrapper
const FinancialTable = lazy(() =>
  import('@/components/tables').then(m => ({ default: m.FinancialTable }))
);
```

**Next.js**: Use `next/dynamic` for SSR control:
```tsx
const Chart = dynamic(() => import('./Chart'), { ssr: false, loading: () => <Skeleton /> });
```

## 4. Virtual Scrolling - @tanstack/react-virtual

Renders only visible items - critical for 100+ rows.

```tsx
import { useVirtualizer } from '@tanstack/react-virtual';

function VirtualStockList({ stocks }: { stocks: Stock[] }) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: stocks.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 48, // row height
    overscan: 5, // buffer rows
  });

  return (
    <div ref={parentRef} style={{ height: 600, overflow: 'auto' }}>
      <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
        {virtualizer.getVirtualItems().map((row) => (
          <div
            key={row.key}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: row.size,
              transform: `translateY(${row.start}px)`,
            }}
          >
            <StockRow stock={stocks[row.index]} />
          </div>
        ))}
      </div>
    </div>
  );
}
```

## 5. CSS Performance Optimization

### GPU Acceleration
```css
/* Use transform instead of top/left for animations */
.stock-ticker {
  transform: translateX(var(--offset));
  will-change: transform; /* hint to browser, use sparingly */
}

/* Promote to own layer for heavy animations */
.animated-chart {
  transform: translateZ(0); /* creates GPU layer */
  backface-visibility: hidden;
}
```

### Smooth Scrolling
```css
.scroll-container {
  overflow-y: auto;
  scroll-behavior: smooth;
  overscroll-behavior: contain; /* prevent scroll chaining */
  -webkit-overflow-scrolling: touch; /* iOS momentum */
}
```

### Reduce Paint/Layout
```css
/* contain limits recalc scope */
.stock-card {
  contain: layout style paint; /* or: content */
}

/* Avoid layout thrashing - batch reads/writes */
.price-change {
  opacity: 1;
  transition: opacity 0.2s; /* opacity is cheap */
}
```

## Summary Table

| Pattern | When to Use | Impact |
|---------|-------------|--------|
| React.memo | Stable props, expensive render | High |
| useMemo | Expensive compute, reference stability | Medium |
| useCallback | Callbacks to memoized children | Medium |
| React.lazy | Heavy components, routes | High (bundle) |
| Virtual scroll | Lists > 100 items | Critical |
| CSS GPU accel | Animations, transforms | High |

---

**Unresolved Questions**: None - patterns well-established in React 18+.
