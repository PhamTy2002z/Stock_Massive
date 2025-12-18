# Phase 3: Frontend - Search Integration & Component Updates

**Status:** Pending
**Effort:** 2-3 hours
**Priority:** High
**Depends On:** Phase 1 (Backend) + Phase 2 (State Management)

---

## Context

**Problem:** Search bar returns stock symbol but doesn't trigger stock detail update. Components still need final integration testing.

**Solution:** Connect search selection to page state, verify all data flows correctly, add polish features.

**Related Research:**
- `/plans/251218-2134-stock-detail-realtime/research/researcher-02-frontend-components.md`

---

## Overview

Final integration phase:
1. Verify search → state → API → components flow
2. Add default stock on page load
3. Implement URL-based stock selection (optional)
4. Add visual feedback for price changes
5. Polish loading transitions

---

## Requirements

### Functional
- Search selection updates all dashboard components
- URL parameter support: `/?symbol=VCB`
- Default to VCB if no symbol provided
- Smooth transitions between stocks
- Price change animation (flash effect)

### Non-Functional
- No layout shift during loading
- Accessible keyboard navigation
- SEO-friendly (server-side rendering compatible)
- Mobile-responsive

---

## Architecture

### Complete Data Flow
```
User Action (Search or URL)
    ↓
setSelectedSymbol(symbol)
    ↓
useStockDetail hook
    ↓
API: GET /stocks/{symbol}/detail
    ↓
Update state: data, isLoading, error
    ↓
Re-render 4 components:
  - StockTickerHeader (price, change)
  - StockDetailPanel (volume, value, cap, industry)
  - StockStatsTable (intraday, 52w, ratios)
  - StockCompanyInfo (metadata, description)
```

---

## Implementation Steps

### Step 1: Add URL Parameter Support (app/page.tsx)

**Update page component to read URL params:**
```typescript
"use client"

import { useState, useEffect } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import { DashboardLayout } from "@/components/layout"
// ... other imports

export default function Home() {
  const searchParams = useSearchParams()
  const router = useRouter()

  // Initialize from URL or default to VCB
  const [selectedSymbol, setSelectedSymbol] = useState<string>(() => {
    return searchParams.get("symbol") || "VCB"
  })

  // Fetch stock detail data
  const { data, isLoading, error, refetch } = useStockDetail(selectedSymbol)

  // Update URL when symbol changes
  const handleStockSelect = (symbol: string) => {
    setSelectedSymbol(symbol)

    // Update URL without page reload
    const params = new URLSearchParams(searchParams.toString())
    params.set("symbol", symbol)
    router.push(`/?${params.toString()}`, { scroll: false })
  }

  // Sync URL changes back to state
  useEffect(() => {
    const urlSymbol = searchParams.get("symbol")
    if (urlSymbol && urlSymbol !== selectedSymbol) {
      setSelectedSymbol(urlSymbol)
    }
  }, [searchParams])

  return (
    <DashboardLayout onStockSelect={handleStockSelect}>
      {/* ... rest of component */}
    </DashboardLayout>
  )
}
```

### Step 2: Add Price Change Animation (components/dashboard/stock-ticker-header.tsx)

