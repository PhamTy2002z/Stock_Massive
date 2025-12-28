# Brainstorming Report: Design Guidelines Upgrade

**Date:** 2024-12-28
**Status:** Draft for Review
**Scope:** 6 High-Priority Sections
**Focus:** Pro-first với Retail mode option

---

## Problem Statement

Design guidelines hiện tại của Stock Massive đã cover các phần cơ bản (color, typography, loading states, tables). Tuy nhiên, để đạt chuẩn modern SaaS dashboard cho financial analysis, cần bổ sung:

1. **Accessibility Standards** - WCAG compliance
2. **Data Density Modes** - Pro vs Retail experience
3. **Keyboard Shortcuts** - Power user productivity
4. **Real-time Update Patterns** - WebSocket, visual cues
5. **Dashboard Customization** - Widget management, saved views
6. **Onboarding & Contextual Help** - Feature discovery

---

## Proposed Additions

### 1. Accessibility (A11y) Standards

**Rationale:** WCAG 2.1 AA compliance là requirement bắt buộc cho SaaS product. Financial dashboards cần đảm bảo mọi user đều có thể access data.

#### 1.1 Color Contrast Requirements

```css
/* Minimum contrast ratios */
:root {
  /* Text: 4.5:1 minimum for normal text */
  /* Large text (18px+): 3:1 minimum */
  /* UI components: 3:1 minimum */

  /* Stock colors with accessible alternatives */
  --stock-up: 142 76% 36%;        /* #22C55E - 4.5:1 on white */
  --stock-up-accessible: 142 71% 29%;  /* Darker for small text */

  --stock-down: 0 84% 60%;        /* #EF4444 - 4.5:1 on white */
  --stock-down-accessible: 0 72% 51%;  /* Darker for small text */
}
```

#### 1.2 Keyboard Navigation

```tsx
// MANDATORY: All interactive elements must be keyboard accessible
interface KeyboardAccessibleProps {
  // Focus must be visible
  className: "focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"

  // Logical tab order
  tabIndex?: number

  // Arrow key navigation for lists/grids
  onKeyDown?: (e: KeyboardEvent) => void
}

// Focus trap for modals
import { FocusTrap } from "@radix-ui/react-focus-trap"

<Dialog>
  <FocusTrap>
    <DialogContent>
      {/* First focusable element receives focus on open */}
      {/* Tab cycles through, Escape closes */}
    </DialogContent>
  </FocusTrap>
</Dialog>

// Skip navigation link
<a
  href="#main-content"
  className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 z-50 bg-primary text-white px-4 py-2 rounded"
>
  Skip to main content
</a>
```

#### 1.3 Screen Reader Support

```tsx
// ARIA labels for complex components
<Card aria-label="VN-INDEX market summary">
  <CardHeader>
    <CardTitle id="vnindex-title">VN-INDEX</CardTitle>
  </CardHeader>
  <CardContent aria-labelledby="vnindex-title">
    <span className="text-3xl font-bold" aria-label="Current value: 1,245.67">
      1,245.67
    </span>
    <Badge
      aria-label="Change: up 2.5 percent"
      role="status"
    >
      ↑ 2.5%
    </Badge>
  </CardContent>
</Card>

// Live regions for real-time updates
<div
  aria-live="polite"
  aria-atomic="true"
  className="sr-only"
>
  {/* Announce price changes without interrupting */}
  VN-INDEX updated to {value}, {change > 0 ? 'up' : 'down'} {Math.abs(change)} percent
</div>

// Data tables with proper semantics
<Table role="grid" aria-label="VN30 stocks performance">
  <TableHeader>
    <TableRow>
      <TableHead scope="col" aria-sort={sortDirection}>Symbol</TableHead>
      <TableHead scope="col">Price</TableHead>
    </TableRow>
  </TableHeader>
</Table>
```

#### 1.4 A11y Checklist

