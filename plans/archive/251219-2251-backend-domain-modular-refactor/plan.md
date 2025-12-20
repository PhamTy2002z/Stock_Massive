---
title: "Backend Domain Modular Refactor"
description: "Split monolithic stocks module into domain-based submodules"
status: in_progress
priority: P2
effort: 6h
branch: main
tags: [refactor, backend, architecture]
created: 2024-12-19
updated: 2025-12-19
---

# Backend Domain Modular Refactor

## Overview

Refactor monolithic `stocks/` module (2,418 lines) into domain-based architecture for maintainability and scalability.

**Current State:**
- `service.py`: 1,507 lines (TOO LARGE)
- `schemas.py`: 426 lines
- `router.py`: 485 lines

**Target:** 4 domain modules (price, company, financial, market) + shared utilities, each ~200-300 lines.

## Research Reports

1. [Service Domain Analysis](research/researcher-01-service-domain-analysis.md)
2. [Schema-Router Mapping](research/researcher-02-schemas-router-mapping.md)

## Implementation Phases

| Phase | Description | Status | Effort |
|-------|-------------|--------|--------|
| [Phase 1](phase-01-shared-utilities.md) | Extract shared utilities | done | 1h |
| [Phase 2](phase-02-schemas-split.md) | Split schemas by domain | done | 1h |
| [Phase 3](phase-03-services-split.md) | Split services by domain | done | 2h |
| [Phase 4](phase-04-routers-split.md) | Split routers by domain | done | 1h |
| [Phase 5](phase-05-integration-testing.md) | Integration testing & verification | pending | 1h |

## Target Architecture

```
stocks/
├── __init__.py              # Re-exports for backward compat
├── router.py                # Main router aggregator
├── models.py                # Keep as-is
├── jobs.py                  # Keep as-is
├── intraday_collector.py    # Keep as-is
│
├── shared/                  # Shared utilities
│   ├── __init__.py
│   ├── exceptions.py        # StockServiceError
│   ├── validators.py        # validate_symbol, SYMBOL_PATTERN
│   └── converters.py        # _df_to_* methods
│
├── price/                   # Price domain (~200 lines)
│   ├── __init__.py
│   ├── router.py
│   ├── service.py
│   └── schemas.py
│
├── company/                 # Company domain (~230 lines)
│   ├── __init__.py
│   ├── router.py
│   ├── service.py
│   └── schemas.py
│
├── financial/               # Financial domain (~300 lines)
│   ├── __init__.py
│   ├── router.py
│   ├── service.py
│   └── schemas.py
│
└── market/                  # Market domain (~140 lines)
    ├── __init__.py
    ├── router.py
    ├── service.py
    └── schemas.py
```

## Success Criteria

- All 27 API endpoints remain functional
- All existing tests pass (8 test files)
- Backward compatibility maintained via re-exports
- Each domain service < 350 lines
- No breaking changes to external consumers

## Risk Mitigation

- Phase-by-phase approach with testing after each phase
- Maintain original files until Phase 5 verification
- Re-export strategy ensures backward compatibility
- Comprehensive test coverage validation

---

## Validation Summary

**Validated:** 2024-12-19
**Questions asked:** 5

### Confirmed Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Service access pattern | Facade pattern | Router imports unchanged, backward compatible |
| vnstock instances | Separate per domain | Simpler, isolated, no coupling |
| Converters location | Centralized in shared/ | DRY, single source of truth |
| Execution strategy | Two batches | Phase 1-2 first, verify, then Phase 3-5 |
| Rollback strategy | Keep backup files | service_old.py, router_old.py until Phase 5 |

### Execution Plan

**Batch 1:** Phase 1 (shared utilities) + Phase 2 (schemas split)
- Low risk extractions
- Verify all tests pass before proceeding

**Batch 2:** Phase 3 (services) + Phase 4 (routers) + Phase 5 (testing)
- Higher complexity changes
- Full integration testing at end

### Action Items

- [x] Plan validated - no changes needed to phase files
- [ ] Ready for implementation
