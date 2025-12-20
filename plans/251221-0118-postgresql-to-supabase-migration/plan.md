---
title: "PostgreSQL to Supabase Migration"
description: "Migrate local PostgreSQL database to Supabase cloud PostgreSQL"
status: pending
priority: P1
effort: 3h
branch: main
tags: [database, migration, supabase, postgresql]
created: 2025-12-21
---

# PostgreSQL to Supabase Migration Plan

## Overview
Migrate from local Docker PostgreSQL to Supabase cloud PostgreSQL while maintaining existing SQLAlchemy + Alembic architecture.

## Context
- **Current**: PostgreSQL 16 (Docker), SQLAlchemy 2.0 async, asyncpg, Alembic
- **Target**: Supabase PostgreSQL with connection pooling
- **Models**: 2 tables (stock_intraday_bars, users)
- **Strategy**: Keep Alembic, use Supabase pooler, minimal code changes

## Research Reports
- [Supabase Migration Best Practices](./research/researcher-01-supabase-migration.md)
- [Current DB Setup Analysis](./research/researcher-02-current-db-setup.md)

## Implementation Phases

### Phase 1: Supabase Setup
**File**: [phase-01-supabase-setup.md](./phase-01-supabase-setup.md)
**Status**: done
**Completed**: 2025-12-21 01:33
**Effort**: 30min
- Create Supabase project
- Get connection credentials (direct + pooler)
- Configure SSL certificates
- Document connection strings

### Phase 2: Schema Migration
**File**: [phase-02-schema-migration.md](./phase-02-schema-migration.md)
**Status**: pending
**Effort**: 45min
- Apply Alembic migrations to Supabase
- Verify schema integrity
- Test indexes and constraints
- Validate PostgreSQL-specific features (UUID, functions)

### Phase 3: Connection Update
**File**: [phase-03-connection-update.md](./phase-03-connection-update.md)
**Status**: pending
**Effort**: 45min
- Update DATABASE_URL format
- Configure SSL/TLS
- Adjust pool settings for cloud
- Update Alembic env.py for dual-port strategy
- Update .env.example

### Phase 4: Data Migration
**File**: [phase-04-data-migration.md](./phase-04-data-migration.md)
**Status**: pending
**Effort**: 30min
- Export existing data (if any)
- Import to Supabase
- Verify data integrity
- Handle edge cases

### Phase 5: Testing & Validation
**File**: [phase-05-testing-validation.md](./phase-05-testing-validation.md)
**Status**: pending
**Effort**: 30min
- Test all API endpoints
- Verify CRUD operations
- Test connection pooling
- Load testing
- Rollback plan validation

## Key Decisions
1. **Keep Alembic** - Familiar, works with Supabase, no migration tool change
2. **Dual-port strategy** - Transaction mode (6543) for app, Session mode (5432) for migrations
3. **SSL required** - Supabase enforces SSL connections
4. **Pool adjustment** - Reduce pool_size for cloud (3 base, 7 overflow)
5. **asyncpg compatible** - No driver changes needed

## Success Criteria
- All migrations apply successfully to Supabase
- All API endpoints functional
- Connection pooling stable
- No data loss
- Performance acceptable (< 100ms latency)

## Rollback Plan
- Keep local PostgreSQL Docker setup
- Switch DATABASE_URL back to local
- Documented in Phase 5

## Validation Summary

**Validated:** 2025-12-21
**Questions asked:** 6

### Confirmed Decisions
- **Migration Tool**: Keep Alembic (familiar workflow, works with Supabase)
- **Supabase Tier**: Free tier for development (60 direct, 200 pooler connections)
- **Local PostgreSQL**: Keep for 1 week as rollback option
- **Row Level Security**: Skip RLS (API handles auth via FastAPI)
- **Data Migration**: Fresh start (no existing data to migrate)
- **Pool Settings**: Conservative 3/7 (optimized for cloud/free tier)

### Action Items
- [x] Plan validated - no changes needed
- [ ] Phase 4 can be simplified (skip data export/import steps)

## Next Steps
1. Start with Phase 1: Create Supabase project
2. Proceed sequentially through phases
3. Skip data migration in Phase 4 (fresh start confirmed)
4. Test thoroughly at each phase
5. Keep local PostgreSQL for 1 week post-migration
