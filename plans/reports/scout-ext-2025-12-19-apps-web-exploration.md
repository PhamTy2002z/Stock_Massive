# Apps/Web Directory Exploration Report

**Date:** 2025-12-19
**Scope:** D:\Stock_Massive\apps\web
**Type:** Codebase Scout Report

---

## 1. Project Structure

- src/app/ - Next.js App Router (layout.tsx, page.tsx, not-found.tsx, globals.css)
- src/components/dashboard/ - Business components (14 files)
- src/components/layout/ - Layout components (4 files)
- src/components/ui/ - ShadCN primitives (17 files)
- src/components/providers/ - Context providers (2 files)
- src/hooks/ - Custom React hooks (6 files)
- src/lib/ - Utilities and API client (2 files)

## 2. Tech Stack

- Next.js 14.2.18 (App Router)
- React 18.3.1 + TypeScript 5.3.0
- TailwindCSS 3.4.0 + tailwindcss-animate
- Radix UI + ShadCN components
- lucide-react icons, next-themesr toasts

## 3. State Management

Pattern: Local State + Custom Hooks (No Redux/Zustand)
- useState for component state
- Custom hooks for data fetching with loading/error
- URL state via useSearchParams
- Context only for sidebar

## 4. Design Patterns

- Barrel exports (index.ts)
- Compound components (Sidebar)
- Skeleton loading pattern
- CVA variants for components
- forwardRef pattern
- Debounced search (300ms)
- URL state sync

