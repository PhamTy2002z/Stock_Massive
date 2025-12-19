# Phase 1: CSS Variables Update

**Status**: Complete ✓
**Estimated**: 15 min
**Completed**: 2025-12-19

## Context

- [Plan Overview](./plan.md)
- [CSS Variables Research](./research/researcher-01-css-variables.md)

## Overview

Update 16 CSS variables in `.dark` selector to implement new color palette.

## Requirements

- Background/content areas: #181C1A (150 8% 10%)
- Sidebar/frames: #0F0F0F (0 0% 6%)
- Primary text: white (0 0% 100%)
- Maintain WCAG AA contrast ratios

## Implementation

### File: `apps/web/src/app/globals.css`

Update `.dark` selector (lines 42-75) with these values:

| Variable | Old Value | New Value |
|----------|-----------|-----------|
| `--background` | 222 47% 6% | 150 8% 10% |
| `--foreground` | 210 40% 98% | 0 0% 100% |
| `--card` | 222 47% 8% | 150 8% 10% |
| `--card-foreground` | 210 40% 98% | 0 0% 100% |
| `--popover` | 222 47% 8% | 150 8% 10% |
| `--popover-foreground` | 210 40% 98% | 0 0% 100% |
| `--secondary` | 217 33% 17% | 0 0% 6% |
| `--secondary-foreground` | 210 40% 98% | 0 0% 100% |
| `--muted` | 217 33% 17% | 0 0% 6% |
| `--muted-foreground` | 215 20% 65% | 0 0% 65% |
| `--accent` | 217 33% 17% | 0 0% 6% |
| `--accent-foreground` | 210 40% 98% | 0 0% 100% |
| `--border` | 217 33% 17% | 0 0% 15% |
| `--input` | 217 33% 17% | 0 0% 10% |
| `--sidebar-background` | 222 47% 8% | 0 0% 6% |
| `--sidebar-foreground` | 210 40% 98% | 0 0% 100% |
| `--sidebar-accent` | 217 33% 17% | 0 0% 10% |
| `--sidebar-accent-foreground` | 210 40% 98% | 0 0% 100% |
| `--sidebar-border` | 217 33% 17% | 0 0% 12% |

### Notes

- Keep `--primary`, `--destructive`, `--ring`, `--chart-*` unchanged (brand colors)
- Keep `--sidebar-primary`, `--sidebar-ring` unchanged

## Todo

- [x] Update `.dark` selector in globals.css
- [x] Verify no syntax errors
- [x] Check dark mode renders correctly

## Success Criteria

1. All 16 variables updated with correct HSL values
2. No CSS syntax errors
3. Dark mode displays new color palette
4. Light mode unaffected