| Requirement | Standard | Implementation |
|-------------|----------|----------------|
| Color contrast | 4.5:1 (text), 3:1 (UI) | Use `--stock-up-accessible` for small text |
| Focus visible | WCAG 2.4.7 | `focus-visible:ring-2` on all interactives |
| Keyboard nav | WCAG 2.1.1 | No mouse-only interactions |
| Screen reader | WCAG 4.1.2 | ARIA labels, live regions |
| Reduced motion | WCAG 2.3.3 | `prefers-reduced-motion` media query |

---

### 2. Data Density Modes

**Rationale:** Pro traders cần high data density, compact layouts. Retail investors cần spacious, easier-to-read layouts. Support both with mode switching.

#### 2.1 Density Configuration

```tsx
type DensityMode = "compact" | "comfortable" | "spacious"

interface DensityConfig {
  mode: DensityMode
  spacing: {
    card: string      // gap between cards
    content: string   // padding inside cards
    table: string     // row height
  }
  typography: {
    kpi: string       // KPI value size
    label: string     // Label size
    body: string      // Body text
  }
  charts: {
    height: string    // Default chart height
    showLabels: boolean
  }
}

const densityConfigs: Record<DensityMode, DensityConfig> = {
  compact: {
    spacing: { card: "gap-2", content: "p-2", table: "h-8" },
    typography: { kpi: "text-xl", label: "text-xs", body: "text-xs" },
    charts: { height: "h-32", showLabels: false }
  },
  comfortable: {
    spacing: { card: "gap-4", content: "p-4", table: "h-10" },
    typography: { kpi: "text-2xl", label: "text-sm", body: "text-sm" },
    charts: { height: "h-48", showLabels: true }
  },
  spacious: {
    spacing: { card: "gap-6", content: "p-6", table: "h-12" },
    typography: { kpi: "text-3xl", label: "text-base", body: "text-base" },
    charts: { height: "h-64", showLabels: true }
  }
}
```

#### 2.2 Density Context Provider

```tsx
// providers/density-provider.tsx
import { createContext, useContext, useState } from "react"

const DensityContext = createContext<{
  density: DensityMode
  setDensity: (mode: DensityMode) => void
  config: DensityConfig
}>()

export function DensityProvider({ children }: { children: React.ReactNode }) {
  // Pro-first: default to compact
  const [density, setDensity] = useState<DensityMode>("compact")
  const config = densityConfigs[density]

  return (
    <DensityContext.Provider value={{ density, setDensity, config }}>
      <div data-density={density}>
        {children}
      </div>
    </DensityContext.Provider>
  )
}

export const useDensity = () => useContext(DensityContext)
```

#### 2.3 Density-Aware Components

```tsx
// Example: Density-aware KPI card
function KPICard({ label, value, delta }: KPICardProps) {
  const { config } = useDensity()

  return (
    <Card className={config.spacing.content}>
      <p className={cn("text-muted-foreground", config.typography.label)}>
        {label}
      </p>
      <p className={cn("font-bold tabular-nums", config.typography.kpi)}>
        {value}
      </p>
    </Card>
  )
}

// Density toggle in header
<ToggleGroup
  type="single"
  value={density}
  onValueChange={setDensity}
  aria-label="Display density"
>
  <ToggleGroupItem value="compact" aria-label="Compact view">
    <LayoutGrid className="h-4 w-4" />
  </ToggleGroupItem>
  <ToggleGroupItem value="comfortable" aria-label="Comfortable view">
    <LayoutList className="h-4 w-4" />
  </ToggleGroupItem>
  <ToggleGroupItem value="spacious" aria-label="Spacious view">
    <Square className="h-4 w-4" />
  </ToggleGroupItem>
</ToggleGroup>
```

#### 2.4 CSS Variables Approach (Alternative)

```css
/* Apply via data attribute for CSS-only density */
[data-density="compact"] {
  --density-spacing-card: 0.5rem;
  --density-spacing-content: 0.5rem;
  --density-kpi-size: 1.25rem;
  --density-chart-height: 8rem;
}

[data-density="comfortable"] {
  --density-spacing-card: 1rem;
  --density-spacing-content: 1rem;
  --density-kpi-size: 1.5rem;
  --density-chart-height: 12rem;
}

[data-density="spacious"] {
  --density-spacing-card: 1.5rem;
  --density-spacing-content: 1.5rem;
  --density-kpi-size: 1.875rem;
  --density-chart-height: 16rem;
}
```

