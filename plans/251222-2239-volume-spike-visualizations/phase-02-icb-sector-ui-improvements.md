# Phase 2: ICB Sector UI/UX Improvements

## Context

- **Research**: `research/researcher-02-icb-ui-ux.md`
- **Current**: Basic collapsible groups, no filtering/sorting controls
- **Goal**: Add sector filtering, sorting, expand/collapse controls, visual enhancements
- **Priority**: High | **Effort**: Medium

## Overview

Enhance ICB sector display with filtering, sorting, expand/collapse controls, and visual hierarchy improvements. Focus on quick wins (low effort, high impact) first.

## Key Insights from Research

1. **Current Patterns**: Collapsible groups, badge variants, sortable tables, pagination
2. **Pain Points**: No sector filtering, no global expand/collapse, no sort options
3. **Quick Wins**: Expand All toggle, sector count, color-coded headers
4. **Medium Effort**: Sector filter dropdown, sort selector
5. **Best Practices**: Progressive disclosure, consistent colors, keyboard nav

## Requirements

### Functional
- Add "Expand All / Collapse All" toggle button
- Add sector count in section header ("Theo ngành ICB (12 ngành)")
- Color-code collapsed headers based on avg_spike_ratio
- Add sector filter dropdown (multi-select or single)
- Add sort selector (spike_count, avg_spike_ratio, alphabetical)
- Persist expand/collapse state per session

### Non-Functional
- Maintain existing performance (useMemo)
- Accessible (ARIA labels, keyboard nav)
- Mobile-friendly (stack controls vertically)
- Consistent with existing design

## Architecture

### Component Structure
```
VolumeSpikeDashboard
├── SectorGroupSection (new wrapper)
│   ├── SectorGroupHeader
│   │   ├── Title + count badge
│   │   ├── SortSelector (Select)
│   │   ├── SectorFilter (Select multi)
│   │   └── ExpandAllToggle (Button)
│   └── SectorGroupList
│       └── IndustrySpikeGroup[] (enhanced)
│           ├── CollapsibleHeader (add color indicator)
│           └── StockTable (existing)
```

### State Management
```typescript
const [expandedSectors, setExpandedSectors] = useState<Set<string>>(new Set())
const [sectorSort, setSectorSort] = useState<"spike_count" | "avg_spike_ratio" | "name">("spike_count")
const [selectedSectors, setSelectedSectors] = useState<string[]>([])
const [expandAll, setExpandAll] = useState(false)
```

### Color Indicator Function
```typescript
function getSectorHeaderColor(avgRatio: number): string {
  if (avgRatio >= 3) return "border-l-4 border-l-red-500"
  if (avgRatio >= 2) return "border-l-4 border-l-orange-500"
  if (avgRatio >= 1.5) return "border-l-4 border-l-yellow-500"
  return "border-l-4 border-l-muted"
}
```

## Related Code Files

- `/apps/web/src/components/dashboard/volume-spike-dashboard.tsx` - Main integration
- `/apps/web/src/components/ui/select.tsx` - ShadCN Select
- `/apps/web/src/components/ui/button.tsx` - ShadCN Button
- `/apps/web/src/components/ui/badge.tsx` - ShadCN Badge

## Implementation Steps

### Step 1: Add State Management
In `volume-spike-dashboard.tsx`:
```typescript
const [expandedSectors, setExpandedSectors] = useState<Set<string>>(new Set([data?.industries[0]?.icb_code]))
const [sectorSort, setSectorSort] = useState<"spike_count" | "avg_spike_ratio" | "name">("spike_count")
const [selectedSectors, setSelectedSectors] = useState<string[]>([])
```

