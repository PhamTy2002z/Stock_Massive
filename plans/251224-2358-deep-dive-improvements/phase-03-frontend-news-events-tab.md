# Phase 03: Frontend News & Events Tab

## Context

- **Plan**: [plan.md](./plan.md)
- **Depends on**: [phase-01](./phase-01-backend-trading-news-apis.md), [phase-02](./phase-02-frontend-money-flow-tab.md)

## Overview

| Field | Value |
|-------|-------|
| Priority | P1 |
| Status | Pending |
| Effort | 3h |
| Description | Create "Tin Tức & Sự Kiện" tab with News, Dividends, Insider Deals |

## Key Insights

- News API returns ~15 items, no pagination
- Dividends returns full history
- Insider Deals already exists - reuse hook
- 3 collapsible sections in single tab
- Cache: News 5min, Dividends 24h

## Requirements

**Functional:**
- News list with title, date, source
- Dividends table with history
- Insider Deals section (reuse existing)
- Collapsible sections

**Non-functional:**
- Fast initial render
- Reuse existing InsiderDeals component if possible

## Architecture

```
apps/web/src/components/dashboard/
├── news-events-tab-content.tsx     # NEW - Main container
├── news-list.tsx                   # NEW - News cards
├── dividends-table.tsx             # NEW - Dividend history
├── news-events-skeleton.tsx        # NEW - Loading state
└── shareholders-tab-content.tsx    # Existing - has InsiderDeals
```

## Related Code Files

**Create:**
- `apps/web/src/components/dashboard/news-events-tab-content.tsx`
- `apps/web/src/components/dashboard/news-list.tsx`
- `apps/web/src/components/dashboard/dividends-table.tsx`
- `apps/web/src/components/dashboard/news-events-skeleton.tsx`
- `apps/web/src/hooks/use-company-news.ts`
- `apps/web/src/hooks/use-company-dividends.ts`

**Modify:**
- `apps/web/src/lib/api.ts` - Add news, dividends types and functions
- `apps/web/src/lib/query-keys.ts` - Add query keys
- `apps/web/src/components/dashboard/stock-detail-client.tsx` - Render NewsEventsTabContent
- `apps/web/src/components/dashboard/index.ts` - Export new components

## Implementation Steps

### Step 1: Add API Types & Functions (15min)

```typescript
// apps/web/src/lib/api.ts - ADD:

export interface NewsItem {
  id: number;
  title: string;
  source: string | null;
  published_at: string;
  price: number | null;
  price_change_pct: number | null;
}

export interface NewsResponse {
  symbol: string;
  items: NewsItem[];
}

export interface DividendItem {
  exercise_date: string;
  year: number;
  dividend_pct: number;
  method: 'cash' | 'share';
}

export interface DividendsResponse {
  symbol: string;
  items: DividendItem[];
}

export async function fetchCompanyNews(symbol: string): Promise<NewsResponse> {
  const res = await fetch(`${API_BASE_URL}/stocks/${symbol}/news`);
  if (!res.ok) throw new Error(`Failed to fetch news: ${res.status}`);
  return res.json();
}

export async function fetchCompanyDividends(symbol: string): Promise<DividendsResponse> {
  const res = await fetch(`${API_BASE_URL}/stocks/${symbol}/dividends`);
  if (!res.ok) throw new Error(`Failed to fetch dividends: ${res.status}`);
  return res.json();
}
```

### Step 2: Add Query Keys (5min)

```typescript
// apps/web/src/lib/query-keys.ts - ADD:
companyNews: (symbol: string) => ['companyNews', symbol] as const,
companyDividends: (symbol: string) => ['companyDividends', symbol] as const,
```

### Step 3: Create Hooks (15min)

```typescript
// apps/web/src/hooks/use-company-news.ts
import { useQuery } from "@tanstack/react-query";
import { fetchCompanyNews, NewsResponse } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

export function useCompanyNews(symbol: string | null) {
  return useQuery<NewsResponse>({
    queryKey: queryKeys.companyNews(symbol ?? ""),
    queryFn: () => fetchCompanyNews(symbol!),
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000, // 5 min
  });
}
```

```typescript
// apps/web/src/hooks/use-company-dividends.ts
import { useQuery } from "@tanstack/react-query";
import { fetchCompanyDividends, DividendsResponse } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

export function useCompanyDividends(symbol: string | null) {
  return useQuery<DividendsResponse>({
    queryKey: queryKeys.companyDividends(symbol ?? ""),
    queryFn: () => fetchCompanyDividends(symbol!),
    enabled: !!symbol,
    staleTime: 60 * 60 * 1000, // 1 hour (rarely changes)
  });
}
```

### Step 4: Create News List Component (30min)

```typescript
// apps/web/src/components/dashboard/news-list.tsx
"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { ChevronDown, Newspaper } from "lucide-react"
import { NewsItem } from "@/lib/api"
import { useState } from "react"
import { cn } from "@/lib/utils"

interface NewsListProps {
  items: NewsItem[];
}

export function NewsList({ items }: NewsListProps) {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <Card>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <Newspaper className="h-4 w-4" />
                Tin Tức Mới Nhất
                <Badge variant="secondary">{items.length}</Badge>
              </CardTitle>
              <ChevronDown className={cn("h-4 w-4 transition-transform", isOpen && "rotate-180")} />
            </div>
          </CardHeader>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent className="pt-0">
            <ul className="space-y-3">
              {items.slice(0, 10).map((item) => (
                <li key={item.id} className="border-b last:border-0 pb-2 last:pb-0">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium line-clamp-2">{item.title}</p>
                      <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                        <span>{new Date(item.published_at).toLocaleDateString('vi-VN')}</span>
                        {item.source && <span>• {item.source}</span>}
                      </div>
                    </div>
                    {item.price_change_pct !== null && (
                      <Badge variant={item.price_change_pct >= 0 ? "default" : "destructive"}>
                        {item.price_change_pct >= 0 ? '+' : ''}{(item.price_change_pct * 100).toFixed(2)}%
                      </Badge>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}
```