---

### 3. Keyboard Shortcuts & Command Palette

**Rationale:** Pro traders cần quick actions. Command palette (Cmd+K) là pattern phổ biến trong modern apps.

#### 3.1 Global Shortcuts

```tsx
// hooks/use-keyboard-shortcuts.ts
const globalShortcuts: Shortcut[] = [
  { key: "k", meta: true, action: "openCommandPalette", description: "Open command palette" },
  { key: "/", action: "focusSearch", description: "Focus search" },
  { key: "g h", action: "goHome", description: "Go to dashboard" },
  { key: "g a", action: "goAnalytics", description: "Go to analytics" },
  { key: "g w", action: "goWatchlist", description: "Go to watchlist" },
  { key: "?", shift: true, action: "showShortcuts", description: "Show keyboard shortcuts" },
  { key: "Escape", action: "closeModal", description: "Close modal/panel" },
]

// Page-specific shortcuts
const stockDetailShortcuts: Shortcut[] = [
  { key: "1", action: "tabOverview", description: "Overview tab" },
  { key: "2", action: "tabFinance", description: "Finance tab" },
  { key: "3", action: "tabShareholders", description: "Shareholders tab" },
  { key: "4", action: "tabVolume", description: "Volume tab" },
  { key: "w", action: "addToWatchlist", description: "Add to watchlist" },
  { key: "c", action: "compareStock", description: "Compare with..." },
  { key: "r", action: "refreshData", description: "Refresh data" },
]
```

#### 3.2 Command Palette Implementation

```tsx
// components/command-palette.tsx
import { Command } from "cmdk"

export function CommandPalette() {
  const [open, setOpen] = useState(false)

  // Cmd+K to open
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setOpen((open) => !open)
      }
    }
    document.addEventListener("keydown", down)
    return () => document.removeEventListener("keydown", down)
  }, [])

  return (
    <Command.Dialog open={open} onOpenChange={setOpen}>
      <Command.Input
        placeholder="Search stocks, actions, or pages..."
        aria-label="Command palette search"
      />
      <Command.List>
        <Command.Empty>No results found.</Command.Empty>

        <Command.Group heading="Quick Actions">
          <Command.Item onSelect={() => router.push("/")}>
            <Home className="mr-2 h-4 w-4" />
            Go to Dashboard
            <kbd className="ml-auto">G H</kbd>
          </Command.Item>
          <Command.Item onSelect={() => setTheme(theme === "dark" ? "light" : "dark")}>
            <Moon className="mr-2 h-4 w-4" />
            Toggle Theme
          </Command.Item>
        </Command.Group>

        <Command.Group heading="Stocks">
          {recentStocks.map(stock => (
            <Command.Item
              key={stock.symbol}
              onSelect={() => router.push(`/stocks/${stock.symbol}`)}
            >
              <TrendingUp className="mr-2 h-4 w-4" />
              {stock.symbol} - {stock.name}
            </Command.Item>
          ))}
        </Command.Group>

        <Command.Group heading="Pages">
          <Command.Item onSelect={() => router.push("/analytics/volume-spikes")}>
            Volume Spikes
          </Command.Item>
          <Command.Item onSelect={() => router.push("/analytics/financial-statements")}>
            Financial Statements
          </Command.Item>
        </Command.Group>
      </Command.List>
    </Command.Dialog>
  )
}
```

#### 3.3 Keyboard Shortcuts Dialog

```tsx
// Show with Shift+? (?)
<Dialog open={showShortcuts} onOpenChange={setShowShortcuts}>
  <DialogContent className="max-w-2xl">
    <DialogHeader>
      <DialogTitle>Keyboard Shortcuts</DialogTitle>
    </DialogHeader>
    <div className="grid grid-cols-2 gap-6">
      <div>
        <h4 className="font-semibold mb-2">Navigation</h4>
        <ShortcutList shortcuts={navigationShortcuts} />
      </div>
      <div>
        <h4 className="font-semibold mb-2">Actions</h4>
        <ShortcutList shortcuts={actionShortcuts} />
      </div>
    </div>
  </DialogContent>
</Dialog>

function ShortcutList({ shortcuts }) {
  return (
    <ul className="space-y-2">
      {shortcuts.map(s => (
        <li key={s.key} className="flex justify-between text-sm">
          <span className="text-muted-foreground">{s.description}</span>
          <kbd className="px-2 py-1 bg-muted rounded text-xs font-mono">
            {s.key}
          </kbd>
        </li>
      ))}
    </ul>
  )
}
```

