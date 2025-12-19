# Design Guidelines - Stock Massive

## Design Philosophy: Modern + Clean

**This is the STANDARD design style for all future development.**

Stock Massive follows a Modern + Clean design philosophy characterized by:
- Clean visual hierarchy with ample whitespace
- HSL-based color system with CSS variables
- Consistent component patterns via ShadCN/UI
- Smooth, purposeful animations
- Full dark/light theme support
- Mobile-first responsive design

---

## Color System (HSL Variables)

All colors use HSL format for easy theming. Defined in `apps/web/src/app/globals.css`.

### Light Mode

```css
:root {
  /* Base */
  --background: 210 20% 98%;        /* Off-white background */
  --foreground: 222 47% 11%;        /* Dark blue-gray text */

  /* Cards & Surfaces */
  --card: 0 0% 100%;                /* Pure white cards */
  --card-foreground: 222 47% 11%;
  --popover: 0 0% 100%;
  --popover-foreground: 222 47% 11%;

  /* Primary (Blue) */
  --primary: 217 91% 60%;           /* Vibrant blue */
  --primary-foreground: 0 0% 100%;

  /* Secondary & Muted */
  --secondary: 210 40% 96%;
  --secondary-foreground: 222 47% 11%;
  --muted: 210 40% 96%;
  --muted-foreground: 215 16% 47%;
  --accent: 210 40% 96%;
  --accent-foreground: 222 47% 11%;

  /* Semantic */
  --destructive: 0 84% 60%;         /* Red for errors/danger */
  --destructive-foreground: 0 0% 98%;

  /* Borders & Inputs */
  --border: 214 32% 91%;
  --input: 214 32% 91%;
  --ring: 217 91% 60%;

  /* Chart Colors */
  --chart-1: 142 76% 36%;           /* Green (positive) */
  --chart-2: 0 84% 60%;             /* Red (negative) */
  --chart-3: 217 91% 60%;           /* Blue (primary) */
  --chart-4: 43 96% 56%;            /* Yellow/Gold */
  --chart-5: 262 83% 58%;           /* Purple */

  /* Sidebar */
  --sidebar-background: 0 0% 100%;
  --sidebar-foreground: 222 47% 11%;
  --sidebar-primary: 217 91% 60%;
  --sidebar-accent: 210 40% 96%;
  --sidebar-border: 214 32% 91%;

  --radius: 0.625rem;               /* 10px border radius */
}
```

### Dark Mode

```css
.dark {
  --background: 222 47% 6%;         /* Deep blue-black */
  --foreground: 210 40% 98%;        /* Off-white text */

  --card: 222 47% 8%;               /* Slightly lighter cards */
  --card-foreground: 210 40% 98%;
  --popover: 222 47% 8%;
  --popover-foreground: 210 40% 98%;

  --primary: 217 91% 60%;           /* Same vibrant blue */
  --primary-foreground: 0 0% 100%;

  --secondary: 217 33% 17%;
  --secondary-foreground: 210 40% 98%;
  --muted: 217 33% 17%;
  --muted-foreground: 215 20% 65%;
  --accent: 217 33% 17%;
  --accent-foreground: 210 40% 98%;

  --destructive: 0 63% 31%;
  --destructive-foreground: 210 40% 98%;

  --border: 217 33% 17%;
  --input: 217 33% 17%;
  --ring: 217 91% 60%;

  /* Chart colors adjusted for dark mode */
  --chart-1: 142 70% 45%;
  --chart-2: 0 84% 60%;
  --chart-3: 217 91% 60%;
  --chart-4: 43 96% 56%;
  --chart-5: 262 83% 58%;

  --sidebar-background: 222 47% 8%;
  --sidebar-foreground: 210 40% 98%;
  --sidebar-primary: 217 91% 60%;
  --sidebar-accent: 217 33% 17%;
  --sidebar-border: 217 33% 17%;
}
```

### Stock-Specific Colors

```tsx
// Price change colors
const priceColors = {
  positive: "text-green-600 dark:text-green-400",  // Price up
  negative: "text-red-600 dark:text-red-400",      // Price down
  neutral: "text-muted-foreground",                // No change
}

// Chart candlestick colors
const candlestickColors = {
  upColor: "#22c55e",      // green-500
  downColor: "#ef4444",    // red-500
}
```

---

## Typography