**Add flash effect when price changes:**
```typescript
"use client"

import { useEffect, useState } from "react"
import { cn } from "@/lib/utils"

interface StockTickerHeaderProps {
  symbol: string
  companyName: string
  price: number
  change: number
  changePercent: number
  className?: string
}

export function StockTickerHeader({
  symbol,
  companyName,
  price,
  change,
  changePercent,
  className,
}: StockTickerHeaderProps) {
  const [priceFlash, setPriceFlash] = useState(false)
  const [prevPrice, setPrevPrice] = useState(price)

  const isPositive = change >= 0

  // Trigger flash animation when price changes
  useEffect(() => {
    if (price !== prevPrice && prevPrice !== 0) {
      setPriceFlash(true)
      const timer = setTimeout(() => setPriceFlash(false), 500)
      return () => clearTimeout(timer)
    }
    setPrevPrice(price)
  }, [price])

  // Format with comma as decimal separator (Vietnamese style)
  const formattedPrice = price.toLocaleString("vi-VN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).replace(".", ",")

  const formattedChange = change.toLocaleString("vi-VN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).replace(".", ",")

  const formattedPercent = `${isPositive ? "+" : ""}${changePercent.toFixed(2).replace(".", ",")}%`

  return (
    <div className={cn("py-4", className)}>
      <div className="flex items-start justify-between gap-4">
        {/* Left: Company Name & Symbol */}
        <div className="min-w-0 flex-1">
          <h2 className="text-xl font-semibold text-foreground leading-tight">
            {companyName}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">{symbol}</p>
        </div>

        {/* Right: Price & Change */}
        <div className="text-right shrink-0">
          <p
            className={cn(
              "text-2xl font-semibold tabular-nums transition-all duration-300",
              isPositive ? "text-emerald-500" : "text-red-500",
              priceFlash && "scale-110 brightness-125"
            )}
          >
            {formattedPrice}
          </p>
          <p
            className={cn(
              "mt-1 text-sm font-medium tabular-nums",
              isPositive ? "text-emerald-500" : "text-red-500"
            )}
          >
            ({formattedPercent}) {isPositive ? "+" : ""}{formattedChange}
          </p>
        </div>
      </div>
    </div>
  )
}
```

### Step 3: Add Empty State Component

**Create file: components/dashboard/stock-detail-empty.tsx**
```typescript
"use client"

import { Search } from "lucide-react"

export function StockDetailEmpty() {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="rounded-full bg-muted p-4 mb-4">
        <Search className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="text-lg font-semibold text-foreground mb-2">
        No Stock Selected
      </h3>
      <p className="text-sm text-muted-foreground max-w-sm">
        Search for a stock symbol using the search bar above to view detailed information.
      </p>
    </div>
  )
}
```

### Step 4: Update Page with Empty State (app/page.tsx)

**Add empty state handling:**
```typescript
export default function Home() {
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null)

  // Initialize with VCB on mount
  useEffect(() => {
    const urlSymbol = searchParams.get("symbol")
    setSelectedSymbol(urlSymbol || "VCB")
  }, [])

  const { data, isLoading, error, refetch } = useStockDetail(selectedSymbol)

  return (
    <DashboardLayout onStockSelect={handleStockSelect}>
      <div className="flex flex-col gap-6">
        {/* Market Indices Section */}
        <section>
          <h2 className="text-lg font-semibold text-foreground mb-4">
            Chỉ số thị trường
          </h2>
          <MarketIndices />
        </section>

        {/* Selected Stock Detail */}
        <section className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
          {/* Empty State */}
          {!selectedSymbol && !isLoading && (
            <div className="lg:col-span-2">
              <StockDetailEmpty />
            </div>
          )}

          {/* Error State */}
          {error && (
            <div className="lg:col-span-2">
              <StockDetailError error={error} onRetry={refetch} />
            </div>
          )}

          {/* Loading or Data State */}
          {selectedSymbol && (
            <>
              {/* Left: Main Content */}
              <div className="space-y-4">
                {isLoading ? (
                  <>
                    <StockTickerHeaderSkeleton />
                    <StockDetailPanelSkeleton />
                    <StockStatsTableSkeleton />
                  </>
                ) : data ? (
                  <>
                    <StockTickerHeader
                      symbol={data.symbol}
                      companyName={data.company_name || data.symbol}
                      price={data.price || 0}
                      change={data.change || 0}
                      changePercent={data.change_pct || 0}
                    />
                    <StockDetailPanel
                      volume={data.volume || 0}
                      tradingValue={(data.trading_value || 0) / 1_000_000_000}
                      marketCap={data.market_cap || 0}
                      industry={data.industry || "N/A"}
                    />
                    <StockStatsTable
                      openPrice={data.open_price || data.ref_price || 0}
                      highPrice={data.high_price || 0}
                      lowPrice={data.low_price || 0}
                      tradingVolume={data.volume || 0}
                      marketCap={data.market_cap || 0}
                      high52Week={data.high_52_week || 0}
                      low52Week={data.low_52_week || 0}
                      avgVolume52Week={data.avg_volume_52_week || 0}
                      eps={data.eps}
                      pe={data.pe}
                      beta={data.beta}
                      dividendYield={data.dividend_yield}
                    />
                  </>
                ) : null}
              </div>

              {/* Right: Company Info Sidebar */}
              <div className="space-y-4">
                {isLoading ? (
                  <StockCompanyInfoSkeleton />
                ) : data ? (
                  <StockCompanyInfo
                    symbol={data.symbol}
                    industry={data.industry || "N/A"}
                    marketCap={data.market_cap || 0}
                    outstandingShares={(data.outstanding_shares || 0) / 1_000_000_000}
                    exchange={data.exchange}
                    vn30Rank={null}
                    description={data.description || "No description available."}
                  />
                ) : null}
              </div>
            </>
          )}
        </section>
      </div>
    </DashboardLayout>
  )
}
```