### Step 5: Create Dividends Table (25min)

```typescript
// apps/web/src/components/dashboard/dividends-table.tsx
"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { ChevronDown, Coins } from "lucide-react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { DividendItem } from "@/lib/api"
import { useState } from "react"
import { cn } from "@/lib/utils"

interface DividendsTableProps {
  items: DividendItem[];
}

export function DividendsTable({ items }: DividendsTableProps) {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <Card>
        <CollapsibleTrigger asChild>
          <CardHeader className="cursor-pointer hover:bg-muted/50 transition-colors">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <Coins className="h-4 w-4" />
                Lịch Sử Cổ Tức
                <Badge variant="secondary">{items.length}</Badge>
              </CardTitle>
              <ChevronDown className={cn("h-4 w-4 transition-transform", isOpen && "rotate-180")} />
            </div>
          </CardHeader>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent className="pt-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Ngày GDKQ</TableHead>
                  <TableHead>Năm</TableHead>
                  <TableHead className="text-right">Tỷ Lệ</TableHead>
                  <TableHead>Loại</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.slice(0, 10).map((item, idx) => (
                  <TableRow key={idx}>
                    <TableCell>{item.exercise_date}</TableCell>
                    <TableCell>{item.year}</TableCell>
                    <TableCell className="text-right font-medium">
                      {(item.dividend_pct * 100).toFixed(1)}%
                    </TableCell>
                    <TableCell>
                      <Badge variant={item.method === 'cash' ? 'outline' : 'secondary'}>
                        {item.method === 'cash' ? 'Tiền mặt' : 'Cổ phiếu'}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}
```

### Step 6: Create Skeleton (10min)

```typescript
// apps/web/src/components/dashboard/news-events-skeleton.tsx
"use client"

import { Skeleton } from "@/components/ui/skeleton"

export function NewsEventsSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-[200px] rounded-lg" />
      <Skeleton className="h-[200px] rounded-lg" />
      <Skeleton className="h-[200px] rounded-lg" />
    </div>
  );
}
```

### Step 7: Create Tab Content Container (30min)

```typescript
// apps/web/src/components/dashboard/news-events-tab-content.tsx
"use client"

import { useCompanyNews } from "@/hooks/use-company-news"
import { useCompanyDividends } from "@/hooks/use-company-dividends"
import { useInsiderDeals } from "@/hooks/use-insider-deals"  // Existing hook
import { NewsList } from "./news-list"
import { DividendsTable } from "./dividends-table"
import { InsiderDealsTable } from "./insider-deals-table"  // Existing component
import { NewsEventsSkeleton } from "./news-events-skeleton"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertCircle } from "lucide-react"

interface NewsEventsTabContentProps {
  symbol: string;
}

export function NewsEventsTabContent({ symbol }: NewsEventsTabContentProps) {
  const { data: newsData, isLoading: newsLoading, error: newsError } = useCompanyNews(symbol);
  const { data: dividendsData, isLoading: dividendsLoading } = useCompanyDividends(symbol);
  const { data: insiderData, isLoading: insiderLoading } = useInsiderDeals(symbol);

  const isLoading = newsLoading || dividendsLoading || insiderLoading;

  if (isLoading) return <NewsEventsSkeleton />;

  if (newsError) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>Failed to load news data</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      <NewsList items={newsData?.items ?? []} />
      <DividendsTable items={dividendsData?.items ?? []} />
      {insiderData && insiderData.items.length > 0 && (
        <InsiderDealsTable items={insiderData.items} />
      )}
    </div>
  );
}
```

### Step 8: Wrap Insider Deals in Collapsible (Optional - if not already)

Check if `InsiderDealsTable` exists. If not, create simple wrapper:

```typescript
// May need to create or modify existing component
```

### Step 9: Render Tab Content (10min)

```typescript
// apps/web/src/components/dashboard/stock-detail-client.tsx - ADD:
import { NewsEventsTabContent } from "./news-events-tab-content"

// In render:
{activeTab === "news-events" && <NewsEventsTabContent symbol={data.symbol} />}
```

### Step 10: Export Components (5min)

```typescript
// apps/web/src/components/dashboard/index.ts - ADD:
export * from "./news-events-tab-content"
export * from "./news-list"
export * from "./dividends-table"
export * from "./news-events-skeleton"
```

## Todo List

- [ ] Add NewsItem, DividendItem types to api.ts
- [ ] Add fetchCompanyNews, fetchCompanyDividends functions
- [ ] Add query keys for news, dividends
- [ ] Create use-company-news.ts hook
- [ ] Create use-company-dividends.ts hook
- [ ] Create news-list.tsx with collapsible
- [ ] Create dividends-table.tsx with collapsible
- [ ] Create news-events-skeleton.tsx
- [ ] Create news-events-tab-content.tsx container
- [ ] Check/wrap existing InsiderDeals component
- [ ] Render NewsEventsTabContent in stock-detail-client
- [ ] Export all new components
- [ ] Test tab functionality

## Success Criteria

- [ ] News & Events tab appears in tabs bar
- [ ] News section shows latest 10 items
- [ ] Dividends table shows history
- [ ] Insider Deals section visible
- [ ] All sections collapsible
- [ ] Loading skeleton works
- [ ] Error handling works

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Empty news | Low | Show "Không có tin tức" |
| Insider deals component missing | Medium | Create simple table |

## Next Steps

→ Phase 04: UI Sticky Elements & Mobile