### Font Stack
- **Primary**: System fonts (Inter recommended for web)
- **Monospace**: For numbers and code

### Scale

```tsx
// Headings
<h1 className="text-3xl font-semibold">Page Title</h1>
<h2 className="text-2xl font-semibold">Section Title</h2>
<h3 className="text-xl font-semibold">Subsection</h3>
<h4 className="text-lg font-medium">Card Title</h4>

// Body
<p className="text-base">Regular text</p>
<p className="text-sm text-muted-foreground">Secondary text</p>
<p className="text-xs text-muted-foreground">Caption/label</p>

// Numbers (tabular for alignment)
<span className="tabular-nums font-semibold">1,234,567</span>
```

---

## Component Patterns

### Cards (Primary Container)

```tsx
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"

// Standard card
<Card>
  <CardHeader>
    <CardTitle>Stock Overview</CardTitle>
  </CardHeader>
  <CardContent>
    {/* Content */}
  </CardContent>
</Card>

// Stat card (compact)
<div className="rounded-lg border bg-card p-3">
  <p className="text-xs text-muted-foreground">Label</p>
  <p className="mt-1 text-sm font-semibold tabular-nums">Value</p>
</div>
```

### Buttons

```tsx
import { Button } from "@/components/ui/button"

<Button>Primary Action</Button>
<Button variant="secondary">Secondary</Button>
<Button variant="destructive">Delete</Button>
<Button variant="ghost">Subtle</Button>
<Button variant="outline">Outlined</Button>

// With icon
<Button>
  <PlusIcon className="mr-2 h-4 w-4" />
  Add Stock
</Button>
```

### Skeleton Loading

```tsx
import { Skeleton } from "@/components/ui/skeleton"

// Text skeleton
<Skeleton className="h-4 w-[200px]" />

// Card skeleton
<div className="space-y-3">
  <Skeleton className="h-8 w-full" />
  <Skeleton className="h-4 w-3/4" />
  <Skeleton className="h-4 w-1/2" />
</div>

// Stock card skeleton
<Card>
  <CardContent className="p-4">
    <Skeleton className="h-6 w-20 mb-2" />
    <Skeleton className="h-8 w-32" />
  </CardContent>
</Card>
```

### Tabs

```tsx
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"

<Tabs defaultValue="overview">
  <TabsList>
    <TabsTrigger value="overview">Overview</TabsTrigger>
    <TabsTrigger value="financials">Financials</TabsTrigger>
    <TabsTrigger value="shareholders">Shareholders</TabsTrigger>
  </TabsList>
  <TabsContent value="overview">...</TabsContent>
  <TabsContent value="financials">...</TabsContent>
  <TabsContent value="shareholders">...</TabsContent>
</Tabs>
```

---

## Animation Patterns

### Sidebar Transition

```css
.sidebar-transition {
  transition-property: width, left, right, margin;
  transition-duration: 300ms;
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  will-change: width, left, right, margin;
}

/* GPU acceleration */
[data-sidebar="sidebar"] {
  transform: translateZ(0);
  backface-visibility: hidden;
}
```

### Stock Detail Enter Animation

```css
.stock-detail-enter {
  animation: stockDetailFadeIn 0.3s ease-out;
}

@keyframes stockDetailFadeIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

### Icon Collapse Transition

```css
[data-collapsible="icon"] [data-sidebar="menu-button"] span:last-child {
  transition: opacity 150ms ease-out;
}

[data-state="collapsed"][data-collapsible="icon"] span:last-child {
  opacity: 0;
  visibility: hidden;
  transition: opacity 100ms ease-in, visibility 0ms 100ms;
}
```

---

## Layout Patterns

### Dashboard Layout

```tsx
<SidebarProvider>
  <AppSidebar />
  <SidebarInset>
    <DashboardHeader />
    <main className="flex-1 p-4 md:p-6">
      {children}
    </main>
  </SidebarInset>
</SidebarProvider>
```

### Page Structure

```tsx
<div className="space-y-6">
  {/* Header */}
  <div className="flex items-center justify-between">
    <h1 className="text-3xl font-semibold">Page Title</h1>
    <Button>Action</Button>
  </div>

  {/* Metric cards grid */}
  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
    {/* Cards */}
  </div>

  {/* Main content */}
  <Card>
    {/* Content */}
  </Card>