---

### 4. Real-time Update Patterns

**Rationale:** Stock data cần real-time updates. Visual cues help users perceive changes quickly.

#### 4.1 Update Strategy

```tsx
// Three levels of real-time updates
type UpdateStrategy = "polling" | "websocket" | "hybrid"

const updateConfig = {
  // Critical data: WebSocket
  marketIndices: { strategy: "websocket", fallbackInterval: 5000 },
  priceBoard: { strategy: "websocket", fallbackInterval: 3000 },

  // Important but less critical: Short polling
  volumeSpikes: { strategy: "polling", interval: 30000 },
  sectorPerformance: { strategy: "polling", interval: 60000 },

  // Static data: Long polling or manual refresh
  financialStatements: { strategy: "polling", interval: 300000 },
  companyInfo: { strategy: "manual" },
}
```

#### 4.2 Visual Change Indicators

```tsx
// Flash animation for value changes
const flashAnimation = {
  up: "animate-flash-green",
  down: "animate-flash-red",
  neutral: ""
}

// CSS
@keyframes flash-green {
  0% { background-color: hsl(var(--stock-up) / 0.3); }
  100% { background-color: transparent; }
}

@keyframes flash-red {
  0% { background-color: hsl(var(--stock-down) / 0.3); }
  100% { background-color: transparent; }
}

.animate-flash-green {
  animation: flash-green 1s ease-out;
}

.animate-flash-red {
  animation: flash-red 1s ease-out;
}

// Component usage
function PriceCell({ value, previousValue }: { value: number; previousValue: number }) {
  const direction = value > previousValue ? "up" : value < previousValue ? "down" : "neutral"
  const [flash, setFlash] = useState(false)

  useEffect(() => {
    if (value !== previousValue) {
      setFlash(true)
      const timer = setTimeout(() => setFlash(false), 1000)
      return () => clearTimeout(timer)
    }
  }, [value, previousValue])

  return (
    <span
      className={cn(
        "tabular-nums transition-colors",
        direction === "up" && "text-green-600 dark:text-green-400",
        direction === "down" && "text-red-600 dark:text-red-400",
        flash && flashAnimation[direction]
      )}
    >
      {formatPrice(value)}
    </span>
  )
}
```

#### 4.3 Stale Data Indicator

```tsx
// Show when data is stale
function DataFreshnessIndicator({ lastUpdated }: { lastUpdated: Date }) {
  const [isStale, setIsStale] = useState(false)

  useEffect(() => {
    const checkStale = () => {
      const staleThreshold = 60000 // 1 minute
      setIsStale(Date.now() - lastUpdated.getTime() > staleThreshold)
    }

    checkStale()
    const interval = setInterval(checkStale, 10000)
    return () => clearInterval(interval)
  }, [lastUpdated])

  return (
    <div className={cn(
      "flex items-center gap-1 text-xs",
      isStale ? "text-yellow-600" : "text-muted-foreground"
    )}>
      <div className={cn(
        "h-2 w-2 rounded-full",
        isStale ? "bg-yellow-500" : "bg-green-500 animate-pulse"
      )} />
      <span>
        {isStale
          ? `Data may be stale (${formatDistanceToNow(lastUpdated)} ago)`
          : "Live"
        }
      </span>
    </div>
  )
}
```

#### 4.4 Optimistic Updates

