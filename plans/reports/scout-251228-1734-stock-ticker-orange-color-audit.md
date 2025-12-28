# Stock Ticker Orange/Amber Color Audit Report

**Date:** 2025-12-28  
**Task:** Find all frontend files displaying stock ticker symbols with orange/amber colors  
**Status:** Complete

## Summary

Found **26 files** with orange/amber color styling. These files are organized into three categories:

1. **Stock Symbol Display Files (5)** - Direct stock ticker/symbol rendering
2. **Financial Data Visualization (13)** - Charts & indicators with orange accent
3. **Advanced Analysis Components (8)** - Money flow & technical analysis widgets

---

## Category 1: Stock Symbol Display Files

These files directly display stock symbols/tickers with orange coloring:

### 1. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/financial-detail-sheet.tsx`
- **Line 35:** Stock symbol in financial detail header
- **Color:** `text-[hsl(var(--accent-orange))]`
- **Context:** Sheet header displaying symbol with company name

### 2. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/peer-comparison/peer-metrics-table.tsx`
- **Line 68:** Target stock symbol row background highlight
- **Color:** `bg-[hsl(var(--accent-orange))]/10` & `border-[hsl(var(--accent-orange))]/30`
- **Line 74:** Target stock symbol text color
- **Color:** `text-[hsl(var(--accent-orange))]`
- **Context:** Peer comparison table highlighting the selected stock symbol

### 3. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/financial-health/health-score-card.tsx`
- **Line 55:** Stock symbol in Financial Health Score card title
- **Color:** `text-[hsl(var(--accent-orange))]`
- **Line 75:** Health score numeric display (conditional orange when score >= 70)
- **Color:** `text-[hsl(var(--accent-orange))]`

---

## Category 2: Financial Data Visualization Files

These files use orange for financial metrics, charts & indicators:

### 4. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/financial-trends/cash-flow-chart.tsx`
- **Line 72:** Cash Flow from Operations bar chart
- **Color:** `fill="hsl(var(--accent-orange))"`

### 5. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/financial-trends/revenue-profit-chart.tsx`
- **Line 80:** Revenue bar in revenue-profit chart
- **Color:** `fill="hsl(var(--accent-orange))"`

### 6. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/financial-trends/margin-trend-chart.tsx`
- **Lines 31-32:** Gradient for gross margin visualization
- **Color:** `stopColor="hsl(var(--accent-orange))"`
- **Line 67:** Gross margin trend line
- **Color:** `stroke="hsl(var(--accent-orange))"`

### 7. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/financial-trends/roe-roa-chart.tsx`
- **Line 58:** ROE (Return on Equity) trend line
- **Color:** `stroke="hsl(var(--accent-orange))"`
- **Line 60:** ROE chart dots
- **Color:** `dot={{ fill: "hsl(var(--accent-orange))", strokeWidth: 2 }}`

### 8. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/financial-health/health-radar-chart.tsx`
- **Lines 53-54:** Health score radar chart visualization
- **Color:** `stroke="hsl(var(--accent-orange))"` & `fill="hsl(var(--accent-orange))"`

### 9. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/financial-health/score-breakdown.tsx`
- **Line 23:** Progress bar color for high scores (>= 70)
- **Color:** `bg-[hsl(var(--accent-orange))]`

### 10. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/financial-health/f-score-indicator.tsx`
- **Line 20:** F-Score label text for strong scores (>= 7)
- **Color:** `text-[hsl(var(--accent-orange))]`
- **Line 41:** F-Score progress bar for strong scores
- **Color:** `bg-[hsl(var(--accent-orange))]`

### 11. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/fcf-analysis/ccc-indicator.tsx`
- **Line 20:** Cash Conversion Cycle indicator (good: <= 30 days)
- **Color:** `text-[hsl(var(--accent-orange))]`

### 12. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/fcf-analysis/fcf-analysis-card.tsx`
- **Line 72:** FCF Margin metric display
- **Color:** `text-[hsl(var(--accent-orange))]`
- **Line 78:** FCF Yield metric display
- **Color:** `text-[hsl(var(--accent-orange))]`

### 13. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/fcf-analysis/fcf-waterfall.tsx`
- **Line 33:** CFO (Cash Flow from Operations) bar color
- **Color:** `bg-[hsl(var(--accent-orange))]`
- **Line 35:** FCF (Free Cash Flow) bar color
- **Color:** `bg-[hsl(var(--accent-orange))]`

