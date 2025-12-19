# Dark Mode CSS Variables Research

**Date**: 2025-12-19
**Status**: Complete

## 1. Current Dark Mode CSS Variables

Location: `apps/web/src/app/globals.css` (lines 42-75)

| Variable | Current Value (HSL) | Purpose |
|----------|---------------------|---------|
| `--background` | 222 47% 6% | Main background |
| `--foreground` | 210 40% 98% | Main text |
| `--card` | 222 47% 8% | Card backgrounds |
| `--card-foreground` | 210 40% 98% | Card text |
| `--popover` | 222 47% 8% | Popover backgrounds |
| `--popover-foreground` | 210 40% 98% | Popover text |
| `--secondary` | 217 33% 17% | Secondary elements |
| `--muted` | 217 33% 17% | Muted backgrounds |
| `--muted-foreground` | 215 20% 65% | Muted text |
| `--accent` | 217 33% 17% | Accent backgrounds |
| `--border` | 217 33% 17% | Border color |
| `--input` | 217 33% 17% | Input backgrounds |
| `--sidebar-background` | 222 47% 8% | Sidebar bg |
| `--sidebar-foreground` | 210 40% 98% | Sidebar text |
| `--sidebar-accent` | 217 33% 17% | Sidebar accent |
| `--sidebar-border` | 217 33% 17% | Sidebar border |

## 2. Hex to HSL Conversions

### Target Colors

| Purpose | Hex | RGB | HSL |
|---------|-----|-----|-----|
| Background/Header | #181C1A | rgb(24, 28, 26) | 150 8% 10% |
| Sidebar/Frames | #0F0F0F | rgb(15, 15, 15) | 0 0% 6% |
| Text | #FFFFFF | rgb(255, 255, 255) | 0 0% 100% |

### HSL Calculation Details
- **#181C1A**: H=150deg (slight green tint), S=8%, L=10%
- **#0F0F0F**: Pure neutral gray, H=0deg, S=0%, L=6%
- **#FFFFFF**: Pure white, H=0deg, S=0%, L=100%

## 3. Variables to Update

### Primary Updates (Background/Content)
```css
--background: 150 8% 10%;        /* #181C1A - main content + header */
--foreground: 0 0% 100%;         /* white text */
--card: 150 8% 10%;              /* same as background */
--card-foreground: 0 0% 100%;   /* white text */
--popover: 150 8% 10%;           /* same as background */
--popover-foreground: 0 0% 100%; /* white text */
```

### Sidebar/Frame Updates
```css
--sidebar-background: 0 0% 6%;   /* #0F0F0F - darker sidebar */
--sidebar-foreground: 0 0% 100%; /* white text */
--sidebar-accent: 0 0% 10%;      /* slightly lighter for hover */
--sidebar-accent-foreground: 0 0% 100%;
--sidebar-border: 0 0% 12%;      /* subtle border */
```

### Secondary/Muted Updates
```css
--secondary: 0 0% 6%;            /* match sidebar for frames */
--secondary-foreground: 0 0% 100%;
--muted: 0 0% 6%;                /* match sidebar for frames */
--muted-foreground: 0 0% 65%;    /* dimmed white for secondary text */
--accent: 0 0% 6%;               /* match sidebar for frames */
--accent-foreground: 0 0% 100%;
--border: 0 0% 15%;              /* visible but subtle */
--input: 0 0% 10%;               /* match background */
```

## 4. Accessibility Considerations

### Contrast Ratios (WCAG 2.1)
| Combination | Ratio | WCAG AA | WCAG AAA |
|-------------|-------|---------|----------|
| White (#FFF) on #181C1A | ~15.5:1 | Pass | Pass |
| White (#FFF) on #0F0F0F | ~18.5:1 | Pass | Pass |
| 65% gray on #0F0F0F | ~7:1 | Pass | Pass |

### Recommendations
- White text on both backgrounds exceeds WCAG AAA (7:1) requirements
- Muted text at 65% lightness still passes AA for large text
- Consider `--muted-foreground: 0 0% 70%` if readability issues arise
- Border at 15% lightness provides sufficient visual separation

### Potential Issues
1. **Chart colors**: May need adjustment for visibility on new backgrounds
2. **Primary blue** (217 91% 60%): Verify contrast on #181C1A - should be fine
3. **Destructive red**: Verify visibility on darker backgrounds

## 5. Implementation Notes

- Tailwind config uses `hsl(var(--variable))` format - no changes needed
- Dark mode triggered by `.dark` class on root element
- `darkMode: ["class"]` in tailwind.config.js confirms class-based switching

## Summary

Update 16 CSS variables in `.dark` selector. New theme uses:
- **#181C1A** (150 8% 10%) for main content areas
- **#0F0F0F** (0 0% 6%) for sidebar and section frames
- **White** (0 0% 100%) for primary text

All combinations pass WCAG AAA contrast requirements.

---

## Unresolved Questions

1. Should `--ring` color be adjusted for focus states on darker backgrounds?
2. Do chart colors need recalibration for new background colors?
3. Are there any component-specific overrides outside globals.css?
