# Design Guidelines

## Overview
Stock Massive follows a modern, professional design system optimized for data-heavy financial applications.

## Color Palette

### Primary Colors
- **Primary**: `hsl(222.2 47.4% 11.2%)` - Dark navy for headers/primary actions
- **Primary Foreground**: `hsl(210 40% 98%)` - Light text on primary

### Semantic Colors
- **Success/Bullish**: `hsl(142 76% 36%)` - Green for positive values
- **Destructive/Bearish**: `hsl(0 84% 60%)` - Red for negative values
- **Warning**: `hsl(38 92% 50%)` - Amber for alerts
- **Muted**: `hsl(210 40% 96.1%)` - Background for cards

### Chart Colors
- Candlestick Up: `#22c55e` (green-500)
- Candlestick Down: `#ef4444` (red-500)
- Volume: `#3b82f6` (blue-500)
- Grid Lines: `#e5e7eb` (gray-200)

## Typography

### Font Stack
- **Primary**: Inter, system-ui, sans-serif
- **Monospace**: JetBrains Mono, monospace (for numbers/data)

### Scale
- `text-xs`: 12px - Table cells, labels
- `text-sm`: 14px - Body text, inputs
- `text-base`: 16px - Primary content
- `text-lg`: 18px - Section headers
- `text-xl`: 20px - Page titles
- `text-2xl`: 24px - Dashboard headers

## Spacing

Based on 4px grid:
- `space-1`: 4px
- `space-2`: 8px
- `space-3`: 12px
- `space-4`: 16px
- `space-6`: 24px
- `space-8`: 32px

## Component Patterns

### Data Tables
- Fixed header on scroll
- Alternating row colors for readability
- Right-align numeric columns
- Monospace font for numbers
- Color-coded positive/negative values

### Charts
- Dark theme option for trading focus
- Crosshair on hover
- Responsive container
- Legend positioned top-right

### Cards
- Subtle shadow: `shadow-sm`
- Border radius: `rounded-lg` (8px)
- Padding: `p-4` or `p-6`

## Responsive Breakpoints

- `sm`: 640px
- `md`: 768px
- `lg`: 1024px
- `xl`: 1280px
- `2xl`: 1536px

## Accessibility

- Minimum contrast ratio: 4.5:1
- Focus indicators on all interactive elements
- Keyboard navigation support
- Screen reader labels for icons
