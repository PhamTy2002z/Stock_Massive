# Phase 5: Integration & Testing

## Context

- **Plan**: [plan.md](../plan.md)
- **Phase 2**: [Health Scorecard UI](phase-2-health-scorecard-ui.md)
- **Phase 3**: [Trend Charts](phase-3-trend-charts.md)
- **Phase 4**: [Peer Comparison & FCF](phase-4-peer-fcf.md)

## Overview

Integrate all components into Financial Statements page and add end-to-end tests.

## Key Insights

- Use Sheet (slide-over) pattern for stock detail panel
- Row click triggers panel with all 4 analysis components
- Parallel API fetching with TanStack Query
- Stale-while-revalidate for smooth UX

## Requirements

### Page Layout

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  Bao Cao Tai Chinh                                                             │
│  Top 50 cong ty co loi nhuan cao nhat tu HOSE & HNX (theo quy)                │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  # │ Symbol │ Company          │ Net Profit │ Revenue │ Margin │ EPS    │  │
│  ├────┼────────┼──────────────────┼────────────┼─────────┼────────┼────────┤  │
│  │  1 │ VCB    │ Vietcombank      │  12.5T     │  85.2T  │ +14.7% │ 8,450  │  │
│  │  2 │ VNM ←  │ Vinamilk  [click]│   8.2T     │  62.1T  │ +13.2% │ 4,820  │ ←Sheet opens
│  │  3 │ VHM    │ Vinhomes         │   7.8T     │  45.3T  │ +17.2% │ 2,310  │  │
│  │ ...│        │                  │            │         │        │        │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘

When row clicked, Sheet opens from right:

┌────────────────────────────────────────────┐
│  VNM - Vinamilk                     [X]    │
├────────────────────────────────────────────┤
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │  Financial Health Score             │  │
│  │  [Radar Chart]    Score: 75/100     │  │
│  └──────────────────────────────────────┘  │
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │  Trend Analysis                     │  │
│  │  [Tabs: Revenue|Margin|ROE|Cash]    │  │
│  └──────────────────────────────────────┘  │
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │  Peer Comparison - Thuc pham        │  │
│  │  [Heatmap Table]                    │  │
│  └──────────────────────────────────────┘  │
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │  FCF Analysis                       │  │
│  │  [Waterfall + CCC]                  │  │
│  └──────────────────────────────────────┘  │
│                                            │
└────────────────────────────────────────────┘
```

## Architecture

```
apps/web/src/
├── app/analytics/financial-statements/
│   └── page.tsx                              # Updated page
├── components/dashboard/
│   ├── financial-statements-table.tsx        # Updated: add row click
│   ├── financial-detail-sheet.tsx            # NEW: Sheet container
│   ├── financial-health/                     # Phase 2
│   ├── financial-trends/                     # Phase 3
│   ├── peer-comparison/                      # Phase 4
│   └── fcf-analysis/                         # Phase 4
└── hooks/
    └── use-financial-detail.ts               # NEW: Combines all queries
```

## Related Files

| File | Action |
|------|--------|
| `/apps/web/src/app/analytics/financial-statements/page.tsx` | Update layout |
| `/apps/web/src/components/dashboard/financial-statements-table.tsx` | Add row click handler |
| `/apps/web/src/components/dashboard/financial-detail-sheet.tsx` | **NEW** |
| `/apps/web/src/hooks/use-financial-detail.ts` | **NEW** |
| `/apps/api/src/tests/test_financial_endpoints.py` | **NEW** |

## Implementation Steps

### Step 1: Create Combined Hook

**File: `/apps/web/src/hooks/use-financial-detail.ts`**

```typescript
import { useHealthScore } from "./use-health-score"
import { useTrendMetrics } from "./use-trend-metrics"
import { useSectorPeers } from "./use-sector-peers"
import { useFCFAnalysis } from "./use-fcf-analysis"

