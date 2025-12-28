# Stock Ticker Orange to White Color Replacement Checklist

## Critical Files (Direct Stock Symbol Display)

### Priority 1: Stock Symbol Text Colors

- [ ] **/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/financial-detail-sheet.tsx**
  - Line 35: `text-[hsl(var(--accent-orange))]` → `text-white`
  - Context: Financial detail sheet header stock symbol

- [ ] **/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/peer-comparison/peer-metrics-table.tsx**
  - Line 68: `bg-[hsl(var(--accent-orange))]/10` → `bg-white/10`
  - Line 68: `border-[hsl(var(--accent-orange))]/30` → `border-white/30`
  - Line 74: `text-[hsl(var(--accent-orange))]` → `text-white`
  - Context: Peer comparison target stock highlighting

- [ ] **/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/financial-health/health-score-card.tsx**
  - Line 55: `text-[hsl(var(--accent-orange))]` → `text-white`
  - Line 75: `text-[hsl(var(--accent-orange))]` → `text-white`
  - Context: Stock symbol in health score card & high score display

---

## Financial Charts (CSS Variable Replacements)

### Priority 2: Chart Visualizations

- [ ] **/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/financial-trends/cash-flow-chart.tsx**
  - Line 72: `fill="hsl(var(--accent-orange))"` → `fill="hsl(0 0% 100%)"`
  - Context: CFO bar chart color

- [ ] **/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/financial-trends/revenue-profit-chart.tsx**
  - Line 80: `fill="hsl(var(--accent-orange))"` → `fill="hsl(0 0% 100%)"`
  - Context: Revenue bar chart color

- [ ] **/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/financial-trends/margin-trend-chart.tsx**
  - Line 31: `stopColor="hsl(var(--accent-orange))"` → `stopColor="hsl(0 0% 100%)"`
  - Line 32: `stopColor="hsl(var(--accent-orange))"` → `stopColor="hsl(0 0% 100%)"`
  - Line 67: `stroke="hsl(var(--accent-orange))"` → `stroke="hsl(0 0% 100%)"`
  - Context: Gross margin gradient & trend line

- [ ] **/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/financial-trends/roe-roa-chart.tsx**
  - Line 58: `stroke="hsl(var(--accent-orange))"` → `stroke="hsl(0 0% 100%)"`
  - Line 60: `fill: "hsl(var(--accent-orange))"` → `fill: "hsl(0 0% 100%)"`
  - Context: ROE trend line & data points

- [ ] **/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/financial-health/health-radar-chart.tsx**
  - Line 53: `stroke="hsl(var(--accent-orange))"` → `stroke="hsl(0 0% 100%)"`
  - Line 54: `fill="hsl(var(--accent-orange))"` → `fill="hsl(0 0% 100%)"`
  - Context: Health score radar chart visualization

---

## Health & Financial Indicators

### Priority 3: Indicator Components

- [ ] **/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/financial-health/score-breakdown.tsx**
  - Line 23: `bg-[hsl(var(--accent-orange))]` → `bg-white`
  - Context: High score progress bar (>= 70)

- [ ] **/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/financial-health/f-score-indicator.tsx**
  - Line 20: `text-[hsl(var(--accent-orange))]` → `text-white`
  - Line 41: `bg-[hsl(var(--accent-orange))]` → `bg-white`
  - Context: F-Score strong rating indicator

- [ ] **/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/fcf-analysis/ccc-indicator.tsx**
  - Line 20: `text-[hsl(var(--accent-orange))]` → `text-white`
  - Context: Good cash conversion cycle indicator (<= 30 days)

- [ ] **/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/fcf-analysis/fcf-analysis-card.tsx**
  - Line 72: `text-[hsl(var(--accent-orange))]` → `text-white`
  - Line 78: `text-[hsl(var(--accent-orange))]` → `text-white`
  - Context: FCF Margin & FCF Yield metric displays

- [ ] **/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/fcf-analysis/fcf-waterfall.tsx**
  - Line 33: `bg-[hsl(var(--accent-orange))]` → `bg-white`
  - Line 35: `bg-[hsl(var(--accent-orange))]` → `bg-white`
  - Context: CFO & FCF waterfall bar colors

---

## Advanced Analysis Components

