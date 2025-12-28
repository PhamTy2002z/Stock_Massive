# Phase 01: Accessibility Standards

## Context Links
- Parent plan: [plan.md](./plan.md)
- Brainstorming: `plans/reports/brainstorm-251228-1941-design-guidelines-upgrade.md`
- Current guidelines: `docs/design-guidelines.md`

## Overview
- **Priority:** P0 (Legal compliance)
- **Effort:** 3h
- **Status:** Pending
- **Description:** Add WCAG 2.1 AA compliance guidelines covering color contrast, keyboard navigation, screen reader support, and reduced motion.

## Key Insights
- ShadCN/Radix components have built-in a11y, need documentation on usage
- Stock colors (green/red) need accessible variants for small text
- Current focus states use `focus:` but should use `focus-visible:` for better UX
- Live regions needed for real-time price updates

## Requirements

### Functional
- Document color contrast requirements (4.5:1 text, 3:1 UI)
- Define keyboard navigation patterns
- Specify ARIA label requirements for complex components
- Add reduced motion guidelines

### Non-Functional
- Lighthouse A11y score ≥ 95
- All interactive elements keyboard accessible
- Screen reader compatibility

## Architecture

No new components. Updates to:
1. `docs/design-guidelines.md` - Add new section
2. `apps/web/src/app/globals.css` - Add accessible color variants

## Related Code Files

| File | Action | Description |
|------|--------|-------------|
| `docs/design-guidelines.md` | Modify | Add "Accessibility Standards" section |
| `apps/web/src/app/globals.css` | Modify | Add `--stock-up-accessible`, `--stock-down-accessible` CSS vars |

## Implementation Steps

### Step 1: Add Accessible Color Variants (30min)
1. Open `apps/web/src/app/globals.css`
2. Add accessible stock colors:
   ```css
   :root {
     --stock-up-accessible: 142 71% 29%;
     --stock-down-accessible: 0 72% 51%;
   }
   .dark {
     --stock-up-accessible: 142 70% 40%;
     --stock-down-accessible: 0 70% 55%;
   }
   ```

### Step 2: Write Color Contrast Section (30min)
1. Open `docs/design-guidelines.md`
2. After "## Semantic Colors" section, add:
   - Minimum contrast ratios table
   - When to use accessible variants
   - Code examples

### Step 3: Write Keyboard Navigation Section (45min)
1. Add section covering:
   - Focus-visible styling pattern
   - Focus trap for modals (Radix built-in)
   - Arrow key navigation for lists/grids
   - Skip navigation link
   - Tab order guidelines
2. Include code examples

### Step 4: Write Screen Reader Section (45min)
1. Add section covering:
   - ARIA labels for KPI cards
   - Live regions for price updates (`aria-live="polite"`)
   - Table semantics (`role="grid"`, `scope="col"`)
   - sr-only helper class
2. Include code examples

### Step 5: Write Reduced Motion Section (15min)
1. Add section on `prefers-reduced-motion` media query
2. Example:
   ```css
   @media (prefers-reduced-motion: reduce) {
     *, *::before, *::after {
       animation-duration: 0.01ms !important;
       transition-duration: 0.01ms !important;
     }
   }
   ```

### Step 6: Add A11y Checklist (15min)
1. Create quick-reference checklist table
2. Include standard, implementation, and testing method

## Todo List
- [ ] Add accessible color variants to globals.css
- [ ] Write color contrast section with examples
- [ ] Write keyboard navigation section
- [ ] Write screen reader section with ARIA patterns
- [ ] Write reduced motion section
- [ ] Add A11y checklist table
- [ ] Test with Lighthouse

## Success Criteria
- [ ] New section added to design-guidelines.md (~150-200 lines)
- [ ] Accessible color variants in CSS
- [ ] Code examples for all patterns
- [ ] Lighthouse A11y audit passes (≥95 score)

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Existing components don't follow patterns | Medium | Document but defer refactoring |
| Screen reader testing gaps | Low | Recommend VoiceOver/NVDA testing in guidelines |

## Security Considerations
- None specific to this phase

## Next Steps
- After this phase: Audit existing components for compliance
- Consider: Automated a11y testing with axe-core in CI
