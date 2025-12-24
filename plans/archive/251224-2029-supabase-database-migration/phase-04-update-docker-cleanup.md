# Phase 4: Update Docker & Cleanup

## Context
- **Parent:** [plan.md](./plan.md)
- **Depends on:** [Phase 3](./phase-03-migrate-data.md)

## Overview

| Property | Value |
|----------|-------|
| Priority | P2 |
| Status | Pending |
| Effort | 30 min |

Remove PostgreSQL from Docker Compose and update API configuration.

## Key Insights

- Remove `db` service from docker-compose.yml
- Remove `depends_on: db` from api service
- Update api environment to use external DATABASE_URL
- Keep docker-compose.yml simple for local development

## Requirements

### Functional
- Remove PostgreSQL service from Docker Compose
- Update API service configuration
- Update production docker-compose.prod.yml

### Non-Functional
- Maintain development workflow
- Document the change

## Related Code Files

**Files to modify:**
- `docker-compose.yml` - remove db service
- `docker-compose.prod.yml` - remove db service

## Implementation Steps

### Step 1: Update docker-compose.yml

```yaml
# docker-compose.yml - MODIFIED
services:
  # REMOVED: db service entirely

  api:
    build:
      context: ./apps/api
      dockerfile: Dockerfile
    container_name: stockmassive-api
    environment:
      DATABASE_URL: ${DATABASE_URL}  # From .env (Supabase)
      DATABASE_URL_DIRECT: ${DATABASE_URL_DIRECT}  # For migrations
      AUTH_SECRET: ${AUTH_SECRET:-dev-secret-change-in-production}
      CORS_ORIGINS: ${CORS_ORIGINS:-http://localhost:3000}
      UPSTASH_REDIS_REST_URL: ${UPSTASH_REDIS_REST_URL:-}
      UPSTASH_REDIS_REST_TOKEN: ${UPSTASH_REDIS_REST_TOKEN:-}
      SCHEDULER_ENABLED: ${SCHEDULER_ENABLED:-true}
      DAILY_OHLCV_ENABLED: ${DAILY_OHLCV_ENABLED:-true}
    volumes:
      - ./apps/api/src:/code/src
      - ./apps/api/alembic:/code/alembic
    ports:
      - "8000:8000"
    # REMOVED: depends_on: db
    networks:
      - stockmassive-network

  web:
    build:
      context: ./apps/web
      dockerfile: Dockerfile
    container_name: stockmassive-web
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000/api/v1
      WATCHPACK_POLLING: "true"
    volumes:
      - ./apps/web/src:/app/src
      - ./apps/web/public:/app/public
    ports:
      - "3000:3000"
    depends_on:
      - api
    networks:
      - stockmassive-network

# REMOVED: volumes: postgres_data

networks:
  stockmassive-network:
    driver: bridge
```

### Step 2: Update docker-compose.prod.yml

Similar changes:
- Remove db service
- Remove depends_on: db from api
- Remove postgres_data volume

### Step 3: Update .env.example

```bash
# .env.example - ADD/UPDATE these lines:

# Database (Supabase)
DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres
DATABASE_URL_DIRECT=postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres

# REMOVED: DB_USER, DB_PASSWORD, DB_NAME (no longer needed)
```

### Step 4: Clean Up Docker Resources

```bash
# Stop all containers
docker-compose down

# Remove old postgres volume (WARNING: data loss if not migrated)
docker volume rm stock_massive_postgres_data 2>/dev/null || true

# Rebuild without db service
docker-compose up -d --build
```

### Step 5: Verify API Starts Correctly

```bash
# Check logs
docker-compose logs -f api

# Expected: No database connection errors
# Expected: Scheduler jobs start successfully
```

## Todo List

- [ ] Update docker-compose.yml (remove db service)
- [ ] Update docker-compose.prod.yml (remove db service)
- [ ] Update .env.example with Supabase template
- [ ] Stop Docker containers
- [ ] Remove postgres volume (after verifying migration success)
- [ ] Rebuild and start services
- [ ] Verify API logs show successful connection

## Success Criteria

- [ ] docker-compose.yml has no db service
- [ ] API starts without database errors
- [ ] Scheduler jobs run successfully
- [ ] No orphaned volumes

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Accidental data loss | Only remove volume AFTER verifying Supabase data |
| API fails to start | Check DATABASE_URL is correct in .env |
| Network issues | Verify Supabase project is active |

## Security Considerations

- Ensure .env is in .gitignore (should already be)
- Remove any hardcoded database credentials
- Production .env should use secure password

## Next Steps

→ [Phase 5: Test & Validate](./phase-05-test-validate.md)