export function useFinancialDetail(symbol: string | null) {
  const healthScore = useHealthScore(symbol)
  const trendMetrics = useTrendMetrics(symbol)
  const sectorPeers = useSectorPeers(symbol)
  const fcfAnalysis = useFCFAnalysis(symbol)

  const isLoading =
    healthScore.isLoading ||
    trendMetrics.isLoading ||
    sectorPeers.isLoading ||
    fcfAnalysis.isLoading

  const hasError =
    healthScore.error ||
    trendMetrics.error ||
    sectorPeers.error ||
    fcfAnalysis.error

  return {
    healthScore,
    trendMetrics,
    sectorPeers,
    fcfAnalysis,
    isLoading,
    hasError,
  }
}
```

### Step 2: Create Financial Detail Sheet

**File: `/apps/web/src/components/dashboard/financial-detail-sheet.tsx`**

```tsx
"use client"

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { HealthScoreCard } from "./financial-health/health-score-card"
import { TrendChartsCard } from "./financial-trends/trend-charts-card"
import { PeerComparisonCard } from "./peer-comparison/peer-comparison-card"
import { FCFAnalysisCard } from "./fcf-analysis/fcf-analysis-card"
import type { FinancialStatementItem } from "@/lib/api"

interface FinancialDetailSheetProps {
  stock: FinancialStatementItem | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function FinancialDetailSheet({
  stock,
  open,
  onOpenChange,
}: FinancialDetailSheetProps) {
  const symbol = stock?.symbol || null

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-xl md:max-w-2xl overflow-hidden">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            {stock ? (
              <>
                <span className="text-primary">{stock.symbol}</span>
                <span className="text-muted-foreground font-normal">
                  - {stock.company_name}
                </span>
              </>
            ) : (
              "Chi tiet co phieu"
            )}
          </SheetTitle>
        </SheetHeader>

        <ScrollArea className="h-[calc(100vh-80px)] pr-4 mt-4">
          <div className="space-y-4 pb-8">
            <HealthScoreCard symbol={symbol} />
            <TrendChartsCard symbol={symbol} />
            <PeerComparisonCard symbol={symbol} />
            <FCFAnalysisCard symbol={symbol} />
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  )
}
```

### Step 3: Update Financial Statements Table

**File: `/apps/web/src/components/dashboard/financial-statements-table.tsx`**

Add row click handler:

```tsx
// Add state for selected stock
const [selectedStock, setSelectedStock] = useState<FinancialStatementItem | null>(null)
const [sheetOpen, setSheetOpen] = useState(false)

// Update row component
const FinancialRow = memo(function FinancialRow({
  item,
  onRowClick
}: FinancialRowProps & { onRowClick: (item: FinancialStatementItem) => void }) {
  return (
    <tr
      className="border-b border-border/30 transition-colors hover:bg-muted/20 cursor-pointer"
      onClick={() => onRowClick(item)}
    >
      {/* ... existing cells ... */}
    </tr>
  )
})

// In render, add handler
const handleRowClick = useCallback((item: FinancialStatementItem) => {
  setSelectedStock(item)
  setSheetOpen(true)
}, [])

// Add Sheet at end of component
<FinancialDetailSheet
  stock={selectedStock}
  open={sheetOpen}
  onOpenChange={setSheetOpen}
/>
```

### Step 4: Update Page Layout

**File: `/apps/web/src/app/analytics/financial-statements/page.tsx`**

```tsx
import { DashboardLayoutClient } from "@/components/layout/dashboard-layout-client"
import { FinancialStatementsTable } from "@/components/dashboard/financial-statements-table"

export default function FinancialStatementsPage() {
  return (
    <DashboardLayoutClient>
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Bao Cao Tai Chinh</h1>
            <p className="text-sm text-muted-foreground">
              Top 50 cong ty co loi nhuan cao nhat tu HOSE &amp; HNX (theo quy).
              Click vao dong de xem chi tiet.
            </p>
          </div>
        </div>
        <FinancialStatementsTable />
      </div>
    </DashboardLayoutClient>
  )
}
```

### Step 5: Add Backend Tests

**File: `/apps/api/src/tests/test_financial_endpoints.py`**

```python
"""Tests for financial analysis endpoints."""

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthScoreEndpoint:
    def test_health_score_valid_symbol(self, client):
        response = client.get("/api/v1/stocks/VNM/health-score")
        assert response.status_code == 200
        data = response.json()
        assert "health_score" in data
        assert 0 <= data["health_score"] <= 100
        assert "f_score" in data
        assert 0 <= data["f_score"] <= 9

    def test_health_score_invalid_symbol(self, client):
        response = client.get("/api/v1/stocks/INVALID123/health-score")
        assert response.status_code in [400, 404]