### Step 5: Add Transition Animations (globals.css)

**Add smooth transitions:**
```css
/* Stock detail transitions */
@layer utilities {
  .stock-detail-enter {
    animation: fadeIn 0.3s ease-in-out;
  }

  .stock-detail-exit {
    animation: fadeOut 0.2s ease-in-out;
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes fadeOut {
    from {
      opacity: 1;
    }
    to {
      opacity: 0;
    }
  }

  /* Price flash animation */
  .price-flash {
    animation: priceFlash 0.5s ease-in-out;
  }

  @keyframes priceFlash {
    0%, 100% {
      transform: scale(1);
      filter: brightness(1);
    }
    50% {
      transform: scale(1.1);
      filter: brightness(1.25);
    }
  }
}
```

### Step 6: Add Keyboard Shortcuts (Optional Enhancement)

**Add keyboard navigation:**
```typescript
// In page.tsx
useEffect(() => {
  const handleKeyPress = (e: KeyboardEvent) => {
    // Cmd/Ctrl + K to focus search
    if ((e.metaKey || e.ctrlKey) && e.key === "k") {
      e.preventDefault()
      // Focus search bar (implement in DashboardHeader)
      document.querySelector<HTMLInputElement>('[data-search-input]')?.focus()
    }
  }

  window.addEventListener("keydown", handleKeyPress)
  return () => window.removeEventListener("keydown", handleKeyPress)
}, [])
```

### Step 7: Add Meta Tags for SEO (app/page.tsx)

**Add dynamic metadata:**
```typescript
import { Metadata } from "next"

export async function generateMetadata({
  searchParams,
}: {
  searchParams: { symbol?: string }
}): Promise<Metadata> {
  const symbol = searchParams.symbol || "VCB"

  return {
    title: `${symbol} - Stock Detail | Stock Massive`,
    description: `View real-time stock data, financial ratios, and company information for ${symbol}`,
    openGraph: {
      title: `${symbol} Stock Detail`,
      description: `Real-time data for ${symbol}`,
    },
  }
}
```

---

## Todo List

- [ ] Add URL parameter support to page.tsx
- [ ] Implement handleStockSelect with URL update
- [ ] Add price change animation to StockTickerHeader
- [ ] Create StockDetailEmpty component
- [ ] Update page.tsx with empty state handling
- [ ] Add transition animations to globals.css
- [ ] Test search → state → API → components flow
- [ ] Test URL navigation: `/?symbol=VCB`, `/?symbol=HAG`
- [ ] Test browser back/forward buttons
- [ ] Verify mobile responsiveness
- [ ] Test keyboard navigation (optional)
- [ ] Add SEO metadata (optional)