```tsx
// For user actions, update UI immediately
const addToWatchlistMutation = useMutation({
  mutationFn: addToWatchlist,
  onMutate: async (symbol) => {
    // Cancel outgoing refetches
    await queryClient.cancelQueries({ queryKey: ["watchlist"] })

    // Snapshot previous value
    const previous = queryClient.getQueryData(["watchlist"])

    // Optimistically update
    queryClient.setQueryData(["watchlist"], (old) => [...old, { symbol }])

    // Show optimistic toast
    toast.success(`Added ${symbol} to watchlist`)

    return { previous }
  },
  onError: (err, symbol, context) => {
    // Rollback on error
    queryClient.setQueryData(["watchlist"], context.previous)
    toast.error(`Failed to add ${symbol}`)
  },
  onSettled: () => {
    queryClient.invalidateQueries({ queryKey: ["watchlist"] })
  },
})
```

---

### 5. Dashboard Customization

**Rationale:** Different users need different widget arrangements. Saved views improve productivity.

#### 5.1 Widget System Architecture

```tsx
// Widget registry
interface WidgetConfig {
  id: string
  type: string
  title: string
  description: string
  defaultSize: { w: number; h: number }
  minSize: { w: number; h: number }
  component: React.ComponentType<WidgetProps>
}

const widgetRegistry: Record<string, WidgetConfig> = {
  "market-indices": {
    id: "market-indices",
    type: "market",
    title: "Market Indices",
    description: "VN-INDEX, VN30, HNX, UPCOM overview",
    defaultSize: { w: 4, h: 2 },
    minSize: { w: 2, h: 1 },
    component: MarketIndicesWidget,
  },
  "vn30-table": {
    id: "vn30-table",
    type: "market",
    title: "VN30 Overview",
    description: "Top 30 stocks by market cap",
    defaultSize: { w: 4, h: 4 },
    minSize: { w: 2, h: 2 },
    component: VN30TableWidget,
  },
  "sector-performance": {
    id: "sector-performance",
    type: "sector",
    title: "Sector Performance",
    description: "ICB Level 2 sector analysis",
    defaultSize: { w: 2, h: 3 },
    minSize: { w: 1, h: 2 },
    component: SectorPerformanceWidget,
  },
  // ... more widgets
}
```

#### 5.2 Grid Layout with react-grid-layout

```tsx
// components/dashboard/customizable-dashboard.tsx
import GridLayout, { WidthProvider } from "react-grid-layout"

const ResponsiveGridLayout = WidthProvider(GridLayout)

interface DashboardLayout {
  i: string      // widget id
  x: number      // grid x position
  y: number      // grid y position
  w: number      // width in grid units
  h: number      // height in grid units
}

function CustomizableDashboard() {
  const [layout, setLayout] = useState<DashboardLayout[]>(defaultLayout)
  const [isEditing, setIsEditing] = useState(false)

  const handleLayoutChange = (newLayout: DashboardLayout[]) => {
    setLayout(newLayout)
    // Persist to localStorage or backend
    saveLayout(newLayout)
  }

  return (
    <div>
      <div className="flex justify-end mb-4">
        <Button
          variant={isEditing ? "default" : "outline"}
          onClick={() => setIsEditing(!isEditing)}
        >
          {isEditing ? <Check className="mr-2 h-4 w-4" /> : <Edit className="mr-2 h-4 w-4" />}
          {isEditing ? "Done" : "Customize"}
        </Button>
      </div>

      <ResponsiveGridLayout
        className="layout"
        layout={layout}
        cols={4}
        rowHeight={100}
        onLayoutChange={handleLayoutChange}
        isDraggable={isEditing}
        isResizable={isEditing}
        draggableHandle=".widget-drag-handle"
      >
        {layout.map(item => {
          const widget = widgetRegistry[item.i]
          if (!widget) return null

          return (
            <div key={item.i} className="relative">
              {isEditing && (
                <div className="widget-drag-handle absolute top-0 left-0 right-0 h-8 bg-muted/50 cursor-move flex items-center px-2">
                  <GripVertical className="h-4 w-4 text-muted-foreground" />
                  <span className="text-xs ml-2">{widget.title}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="ml-auto h-6 w-6"
                    onClick={() => removeWidget(item.i)}
                  >
                    <X className="h-3 w-3" />
                  </Button>
                </div>
              )}
              <widget.component />
            </div>
          )
        })}
      </ResponsiveGridLayout>
    </div>
  )
}
```