class TestTrendMetricsEndpoint:
    def test_trend_metrics_default_periods(self, client):
        response = client.get("/api/v1/stocks/VNM/trend-metrics")
        assert response.status_code == 200
        data = response.json()
        assert len(data["periods"]) == 8
        assert len(data["revenue"]) == 8

    def test_trend_metrics_custom_periods(self, client):
        response = client.get("/api/v1/stocks/VNM/trend-metrics?periods=4")
        assert response.status_code == 200
        data = response.json()
        assert len(data["periods"]) == 4


class TestFCFAnalysisEndpoint:
    def test_fcf_analysis_valid_symbol(self, client):
        response = client.get("/api/v1/stocks/VNM/fcf-analysis")
        assert response.status_code == 200
        data = response.json()
        assert "fcf" in data
        assert "fcf_margin" in data
        # CCC may be null for banks

    def test_fcf_analysis_bank_symbol(self, client):
        response = client.get("/api/v1/stocks/VCB/fcf-analysis")
        assert response.status_code == 200
        data = response.json()
        # CCC should be null for banks
        assert data.get("ccc") is None or isinstance(data["ccc"], (int, float))


class TestSectorPeersEndpoint:
    def test_sector_peers_valid_symbol(self, client):
        response = client.get("/api/v1/stocks/analytics/sector-peers?symbol=VNM")
        assert response.status_code == 200
        data = response.json()
        assert "icb_code" in data
        assert "peers" in data
        assert len(data["peers"]) <= 5

    def test_sector_peers_custom_limit(self, client):
        response = client.get("/api/v1/stocks/analytics/sector-peers?symbol=VNM&limit=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data["peers"]) <= 3
```

### Step 6: Add Frontend E2E Test

**File: `/apps/web/e2e/financial-statements.spec.ts`** (if using Playwright)

```typescript
import { test, expect } from "@playwright/test"

test.describe("Financial Statements Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/analytics/financial-statements")
  })

  test("should display ranking table", async ({ page }) => {
    await expect(page.getByText("Bao Cao Tai Chinh")).toBeVisible()
    await expect(page.getByRole("table")).toBeVisible()
  })

  test("should open detail sheet on row click", async ({ page }) => {
    // Wait for data to load
    await page.waitForSelector("tbody tr", { timeout: 10000 })

    // Click first row
    await page.locator("tbody tr").first().click()

    // Sheet should open with health score card
    await expect(page.getByText("Financial Health Score")).toBeVisible()
    await expect(page.getByText("Trend Analysis")).toBeVisible()
    await expect(page.getByText("Peer Comparison")).toBeVisible()
    await expect(page.getByText("FCF Analysis")).toBeVisible()
  })

  test("should close sheet on close button click", async ({ page }) => {
    await page.waitForSelector("tbody tr", { timeout: 10000 })
    await page.locator("tbody tr").first().click()

    // Click close button
    await page.locator('[data-state="open"] button[aria-label="Close"]').click()

    // Sheet should close
    await expect(page.getByText("Financial Health Score")).not.toBeVisible()
  })
})
```

## Todo

- [x] Create `useFinancialDetail` combined hook
- [x] Create `FinancialDetailSheet` component
- [x] Update `FinancialStatementsTable` with row click handler
- [x] Update page description text
- [ ] Write backend unit tests for all 4 endpoints
- [ ] Write frontend E2E tests
- [ ] Test responsive layout on mobile
- [x] Test loading and error states

## Success Criteria

- [x] Row click opens Sheet with all 4 analysis cards
- [x] All cards load data independently
- [x] Sheet closes on X button or outside click
- [x] Responsive: Sheet full-width on mobile
- [ ] All backend tests pass
- [ ] E2E tests pass

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Sheet too large on mobile | Medium | Medium | Use ScrollArea, collapse sections |
| Slow initial load | Medium | Medium | Show skeleton per card, parallel fetch |
| API failures | Low | Medium | Show error per card, not whole sheet |

## Security Considerations

- Validate symbol in all endpoints
- Rate limit API calls (standard: 100/60s)
- Sanitize user input in search/filter