</div>
```

### Responsive Grid

```tsx
// 1 col mobile, 2 col tablet, 4 col desktop
<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
  {items.map(item => <Card key={item.id}>...</Card>)}
</div>

// Stock detail stats
<div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
  <StatCard label="Volume" value="1.2M" />
  <StatCard label="Exchange" value="HOSE" />
  <StatCard label="Market Cap" value="150.5 ty" />
  <StatCard label="Industry" value="Banking" />
</div>
```

---

## Scrollbar Styling

```css
.scrollbar-thin {
  scrollbar-width: thin;
  scrollbar-color: hsl(var(--muted-foreground) / 0.3) transparent;
}

.scrollbar-thin::-webkit-scrollbar {
  height: 6px;
  width: 6px;
}

.scrollbar-thin::-webkit-scrollbar-track {
  background: transparent;
}

.scrollbar-thin::-webkit-scrollbar-thumb {
  background-color: hsl(var(--muted-foreground) / 0.3);
  border-radius: 3px;
}

.scrollbar-thin::-webkit-scrollbar-thumb:hover {
  background-color: hsl(var(--muted-foreground) / 0.5);
}
```

---

## Icons

Use Lucide React icons consistently:

```tsx
import {
  Home, LineChart, Briefcase, Star, Settings,
  Plus, Search, ChevronDown, TrendingUp, TrendingDown
} from "lucide-react"

// Standard size
<Home className="h-4 w-4" />

// In buttons
<Button>
  <Plus className="mr-2 h-4 w-4" />
  Add
</Button>

// Icon-only button
<Button variant="ghost" size="icon" aria-label="Search">
  <Search className="h-4 w-4" />
</Button>
```

---

## Theme Implementation

### Theme Provider

```tsx
// components/providers/theme-provider.tsx
import { ThemeProvider as NextThemesProvider } from "next-themes"

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  )
}
```

### Theme Toggle

```tsx
import { useTheme } from "next-themes"
import { Moon, Sun } from "lucide-react"

function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
    >
      <Sun className="h-4 w-4 rotate-0 scale-100 dark:-rotate-90 dark:scale-0" />
      <Moon className="absolute h-4 w-4 rotate-90 scale-0 dark:rotate-0 dark:scale-100" />
    </Button>
  )
}
```

---

## Accessibility Requirements

1. **Keyboard Navigation**: All interactive elements must be keyboard accessible
2. **Semantic HTML**: Use proper heading hierarchy and landmarks
3. **ARIA Labels**: Provide labels for icon-only buttons
4. **Color Contrast**: Maintain WCAG AA contrast ratios
5. **Focus Indicators**: Visible focus states on all interactive elements

```tsx
// Icon button with label
<Button variant="ghost" size="icon" aria-label="Search stocks">
  <Search className="h-4 w-4" />
</Button>

// Form accessibility
<Label htmlFor="symbol">Stock Symbol</Label>
<Input id="symbol" placeholder="VCB" aria-describedby="symbol-hint" />
<p id="symbol-hint" className="text-sm text-muted-foreground">
  Enter a Vietnamese stock ticker
</p>
```

---

## Best Practices Summary

1. **Use CSS Variables**: Always use `hsl(var(--color))` for theming
2. **Consistent Spacing**: Follow Tailwind spacing scale (4, 6, 8, etc.)
3. **Component Reuse**: Use ShadCN components, avoid custom implementations
4. **Loading States**: Always show skeleton loaders during data fetch
5. **Error States**: Provide clear error messages with recovery actions
6. **Mobile First**: Design for mobile, enhance for desktop
7. **Animation Purpose**: Use animations to guide attention, not distract
8. **Tabular Numbers**: Use `tabular-nums` for numeric data alignment

---

## File Organization

```
components/
├── ui/                    # ShadCN base components
│   ├── button.tsx
│   ├── card.tsx
│   ├── skeleton.tsx
│   └── ...
├── dashboard/             # Feature-specific components
│   ├── market-indices.tsx
│   ├── stock-detail-panel.tsx
│   ├── stock-ticker-header.tsx
│   └── ...
├── layout/                # Layout components
│   ├── app-sidebar.tsx
│   ├── dashboard-header.tsx
│   └── dashboard-layout.tsx
└── providers/             # Context providers
    └── theme-provider.tsx
```
