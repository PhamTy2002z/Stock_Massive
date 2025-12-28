# Phase 03: Keyboard Shortcuts & Command Palette

## Context Links
- Parent plan: [plan.md](./plan.md)
- Brainstorming: `plans/reports/brainstorm-251228-1941-design-guidelines-upgrade.md`

## Overview
- **Priority:** P1 (Pro user productivity)
- **Effort:** 2h
- **Status:** Pending
- **Description:** Document keyboard shortcuts and command palette (Cmd+K) patterns for power users.

## Key Insights
- `cmdk` library is ShadCN-compatible and lightweight (4kb)
- Need both global shortcuts and page-specific shortcuts
- Vim-style shortcuts (g h = go home) familiar to devs
- Shortcuts dialog (?) helps discoverability

## Requirements

### Functional
- Define global shortcuts list
- Define page-specific shortcuts pattern
- Document command palette implementation
- Document shortcuts help dialog

### Non-Functional
- No conflicts with browser shortcuts
- Work with all keyboard layouts
- Support both Mac (⌘) and Windows (Ctrl)

## Architecture

```
components/
├── command-palette.tsx        # New: Cmd+K palette
└── keyboard-shortcuts-dialog.tsx  # New: ? dialog

hooks/
└── use-keyboard-shortcuts.ts  # New: Shortcut registry
```

## Related Code Files

| File | Action | Description |
|------|--------|-------------|
| `docs/design-guidelines.md` | Modify | Add "Keyboard Shortcuts" section |
| `apps/web/src/components/command-palette.tsx` | Create | Command palette component |
| `apps/web/src/components/keyboard-shortcuts-dialog.tsx` | Create | Shortcuts help dialog |
| `apps/web/src/hooks/use-keyboard-shortcuts.ts` | Create | Shortcut handling hook |
| `apps/web/package.json` | Modify | Add `cmdk` dependency |

## Implementation Steps

### Step 1: Define Shortcut Registry (20min)
1. Create shortcut types and registry pattern
2. Define global shortcuts:
   ```ts
   const globalShortcuts = [
     { key: "k", meta: true, action: "openCommandPalette" },
     { key: "/", action: "focusSearch" },
     { key: "g h", action: "goHome" },
     { key: "g a", action: "goAnalytics" },
     { key: "?", shift: true, action: "showShortcuts" },
     { key: "Escape", action: "closeModal" },
   ]
   ```

### Step 2: Define Stock Detail Shortcuts (10min)
1. Document page-specific shortcuts:
   ```ts
   const stockDetailShortcuts = [
     { key: "1", action: "tabOverview" },
     { key: "2", action: "tabFinance" },
     { key: "3", action: "tabShareholders" },
     { key: "4", action: "tabVolume" },
     { key: "w", action: "addToWatchlist" },
     { key: "r", action: "refreshData" },
   ]
   ```

### Step 3: Document Command Palette (30min)
1. Recommend `cmdk` library (used by Vercel, Linear)
2. Document structure:
   - Input field with placeholder
   - Grouped items (Quick Actions, Stocks, Pages)
   - Keyboard navigation (↑↓, Enter, Escape)
3. Include full code example

### Step 4: Document Shortcuts Dialog (20min)
1. Pattern for Shift+? dialog
2. Grid layout with categories
3. kbd element styling
4. Include code example

### Step 5: Write use-keyboard-shortcuts Hook (20min)
1. Document hook pattern for registering shortcuts
2. Handle meta/ctrl key for cross-platform
3. Conflict detection
4. Cleanup on unmount

### Step 6: Add to Design Guidelines (30min)
1. Add "Keyboard Shortcuts & Command Palette" section
2. Structure:
   - Shortcut registry pattern
   - Global shortcuts table
   - Page-specific shortcuts example
   - Command palette implementation
   - Shortcuts dialog pattern
   - Installation (cmdk)

## Todo List
- [ ] Define shortcut registry types
- [ ] Document global shortcuts list
- [ ] Document page-specific shortcuts pattern
- [ ] Document command palette with cmdk
- [ ] Document shortcuts dialog
- [ ] Document use-keyboard-shortcuts hook
- [ ] Add full section to design-guidelines.md

## Success Criteria
- [ ] Global shortcuts defined and documented
- [ ] Command palette pattern with code example
- [ ] Shortcuts dialog pattern with code example
- [ ] cmdk installation documented

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Conflicts with browser | Medium | Avoid Ctrl+W, Ctrl+T, etc. |
| Complex multi-key shortcuts | Low | Limit to 2-key sequences max |

## Security Considerations
- Command palette should not expose admin actions to unauthorized users
- Shortcuts should respect auth state

## Next Steps
- After docs: Install cmdk, implement command-palette.tsx
- Integrate with router for navigation shortcuts
