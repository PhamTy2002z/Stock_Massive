# Sector Comparison UI/UX Research Report

**Research ID:** researcher-01-ui-patterns
**Date:** 2025-12-28
**Focus:** Peer comparison table design patterns for financial metrics (P/E, P/B, ROE, ROA)

---

## Key Findings

### 1. Table Design Best Practices

**Layout & Readability:**
- Left-align: company names, text labels
- Right-align: all numeric values (P/E, P/B, ROE, ROA)
- Sticky headers for vertical scroll
- Freeze first column (company name) for horizontal scroll
- Consistent spacing (prevent clutter)
- Visual hierarchy: bold headers, subtle color for key metrics

**Interactivity:**
- Sortable columns (click header to sort by metric)
- Filter by industry, market cap
- Search functionality
- Column reordering/hide/show
- Drill-down: click company → detail view
- Tooltips: explain each ratio

**Metric Grouping:**
```
| Company | Price | --- Valuation --- | --- Performance --- | --- vs Sector --- |
|         |       | P/E   | P/B      | ROE   | ROA       | Premium/Discount   |
```
- Group valuation ratios (P/E, P/B) together
- Group performance ratios (ROE, ROA) together
- Separate premium/discount column

---

### 2. Premium/Discount Visualization

**Diverging Color Palette (Recommended):**

```typescript
const premiumDiscountColors = {
  strongPremium: '#16a34a',   // green-600 (>20% above median)
  premium: '#22c55e',          // green-500 (5-20% above)
  neutral: '#9ca3af',          // gray-400 (±5% of median)
  discount: '#f97316',         // orange-500 (5-20% below)
  strongDiscount: '#dc2626',   // red-600 (>20% below)
};
```

**Color Coding Rules:**
- Premium (above sector median): Green shades
- Discount (below sector median): Red/Orange shades
- Near median (±5%): Gray/neutral
- Limit to 5-6 distinct colors max
- 4.5:1 contrast ratio minimum (WCAG AA)
- Test for color blindness compatibility

**Visual Elements:**
```tsx
// Badge style for premium/discount
<Chip
  label={`+15.2%`}
  sx={{
    bgcolor: premiumColors.premium,
    color: 'white',
    fontWeight: 600
  }}
/>

// Or background cell highlighting
<TableCell
  sx={{
    bgcolor: alpha(premiumColors.premium, 0.1),
    color: premiumColors.premium
  }}
>
  +15.2%
</TableCell>
```

**Benchmark Display:**
- Show sector median value in table header/footer
- Add visual reference line in charts
- Clear legend: "Above Median", "Below Median"

---

### 3. Responsive Design Patterns (Material-UI)

**Desktop (>960px):**
```tsx
<TableContainer component={Paper}>
  <Table stickyHeader>
    <TableHead>
      <TableRow>
        <TableCell sx={{ minWidth: 150 }}>Company</TableCell>
        <TableCell align="right">P/E</TableCell>
        <TableCell align="right">P/B</TableCell>
        <TableCell align="right">ROE (%)</TableCell>
        <TableCell align="right">ROA (%)</TableCell>
        <TableCell align="right">vs Sector</TableCell>
      </TableRow>
    </TableHead>
    <TableBody>
      {/* rows */}
    </TableBody>
  </Table>
</TableContainer>
```

**Mobile (<960px) - Horizontal Scroll:**
```tsx
<TableContainer
  sx={{
    overflowX: 'auto',
    '&::-webkit-scrollbar': { height: 8 },
    '&::-webkit-scrollbar-thumb': { bgcolor: 'grey.400' }
  }}
>
  <Table sx={{ minWidth: 650 }}>
    {/* Same structure, allow horizontal pan */}
  </Table>
</TableContainer>
```

**Alternative: Card Layout (Mobile):**
```tsx
{isMobile ? (
  <Stack spacing={2}>
    {companies.map(company => (
      <Card key={company.symbol}>
        <CardContent>
          <Typography variant="h6">{company.name}</Typography>
          <Grid container spacing={2}>
            <Grid item xs={6}>
              <Typography variant="caption">P/E</Typography>
              <Typography variant="body1">{company.pe}</Typography>
            </Grid>
            <Grid item xs={6}>
              <Typography variant="caption">P/B</Typography>
              <Typography variant="body1">{company.pb}</Typography>
            </Grid>
            {/* ROE, ROA, Premium */}
          </Grid>
        </CardContent>
      </Card>
    ))}
  </Stack>
) : (
  <Table>...</Table>
)}
```

---

## Recommended Approach

### Component Structure
```
PeerComparisonTable/
├── PeerComparisonTable.tsx      # Main container
├── ComparisonTableHeader.tsx    # Sortable headers
├── ComparisonTableRow.tsx       # Data row with metrics
├── PremiumDiscountCell.tsx      # Colored badge/cell
└── types.ts                     # PeerMetrics interface
```

### Data Schema
```typescript
interface PeerMetrics {
  symbol: string;
  companyName: string;
  pe: number;
  pb: number;
  roe: number;
  roa: number;
  sectorMedian: {
    pe: number;
    pb: number;
    roe: number;
    roa: number;
  };
  premiumDiscount: {
    pe: number;      // % deviation from median
    pb: number;
    roe: number;
    roa: number;
  };
}
```

### Implementation Checklist
- [ ] Use Material-UI Table components (TableContainer, Table, TableHead, TableBody)
- [ ] Implement sticky header + frozen first column
- [ ] Add sort functionality per column
- [ ] Apply diverging color palette (5 levels)
- [ ] Show sector median in footer row
- [ ] Add tooltips for metric explanations
- [ ] Responsive: horizontal scroll on mobile
- [ ] Test WCAG AA contrast ratios
- [ ] Add loading skeleton state
- [ ] Handle empty/error states

---

## Code Pattern Example

```tsx
const getPremiumColor = (deviation: number) => {
  if (deviation > 20) return '#16a34a';      // strong premium
  if (deviation > 5) return '#22c55e';       // premium
  if (deviation > -5) return '#9ca3af';      // neutral
  if (deviation > -20) return '#f97316';     // discount
  return '#dc2626';                          // strong discount
};

const PremiumDiscountCell = ({ value }: { value: number }) => (
  <TableCell align="right">
    <Chip
      size="small"
      label={`${value > 0 ? '+' : ''}${value.toFixed(1)}%`}
      sx={{
        bgcolor: getPremiumColor(value),
        color: 'white',
        fontWeight: 600,
        minWidth: 70
      }}
    />
  </TableCell>
);
```

---

## Unresolved Questions

None - all focus areas covered with actionable patterns.
