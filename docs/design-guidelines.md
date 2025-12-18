# Design Guidelines - Stock Massive

## Overview

Stock Massive uses ShadCN/UI (new-york style) with TailwindCSS for consistent, accessible UI components.

---

## Design System

### Color Palette

Based on ShadCN new-york theme with CSS variables:

```css
/* Light Mode */
--background: 0 0% 100%;
--foreground: 240 10% 3.9%;
--primary: 240 5.9% 10%;
--secondary: 240 4.8% 95.9%;
--muted: 240 4.8% 95.9%;
--accent: 240 4.8% 95.9%;
--destructive: 0 84.2% 60.2%;

/* Dark Mode */
--background: 240 10% 3.9%;
--foreground: 0 0% 98%;
--primary: 0 0% 98%;
--secondary: 240 3.7% 15.9%;
```

### Typography

- **Font Family**: System fonts (Inter recommended)
- **Headings**: font-semibold
- **Body**: font-normal
- **Small**: text-sm text-muted-foreground

```tsx
// Heading examples
<h1 className="text-3xl font-semibold">Page Title</h1>
<h2 className="text-2xl font-semibold">Section Title</h2>
<h3 className="text-xl font-semibold">Subsection</h3>

// Body text
<p className="text-base">Regular text</p>
<p className="text-sm text-muted-foreground">Secondary text</p>
```

### Spacing

Use Tailwind spacing scale consistently:
- **xs**: 1 (4px)
- **sm**: 2 (8px)
- **md**: 4 (16px)
- **lg**: 6 (24px)
- **xl**: 8 (32px)

```tsx
// Component spacing
<div className="p-4 space-y-4">
  <Card className="p-6">...</Card>
</div>
```

---

## Component Guidelines

### Buttons

```tsx
import { Button } from "@/components/ui/button"

// Primary action
<Button>Submit</Button>

// Secondary action
<Button variant="secondary">Cancel</Button>

// Destructive action
<Button variant="destructive">Delete</Button>

// Ghost/subtle
<Button variant="ghost">More</Button>

// With icon
<Button>
  <PlusIcon className="mr-2 h-4 w-4" />
  Add Stock
</Button>
```

### Cards

```tsx
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"

<Card>
  <CardHeader>
    <CardTitle>Stock Overview</CardTitle>
  </CardHeader>
  <CardContent>
    {/* Content */}
  </CardContent>
</Card>
```

### Forms

```tsx
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

<div className="space-y-2">
  <Label htmlFor="symbol">Stock Symbol</Label>
  <Input id="symbol" placeholder="VNM" />
</div>
```

### Tables (TanStack Table)

```tsx
// Use consistent styling
<Table>
  <TableHeader>
    <TableRow>
      <TableHead>Symbol</TableHead>
      <TableHead className="text-right">Price</TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    <TableRow>
      <TableCell className="font-medium">VNM</TableCell>
      <TableCell className="text-right">85,000</TableCell>
    </TableRow>
  </TableBody>
</Table>
```

---

## Layout Patterns

### Dashboard Layout

```tsx
// Standard dashboard structure
<div className="flex min-h-screen">
  <AppSidebar />
  <div className="flex-1">
    <DashboardHeader />
    <main className="p-6">
      {children}
    </main>
  </div>
</div>
```

### Page Layout

```tsx
// Standard page structure
<div className="space-y-6">
  <div className="flex items-center justify-between">
    <h1 className="text-3xl font-semibold">Page Title</h1>
    <Button>Action</Button>
  </div>

  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
    {/* Metric cards */}
  </div>

  <Card>
    {/* Main content */}
  </Card>
</div>
```

### Responsive Grid

```tsx
// Responsive card grid
<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
  {items.map(item => <Card key={item.id}>...</Card>)}
</div>
```

---

## Chart Styling

### TradingView Lightweight Charts

```tsx
// Recommended chart options
const chartOptions = {
  layout: {
    background: { type: 'solid', color: 'transparent' },
    textColor: 'hsl(var(--foreground))',
  },
  grid: {
    vertLines: { color: 'hsl(var(--border))' },
    horzLines: { color: 'hsl(var(--border))' },
  },
  crosshair: {
    mode: CrosshairMode.Normal,
  },
}

// Candlestick colors
const candlestickOptions = {
  upColor: '#22c55e',      // green-500
  downColor: '#ef4444',    // red-500
  borderUpColor: '#22c55e',
  borderDownColor: '#ef4444',
  wickUpColor: '#22c55e',
  wickDownColor: '#ef4444',
}
```

---

## Icons

Use Lucide React icons consistently:

```tsx
import {
  Home,
  LineChart,
  Briefcase,
  Star,
  Settings,
  Plus,
  Search,
  ChevronDown
} from "lucide-react"

// Standard icon size
<Home className="h-4 w-4" />

// In buttons
<Button>
  <Plus className="mr-2 h-4 w-4" />
  Add
</Button>
```

---

## Accessibility

### Requirements
- All interactive elements must be keyboard accessible
- Use semantic HTML elements
- Provide aria-labels for icon-only buttons
- Maintain color contrast ratios (WCAG AA)

### Examples

```tsx
// Icon button with label
<Button variant="ghost" size="icon" aria-label="Search">
  <Search className="h-4 w-4" />
</Button>

// Form accessibility
<Label htmlFor="email">Email</Label>
<Input id="email" type="email" aria-describedby="email-hint" />
<p id="email-hint" className="text-sm text-muted-foreground">
  We'll never share your email.
</p>
```

---

## Mobile Considerations

### Breakpoints
- **sm**: 640px
- **md**: 768px
- **lg**: 1024px
- **xl**: 1280px

### Mobile-first Approach

```tsx
// Mobile-first responsive design
<div className="p-4 md:p-6 lg:p-8">
  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
    {/* Content */}
  </div>
</div>
```

### useIsMobile Hook

```tsx
import { useIsMobile } from "@/hooks/use-mobile"

function Component() {
  const isMobile = useIsMobile()

  return isMobile ? <MobileView /> : <DesktopView />
}
```

---

## Best Practices

1. **Consistency**: Use ShadCN components instead of custom implementations
2. **Reusability**: Extract repeated patterns into components
3. **Performance**: Use `cn()` for conditional classes
4. **Accessibility**: Test with keyboard navigation
5. **Responsiveness**: Design mobile-first, enhance for desktop