#### 5.3 Saved Views

```tsx
// Saved view management
interface SavedView {
  id: string
  name: string
  layout: DashboardLayout[]
  filters: FilterState
  density: DensityMode
  isDefault: boolean
  createdAt: Date
}

function SavedViewsManager() {
  const { views, currentView, setCurrentView, saveView, deleteView } = useSavedViews()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline">
          <Layers className="mr-2 h-4 w-4" />
          {currentView?.name || "Default View"}
          <ChevronDown className="ml-2 h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuLabel>Saved Views</DropdownMenuLabel>
        <DropdownMenuSeparator />

        {views.map(view => (
          <DropdownMenuItem
            key={view.id}
            onClick={() => setCurrentView(view)}
          >
            {view.name}
            {view.isDefault && <Star className="ml-auto h-3 w-3 text-yellow-500" />}
          </DropdownMenuItem>
        ))}

        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => saveCurrentAsNew()}>
          <Plus className="mr-2 h-4 w-4" />
          Save Current as New View
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
```

#### 5.4 Add Widget Dialog

```tsx
function AddWidgetDialog({ onAdd }: { onAdd: (widgetId: string) => void }) {
  const [open, setOpen] = useState(false)
  const availableWidgets = Object.values(widgetRegistry)

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="border-dashed">
          <Plus className="mr-2 h-4 w-4" />
          Add Widget
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Add Widget</DialogTitle>
          <DialogDescription>
            Choose a widget to add to your dashboard
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-4 mt-4">
          {availableWidgets.map(widget => (
            <Card
              key={widget.id}
              className="cursor-pointer hover:border-primary transition-colors"
              onClick={() => {
                onAdd(widget.id)
                setOpen(false)
              }}
            >
              <CardHeader className="p-4">
                <CardTitle className="text-sm">{widget.title}</CardTitle>
                <CardDescription className="text-xs">
                  {widget.description}
                </CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
```

---

### 6. Onboarding & Contextual Help

**Rationale:** First-time users cần guidance. Pro users cần quick feature discovery.

#### 6.1 First-time User Onboarding

```tsx
// components/onboarding/onboarding-tour.tsx
import { driver } from "driver.js"

const onboardingSteps = [
  {
    element: "#market-indices",
    popover: {
      title: "Market Overview",
      description: "Real-time market indices. Click any card for detailed analysis.",
      side: "bottom"
    }
  },
  {
    element: "#vn30-table",
    popover: {
      title: "VN30 Stocks",
      description: "Top 30 stocks by market cap. Click any row for stock details.",
      side: "left"
    }
  },
  {
    element: "#command-palette-trigger",
    popover: {
      title: "Quick Actions",
      description: "Press ⌘K to open command palette. Search stocks, navigate, and more.",
      side: "bottom"
    }
  },
  {
    element: "#density-toggle",
    popover: {
      title: "Display Density",
      description: "Switch between Compact (pro), Comfortable, and Spacious views.",
      side: "bottom"
    }
  }
]

function OnboardingTour() {
  const { hasCompletedOnboarding, setHasCompletedOnboarding } = useOnboarding()

  useEffect(() => {
    if (!hasCompletedOnboarding) {
      const driverObj = driver({
        showProgress: true,
        steps: onboardingSteps,
        onDestroyStarted: () => {
          setHasCompletedOnboarding(true)
        }
      })

      // Start after initial render
      setTimeout(() => driverObj.drive(), 1000)
    }
  }, [hasCompletedOnboarding])

  return null
}
```

#### 6.2 Contextual Tooltips

```tsx
// Tooltip for complex features
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

function HelpTooltip({ content, learnMoreUrl }: { content: string; learnMoreUrl?: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button className="text-muted-foreground hover:text-foreground">
          <HelpCircle className="h-4 w-4" />
        </button>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        <p>{content}</p>
        {learnMoreUrl && (
          <a
            href={learnMoreUrl}
            className="text-primary text-xs mt-2 block"
            target="_blank"
          >
            Learn more →
          </a>
        )}
      </TooltipContent>
    </Tooltip>
  )
}

// Usage
<CardHeader className="flex flex-row items-center">
  <CardTitle>P/E Ratio</CardTitle>
  <HelpTooltip
    content="Price-to-Earnings ratio. Lower P/E may indicate undervaluation. Compare with industry average."
    learnMoreUrl="/docs/pe-ratio"
  />
</CardHeader>
```

