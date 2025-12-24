# Phase 2: Configure Backend Connection

## Context
- **Parent:** [plan.md](./plan.md)
- **Depends on:** [Phase 1](./phase-01-setup-supabase-project.md)
- **Research:** [researcher-01-supabase-sqlalchemy-config.md](./research/researcher-01-supabase-sqlalchemy-config.md)

## Overview

| Property | Value |
|----------|-------|
| Priority | P1 |
| Status | In Review |
| Effort | 30 min |

Update FastAPI backend to connect to Supabase PostgreSQL.

## Key Insights

- Use **Session mode (port 5432)** for FastAPI backend - supports prepared statements
- Add `pool_pre_ping=True` for connection health checks
- SSL required: add `?sslmode=require` to connection string
- Alembic needs separate direct connection URL

## Requirements

### Functional
- Update database.py to support Supabase connection
- Update config.py to handle new env vars
- Update Alembic env.py for migrations

### Non-Functional
- Maintain backward compatibility with Docker DB (for local dev)
- Use SSL for all connections

## Architecture

```
FastAPI Backend
    │
    ├── Runtime (DATABASE_URL)
    │   └── Session Pooler (port 5432)
    │       └── SQLAlchemy async engine
    │
    └── Migrations (DATABASE_URL_DIRECT)
        └── Direct Connection
            └── Alembic sync engine
```

## Related Code Files

**Files to modify:**
- `apps/api/src/core/config.py` - add DATABASE_URL_DIRECT
- `apps/api/src/core/database.py` - add SSL, pool_pre_ping
- `apps/api/alembic/env.py` - use direct connection

**Files to reference:**
- `apps/api/alembic.ini` - current config

## Implementation Steps

### Step 1: Update config.py

```python
# apps/api/src/core/config.py

class Settings(BaseSettings):
    # ... existing fields ...

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/stockmassive"
    database_url_direct: str = ""  # For migrations (direct connection)
```

### Step 2: Update database.py

```python
# apps/api/src/core/database.py

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

settings = get_settings()

# Convert to asyncpg driver
DATABASE_URL = settings.database_url.replace(
    "postgresql://", "postgresql+asyncpg://"
)

# Add SSL if connecting to Supabase (contains "supabase")
connect_args = {}
if "supabase" in DATABASE_URL.lower():
    connect_args["ssl"] = "require"

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # ADD: Health check before use
    pool_timeout=30,
    pool_recycle=3600,
    connect_args=connect_args,  # ADD: SSL for Supabase
)
```

### Step 3: Update Alembic env.py

```python
# apps/api/alembic/env.py

import os
from sqlalchemy import create_engine

def get_url():
    """Get migration URL - prefer direct connection for Supabase."""
    direct_url = os.getenv("DATABASE_URL_DIRECT")
    if direct_url:
        return direct_url
    return config.get_main_option("sqlalchemy.url")

def run_migrations_online():
    connectable = create_engine(get_url())  # Use sync engine
    # ... rest unchanged ...
```

### Step 4: Update .env.example

```bash
# .env.example - ADD new variable
DATABASE_URL_DIRECT=  # Direct connection for migrations (optional, for Supabase)
```

## Todo List

- [x] Add `database_url_direct` to config.py Settings
- [x] Update database.py with SSL and pool_pre_ping
- [~] Update alembic/env.py to use direct URL (**PARTIAL: missing SSL connect_args**)
- [ ] Update .env.example with new variable (file not found)
- [ ] Test connection in local environment

### Code Review Findings (2024-12-24)

**HIGH:** `alembic/env.py` - `async_engine_from_config` lacks SSL `connect_args`. Migrations may fail.

See: `plans/reports/code-reviewer-251224-2102-phase2-supabase-backend.md`

## Success Criteria

- [ ] App connects to Supabase via DATABASE_URL
- [ ] Alembic uses DATABASE_URL_DIRECT for migrations
- [ ] SSL connection established (no plaintext)
- [ ] Connection pooling works correctly

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Breaking local Docker DB | Env var fallback to localhost default |
| SSL connection issues | Add explicit ssl=require in connect_args |

## Security Considerations

- SSL required for all Supabase connections
- No credentials in code, only env vars
- Direct connection URL only used for migrations

## Next Steps

→ [Phase 3: Migrate Data](./phase-03-migrate-data.md)
