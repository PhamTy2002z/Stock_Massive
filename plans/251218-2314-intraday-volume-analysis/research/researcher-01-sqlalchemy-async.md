# SQLAlchemy 2.0 Async Patterns for FastAPI

## 1. Async Engine & Session Setup with asyncpg

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Create async engine with asyncpg driver
engine = create_async_engine(
    "postgresql+asyncpg://user:pass@hostname/dbname",
    echo=True,  # SQL logging (disable in prod)
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
)

# Create session factory (expire_on_commit=False recommended for async)
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
```

**Key points:**
- Use `create_async_engine` (not `create_engine`)
- `AsyncAdaptedQueuePool` is auto-used (not `QueuePool`)
- `expire_on_commit=False` prevents detached instance errors after commit

Source: [SQLAlchemy Async Extension](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)

---

## 2. FastAPI Dependency Injection

```python
from typing import AsyncGenerator
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Usage in route
@app.get("/items/{id}")
async def get_item(id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item).where(Item.id == id))
    return result.scalar_one_or_none()
```

**Alternative with lifespan (app-level):**
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: engine already created
    yield
    # Shutdown: dispose engine
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
```

Source: [FastAPI Dependencies with Yield](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/)

---

## 3. Upsert Patterns (INSERT ON CONFLICT)

### PostgreSQL Upsert with DO UPDATE
```python
from sqlalchemy.dialects.postgresql import insert

async def upsert_stock_data(db: AsyncSession, records: list[dict]):
    stmt = insert(StockPrice).values(records)

    stmt = stmt.on_conflict_do_update(
        index_elements=["symbol", "timestamp"],  # Conflict target
        set_={
            "price": stmt.excluded.price,
            "volume": stmt.excluded.volume,
            "updated_at": func.now(),
        }
    )
    await db.execute(stmt)
    await db.commit()
```

### Upsert with DO NOTHING (skip duplicates)
```python
from sqlalchemy.dialects.postgresql import insert

stmt = insert(StockPrice).values(records)
stmt = stmt.on_conflict_do_nothing(index_elements=["symbol", "timestamp"])
await db.execute(stmt)
```

### Bulk Upsert with Returning
```python
stmt = insert(StockPrice).values(records)
stmt = stmt.on_conflict_do_update(
    index_elements=["symbol", "timestamp"],
    set_={"price": stmt.excluded.price}
).returning(StockPrice.id)

result = await db.execute(stmt)
inserted_ids = result.scalars().all()
```

Source: [PostgreSQL INSERT ON CONFLICT](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#insert-on-conflict-upsert)

---

## 4. Connection Pooling Best Practices

### Pool Configuration
```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,        # Persistent connections
    max_overflow=10,    # Extra connections when pool exhausted
    pool_timeout=30,    # Wait time before timeout error
    pool_recycle=1800,  # Recycle connections after 30 min
    pool_pre_ping=True, # Verify connection health before use
)
```

### Recommended Settings by Use Case
| Setting | Dev | Production | High Load |
|---------|-----|------------|-----------|
| pool_size | 5 | 10-20 | 20-50 |
| max_overflow | 5 | 10 | 20 |
| pool_timeout | 30 | 30 | 10 |
| pool_pre_ping | False | True | True |

### Cleanup on Shutdown
```python
# Always dispose engine on app shutdown
await engine.dispose()
```

**Important notes:**
- `AsyncAdaptedQueuePool` used automatically for async engines
- Never rely on garbage collection for connection cleanup in async
- Always explicitly close sessions and dispose engines

Source: [Connection Pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html)

---

## Quick Reference

| Operation | Sync | Async |
|-----------|------|-------|
| Create engine | `create_engine()` | `create_async_engine()` |
| Session factory | `sessionmaker()` | `async_sessionmaker()` |
| Execute | `session.execute()` | `await session.execute()` |
| Commit | `session.commit()` | `await session.commit()` |
| Close | `session.close()` | `await session.close()` |

---

## Unresolved Questions
- None identified for basic async patterns