#### 6.3 Feature Discovery Hints

```tsx
// Show hint for undiscovered features
function FeatureHint({
  featureKey,
  children,
  hint
}: {
  featureKey: string
  children: React.ReactNode
  hint: string
}) {
  const { discoveredFeatures, markAsDiscovered } = useFeatureDiscovery()
  const isDiscovered = discoveredFeatures.includes(featureKey)

  if (isDiscovered) return <>{children}</>

  return (
    <div className="relative">
      {children}
      <div
        className="absolute -top-1 -right-1 h-3 w-3 bg-primary rounded-full animate-pulse"
        title={hint}
        onClick={() => markAsDiscovered(featureKey)}
      />
    </div>
  )
}

// Usage
<FeatureHint featureKey="keyboard-shortcuts" hint="Press ? for keyboard shortcuts">
  <Button variant="ghost" size="icon">
    <Keyboard className="h-4 w-4" />
  </Button>
</FeatureHint>
```

#### 6.4 Empty State with Guidance

```tsx
// Enhanced empty state with CTA
function EmptyState({
  icon: Icon,
  title,
  description,
  action
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="rounded-full bg-muted p-4 mb-4">
        <Icon className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="font-semibold text-lg mb-2">{title}</h3>
      <p className="text-muted-foreground text-sm max-w-sm mb-4">
        {description}
      </p>
      {action && (
        <Button onClick={action.onClick}>
          {action.icon && <action.icon className="mr-2 h-4 w-4" />}
          {action.label}
        </Button>
      )}
    </div>
  )
}

// Usage
<EmptyState
  icon={Star}
  title="No stocks in watchlist"
  description="Add stocks to your watchlist to track them. Use the search bar or press ⌘K to find stocks."
  action={{
    label: "Search Stocks",
    icon: Search,
    onClick: () => openCommandPalette()
  }}
/>
```

---

## Implementation Considerations

### Priority Order

1. **Accessibility** (P0) - Legal compliance, user trust
2. **Data Density** (P1) - Core UX for pro users
3. **Keyboard Shortcuts** (P1) - Pro user productivity
4. **Real-time Updates** (P2) - Already have polling, enhance visuals
5. **Customization** (P2) - Complex, phased implementation
6. **Onboarding** (P3) - After core features stable

### Dependencies

| Section | Dependencies |
|---------|--------------|
| A11y | None, can start immediately |
| Data Density | CSS variables, context provider |
| Keyboard | cmdk library, shortcut registry |
| Real-time | WebSocket backend, TanStack Query |
| Customization | react-grid-layout, persistence layer |
| Onboarding | driver.js, feature discovery store |

### Risks

1. **A11y testing** - Need manual + automated testing, screen reader expertise
2. **Density modes** - All components must support, refactoring needed
3. **WebSocket** - Backend infrastructure changes required
4. **Customization** - Complex state management, performance concerns
5. **Onboarding** - May be intrusive if poorly timed

---

## Success Metrics

| Metric | Target |
|--------|--------|
| A11y Score (Lighthouse) | ≥ 95 |
| Keyboard-only navigation | 100% features accessible |
| Time to first insight | < 3 seconds |
| Feature discovery rate | > 70% within first week |
| Dashboard customization usage | > 30% users customize |

---

## Next Steps

1. Review và approve brainstorming report
2. Nếu approved → Create implementation plan cho từng section
3. Prioritize based on effort vs impact
4. Phased implementation over sprints

---

## Unresolved Questions

1. **WebSocket infrastructure**: Backend có sẵn sàng cho WebSocket chưa hay cần build mới?
2. **Persistence layer**: Saved views lưu ở localStorage hay backend (cần sync across devices)?
3. **A11y audit**: Có budget cho accessibility audit bởi chuyên gia không?
4. **Density default**: Confirm "compact" là default cho pro-first approach?
