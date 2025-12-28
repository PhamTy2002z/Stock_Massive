# Phase 05: Dashboard Customization

## Context Links
- Parent plan: [plan.md](./plan.md)
- Brainstorming: `plans/reports/brainstorm-251228-1941-design-guidelines-upgrade.md`

## Overview
- **Priority:** P2 (Complex feature)
- **Effort:** 3h
- **Status:** Pending
- **Description:** Document widget system, drag-drop layouts, and saved views for customizable dashboards.

## Key Insights
- `react-grid-layout` is mature and widely used
- Widget registry pattern enables extensibility
- localStorage sufficient for MVP, backend sync later
- Edit mode toggle keeps normal view clean

## Requirements

### Functional
- Define widget registry pattern
- Document grid layout with react-grid-layout
- Define saved views system
- Document add/remove widget dialogs

### Non-Functional
- Drag-drop should be smooth (60fps)
- Persist layout to localStorage
- Support responsive breakpoints

## Architecture

```
apps/web/src/
├── lib/
│   └── widget-registry.ts       # Widget definitions
├── components/
│   ├── customizable-dashboard.tsx
│   ├── add-widget-dialog.tsx
│   └── saved-views-manager.tsx
└── hooks/
    ├── use-dashboard-layout.ts  # Layout state + persistence
    └── use-saved-views.ts       # Views CRUD
```

## Related Code Files

| File | Action | Description |
|------|--------|-------------|
| `docs/design-guidelines.md` | Modify | Add "Dashboard Customization" section |
| `apps/web/package.json` | Modify | Add `react-grid-layout` dependency |

## Implementation Steps

### Step 1: Document Widget Registry (30min)
1. Define WidgetConfig interface:
   ```ts
   interface WidgetConfig {
     id: string
     type: string
     title: string
     description: string
     defaultSize: { w: number; h: number }
     minSize: { w: number; h: number }
     component: React.ComponentType
   }
   ```
2. Example registry with 3-4 widgets
3. Pattern for registering new widgets

### Step 2: Document Grid Layout (45min)
1. Recommend `react-grid-layout`
2. Layout configuration:
   - cols: 4 (responsive)
   - rowHeight: 100
   - draggableHandle: ".widget-drag-handle"
3. Edit mode toggle pattern
4. Include full code example

### Step 3: Document Widget Wrapper (20min)
1. Drag handle visibility in edit mode
2. Remove button
3. Widget title overlay
4. Include code example

### Step 4: Document Saved Views (30min)
1. SavedView interface:
   ```ts
   interface SavedView {
     id: string
     name: string
     layout: DashboardLayout[]
     density: DensityMode
     isDefault: boolean
   }
   ```
2. useSavedViews hook pattern
3. Dropdown menu for view selection
4. Save current as new view
5. localStorage persistence

### Step 5: Document Add Widget Dialog (20min)
1. Grid of available widgets
2. Click to add to dashboard
3. Widget descriptions and previews
4. Include code example

### Step 6: Add to Design Guidelines (35min)
1. Add "Dashboard Customization" section
2. Structure:
   - Widget registry pattern
   - Grid layout configuration
   - Edit mode toggle
   - Widget wrapper with drag handle
   - Saved views system
   - Add widget dialog
   - localStorage persistence

## Todo List
- [ ] Document widget registry pattern
- [ ] Document react-grid-layout setup
- [ ] Document edit mode toggle
- [ ] Document widget wrapper with drag handle
- [ ] Document saved views system
- [ ] Document add widget dialog
- [ ] Add section to design-guidelines.md

## Success Criteria
- [ ] Widget registry pattern documented
- [ ] Grid layout with edit mode documented
- [ ] Saved views pattern documented
- [ ] Add widget dialog pattern documented

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Complex state management | High | Use dedicated hooks for layout/views |
| Performance with many widgets | Medium | Virtualize if >20 widgets |
| react-grid-layout bundle size | Low | Tree-shakeable, ~30kb gzipped |

## Security Considerations
- Validate widget IDs from localStorage
- Don't execute arbitrary code from saved layouts

## Next Steps
- After docs: Install react-grid-layout
- Implement widget registry with current dashboard components
- Add customization to home page
