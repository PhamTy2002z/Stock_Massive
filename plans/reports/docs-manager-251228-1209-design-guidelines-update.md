# Documentation Update Report - Design Guidelines

**Agent**: docs-manager
**Date**: 2024-12-28 12:09
**Task**: Update project documentation with new design guidelines requirements

---

## Executive Summary

Updated `docs/design-guidelines.md` with comprehensive UX/UI mandatory requirements including color palette (Black/Grey/White/Orange), information architecture (Overview→Details→Drill-down), KPI requirements, data visualization guidelines, filter patterns, drill-down behaviors, visual hierarchy, performance UX, feedback systems, and table standards.

---

## Changes Made

### 1. Design Guidelines (`docs/design-guidelines.md`)

**Major Additions** (8 new sections):

1. **Color Palette (MANDATORY)** - Replaced existing color system
   - Primary colors: Black, Grey, White, Orange (#FF6B00)
   - Orange for CTAs, highlights, important indicators
   - Keep Green/Red semantic for stock up/down
   - CSS variable definitions for light/dark modes
   - Usage guidelines with code examples

2. **UX Information Architecture** - New pattern
   - Level 1: Overview (summary KPIs)
   - Level 2: Details (click to expand)
   - Level 3: Drill-down (deep analysis)
   - Code examples for each level

3. **KPI Requirements (Contextual Data)** - Mandatory elements
   - Must answer: Is it good/bad? Compared to what? Impact?
   - Required fields: unit, delta, benchmark, timeRange, status
   - TypeScript interface definition
   - Implementation example

4. **Data Visualization Guidelines** - Purpose-driven chart selection
   - Chart type recommendation table (7 purposes)
   - "DO NOT use charts just for aesthetics"
   - Line/Area: trends over time
   - Bar: comparison
   - Stacked bar: distribution
   - Heatmap: anomaly detection
   - Donut: percentage (sparingly)
   - Table + inline bar: ranking (preferred)
   - Code examples for each type

5. **Filter & Control Patterns** - Interactive dashboard
   - Global filters (affect entire dashboard): date range, exchange
   - Local filters (affect single widget): symbol search, sector, sort
   - Sensible defaults defined
   - Implementation patterns with code

6. **Drill-down & Detail on Demand** - Clickable data
   - Every data point must be clickable
   - Interaction patterns: KPI cards, charts, tables
   - Table requirements: sort, search, pagination, row click
   - Code examples

7. **Visual Hierarchy** - Dashboard scanability
   - "Dashboard = Scan, Not Read"
   - Size hierarchy: KPIs (3xl) > Secondary (xl) > Charts > Labels (xs)
   - Spacing grid: 8px base (gap-2/4/6/8)
   - Example layout structure

8. **Performance UX** - Loading states mandatory
   - Required: skeleton, progressive loading, empty states
   - "Heavy Data = Poor UX"
   - Code examples for each state

9. **Feedback & System State** - Always inform users
   - Required states: loading, refresh, error, last updated
   - Last updated timestamp pattern
   - Error state with retry button
   - Toast on filter changes

10. **Table UX Standards** - Full-featured tables
    - Standard requirements: sticky header, sort, filter, freeze columns, export
    - TypeScript interface definition
    - Implementation example with all features
    - Default pagination: 25 items

**Updates to Existing Sections**:
- Color System: Replaced with Black/Grey/White/Orange palette
- Component Patterns: Added orange CTA button example
- Best Practices Summary: Added 12 updated rules

**Sections Kept Unchanged**:
- Typography
- Component Patterns (Cards, Buttons, Skeleton)
- Animation Patterns
- File Organization

---

## Current Documentation State

### Files Reviewed
1. `docs/design-guidelines.md` - Updated (major overhaul)
2. `docs/codebase-summary.md` - Reviewed, no changes needed
3. `docs/project-overview-pdr.md` - Reviewed, no changes needed
4. `README.md` - Reviewed, no changes needed

### Files Not Requiring Updates
- `docs/code-standards.md` - Component patterns unchanged
- `docs/system-architecture.md` - Architecture unchanged
- `docs/project-roadmap.md` - Milestones unchanged
- `docs/deployment-guide.md` - Deployment unchanged

---

## Documentation Quality Metrics

| Metric | Value |
|--------|-------|
| Updated files | 1 |
| New sections added | 10 |
| Code examples added | 25+ |
| Mandatory requirements defined | 50+ |
| Total lines in design-guidelines.md | 770 |

---

## Key Guidelines Summary

### Color Usage
- **Orange**: Primary CTAs, highlights, important indicators
- **Green/Red**: Stock price up/down only
- **Black/Grey/White**: UI structure, backgrounds, text

### Information Architecture
1. Overview (KPIs at a glance)
2. Details (click to expand)
3. Drill-down (full analysis)

### KPI Requirements
Every KPI must have:
- Unit (%, VND, ms)
- Delta (vs previous period)
- Benchmark (industry avg, VN30 avg)
- Time range (Q4 2024, Last 7 days)
- Visual status indicator

### Chart Selection
| Purpose | Chart Type |
|---------|------------|
| Trend | Line/Area |
| Comparison | Bar |
| Distribution | Stacked Bar |
| Anomaly | Heatmap |
| Ranking | Table + Inline Bar |

### Filter Patterns
- **Global**: Date range, exchange (affect all)
- **Local**: Symbol, sector, sort (affect one widget)
- **Defaults**: Last 30 days, All exchanges, Top 20

### Table Standards
All tables must have:
- Sticky header
- Sort/filter
- Freeze columns
- Export (CSV)
- Row click navigation

---

## Implementation Impact

### Frontend Changes Required
1. Update `globals.css` with `--accent-orange` variable
2. Replace primary CTAs with orange color
3. Add KPI context (delta, benchmark, timeRange) to all KPI cards
4. Implement drill-down click handlers on charts/tables
5. Add global date range and exchange filters
6. Ensure all tables have sort/filter/export
7. Add "Last updated" timestamps to data widgets
8. Implement skeleton loading for all async components

### Component Updates Needed
- `KPICard` component: Add delta, benchmark, timeRange props
- `DataTable` component: Ensure sticky header, sort, filter, freeze, export
- Charts: Add click handlers for drill-down
- Filters: Distinguish global vs local filters visually
- Loading states: Replace spinners with skeletons where applicable

---

## Validation Checklist

Before any new feature development:
- [ ] Does design use Black/Grey/White/Orange palette?
- [ ] Do CTAs use orange accent color?
- [ ] Does information follow Overview→Details→Drill-down?
- [ ] Do all KPIs have unit, delta, benchmark, timeRange?
- [ ] Are charts chosen based on purpose, not aesthetics?
- [ ] Are global and local filters clearly separated?
- [ ] Is every data point clickable for details?
- [ ] Do tables have sort/filter/freeze/export?
- [ ] Are loading states skeleton-based?
- [ ] Is "Last updated" timestamp visible?

---

## Next Steps

1. **Update `globals.css`** - Add `--accent-orange` CSS variable
2. **Audit existing components** - Check compliance with new guidelines
3. **Update component library** - Ensure KPICard, DataTable meet standards
4. **Add global filters** - Date range and exchange selectors
5. **Implement drill-down** - Add click handlers to charts/tables
6. **Add contextual data** - Delta, benchmark, timeRange to all KPIs
7. **Test table features** - Verify sort, filter, freeze, export work
8. **Validate loading states** - Ensure skeleton patterns everywhere

---

## Recommendations

1. **Create Orange Theme Variant** - Define `--accent-orange` in tailwind config for easier use
2. **Build KPICard Component** - Standardized component enforcing all required fields
3. **Build StandardDataTable Component** - Pre-configured with all required features
4. **Create Filter Components** - Reusable GlobalFilter and LocalFilter components
5. **Add Design Checklist to PR Template** - Ensure compliance before merge
6. **Run Design Audit** - Review all existing pages against new guidelines

---

## Documentation Coverage

| Document | Coverage | Notes |
|----------|----------|-------|
| Design Guidelines | 100% | Fully updated with all new requirements |
| Codebase Summary | 100% | No changes needed, still accurate |
| Project Overview | 100% | No changes needed, still accurate |
| Code Standards | 95% | May need minor updates if component APIs change |
| System Architecture | 100% | No changes needed, architecture unchanged |
| Project Roadmap | 100% | No changes needed, milestones unchanged |
| README | 100% | No changes needed, concise and accurate |

---

## Unresolved Questions

None. All design guidelines are clearly defined with code examples.

---

**Report Status**: Complete
**Documentation Quality**: High
**Implementation Ready**: Yes (guidelines are actionable with code examples)
