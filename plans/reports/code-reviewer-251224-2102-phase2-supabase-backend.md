# Code Review: Phase 2 - Configure Backend Connection (Supabase)

**Date:** 2024-12-24
**Reviewer:** code-reviewer subagent
**Scope:** SSL + connection config for Supabase migration

---

## Summary

| Metric | Value |
|--------|-------|
| Files reviewed | 3 |
| Lines changed | ~35 |
| Critical issues | 0 |
| High priority | 1 |
| Medium priority | 1 |
| Low priority | 1 |

**Overall:** Implementation is functional and follows plan. One SSL gap in Alembic migrations needs attention.

---

## Critical Issues

None.

---

## High Priority

### H1: Alembic migrations missing SSL connect_args

**File:** `apps/api/alembic/env.py`
**Line:** 73-77

```python
connectable = async_engine_from_config(
    config.get_section(config.config_ini_section, {}),
    prefix="sqlalchemy.",
    poolclass=pool.NullPool,
)
```

**Problem:** `async_engine_from_config` doesn't receive SSL `connect_args`. Migrations to Supabase may fail with SSL handshake error.

**Fix required:**
```python
# Add SSL detection
connect_args = {}
if settings.database_url_direct and "supabase" in settings.database_url_direct.lower():
    connect_args["ssl"] = "require"
elif "supabase" in settings.database_url.lower():
    connect_args["ssl"] = "require"

connectable = async_engine_from_config(
    config.get_section(config.config_ini_section, {}),
    prefix="sqlalchemy.",
    poolclass=pool.NullPool,
    connect_args=connect_args,
)
```

---

## Medium Priority

### M1: Missing .env.example update

**File:** `.env.example` (not found)
**Plan requirement:** "Update .env.example with new variable"

**Status:** No `.env.example`, `.env.sample`, or `.env.template` found in `apps/api/`.

**Recommendation:** Either create file or verify if project uses different env documentation pattern.

---

## Low Priority

### L1: SSL detection via string matching

**Files:** `database.py` lines 20-21, 42-43

```python
if "supabase" in DATABASE_URL.lower():
```

**Observation:** Fragile if using custom domains. Acceptable for current scope (YAGNI), but consider env var flag `USE_SSL=true` if requirements expand.

---

## Positive Observations

1. **Correct driver-specific SSL keys:**
   - `ssl` for asyncpg (async engine)
   - `sslmode` for psycopg2 (sync engine)

2. **Connection pooling config is solid:**
   - `pool_pre_ping=True` - connection health check
   - `pool_recycle=3600` - prevents stale connections
   - `pool_size=5, max_overflow=10` - reasonable defaults

3. **Clean separation:** Runtime URL vs migration URL pattern correct

4. **KISS compliant:** Minimal changes, no over-engineering

5. **Backward compatible:** Empty string default for `database_url_direct`

---

## Security Checklist (OWASP)

| Check | Status |
|-------|--------|
| A02: Cryptographic - SSL enforced | PASS (with H1 fix) |
| A05: Misconfiguration | PASS |
| A07: No hardcoded credentials | PASS |

---

## Todo List Status

| Task | Status |
|------|--------|
| Add `database_url_direct` to config.py | DONE |
| Update database.py with SSL + pool_pre_ping | DONE |
| Update alembic/env.py to use direct URL | PARTIAL (missing SSL) |
| Update .env.example | NOT VERIFIED |
| Test connection in local environment | NOT DONE |

---

## Recommended Actions

1. **[HIGH]** Add SSL `connect_args` to `async_engine_from_config` in `env.py`
2. **[MEDIUM]** Verify/create .env documentation for `DATABASE_URL_DIRECT`
3. **[LOW]** Test migration command with Supabase connection

---

## Unresolved Questions

1. Does project use `.env.example` or different env documentation pattern?
2. Has connection been tested against actual Supabase instance?
