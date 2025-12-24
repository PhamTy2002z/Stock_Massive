# Phase 04: UI Sticky Elements & Mobile

## Context

- **Plan**: [plan.md](./plan.md)
- **Depends on**: [phase-02](./phase-02-frontend-money-flow-tab.md), [phase-03](./phase-03-frontend-news-events-tab.md)

## Overview

| Field | Value |
|-------|-------|
| Priority | P2 |
| Status | Pending |
| Effort | 3h |
| Description | Add Quick Stats Bar, Sticky Tabs, Mobile dropdown overflow |

## Key Insights

- Quick Stats Bar: Always visible, shows key metrics
- Sticky Tabs: Stays at top when scrolling
- Mobile: 4 tabs visible + "More" dropdown for extras
- Use existing ShadCN components (DropdownMenu)

## Requirements

**Functional:**
- Quick Stats Bar: Symbol, price, change, volume, foreign net, P/E
- Sticky Tabs + Quick Stats when scrolling
- Mobile: First 4 tabs + dropdown for rest

**Non-functional:**
- Smooth scroll behavior
- No layout shift on sticky
- Accessible dropdown

## Architecture

```
apps/web/src/components/dashboard/
├── quick-stats-bar.tsx           # NEW - Sticky stats bar
├── stock-detail-tabs.tsx         # MODIFY - Add mobile dropdown
└── stock-detail-client.tsx       # MODIFY - Sticky container
```

## Related Code Files

**Create:**
- `apps/web/src/components/dashboard/quick-stats-bar.tsx`

**Modify:**
- `apps/web/src/components/dashboard/stock-detail-tabs.tsx` - Mobile dropdown logic
- `apps/web/src/components/dashboard/stock-detail-client.tsx` - Sticky wrapper
- `apps/web/src/app/analytics/deep-dive/page.tsx` - Scroll container

## Implementation Steps

### Step 1: Create Quick Stats Bar (30min)

```typescript
// apps/web/src/components/dashboard/quick-stats-bar.tsx
"use client"

import { cn } from "@/lib/utils"
import { TrendingUp, TrendingDown, Volume2, Users, BarChart3 } from "lucide-react"

interface QuickStatsBarProps {
  symbol: string;
  companyName: string;
  price: number;
  change: number;
  changePct: number;
  volume: number;
  foreignNet?: number;
  pe?: number;
  className?: string;
}

export function QuickStatsBar({
  symbol,
  companyName,
  price,
  change,
  changePct,
  volume,
  foreignNet,
  pe,
  className,
}: QuickStatsBarProps) {
  const isPositive = change >= 0;
  const TrendIcon = isPositive ? TrendingUp : TrendingDown;

  const formatVolume = (vol: number) => {
    if (vol >= 1_000_000) return `${(vol / 1_000_000).toFixed(1)}M`;
    if (vol >= 1_000) return `${(vol / 1_000).toFixed(0)}K`;
    return vol.toString();
  };

  const formatForeignNet = (net: number) => {
    const absNet = Math.abs(net);
    const formatted = absNet >= 1_000_000
      ? `${(absNet / 1_000_000).toFixed(1)}M`
      : `${(absNet / 1_000).toFixed(0)}K`;
    return net >= 0 ? `+${formatted}` : `-${formatted}`;
  };

  return (
    <div className={cn(
      "flex items-center gap-4 px-4 py-2 bg-background/95 backdrop-blur border-b",
      "overflow-x-auto scrollbar-hide",
      className
    )}>
      {/* Symbol & Name */}
      <div className="flex items-center gap-2 shrink-0">
        <span className="font-bold text-lg">{symbol}</span>
        <span className="text-sm text-muted-foreground hidden sm:inline truncate max-w-[120px]">
          {companyName}
        </span>
      </div>

      {/* Price & Change */}
      <div className="flex items-center gap-2 shrink-0">
        <span className="font-semibold">{price.toLocaleString()}</span>
        <div className={cn(
          "flex items-center gap-1 text-sm",
          isPositive ? "text-green-500" : "text-red-500"
        )}>
          <TrendIcon className="h-3 w-3" />
          <span>{isPositive ? '+' : ''}{changePct.toFixed(2)}%</span>
        </div>
      </div>

      {/* Divider */}
      <div className="h-4 w-px bg-border shrink-0" />

      {/* Stats */}
      <div className="flex items-center gap-4 text-sm text-muted-foreground shrink-0">
        <div className="flex items-center gap-1">
          <Volume2 className="h-3 w-3" />
          <span>Vol: {formatVolume(volume)}</span>
        </div>

        {foreignNet !== undefined && (
          <div className="flex items-center gap-1">
            <Users className="h-3 w-3" />
            <span className={cn(
              foreignNet >= 0 ? "text-green-500" : "text-red-500"
            )}>
              Ngoại: {formatForeignNet(foreignNet)}
            </span>
          </div>
        )}

        {pe !== undefined && pe > 0 && (
          <div className="flex items-center gap-1">
            <BarChart3 className="h-3 w-3" />
            <span>P/E: {pe.toFixed(1)}</span>
          </div>
        )}
      </div>
    </div>
  );
}
```

