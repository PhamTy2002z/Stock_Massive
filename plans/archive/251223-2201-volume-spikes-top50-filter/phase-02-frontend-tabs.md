# Phase 02: Frontend Tabs Implementation

## Context

- **Parent Plan:** [plan.md](./plan.md)
- **Dependencies:** [Phase 01](./phase-01-backend-filter.md) must be complete
- **Docs:** `docs/code-standards.md`, `docs/design-guidelines.md`

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-23 |
| Priority | P2 |
| Effort | 1.5h |
| Implementation Status | completed |
| Review Status | approved |

## Description

Add Data Source Tabs (Top 50 LN | Tất cả) above filters in VolumeSpikeDashboard. Default to "Top 50 LN" tab. Hide exchange filter in Top 50 mode.

## Key Insights

1. Use existing ShadCN Tabs component
2. Tab state controls `topProfitableOnly` param passed to hook
3. Different headers/subheaders per tab
4. Exchange filter only visible in "Tất cả" mode
5. Reuse all existing charts and industry groups

## Requirements

- [x] Add `topProfitableOnly` to API types and hook
- [x] Add Data Source Tabs component above filters
- [x] Default to "top50" tab
- [x] Dynamic header based on active tab
- [x] Hide exchange filter in Top 50 mode
- [x] Handle empty state for Top 50

## Related Files

| File | Changes |
|------|---------|
| `apps/web/src/lib/api.ts` | Add `topProfitableOnly` param |
| `apps/web/src/lib/query-keys.ts` | Update query key |
| `apps/web/src/hooks/use-volume-spikes.ts` | Add param to hook |
| `apps/web/src/components/dashboard/volume-spike-dashboard.tsx` | Add tabs, dynamic UI |

## Implementation Steps

### Step 1: Update API Types (lib/api.ts)

```typescript
export interface VolumeSpikeParams {
  targetDate?: string
  minRatio?: number
  exchange?: string
  includeUpcom?: boolean
  limit?: number
  topProfitableOnly?: boolean  // NEW
}

export async function fetchVolumeSpikes(params: VolumeSpikeParams = {}) {
  const searchParams = new URLSearchParams()
  // ... existing params ...
  if (params.topProfitableOnly) {
    searchParams.set("top_profitable_only", "true")
  }
  // ...
}
```

### Step 2: Update Query Keys (lib/query-keys.ts)

```typescript
export const queryKeys = {
  // ...
  volumeSpikes: (params: VolumeSpikeParams = {}) => [
    "volumeSpikes",
    params.minRatio,
    params.exchange,
    params.includeUpcom,
    params.topProfitableOnly,  // NEW
  ] as const,
}
```

### Step 3: Update Hook (use-volume-spikes.ts)

No changes needed - hook already passes full params object.

### Step 4: Update Dashboard (volume-spike-dashboard.tsx)

```tsx
// Add state for data source tab
const [dataSource, setDataSource] = useState<"top50" | "all">("top50")
const topProfitableOnly = dataSource === "top50"

// Update hook call
const { data, isLoading, isFetching, error, refetch } = useVolumeSpikes({
  minRatio,
  exchange: topProfitableOnly ? undefined : exchange,  // Hide in top50 mode
  includeUpcom: topProfitableOnly ? false : includeUpcom,
  topProfitableOnly,
})

// Add Tabs above filters
<Tabs value={dataSource} onValueChange={(v) => setDataSource(v as "top50" | "all")}>
  <TabsList className="mb-4">
    <TabsTrigger value="top50">Top 50 LN</TabsTrigger>
    <TabsTrigger value="all">Tất cả</TabsTrigger>
  </TabsList>
</Tabs>

// Dynamic header
<h1 className="text-2xl font-bold">
  {topProfitableOnly
    ? "Khối lượng đột biến - Top 50 Lợi nhuận"
    : "Khối lượng đột biến - Tất cả"
  }
</h1>
{topProfitableOnly && (
  <p className="text-sm text-muted-foreground">
    Chỉ hiển thị CP từ 50 công ty có lợi nhuận cao nhất
  </p>
)}

// Conditional exchange filter (only show in "all" mode)
{!topProfitableOnly && (
  <div className="flex items-center gap-2">
    <Label>Sàn:</Label>
    <Select value={exchange || "all"} onValueChange={...}>
      {/* Exchange options */}
    </Select>
  </div>
)}

// Empty state for Top 50
{topProfitableOnly && data?.total_spikes === 0 && (
  <div className="text-center py-8">
    <p className="text-muted-foreground">
      Không có cổ phiếu Top 50 nào đạt ngưỡng đột biến hôm nay.
    </p>
    <Button variant="link" onClick={() => setDataSource("all")}>
      Xem tab "Tất cả" để xem toàn bộ thị trường
    </Button>
  </div>
)}
```

## Architecture

```
VolumeSpikeDashboard
├── Header (dynamic based on dataSource)
├── Data Source Tabs [ Top 50 LN | Tất cả ]
├── Filters
│   ├── Ngưỡng (always visible)
│   └── Sàn (hidden in top50 mode)
├── Summary Cards
├── Chart Tabs
└── Industry Groups
```

## Todo List

- [ ] Add `topProfitableOnly` to VolumeSpikeParams interface
- [ ] Update fetchVolumeSpikes to include new param
- [ ] Update query keys
- [ ] Add `dataSource` state to dashboard
- [ ] Add Data Source Tabs component
- [ ] Update header to be dynamic
- [ ] Conditionally show exchange filter
- [ ] Add empty state for Top 50 mode

## Success Criteria

1. Page loads with "Top 50 LN" tab active by default
2. Switching tabs triggers new API call with correct param
3. Exchange filter hidden in Top 50 mode
4. Header updates based on active tab
5. Empty state shows helpful message with link to "Tất cả"

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Tab state not synced with API | Low | Medium | Use single source of truth |
| Flash of wrong content | Low | Low | keepPreviousData already enabled |

## Security Considerations

- No security concerns - only UI changes
- Boolean param sanitized by backend

## Next Steps

After this phase: [Phase 03 - Testing](./phase-03-testing.md)