---

## Success Criteria

- [ ] Search selection updates URL and components
- [ ] Direct URL access works: `/?symbol=VCB`
- [ ] Browser back/forward buttons work correctly
- [ ] Price flash animation triggers on data update
- [ ] Smooth transitions between stocks
- [ ] No layout shift during loading
- [ ] Empty state displays when no symbol selected
- [ ] Mobile layout works correctly
- [ ] All TypeScript types are correct

---

## Testing Scenarios

### Search Integration
1. Open page → VCB loads by default
2. Search for "HAG" → Select from dropdown
3. Verify URL updates to `/?symbol=HAG`
4. Verify all 4 components update with HAG data
5. Search for "ACB" → Select from dropdown
6. Verify smooth transition from HAG to ACB

### URL Navigation
1. Navigate to `/?symbol=VCB` → Verify VCB loads
2. Navigate to `/?symbol=HAG` → Verify HAG loads
3. Click browser back button → Verify returns to VCB
4. Click browser forward button → Verify returns to HAG

### Edge Cases
1. Navigate to `/?symbol=INVALID` → Verify error state
2. Navigate to `/?symbol=` → Verify default VCB loads
3. Rapid symbol changes → Verify debounce works
4. Network offline → Verify error message

### Visual Polish
1. Select new stock → Verify price flash animation
2. Throttle network → Verify loading skeletons
3. Resize window → Verify responsive layout
4. Test on mobile device → Verify touch interactions

---

## Performance Checklist

- [ ] Debounce prevents rapid API calls (300ms)
- [ ] No memory leaks from unmounted components
- [ ] Smooth 60fps animations
- [ ] No unnecessary re-renders
- [ ] Images lazy load (if any added)
- [ ] API responses cached (browser cache)

---

## Accessibility Checklist

- [ ] Keyboard navigation works
- [ ] Screen reader announces loading states
- [ ] Error messages are accessible
- [ ] Focus management on search selection
- [ ] Color contrast meets WCAG AA
- [ ] Skip links for keyboard users

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| URL sync issues | Low | Medium | Test thoroughly, add error boundaries |
| Animation jank on slow devices | Medium | Low | Use CSS transforms, test on mobile |
| SEO issues with client-side rendering | Medium | Medium | Add metadata, consider SSR later |
| Browser history pollution | Low | Low | Use replace instead of push for some updates |

---

## Related Files

**Modified:**
- `/apps/web/src/app/page.tsx` - URL params, empty state
- `/apps/web/src/components/dashboard/stock-ticker-header.tsx` - Price animation
- `/apps/web/src/app/globals.css` - Transition animations

**New:**
- `/apps/web/src/components/dashboard/stock-detail-empty.tsx`

**Referenced:**
- All Phase 2 files (hooks, skeletons, error components)

---

## Post-Implementation Tasks

After all phases complete:

1. **Documentation:**
   - Update API documentation with new endpoint
   - Add component usage examples
   - Document URL parameter format

2. **Monitoring:**
   - Add analytics for stock searches
   - Track API response times
   - Monitor error rates

3. **Future Enhancements:**
   - Add stock comparison feature
   - Implement watchlist
   - Add real-time WebSocket updates
   - Add chart visualization
   - Add news feed integration

---

## Completion Checklist

- [ ] All 3 phases implemented
- [ ] End-to-end testing complete
- [ ] No console errors or warnings
- [ ] TypeScript compiles without errors
- [ ] Mobile responsive verified
- [ ] Accessibility tested
- [ ] Performance benchmarked
- [ ] Code reviewed
- [ ] Documentation updated
- [ ] Ready for production deployment

---

## Next Steps

1. Complete Phase 1 backend implementation
2. Complete Phase 2 state management
3. Complete Phase 3 integration (this phase)
4. Conduct end-to-end testing
5. Deploy to staging environment
6. User acceptance testing
7. Production deployment