### Step 2: Update Tabs for Mobile Dropdown (45min)

```typescript
// apps/web/src/components/dashboard/stock-detail-tabs.tsx - REPLACE:
"use client"

import { useState } from "react"
import { cn } from "@/lib/utils"
import { BarChart3, Wallet, Users, Activity, TrendingUp, Newspaper, MoreHorizontal } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"
import { useMediaQuery } from "@/hooks/use-media-query"

export type StockDetailTabValue = "overview" | "finance" | "shareholders" | "volume" | "money-flow" | "news-events"

interface StockDetailTabsProps {
  value?: StockDetailTabValue
  onChange?: (value: StockDetailTabValue) => void
  className?: string
}

const allTabs = [
  { value: "overview" as const, label: "Tổng Quan", icon: BarChart3 },
  { value: "finance" as const, label: "Tài Chính", icon: Wallet },
  { value: "shareholders" as const, label: "Cổ Đông", icon: Users },
  { value: "volume" as const, label: "Khối Lượng", icon: Activity },
  { value: "money-flow" as const, label: "Dòng Tiền", icon: TrendingUp },
  { value: "news-events" as const, label: "Tin Tức", icon: Newspaper },
]

const MOBILE_VISIBLE_TABS = 4

export function StockDetailTabs({
  value = "overview",
  onChange,
  className,
}: StockDetailTabsProps) {
  const [activeTab, setActiveTab] = useState<StockDetailTabValue>(value)
  const isMobile = useMediaQuery("(max-width: 768px)")

  const handleTabClick = (tabValue: StockDetailTabValue) => {
    setActiveTab(tabValue)
    onChange?.(tabValue)
  }

  const visibleTabs = isMobile ? allTabs.slice(0, MOBILE_VISIBLE_TABS) : allTabs
  const overflowTabs = isMobile ? allTabs.slice(MOBILE_VISIBLE_TABS) : []
  const activeOverflowTab = overflowTabs.find(t => t.value === activeTab)

  return (
    <div className={cn("w-full", className)}>
      <div className="flex items-center gap-2 p-1 rounded-xl bg-muted/50 border border-border/50">
        {visibleTabs.map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.value

          return (
            <button
              key={tab.value}
              onClick={() => handleTabClick(tab.value)}
              className={cn(
                "relative flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg",
                "text-sm font-medium transition-all duration-200 ease-out",
                "flex-1 min-w-0",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                isActive && [
                  "bg-background text-foreground shadow-sm border border-border/80",
                ],
                !isActive && [
                  "text-muted-foreground hover:text-foreground hover:bg-background/50",
                  "active:scale-[0.98]",
                ]
              )}
            >
              {isActive && (
                <span className="absolute inset-x-0 -bottom-px h-0.5 bg-gradient-to-r from-transparent via-primary/50 to-transparent" />
              )}
              <Icon className={cn(
                "h-4 w-4 shrink-0",
                isActive ? "text-primary" : "text-muted-foreground"
              )} />
              <span className="truncate">{tab.label}</span>
            </button>
          )
        })}

        {/* Mobile Overflow Dropdown */}
        {isMobile && overflowTabs.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant={activeOverflowTab ? "default" : "ghost"}
                size="sm"
                className={cn(
                  "flex items-center gap-2 px-3 py-2.5 rounded-lg",
                  activeOverflowTab && "bg-background shadow-sm border"
                )}
              >
                {activeOverflowTab ? (
                  <>
                    <activeOverflowTab.icon className="h-4 w-4" />
                    <span className="truncate">{activeOverflowTab.label}</span>
                  </>
                ) : (
                  <>
                    <MoreHorizontal className="h-4 w-4" />
                    <span>Thêm</span>
                  </>
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {overflowTabs.map((tab) => {
                const Icon = tab.icon
                return (
                  <DropdownMenuItem
                    key={tab.value}
                    onClick={() => handleTabClick(tab.value)}
                    className={cn(
                      activeTab === tab.value && "bg-muted"
                    )}
                  >
                    <Icon className="h-4 w-4 mr-2" />
                    {tab.label}
                  </DropdownMenuItem>
                )
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
    </div>
  )
}

// Keep skeleton unchanged
export function StockDetailTabsSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("w-full", className)}>
      <div className="flex items-center gap-2 p-1 rounded-xl bg-muted/50 border border-border/50">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="flex-1 h-10 rounded-lg bg-muted animate-pulse" />
        ))}
      </div>
    </div>
  )
}
```