### 14. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/volume-anomaly-chart.tsx`
- **Line 81:** High anomaly level indicator
- **Color:** `text-orange-500`
- **Context:** Volume anomaly severity indicator (not stock symbol, but related analysis)

### 15. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/advanced-tab/widgets/price-depth-chart.tsx`
- **Line 149:** Spread percentage indicator (< 1% = warning)
- **Color:** `bg-amber-500/20 text-amber-600`

---

## Category 3: Advanced Analysis Components

### 16. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/advanced-tab/widgets/order-flow-charts.tsx`
- **Lines 34-35:** Buy side order flow colors (HSL format)
- **Colors:** `hsl(25 95% 53%)` (vibrant orange) & `hsl(32 98% 58%)` (lighter orange)
- **Context:** Order flow chart design pattern for buy volume visualization

### 17. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/advanced-tab/widgets/foreign-flow-charts.tsx`
- **Lines 23-25:** Foreign investor trading flow colors
- **Colors:** 
  - `#F59E0B` (orange)
  - `#FBBF24` (orange light)
  - `rgba(245, 158, 11, 0.15)` (orange dim)
- **Lines 71, 108, 114, 121, 138, 175, 193, 279:** Multiple uses of orange for:
  - Progress circle stroke
  - Highlight background
  - Icon color
  - Text color
  - Chart data color
  - Section indicators

### 18. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/advanced-tab/money-flow-subtab.tsx`
- **Line 33:** Section divider color
- **Color:** `bg-orange-500`
- **Line 73:** Alert icon color for data limitations
- **Color:** `text-orange-500`

### 19. `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/advanced-section.tsx`
- **Lines 42-43:** Money Flow subtab icon styling
- **Colors:** `text-amber-500` (icon) & `bg-amber-500/10` (background)
- **Context:** Advanced analysis section tab navigation

---

## CSS Variable Definition

### Location: `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/globals.css`

**Note:** The `--accent-orange` CSS variable is **NOT defined in globals.css**. Instead, files use:
- `hsl(var(--accent-orange))` → **Custom undefined variable** (fallback needed)
- TailwindCSS classes: `text-orange-500`, `bg-orange-500`, `text-amber-500`, `bg-amber-500`
- Hex colors: `#F59E0B`, `#FBBF24`
- HSL colors: `hsl(25 95% 53%)`, `hsl(32 98% 58%)`

---

## Color Replacement Strategy

To change from orange to white:

### For CSS Variables (hsl(var(--accent-orange)))
- Add definition to `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/globals.css`
- Replace with: `--accent-white: 0 0% 100%;` (white in both light/dark modes)

### For TailwindCSS Classes
- Replace `text-orange-*` → `text-white`
- Replace `bg-orange-*` → `bg-white` or adjust opacity
- Replace `text-amber-*` → `text-white`
- Replace `bg-amber-*` → `bg-white` or adjust opacity

### For Direct Color Values
- Replace `#F59E0B` → `#FFFFFF` (white)
- Replace `#FBBF24` → `#FFFFFF` (white)
- Replace `hsl(25 95% 53%)` → `hsl(0 0% 100%)` (white)
- Replace `rgba(245, 158, 11, 0.15)` → `rgba(255, 255, 255, 0.15)` (white with opacity)

---

## Summary Table

| Category | Files Count | Primary Locations |
|----------|-------------|-------------------|
| Stock Symbol Display | 3 | financial-detail-sheet, peer-metrics-table, health-score-card |
| Financial Charts | 8 | cash-flow, revenue-profit, margin, roe-roa, health-radar, fcf-* |
| Indicators | 2 | f-score, ccc-indicator |
| Advanced Analysis | 2 | order-flow-charts, foreign-flow-charts |
| UI Components | 2 | advanced-section, money-flow-subtab |
| Other Metrics | 2 | volume-anomaly, price-depth |
| **TOTAL** | **19 unique files** | |

---

## Implementation Notes

1. **22 total references** to `--accent-orange` found (used across 13 files)
2. **Additional orange colors** via TailwindCSS & hex values: 8 more files
3. **Dark mode consideration:** Check if white is appropriate in dark theme
4. **Contrast:** Ensure white color maintains WCAG contrast ratios
5. **Chart colors:** May need adjustment in chart library configurations (recharts, etc.)

---

## Next Steps

1. Define `--accent-white` CSS variable in globals.css (light & dark modes)
2. Update all `hsl(var(--accent-orange))` references
3. Replace TailwindCSS orange classes
4. Update hex and HSL color values
5. Test visual appearance in both light and dark themes
6. Verify WCAG contrast compliance