### Step 2: Create Sector Sorting Logic
```typescript
const sortedIndustries = useMemo(() => {
  if (!data?.industries) return []

  let filtered = data.industries
  if (selectedSectors.length > 0) {
    filtered = filtered.filter(g => selectedSectors.includes(g.icb_code))
  }

  return [...filtered].sort((a, b) => {
    switch (sectorSort) {
      case "spike_count":
        return b.spike_count - a.spike_count
      case "avg_spike_ratio":
        return b.avg_spike_ratio - a.avg_spike_ratio
      case "name":
        return a.icb_name.localeCompare(b.icb_name, "vi")
      default:
        return 0
    }
  })
}, [data?.industries, sectorSort, selectedSectors])
```

### Step 3: Create Sector Header Component
```typescript
function SectorGroupHeader({
  sectorCount,
  sectorSort,
  onSortChange,
  selectedSectors,
  onSectorFilterChange,
  allSectors,
  expandAll,
  onExpandAllToggle,
}: {
  sectorCount: number
  sectorSort: string
  onSortChange: (value: string) => void
  selectedSectors: string[]
  onSectorFilterChange: (sectors: string[]) => void
  allSectors: { code: string; name: string }[]
  expandAll: boolean
  onExpandAllToggle: () => void
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
      <div className="flex items-center gap-2">
        <h2 className="text-lg font-semibold">Theo ngành ICB</h2>
        <Badge variant="secondary" className="text-xs">
          {sectorCount} ngành
        </Badge>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {/* Sort Selector */}
        <div className="flex items-center gap-2">
          <Label className="text-xs text-muted-foreground whitespace-nowrap">Sắp xếp:</Label>
          <Select value={sectorSort} onValueChange={onSortChange}>
            <SelectTrigger className="w-[140px] h-8 text-xs bg-background">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="spike_count">Số CP</SelectItem>
              <SelectItem value="avg_spike_ratio">Tỷ lệ TB</SelectItem>
              <SelectItem value="name">Tên A-Z</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Sector Filter */}
        <div className="flex items-center gap-2">
          <Label className="text-xs text-muted-foreground whitespace-nowrap">Ngành:</Label>
          <Select
            value={selectedSectors.length === 0 ? "all" : selectedSectors[0]}
            onValueChange={(v) => onSectorFilterChange(v === "all" ? [] : [v])}
          >
            <SelectTrigger className="w-[140px] h-8 text-xs bg-background">
              <SelectValue placeholder="Tất cả" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tất cả</SelectItem>
              {allSectors.map(s => (
                <SelectItem key={s.code} value={s.code}>
                  {s.name.length > 20 ? s.name.slice(0, 18) + "..." : s.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Expand All Toggle */}
        <Button
          variant="outline"
          size="sm"
          onClick={onExpandAllToggle}
          className="h-8 text-xs"
        >
          {expandAll ? "Thu gọn" : "Mở rộng"} tất cả
        </Button>
      </div>
    </div>
  )
}
```

### Step 4: Enhance IndustrySpikeGroup Header
Modify `IndustrySpikeGroup` component:
```typescript
function IndustrySpikeGroup({
  group,
  isOpen,
  onToggle,
}: {
  group: IndustryVolumeSpikeGroup
  isOpen: boolean
  onToggle: () => void
}) {
  // ... existing code ...

  const headerColorClass = getSectorHeaderColor(group.avg_spike_ratio)

  return (
    <Collapsible open={isOpen} onOpenChange={onToggle}>
      <CollapsibleTrigger className="w-full">
        <div className={cn(
          "flex items-center justify-between p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors",
          headerColorClass
        )}>
          {/* ... existing content ... */}
        </div>
      </CollapsibleTrigger>
      {/* ... existing content ... */}
    </Collapsible>
  )
}
```

### Step 5: Implement Expand All Logic
```typescript
const handleExpandAllToggle = () => {
  if (expandAll) {
    setExpandedSectors(new Set())
  } else {
    setExpandedSectors(new Set(sortedIndustries.map(g => g.icb_code)))
  }
  setExpandAll(!expandAll)
}

// Update expand state when individual sector toggled
const handleSectorToggle = (icbCode: string) => {
  setExpandedSectors(prev => {
    const next = new Set(prev)
    if (next.has(icbCode)) {
      next.delete(icbCode)
    } else {
      next.add(icbCode)
    }
    return next
  })
}
```

