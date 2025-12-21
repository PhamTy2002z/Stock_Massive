# Codebase Verification Report

**Date:** 2025-12-21
**Type:** Brainstorm / Codebase Audit
**Status:** Complete

---

## Executive Summary

Stock Massive codebase is **well-structured** with solid architecture. Core functionality (stock data, volume anomaly, sector performance) works. Auth scaffolding with Supabase is in place. Several cleanup items and minor improvements identified.

---

## Findings

### ✅ What's Working Well

| Area | Status | Notes |
|------|--------|-------|
| TypeScript | ✅ Pass | `tsc --noEmit` passes with no errors |
| Project Structure | ✅ Good | Monorepo with clear separation (apps/web, apps/api) |
| Backend Architecture | ✅ Solid | Feature-based modules, layered design (router→service→repository) |
| Frontend Architecture | ✅ Good | App Router, ShadCN/UI, TanStack Query |
| API Design | ✅ RESTful | 27 endpoints, versioned `/api/v1/stocks` |
| Caching | ✅ Implemented | Upstash Redis with trading-hours-aware TTL |
| Rate Limiting | ✅ Implemented | Sliding window via Upstash |
| Scheduler | ✅ Working | APScheduler for intraday collection |
| Auth Scaffold | ✅ Ready | Supabase Google OAuth, middleware, protected routes |

### ⚠️ Issues Requiring Attention

#### 1. Security Concerns

| Issue | Location | Severity | Recommendation |
|-------|----------|----------|----------------|
| JWT Secret default | `docker-compose.yml:26`, `core/config.py:26` | **High** | Remove default, require env var |
| Non-null assertions | `utils/supabase/*.ts` | Medium | Add runtime validation for env vars |
| CORS hardcoded | `main.py:44` | Medium | Make configurable via env var |

#### 2. Code Cleanup Needed

| Issue | Location | Size | Action |
|-------|----------|------|--------|
| Legacy files | `apps/api/src/stocks/*_old.py` | ~100KB | Delete or archive |
| Empty users module | `apps/api/src/users/` | - | Remove (only __pycache__) |
| Empty auth module | `apps/api/src/auth/` | - | Remove .gitkeep (using Supabase) |
| Test file misplaced | `apps/api/test_volume_anomaly_api.py` | 8KB | Move to `tests/` |
| Strange directory | `apps/api/APPROVED:/` | - | Investigate/remove |
| Duplicate lock file | `apps/web/package-lock.json` | - | Remove (using pnpm) |

#### 3. Configuration Gaps

| Issue | Impact | Recommendation |
|-------|--------|----------------|
| Missing `NEXT_PUBLIC_SITE_URL` in .env.example | OAuth redirect fails | Add to .env.example |
| ESLint not configured | Lint command prompts for setup | Run `pnpm lint` and select "Strict" |
| CORS not configurable | Can't deploy to different domains | Add `CORS_ORIGINS` env var |

#### 4. Dependency Concerns

| Package | Issue | Risk | Recommendation |
|---------|-------|------|----------------|
| `apscheduler>=4.0.0a6` | Alpha version | Medium | Monitor for stable release |
| `python-jose`, `passlib` | Installed but unused | Low | Remove if using Supabase only |

---

## Architecture Decision: Backend Auth

**Current State:**
- Backend has `python-jose`, `passlib` in requirements (JWT auth)
- Backend `auth/` and `users/` modules are empty
- Frontend uses Supabase Auth (Google OAuth)

**Question:** Should backend implement its own JWT auth or rely on Supabase?

**Recommendation:**
- **Option A (Recommended):** Use Supabase only - remove unused auth deps from backend
- **Option B:** Implement backend JWT for API-to-API auth scenarios

---

## Improvement Opportunities

### Quick Wins (Low Effort, High Impact)

1. **Delete legacy `*_old.py` files** - saves 100KB, reduces confusion
2. **Remove empty modules** - cleaner codebase
3. **Configure ESLint** - catch issues early
4. **Add missing env vars to .env.example** - better DX

### Medium-Term Improvements

1. **Make CORS configurable** - required for production deployment
2. **Add env var validation** - fail fast on missing config
3. **Upgrade APScheduler** - when stable 4.0 releases
4. **Add health check for Redis** - graceful degradation already works

### Future Considerations

1. **WebSocket support** - for real-time price updates
2. **TradingView charts** - currently using Recharts
3. **Portfolio/Watchlist** - routes scaffolded, not implemented

---

## Recommended Actions

### Priority 1 - Security (Do Now)

```bash
# 1. Remove JWT default in docker-compose.yml
# Change: JWT_SECRET: ${JWT_SECRET:-change-me-in-production}
# To: JWT_SECRET: ${JWT_SECRET}

# 2. Add CORS_ORIGINS env var support in main.py
```

### Priority 2 - Cleanup (This Week)

```bash
# Delete legacy files
rm apps/api/src/stocks/router_old.py
rm apps/api/src/stocks/schemas_old.py
rm apps/api/src/stocks/service_old.py

# Remove empty modules
rm -rf apps/api/src/auth/
rm -rf apps/api/src/users/

# Move test file
mv apps/api/test_volume_anomaly_api.py apps/api/tests/

# Remove duplicate lock file
rm apps/web/package-lock.json

# Investigate and remove strange directory
rm -rf "apps/api/APPROVED:/"
```

### Priority 3 - Configuration (This Week)

1. Add to `apps/web/.env.example`:
   ```
   NEXT_PUBLIC_SITE_URL=http://localhost:3000
   ```

2. Configure ESLint:
   ```bash
   cd apps/web && pnpm lint  # Select "Strict"
   ```

---

## Unresolved Questions

1. **Backend auth strategy?** - Keep JWT deps or remove? (Recommend: remove if Supabase-only)
2. **What is `APPROVED:/` directory?** - Appears to be accidental creation
3. **APScheduler 4.0 alpha stability?** - Any issues in production?
4. **Production deployment target?** - Affects CORS, env var requirements

---

## Conclusion

Codebase is in **good shape** for a development project. Main concerns are:
- Security defaults need hardening before production
- ~100KB of legacy code should be cleaned up
- Minor configuration gaps to address

No blocking issues found. Project can continue development while addressing cleanup items incrementally.
