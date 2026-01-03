# Scout Report: Packages Directory Structure
**Date**: 2026-01-03 14:54  
**Scope**: Comprehensive analysis of `/packages/` directory  
**Status**: Complete

---

## Executive Summary

The `packages/` directory is a **monorepo shared packages workspace** with **2 placeholder packages** currently defined but **not yet implemented**. The directory structure is prepared for future shared code but contains only `.gitkeep` files.

**Current State**: Placeholder directories ready for implementation  
**Shared Packages**: 2 (config, types)  
**Active Implementations**: 0  
**Package Consumption**: None (no @stock-massive/* imports found in apps)

---

## Directory Structure

```
packages/
├── config/              # Placeholder for shared configuration
│   └── .gitkeep
└── types/               # Placeholder for shared TypeScript types
    └── .gitkeep
```

---

## Packages Inventory

### 1. `packages/config/`
**Status**: Placeholder (not implemented)  
**Purpose**: Intended for shared configuration files  
**Current Contents**: `.gitkeep` only  
**Expected Use Cases**:
- ESLint configurations
- TypeScript configurations (tsconfig.json)
- Build tool configurations
- Environment variable schemas
- Shared constants

**Files**: None (ready for implementation)

---

### 2. `packages/types/`
**Status**: Placeholder (not implemented)  
**Purpose**: Intended for shared TypeScript type definitions  
**Current Contents**: `.gitkeep` only  
**Expected Use Cases**:
- Common API response types
- Domain models (Stock, Sector, Financial data)
- Shared interfaces
- Type utilities
- Enums for market data

**Files**: None (ready for implementation)

---

## Current App Structure (No Shared Package Consumption)

### Frontend (`apps/web/`)
- **Package Name**: `stock-massive-web`
- **Type**: Next.js 15.5.9 application
- **Shared Package Imports**: None detected
- **Dependencies**: Direct external packages only (Radix UI, TanStack Query, Recharts, etc.)

### Backend (`apps/api/`)
- **Type**: FastAPI Python application
- **Shared Package Imports**: N/A (Python-based, not using npm packages)

---

## Workspace Configuration

**Root `package.json`**:
```json
{
  "name": "stock-massive",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "docker compose up --build",
    "dev:detach": "docker compose up --build -d",
    "stop": "docker compose down",
    "stop:clean": "docker compose down -v",
    "logs": "docker compose logs -f",
    "logs:api": "docker compose logs -f api",
    "logs:web": "docker compose logs -f web",
    "db:shell": "docker compose exec db psql -U postgres -d stockmassive",
    "api:shell": "docker compose exec api bash",
    "web:shell": "docker compose exec web sh"
  }
}
```

**Workspace Type**: pnpm monorepo (uses `pnpm-lock.yaml`)

---

## Recommendations for Implementation

### Phase 1: Types Package
**Priority**: High  
**Suggested Structure**:
```
packages/types/
├── package.json
├── tsconfig.json
├── src/
│   ├── index.ts
│   ├── api/
│   │   ├── responses.ts
│   │   ├── requests.ts
│   │   └── errors.ts
│   ├── domain/
│   │   ├── stock.ts
│   │   ├── sector.ts
│   │   ├── financial.ts
│   │   └── market.ts
│   └── utils/
│       └── types.ts
└── README.md
```

**Initial Exports**:
- Stock data types (OHLCV, Intraday)
- Sector performance types
- Financial statement types
- Market indices types
- API response wrappers

### Phase 2: Config Package
**Priority**: Medium  
**Suggested Structure**:
```
packages/config/
├── package.json
├── eslint.config.js
├── tsconfig.base.json
├── tsconfig.react.json
├── jest.config.js
├── src/
│   ├── index.ts
│   ├── constants.ts
│   ├── env.ts
│   └── validation.ts
└── README.md
```

**Initial Exports**:
- ESLint configuration
- Base TypeScript configuration
- Shared constants (API endpoints, cache TTLs, etc.)
- Environment variable validation schema

---

## Current Consumption Pattern

**Apps**: 2 (web, api)  
**Shared Package Usage**: None  
**Dependency Flow**: Apps → External packages only

```
apps/web/
  ├── @radix-ui/* (UI primitives)
  ├── @tanstack/react-query (Data fetching)
  ├── recharts (Charting)
  ├── next (Framework)
  └── [other external deps]

apps/api/
  ├── fastapi (Framework)
  ├── vnstock (Data source)
  ├── sqlalchemy (ORM)
  └── [other external deps]
```

---

## File Inventory

| Path | Type | Status | Purpose |
|------|------|--------|---------|
| `/packages/config/.gitkeep` | Placeholder | Ready | Config package marker |
| `/packages/types/.gitkeep` | Placeholder | Ready | Types package marker |

**Total Files**: 2 (both placeholders)  
**Total Directories**: 2 (both empty)

---

## Unresolved Questions

1. **When should shared packages be implemented?** - Currently no shared code exists between apps; consider implementing when code duplication appears.
2. **Should API types be generated from FastAPI schemas?** - Consider using `pydantic-to-typescript` or similar tools for type generation.
3. **Will Python backend use shared types?** - Current setup is JavaScript-only; Python backend uses separate type system.
4. **Package versioning strategy?** - Define semver approach for internal packages.
5. **Publishing strategy?** - Will packages be published to npm or used only internally?

---

## Summary

The `packages/` directory is **structurally prepared** for a monorepo setup but **not yet populated**. Both placeholder packages (`config` and `types`) are ready for implementation when shared code patterns emerge. Currently, the project operates with **zero shared package consumption**, with each app managing its own dependencies independently.

**Next Steps**:
1. Implement `packages/types/` with common API and domain types
2. Implement `packages/config/` with shared configurations
3. Update `apps/web/package.json` to import from `@stock-massive/types` and `@stock-massive/config`
4. Add workspace scripts for building and testing shared packages