### Priority 4: Order Flow & Foreign Trading

- [ ] **/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/advanced-tab/widgets/order-flow-charts.tsx**
  - Line 34: `buy: "hsl(25 95% 53%)"` → `buy: "hsl(0 0% 100%)"`
  - Line 35: `buyLight: "hsl(32 98% 58%)"` → `buyLight: "hsl(0 0% 85%)"`
  - Context: Buy side order flow color design pattern

- [ ] **/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/advanced-tab/widgets/foreign-flow-charts.tsx**
  - Line 23: `orange: "#F59E0B"` → `orange: "#FFFFFF"`
  - Line 24: `orangeLight: "#FBBF24"` → `orangeLight: "#E8E8E8"`
  - Line 25: `orangeDim: "rgba(245, 158, 11, 0.15)"` → `orangeDim: "rgba(255, 255, 255, 0.15)"`
  - Multiple uses: Lines 71, 108, 114, 121, 138, 175, 193, 279
  - Context: Foreign investor trading flow visualization

### Priority 5: UI Components & Sections

- [ ] **/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/advanced-tab/money-flow-subtab.tsx**
  - Line 33: `bg-orange-500` → `bg-white`
  - Line 73: `text-orange-500` → `text-white`
  - Context: Money flow subtab divider & alert icon

- [ ] **/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/advanced-section.tsx**
  - Line 42: `color: "text-amber-500"` → `color: "text-white"`
  - Line 43: `bgColor: "bg-amber-500/10"` → `bgColor: "bg-white/10"`
  - Context: Money Flow subtab icon & background styling

---

## Related But Secondary Files

### Priority 6: Anomaly & Depth Indicators

- [ ] **/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/volume-anomaly-chart.tsx**
  - Line 81: `text-orange-500` → `text-white`
  - Context: High volume anomaly severity indicator

- [ ] **/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/dashboard/advanced-tab/widgets/price-depth-chart.tsx**
  - Line 149: `bg-amber-500/20 text-amber-600` → `bg-white/20 text-white`
  - Context: Price depth spread warning indicator

---

## CSS Global Variable Setup

- [ ] **/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/globals.css**
  - **AFTER line 40** (in `:root` section): Add `--accent-white: 0 0% 100%;`
  - **AFTER line 75** (in `.dark` section): Add `--accent-white: 0 0% 100%;` (same value for consistency)

---

## Search & Replace Reference

### For VSCode Find & Replace:

**Find (CSS Variable):**
```
hsl\(var\(--accent-orange\)\)
```
**Replace with:**
```
hsl(0 0% 100%)
```

**Find (Tailwind Classes - Orange):**
```
text-orange-500
```
**Replace with:**
```
text-white
```

**Find (Tailwind Classes - Amber):**
```
text-amber-500
```
**Replace with:**
```
text-white
```

**Find (Hex Orange Bright):**
```
#F59E0B
```
**Replace with:**
```
#FFFFFF
```

**Find (Hex Orange Light):**
```
#FBBF24
```
**Replace with:**
```
#E8E8E8
```

**Find (HSL Buy Orange):**
```
hsl\(25 95% 53%\)
```
**Replace with:**
```
hsl(0 0% 100%)
```

**Find (HSL Buy Light Orange):**
```
hsl\(32 98% 58%\)
```
**Replace with:**
```
hsl(0 0% 85%)
```

---

## Verification Checklist

After making all replacements:

- [ ] Check light theme appearance - ensure white text has sufficient contrast
- [ ] Check dark theme appearance - white may need adjustment for dark background
- [ ] Run tests to ensure no visual regressions
- [ ] Verify WCAG AA compliance for color contrast
- [ ] Test in all major browsers (Chrome, Firefox, Safari, Edge)
- [ ] Verify mobile responsiveness
- [ ] Check stock detail page displays correctly
- [ ] Verify peer comparison highlighting is visible
- [ ] Test financial charts render with new colors
- [ ] Check advanced analysis tabs display properly

---

## File Count Summary

- **Total files to update:** 19
- **Critical (stock symbols):** 3
- **Charts & visualizations:** 8
- **Indicators:** 5
- **Advanced analysis:** 2
- **CSS globals:** 1

**Total lines to modify:** ~30+