### Step 6: Update Render Logic
```typescript
{sortedIndustries.length > 0 ? (
  <div className="space-y-3">
    <SectorGroupHeader
      sectorCount={sortedIndustries.length}
      sectorSort={sectorSort}
      onSortChange={setSectorSort}
      selectedSectors={selectedSectors}
      onSectorFilterChange={setSelectedSectors}
      allSectors={data.industries.map(g => ({ code: g.icb_code, name: g.icb_name }))}
      expandAll={expandAll}
      onExpandAllToggle={handleExpandAllToggle}
    />
    {sortedIndustries.map((group) => (
      <IndustrySpikeGroup
        key={group.icb_code}
        group={group}
        isOpen={expandedSectors.has(group.icb_code)}
        onToggle={() => handleSectorToggle(group.icb_code)}
      />
    ))}
  </div>
) : (
  <div className="rounded-lg border border-border/50 bg-card/50 p-8 text-center">
    <p className="text-muted-foreground">Không có ngành nào phù hợp.</p>
  </div>
)}
```

### Step 7: Add Color Indicator Helper
```typescript
function getSectorHeaderColor(avgRatio: number): string {
  if (avgRatio >= 3) return "border-l-red-500"
  if (avgRatio >= 2) return "border-l-orange-500"
  if (avgRatio >= 1.5) return "border-l-yellow-500"
  return "border-l-muted"
}
```

### Step 8: Mobile Responsiveness
Ensure controls stack properly:
```typescript
<div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
  {/* Title + Badge */}
  <div className="flex items-center gap-2">...</div>

  {/* Controls - wrap on mobile */}
  <div className="flex flex-wrap items-center gap-2">...</div>
</div>
```

### Step 9: Testing
- Test sort by spike_count, avg_spike_ratio, name
- Test sector filter (all, specific sector)
- Test expand all / collapse all
- Test color indicators for different ratios
- Test mobile layout (controls stack)
- Test keyboard navigation
- Test with 0 sectors, 1 sector, many sectors

## Todo List

- [ ] Add state management (expandedSectors, sectorSort, selectedSectors)
- [ ] Create sortedIndustries useMemo with filtering
- [ ] Create SectorGroupHeader component
- [ ] Add sort selector (spike_count, avg_spike_ratio, name)
- [ ] Add sector filter dropdown
- [ ] Add expand all / collapse all button
- [ ] Implement expand all logic
- [ ] Add color indicator to sector headers
- [ ] Update IndustrySpikeGroup to accept isOpen/onToggle props
- [ ] Test sorting functionality
- [ ] Test filtering functionality
- [ ] Test expand/collapse functionality
- [ ] Test mobile responsiveness
- [ ] Test accessibility
- [ ] Code review

## Success Criteria

- [ ] Sort selector changes order correctly
- [ ] Sector filter shows only selected sectors
- [ ] Expand all opens all sectors
- [ ] Collapse all closes all sectors
- [ ] Color indicators match avg_spike_ratio thresholds
- [ ] Sector count badge shows correct number
- [ ] Controls stack properly on mobile
- [ ] No performance degradation
- [ ] Keyboard navigation works
- [ ] No console errors/warnings

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Too many controls overwhelm UI | Medium | Low | Use compact layout, clear labels |
| Filter state confusion | Medium | Medium | Clear "all" option, visual feedback |
| Performance with many sectors | Low | Low | Already using useMemo |
| Mobile layout breaks | Medium | Low | Test thoroughly, use flex-wrap |

## Security Considerations

- No user input stored
- Filter/sort state is client-side only
- No API calls affected

## Next Steps

1. Implement all steps above
2. Test thoroughly on various screen sizes
3. Gather user feedback
4. Move to Phase 3 (advanced charts)
5. Consider localStorage persistence for preferences
