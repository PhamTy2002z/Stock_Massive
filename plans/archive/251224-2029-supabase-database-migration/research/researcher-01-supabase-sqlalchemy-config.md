# Supabase PostgreSQL + SQLAlchemy Configuration

## 1. Connection Configuration

### Supabase Connection Modes

| Mode | Port | Use Case | Prepared Statements |
|------|------|----------|---------------------|
| **Direct** | 5432 | Persistent servers, migrations | Full support |
| **Session Pooler** | 5432 | Long-running apps | Full support |
| **Transaction Pooler** | 6543 | Serverless/Edge functions | NOT supported |

### Connection String Format
```
# Direct connection (recommended for backend services)
postgresql+asyncpg://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres

# Transaction mode (serverless only)
postgresql+asyncpg://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
```

**Recommendation**: Use Direct/Session mode (port 5432) for persistent backend services.

---

## 2. SQLAlchemy 2.0 + asyncpg Configuration

### For Direct/Session Mode (Port 5432)
```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Verify connections before use
)

async_session = async_sessionmaker(engine, expire_on_commit=False)
```

### For Transaction Mode (Port 6543) - Serverless Only
```python
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    poolclass=NullPool,  # REQUIRED: Disable SQLAlchemy pooling
    connect_args={
        "statement_cache_size": 0,  # REQUIRED: Disable prepared statements
    }
)
```

### Alternative: Disable Cache via URL
```python
engine = create_async_engine(
    "postgresql+asyncpg://...?prepared_statement_cache_size=0"
)
```

---

## 3. Alembic Migrations

### Critical: Use Direct Connection for Migrations
Migrations require DDL operations - use direct connection, NOT pooler.

### env.py Configuration
```python
import os
from sqlalchemy import create_engine

def get_url():
    # Use separate migration URL (direct connection)
    return os.getenv("DATABASE_URL_DIRECT", config.get_main_option("sqlalchemy.url"))

def run_migrations_offline():
    url = get_url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = create_engine(get_url())  # Sync engine for migrations
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
```

### Production Migration Commands
```bash
# Run migrations
alembic upgrade head

# Generate new migration
alembic revision --autogenerate -m "description"
```

---

## 4. Security Best Practices

### SSL Configuration
```python
# Option 1: sslmode in URL (simpler)
DATABASE_URL = "postgresql+asyncpg://...?sslmode=require"

# Option 2: Full SSL verification (more secure)
DATABASE_URL = "postgresql+asyncpg://...?sslmode=verify-full&sslrootcert=/path/to/supabase-ca.crt"
```

### Environment Variables (.env)
```bash
# Application runtime (Session mode)
DATABASE_URL=postgresql+asyncpg://postgres.[ref]:[pwd]@aws-0-[region].pooler.supabase.com:5432/postgres?sslmode=require

# Migrations only (Direct connection)
DATABASE_URL_DIRECT=postgresql://postgres:[pwd]@db.[ref].supabase.co:5432/postgres?sslmode=require
```

### Security Checklist
- [ ] Store credentials in env vars, never in code
- [ ] Use `sslmode=require` minimum (or `verify-full` with cert)
- [ ] Separate migration URL from runtime URL
- [ ] Rotate database password periodically
- [ ] Use Row Level Security (RLS) for additional protection

---

## Quick Reference

| Scenario | Port | Pool Class | statement_cache_size |
|----------|------|------------|---------------------|
| Backend API | 5432 | Default (QueuePool) | Default (100) |
| Serverless | 6543 | NullPool | 0 |
| Alembic | 5432 (direct) | N/A (sync) | N/A |

---

## Unresolved Questions
- None identified. Configuration patterns well-documented.