### Step 3: Create useMediaQuery Hook (10min)

```typescript
// apps/web/src/hooks/use-media-query.ts
import { useState, useEffect } from "react"

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false)

  useEffect(() => {
    const media = window.matchMedia(query)
    setMatches(media.matches)

    const listener = (event: MediaQueryListEvent) => setMatches(event.matches)
    media.addEventListener("change", listener)
    return () => media.removeEventListener("change", listener)
  }, [query])

  return matches
}
```

### Step 4: Add Sticky Container in Stock Detail Client (30min)

```typescript
// apps/web/src/components/dashboard/stock-detail-client.tsx - MODIFY:

import { QuickStatsBar } from "./quick-stats-bar"

// In render, wrap header elements in sticky container:
{!isLoading && !error && data && (
  <div className="stock-detail-enter">
    {/* Sticky Header Group */}
    <div className="sticky top-0 z-20 -mx-6 px-6 bg-background/95 backdrop-blur">
      <QuickStatsBar
        symbol={data.symbol}
        companyName={data.company_name || data.symbol}
        price={data.price || 0}
        change={data.change || 0}
        changePct={data.change_pct || 0}
        volume={data.volume || 0}
        foreignNet={undefined}  // TODO: Add from foreignTrading data
        pe={data.pe}
      />
      <StockDetailTabs
        value={activeTab}
        onChange={setActiveTab}
        className="py-2"
      />
    </div>

    {/* Tab Content (scrollable) */}
    {activeTab === "overview" && (
      <div className="space-y-4 pt-4">
        <StockDetailPanel ... />
        <StockStatsTable ... />
      </div>
    )}
    {activeTab === "finance" && <FinanceTabContent symbol={data.symbol} />}
    {activeTab === "shareholders" && <ShareholdersTabContent symbol={data.symbol} />}
    {activeTab === "volume" && <VolumeTabContent symbol={data.symbol} />}
    {activeTab === "money-flow" && <MoneyFlowTabContent symbol={data.symbol} />}
    {activeTab === "news-events" && <NewsEventsTabContent symbol={data.symbol} />}
  </div>
)}
```

### Step 5: Add Scrollbar Hide Utility (5min)

```css
/* apps/web/src/app/globals.css - ADD: */
.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
```

### Step 6: Export Components (5min)

```typescript
// apps/web/src/components/dashboard/index.ts - ADD:
export * from "./quick-stats-bar"

// apps/web/src/hooks/index.ts - ADD:
export * from "./use-media-query"
```

### Step 7: Test Responsive Behavior (30min)

1. Desktop: All 6 tabs visible
2. Tablet: All 6 tabs visible (may be cramped)
3. Mobile (<768px): 4 tabs + "Thêm" dropdown
4. Scroll: Quick Stats + Tabs stick to top
5. Dropdown: Shows extra tabs, clicking switches tab

## Todo List

- [ ] Create quick-stats-bar.tsx component
- [ ] Create use-media-query.ts hook
- [ ] Update stock-detail-tabs.tsx with mobile dropdown
- [ ] Add sticky wrapper in stock-detail-client.tsx
- [ ] Add scrollbar-hide utility to globals.css
- [ ] Export new components and hooks
- [ ] Test on desktop (all tabs visible)
- [ ] Test on mobile (4 tabs + dropdown)
- [ ] Test sticky behavior on scroll
- [ ] Test dropdown navigation

## Success Criteria

- [ ] Quick Stats Bar shows key metrics
- [ ] Sticky header stays at top on scroll
- [ ] Mobile shows 4 tabs + "Thêm" dropdown
- [ ] Dropdown shows remaining tabs
- [ ] Active tab in dropdown shows in button
- [ ] No layout shift on sticky
- [ ] Smooth transitions

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Sticky z-index conflicts | Low | Test with modals, overlays |
| Mobile dropdown UX | Low | Clear visual indicator |

## Security Considerations

- No security concerns for UI-only changes

## Next Steps

→ Testing & QA across all phases
→ Performance optimization if needed
