# ICB Sector UI/UX Research Report

**Date:** 2025-12-22
**Researcher:** researcher-02
**Scope:** ICB sector display in Volume Spikes dashboard

---

## 1. Current Implementation Analysis

### 1.1 Volume Spike Dashboard (`volume-spike-dashboard.tsx`)

**ICB Sector Grouping:**
- Uses `IndustrySpikeGroup` component with ShadCN `Collapsible`
- Groups sorted by `spike_count` descending
- First group auto-expanded (`defaultOpen={idx === 0}`)
- Each group shows: `icb_name`, `spike_count` badge, `avg_spike_ratio`

**Existing Features:**
- Collapsible accordion pattern
- Internal table with sorting (spike_ratio, volume, price_change)
- Pagination (10 items/page)
- Row click navigates to deep-dive
- Anomaly level badges with color coding

**Filters Available:**
- Min ratio threshold (1.5x, 2x, 2.5x, 3x)
- Exchange filter (HOSE, HNX, all)
- UPCOM toggle

### 1.2 Sector Performance Component (`sector-performance.tsx`)

**Pattern Used:**
- Two-column grid: Top 5 gainers vs Top 5 losers
- `SectorRow` component with rank badge, sector info, change %
- Shows market cap, stock count, top stocks
- Color-coded by performance (green/red)

**Reusable Elements:**
- Rank badge styling
- Market cap formatting
- Sector row layout pattern

---

## 2. Current UI Patterns Summary

| Pattern | Component | Usage |
|---------|-----------|-------|
| Collapsible groups | `Collapsible` | ICB sector accordion |
| Badge variants | `Badge` | Anomaly levels, counts |
| Sortable table | Custom | Stock list within group |
| Pagination | Custom | 10 items/page |
| Select filters | `Select` | Threshold, exchange |
| Summary cards | `Card` | Top-level stats |

---

## 3. Recommended UI/UX Improvements

### 3.1 Sector Filtering & Search (Priority: High)
- Add sector filter dropdown to filter by specific ICB sectors
- Quick search/filter for sector names
- "Expand All / Collapse All" toggle button

### 3.2 Visual Hierarchy Enhancements (Priority: High)
- Add sector heat indicator (color bar) based on avg_spike_ratio
- Show mini sparkline or bar chart in collapsed header
- Highlight sectors with very_high anomaly stocks

### 3.3 Sorting Options for Sectors (Priority: Medium)
- Sort sectors by: spike_count, avg_spike_ratio, alphabetical
- Persist sort preference in localStorage

### 3.4 Compact View Mode (Priority: Medium)
- Toggle between detailed table vs compact card grid
- Card view: symbol, ratio, price change in condensed format
- Better for mobile/quick scanning

### 3.5 Sector Comparison (Priority: Low)
- Multi-select sectors for side-by-side comparison
- Aggregate stats comparison panel

---

## 4. Best Practices for Sector-Based Visualization

### 4.1 Information Density
- Progressive disclosure: summary -> details on expand
- Use consistent color coding across all sector views
- Limit visible items, use "Show more" pattern

### 4.2 Accessibility
- Keyboard navigation for collapsibles (already implemented)
- ARIA labels for interactive elements
- Sufficient color contrast for anomaly indicators

### 4.3 Performance
- Virtualize long lists if >50 sectors
- Lazy load expanded content
- Memoize sorted/filtered results (already using `useMemo`)

### 4.4 Mobile Responsiveness
- Stack filters vertically on mobile
- Horizontal scroll for tables (already implemented)
- Touch-friendly tap targets

---

## 5. Implementation Recommendations

### Quick Wins (Low Effort, High Impact)
1. Add "Expand All / Collapse All" button
2. Add sector count in section header ("Theo ngành ICB (12 ngành)")
3. Color-code collapsed header based on avg_spike_ratio

### Medium Effort
1. Sector filter dropdown using existing `Select` component
2. Sort selector for sector list
3. Compact/detailed view toggle

### Higher Effort
1. Mini bar chart in collapsed header showing stock distribution
2. Sector comparison mode
3. Treemap visualization for sector overview

---

## 6. Suggested Component Structure

```
VolumeSpikeDashboard
├── SummaryCards (existing)
├── VolumeSpikeChart (existing)
├── SectorGroupSection (new wrapper)
│   ├── SectorGroupHeader
│   │   ├── Title + count
│   │   ├── SortSelector
│   │   ├── SectorFilter
│   │   └── ExpandAllToggle
│   └── SectorGroupList
│       └── IndustrySpikeGroup[] (existing, enhanced)
│           ├── CollapsibleHeader (add heat indicator)
│           └── StockTable (existing)
```

---

## 7. Unresolved Questions

1. **Data availability:** Does API support filtering by ICB code? Need to verify endpoint capabilities.
2. **ICB hierarchy:** Should we support ICB levels (L1/L2/L3) or just current flat list?
3. **Performance threshold:** At what sector count should we implement virtualization?
4. **User preference persistence:** Use localStorage or backend for view preferences?
5. **Mobile priority:** Is compact card view needed for MVP or can defer?

---

## 8. References

- Current files analyzed:
  - `/apps/web/src/components/dashboard/volume-spike-dashboard.tsx`
  - `/apps/web/src/components/dashboard/sector-performance.tsx`
- ShadCN components in use: Collapsible, Badge, Select, Card, Checkbox, Label
