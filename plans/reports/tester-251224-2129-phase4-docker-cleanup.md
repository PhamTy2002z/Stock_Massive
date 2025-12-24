# Test Report: Phase 4 - Docker Cleanup & Supabase Migration

**ID:** tester-251224-2129-phase4-docker-cleanup
**Date:** 2024-12-24 21:29
**Test Phase:** Phase 4 - Docker & Cleanup for Supabase Migration
**Tester:** QA Engineer

---

## Executive Summary

**Status:** ⚠️ PARTIAL PASS - Docker configuration valid but legacy db service still running

### Key Findings
- ✅ Docker Compose syntax valid for both dev/prod files
- ✅ Only 2 services defined (api, web) - no db service in config
- ✅ API service has correct DATABASE_URL and DATABASE_URL_DIRECT env vars
- ⚠️ Legacy db container still running from old docker-compose.yml
- ⚠️ Test failures due to old localhost:5432 default in config.py
- ⚠️ API container metadata shows `depends_on: db` in labels (cached from old image)

---

## Test Results

### 1. Docker Compose Validation

#### 1.1 Syntax Validation
```bash
docker compose config          # ✅ PASS - Valid YAML
docker compose -f docker-compose.prod.yml config  # ✅ PASS - Valid YAML
```

**Result:** Both files parse successfully without errors

#### 1.2 Service Count
```bash
services:
  api:   # ✅ Present
  web:   # ✅ Present
```

**Result:** ✅ Exactly 2 services (no db service)

#### 1.3 Environment Variables
**docker-compose.yml:**
```yaml
environment:
  DATABASE_URL: ${DATABASE_URL}  # ✅ From .env (Supabase)
  DATABASE_URL_DIRECT: ${DATABASE_URL_DIRECT:-}  # ✅ For migrations
```

**docker-compose.prod.yml:**
```yaml
environment:
  DATABASE_URL: ${DATABASE_URL:?DATABASE_URL is required}  # ✅ Required
  DATABASE_URL_DIRECT: ${DATABASE_URL_DIRECT:-}  # ✅ Optional
```

**Result:** ✅ Correct env var configuration

---

### 2. Orphaned References Check

#### 2.1 depends_on: db References
**Files searched:** All project files
**Pattern:** `depends_on.*db`

**Found in:**
- ❌ Documentation/plan files only (not active code)
- ✅ No active docker-compose.yml or docker-compose.prod.yml references

**Result:** ✅ No active depends_on: db in compose files

#### 2.2 Hardcoded Database Strings
**Pattern:** `postgresql://postgres:postgres@db:` or `@localhost:5432`

**Found in:**
1. ❌ `apps/api/src/core/config.py:23`
   ```python
   database_url: str = "postgresql://postgres:postgres@localhost:5432/stockmassive"
   ```
   **Impact:** Default value in Settings class points to localhost instead of requiring Supabase URL

2. ✅ Documentation/plan files (expected)

**Result:** ❌ Hardcoded localhost:5432 default in config.py

---

### 3. API Connection Tests

#### 3.1 Test Execution
```bash
cd apps/api && python -m pytest tests/ -v
```

**Total:** 253 tests
**Passed:** 241 (95.3%)
**Failed:** 8 (3.2%)
**Skipped:** 3 (1.2%)
**Errors:** 1 (0.4%)
**Duration:** 29.09s

#### 3.2 Failed Tests Analysis

**Category 1: Database Role Issues (7 failures)**
```
tests/test_database_phase01.py::TestStockIntradayBarModel::*
tests/test_database_phase01.py::TestUniqueConstraint::*
```

**Error:**
```
asyncpg.exceptions.InvalidAuthorizationSpecificationError: role "postgres" does not exist
```

**Root Cause:** Tests trying to connect to localhost:5432 (old Docker db) with default credentials. Supabase uses different role names.

**Category 2: Data Format Issue (1 failure)**
```
tests/test_sector_performance.py::TestMarketCapWeightedCalculation::test_total_market_cap_in_billions
```

**Error:**
```python
assert 150000000.0 == 150.0  # Expected billions, got actual value
```

**Root Cause:** Data scaling issue (not related to migration)

---

### 4. Docker Runtime Check

#### 4.1 Currently Running Services
```bash
docker compose ps
```

**Running Containers:**
1. ✅ stockmassive-api (healthy, Up 39 mins)
2. ❌ **stockmassive-db** (healthy, Up 39 mins) - **SHOULD NOT EXIST**
3. ✅ stockmassive-web (healthy, Up 39 mins)

**Issue:** Legacy PostgreSQL db container still running from previous docker-compose version

#### 4.2 Container Metadata
**API Container Labels:**
```
com.docker.compose.depends_on=db:service_healthy:false
```

