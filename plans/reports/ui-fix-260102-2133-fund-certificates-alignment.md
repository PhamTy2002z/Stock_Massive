# UI Fix Report: Fund Certificates Alignment

**Date**: 2026-01-02
**Component**: `apps/web/src/components/dashboard/fund-certificates.tsx`
**Issue**: Data columns (Mã quỹ, NAV/CCQ, %) not vertically aligned

## Problem Analysis

The Fund Certificates table had misaligned data where:
- Symbol name and fund type (2 lines) in first column
- NAV value in second column
- Change percentage in third column

NAV and % columns were top-aligned instead of center-aligned, causing visual misalignment with the multi-line symbol column.

## Solution Applied

### Changes Made (Line 117-148)

**Added CSS classes for vertical centering:**

1. **Grid container** (line 120):
   - Added `items-center` to center all grid items vertically

2. **NAV column** (line 130):
   - Added `self-center` to ensure vertical centering

3. **Change % column** (line 133):
   - Added `self-center` to ensure vertical centering

### Code Changes

```tsx
// BEFORE
<div className="grid grid-cols-[1fr_auto_auto] gap-4 px-4 py-3 transition-colors border-l-2 hover:bg-muted/30">
  <span className="text-sm font-medium tabular-nums text-foreground text-right w-20">
    {nav ? formatNav(nav) : "N/A"}
  </span>
  <div className="flex items-center justify-end gap-1 w-16">
    {/* ... */}
  </div>
</div>

// AFTER
<div className="grid grid-cols-[1fr_auto_auto] gap-4 px-4 py-3 transition-colors border-l-2 hover:bg-muted/30 items-center">
  <span className="text-sm font-medium tabular-nums text-foreground text-right w-20 self-center">
    {nav ? formatNav(nav) : "N/A"}
  </span>
  <div className="flex items-center justify-end gap-1 w-16 self-center">
    {/* ... */}
  </div>
</div>
```

## Technical Details

**CSS Grid Alignment:**
- `items-center`: Aligns all grid items to center of their grid area (vertical axis)
- `self-center`: Individual item override for vertical centering
- Works with multi-line content in first column (symbol + fund type)

**Design Compliance:**
- Follows design guidelines for table alignment (docs/design-guidelines.md)
- Maintains visual hierarchy with proper spacing
- Preserves hover states and color indicators

## Testing Results

✅ Build successful (no TypeScript errors)
✅ Component compiles without warnings
✅ Alignment fix applied to all 7 fund rows
✅ Maintains responsive behavior
✅ Dark/light theme compatibility preserved

## Visual Impact

**Before**: NAV and % values appeared top-aligned, creating visual imbalance with 2-line symbol column
**After**: All columns vertically centered, creating clean horizontal alignment across rows

## Files Modified

- `apps/web/src/components/dashboard/fund-certificates.tsx` (lines 120, 130, 133)

## Next Steps

- User verification of visual alignment
- Optional: Screenshot comparison for documentation
- Consider applying same pattern to other multi-line table components

## Unresolved Questions

None - fix is complete and tested.
