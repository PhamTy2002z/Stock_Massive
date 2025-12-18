# Scout Report: Next.js Frontend Analysis

**Date:** 2025-12-18  
**Path:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/web`  
**Framework:** Next.js 14.2.18 (App Router)

---

## 1. Project Structure Overview

```
apps/web/
├── src/
│   ├── app/                    # App Router pages
│   ├── components/             # React components
│   │   ├── layout/            # Layout components
│   │   ├── ui/                # ShadCN UI primitives
│   │   ├── charts/            # Chart components (empty)
│   │   ├── shared/            # Shared components (empty)
│   │   └── tables/columns/    # Table columns (empty)
│   ├── hooks/                 # Custom React hooks
│   ├── lib/                   # Utility functions
│   ├── config/                # Config files (empty)
│   ├── services/              # API services (empty)
│   └── types/                 # TypeScript types (empty)
├── public/images/             # Static assets
└── [config files]
```

---

## 2. Components

### Layout Components (3 files)
| File | Description |
|------|-------------|
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/layout/app-sidebar.tsx` | Main sidebar with navigation, watchlists, user menu |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/layout/dashboard-header.tsx` | Header with search, notifications, share button |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/layout/dashboard-layout.tsx` | Wrapper combining SidebarProvider + AppSidebar + Header |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/layout/index.ts` | Barrel export file |

### UI Components (ShadCN - 10 files)
| File | Description |
|------|-------------|
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/ui/avatar.tsx` | Avatar with image/fallback |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/ui/button.tsx` | Button variants |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/ui/collapsible.tsx` | Collapsible container |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/ui/dropdown-menu.tsx` | Dropdown menu |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/ui/input.tsx` | Input field |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/ui/separator.tsx` | Visual separator |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/ui/sheet.tsx` | Slide-out panel |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/ui/sidebar.tsx` | Complex sidebar system (790 LOC) |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/ui/skeleton.tsx` | Loading skeleton |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/components/ui/tooltip.tsx` | Tooltip component |

---

## 3. App Router Pages

### Route Groups
| Route Group | Purpose | Status |
|-------------|---------|--------|
| `(auth)` | Authentication pages | Scaffolded (empty) |
| `(dashboard)` | Dashboard feature pages | Scaffolded (empty) |

### Pages
| File | Route | Description |
|------|-------|-------------|
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/layout.tsx` | Root | Root layout with Inter font, metadata |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/page.tsx` | `/` | Home page with DashboardLayout wrapper |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/not-found.tsx` | 404 | Custom 404 page |
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/app/globals.css` | - | Global styles + CSS variables |

### Scaffolded Routes (empty .gitkeep)
- `/src/app/(auth)/login/`
- `/src/app/(auth)/register/`
- `/src/app/(dashboard)/charts/_components/`
- `/src/app/(dashboard)/portfolio/_components/`
- `/src/app/(dashboard)/watchlist/_components/`
- `/src/app/api/`

---

## 4. Hooks & Utilities

### Hooks (1 file)
| File | Export | Description |
|------|--------|-------------|
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/hooks/use-mobile.tsx` | `useIsMobile()` | Detects mobile viewport (<768px) |

### Utilities (1 file)
| File | Export | Description |
|------|--------|-------------|
| `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/src/lib/utils.ts` | `cn()` | Tailwind class merger (clsx + tailwind-merge) |

---

## 5. Dependencies

### Production Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| `next` | 14.2.18 | React framework |
| `react` | ^18.3.1 | UI library |
| `react-dom` | ^18.3.1 | React DOM |
| `@radix-ui/react-avatar` | ^1.1.11 | Avatar primitive |
| `@radix-ui/react-collapsible` | ^1.1.12 | Collapsible primitive |
| `@radix-ui/react-dialog` | ^1.1.15 | Dialog/Sheet primitive |
| `@radix-ui/react-dropdown-menu` | ^2.1.16 | Dropdown primitive |
| `@radix-ui/react-separator` | ^1.1.8 | Separator primitive |
| `@radix-ui/react-slot` | ^1.2.4 | Slot primitive |
| `@radix-ui/react-tooltip` | ^1.2.8 | Tooltip primitive |
| `class-variance-authority` | ^0.7.1 | Component variants |
| `clsx` | ^2.1.1 | Class concatenation |
| `lucide-react` | ^0.561.0 | Icon library |
| `tailwind-merge` | ^3.4.0 | Tailwind class deduplication |
| `tailwindcss-animate` | ^1.0.7 | Animation utilities |

### Dev Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| `typescript` | ^5.3.0 | Type checking |
| `tailwindcss` | ^3.4.0 | CSS framework |
| `postcss` | ^8.4.32 | CSS processing |
| `autoprefixer` | ^10.4.16 | CSS vendor prefixes |
| `@types/node` | ^20.10.0 | Node types |
| `@types/react` | ^18.3.0 | React types |
| `@types/react-dom` | ^18.3.0 | React DOM types |

---

## 6. Configuration Files

### next.config.js
- Empty config (default settings)

### tailwind.config.js
- Dark mode: class-based
- Content: `./src/**/*.{js,ts,jsx,tsx,mdx}`
- Extended colors: background, foreground, card, popover, primary, secondary, muted, accent, destructive, border, input, ring, chart (1-5), sidebar variants
- Custom timing function: `sidebar` (cubic-bezier)
- Plugin: `tailwindcss-animate`

### tsconfig.json
- Strict mode enabled
- Module resolution: bundler
- Path alias: `@/*` -> `./src/*`
- Incremental builds enabled

### components.json (ShadCN)
- Style: new-york
- RSC: true
- Base color: neutral
- CSS variables: enabled
- Icon library: lucide

---

## 7. Sidebar Navigation Structure

Defined in `app-sidebar.tsx`:

```
Dashboard (/)
Markets
  ├── Overview
  ├── Stocks
  ├── Indices
  └── Sectors
Charts
  ├── TradingView
  ├── Technical Analysis
  └── Comparisons
Screener
  ├── Stock Screener
  ├── Saved Screens
  ├── Top Gainers
  └── Top Losers
Portfolio
  ├── Holdings
  ├── Performance
  └── Transactions
Analytics
  ├── Reports
  ├── Insights
  └── Alerts

Watchlists:
  - Tech Giants
  - Dividend Stocks
  - Growth Picks
```

---

## 8. CSS Theme Variables

Light/Dark mode support with HSL color variables:
- Primary: Blue (`217 91% 60%`)
- Chart colors: Green, Red, Blue, Yellow, Purple
- Sidebar-specific colors defined

---

## Summary

**Maturity:** Early stage - scaffolded structure with dashboard layout implemented  
**UI Framework:** ShadCN (new-york style) + Tailwind CSS  
**Key Feature:** Collapsible sidebar with navigation hierarchy  
**Missing:** Auth pages, dashboard feature pages, API routes, charts, tables

---

## Unresolved Questions

1. No state management library detected - will Redux/Zustand be added?
2. No data fetching library (TanStack Query, SWR) - how will API calls be handled?
3. No form library detected - will react-hook-form be used for auth?