**Issue:** API container built from old compose file still has db dependency in metadata

---

## Critical Issues

### Issue #1: Legacy DB Container Running
**Severity:** HIGH
**Impact:** Resource waste, confusion about which DB is being used

**Evidence:**
- `stockmassive-db` container running (postgres:16-alpine)
- Created 3 days ago (before migration)
- Not in current docker-compose.yml but still running

**Recommendation:**
```bash
docker compose down  # Stop all containers
docker compose up -d  # Recreate with new config
```

### Issue #2: config.py Default Points to Localhost
**Severity:** HIGH
**Impact:** Tests and fresh installs will fail without .env

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/config.py:23`

**Current:**
```python
database_url: str = "postgresql://postgres:postgres@localhost:5432/stockmassive"
```

**Expected:**
```python
database_url: str = ""  # Force env var requirement
# OR
database_url: str  # No default (pydantic will require .env)
```

**Recommendation:** Remove default or set to empty string

### Issue #3: Cached Docker Images
**Severity:** MEDIUM
**Impact:** API container metadata shows old dependencies

**Evidence:**
```
com.docker.compose.depends_on=db:service_healthy:false
```

**Recommendation:**
```bash
docker compose build --no-cache
docker compose up -d
```

---

## Test Pass Criteria

| Criteria | Status | Notes |
|----------|--------|-------|
| docker-compose.yml valid | ✅ PASS | No syntax errors |
| docker-compose.prod.yml valid | ✅ PASS | No syntax errors |
| Only 2 services (api, web) | ✅ PASS | db service removed from config |
| DATABASE_URL env var present | ✅ PASS | Both dev/prod configs |
| DATABASE_URL_DIRECT env var present | ✅ PASS | Both dev/prod configs |
| No depends_on: db in configs | ✅ PASS | Removed from compose files |
| No hardcoded db connections | ❌ FAIL | config.py has localhost default |
| API connects to Supabase | ⚠️ PARTIAL | 95.3% tests pass, 7 fail on old DB |
| No orphaned db containers | ❌ FAIL | Legacy db container still running |

---

## Recommendations

### Immediate Actions

1. **Stop legacy containers:**
   ```bash
   docker compose down
   docker volume ls | grep stock_massive  # Check for old volumes
   docker volume rm stock_massive_postgres_data  # If exists
   ```

2. **Fix config.py default:**
   ```python
   # Option 1: Require env var
   database_url: str  # No default

   # Option 2: Empty default with validation
   database_url: str = ""

   @field_validator('database_url')
   def validate_db_url(cls, v):
       if not v:
           raise ValueError("DATABASE_URL must be set in .env")
       return v
   ```

3. **Rebuild containers:**
   ```bash
   docker compose build --no-cache
   docker compose up -d
   ```

4. **Verify Supabase connection:**
   ```bash
   docker compose logs api | grep -i "database"
   docker compose exec api python -c "from src.core.database import engine; print('OK')"
   ```

### Follow-up Tests

1. Run full test suite with Supabase connection:
   ```bash
   cd apps/api
   pytest tests/ -v --tb=short -x  # Stop on first failure
   ```

2. Verify no localhost:5432 connections:
   ```bash
   docker compose logs api | grep "5432"  # Should show Supabase port, not 5432
   ```

3. Check for remaining docker volumes:
   ```bash
   docker volume ls
   docker system df  # Check disk usage
   ```

---

## Warnings

### Test Suite Warnings
1. **Deprecated Pydantic V2:** `config` class-based setup
2. **Deprecated Pandas:** `DataFrame.applymap` → use `DataFrame.map`
3. **Jupyter paths migration:** platformdirs warning

**Impact:** Non-critical, should be addressed in future refactoring

---

## Performance Metrics

- **Docker config validation:** <1s
- **Test suite execution:** 29.09s
- **Test pass rate:** 95.3%
- **Container startup:** Healthy within 39 minutes

---

## Conclusion

**Phase 4 Status:** ⚠️ PARTIAL PASS with critical cleanup required

**Summary:**
- Docker configuration files correctly updated
- Environment variables properly configured
- Legacy db service definition removed
- **BUT:** Old db container still running, config.py needs update

**Next Steps:**
1. Stop/remove legacy db container
2. Fix config.py localhost default
3. Rebuild Docker images
4. Re-run tests with clean environment
5. Verify 100% Supabase connectivity

**Estimated Time to Fix:** 10-15 minutes

---

## Unresolved Questions

1. Should we remove localhost:5432 default entirely or provide fallback for local dev?
2. Are there any data in old postgres container that needs backup before removal?
3. Should .env.example include required vs optional env vars documentation?
4. Do we need migration guide for developers with existing local setups?
5. Should test suite have separate fixture for Supabase vs local testing?
