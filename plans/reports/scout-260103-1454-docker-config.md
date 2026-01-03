# Scout Report: Docker & Root Configuration Files
**Date:** 2026-01-03 14:54  
**Scope:** Docker configurations, environment setup, database files, container orchestration

---

## Directory Structure

```
Stock_Massive/
├── docker/                          # Docker directory (minimal)
│   └── .gitkeep                     # Empty placeholder
├── docker-compose.yml               # Development compose config
├── docker-compose.prod.yml          # Production compose config
├── package.json                     # Root workspace config
├── data_export.sql                  # Database export (115,291 lines)
├── README.md                        # Project documentation
└── .gitignore                       # Git ignore rules

apps/api/
├── Dockerfile                       # Development image (746B)
├── Dockerfile.prod                  # Production image (1.6K, multi-stage)
├── entrypoint.sh                    # Container startup script (1.4K)
├── requirements.txt                 # Python dependencies (461B)

apps/web/
├── Dockerfile                       # Development image (487B)
├── Dockerfile.prod                  # Production image (1.7K, 3-stage)
├── .dockerignore                    # Docker build ignore rules (42B)
├── next.config.js                   # Next.js configuration (178B)
└── tsconfig.json                    # TypeScript configuration (701B)
```

---

## Comprehensive File List

### Root Configuration Files

| File | Size | Purpose | Key Details |
|------|------|---------|------------|
| `package.json` | 17 lines | Workspace root config | Monorepo setup with docker-compose scripts |
| `.gitignore` | Present | Git ignore rules | Standard Node/Python ignores |
| `README.md` | Present | Project docs | Main documentation |

### Docker Compose Files

| File | Type | Purpose | Services | Ports |
|------|------|---------|----------|-------|
| `docker-compose.yml` | Development | Local dev environment | api, web | 8000, 3000 |
| `docker-compose.prod.yml` | Production | Production deployment | api, web | 8000, 3000 |

**Development (`docker-compose.yml`):**
- Hot reload volumes for source code
- No restart policy
- Environment from config file
- Network: stockmassive-network (bridge)

**Production (`docker-compose.prod.yml`):**
- Multi-stage builds
- Restart: unless-stopped
- Required env vars: DATABASE_URL, AUTH_SECRET
- Build args: NEXT_PUBLIC_* variables
- No volumes (immutable containers)

### API Container Files

| File | Size | Purpose | Details |
|------|------|---------|---------|
| `Dockerfile` | 746B | Dev image | Python 3.11-slim, uvicorn, health check |
| `Dockerfile.prod` | 1.6K | Prod image | Multi-stage build, non-root user, single worker |
| `entrypoint.sh` | 1.4K | Startup script | DB wait logic, migration runner, remote DB support |
| `requirements.txt` | 461B | Python deps | 34 packages total |

**Python Dependencies (34 packages):**
- **Core:** FastAPI (>=0.100.0), Uvicorn (>=0.23.0), Pydantic (>=2.0.0)
- **Database:** SQLAlchemy (>=2.0.0), Alembic (>=1.12.0), asyncpg (>=0.28.0), psycopg2-binary (>=2.9.0), greenlet (>=3.0.0)
- **Cache & Rate Limiting:** Upstash Redis (>=1.0.0), Upstash RateLimit (>=1.0.0)
- **Data Processing:** vnstock (>=3.0.0), pandas (>=2.0.0), numpy (>=1.24.0)
- **Scheduler:** APScheduler (>=4.0.0a6)
- **Testing:** pytest (>=7.4.0), pytest-asyncio (>=0.21.0)
- **Utils:** httpx (>=0.25.0), python-multipart (>=0.0.6), tenacity (>=8.2.0)

**API Dockerfile (Dev):**
```dockerfile
FROM python:3.11-slim
WORKDIR /code
RUN apt-get update && apt-get install -y gcc g++ python3-dev
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**API Dockerfile.prod (Multi-stage):**
- Stage 1 (builder): Compile dependencies
- Stage 2 (production): Runtime only, non-root user (app), single worker for APScheduler
- Note: Single worker enforced because APScheduler requires single process (multiple workers = duplicate jobs)

**Entrypoint Script (`entrypoint.sh`):**
1. Parse DATABASE_URL for host/port
2. Wait for local DB (if docker hostname detected)
3. Run Alembic migrations:
   - Local DB: Fail startup if migrations fail
   - Remote DB: Warn but continue if migrations fail
4. Start Uvicorn with single worker

### Web Container Files

| File | Size | Purpose | Details |
|------|------|---------|---------|
| `Dockerfile` | 487B | Dev image | Node 20-alpine, pnpm, hot reload |
| `Dockerfile.prod` | 1.7K | Prod image | 3-stage build (deps, builder, production) |
| `.dockerignore` | 42B | Build ignore | node_modules, .next, .git, logs |
| `next.config.js` | 178B | Next.js config | Build configuration |
| `tsconfig.json` | 701B | TypeScript config | Type checking configuration |

**Web Dockerfile (Dev):**
```dockerfile
FROM node:20-alpine
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@latest --activate
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000
CMD ["pnpm", "dev"]
```

**Web Dockerfile.prod (3-stage):**
- Stage 1 (deps): Install dependencies
- Stage 2 (builder): Build Next.js application
- Stage 3 (production): Non-root user (nextjs), standalone output, static assets

**Web .dockerignore:**
```
node_modules
.next
.git
*.log
```

### Database Files

| File | Size | Purpose | Details |
|------|------|---------|---------|
| `data_export.sql` | 115,291 lines | DB dump | PostgreSQL 16.11 export with financial_statements data |

**Content Sample:**
- Vietnamese stock market data (MTV, MTG, MQB, MLS, MIM, MHL, etc.)
- Financial metrics: net_profit, revenue, eps, profit_margin, rank
- Exchanges: UPCOM, HSX, DELISTED
- Years: 2013-2025, quarterly data
- Timestamps: created_at, updated_at

### Root Package.json Scripts

```json
{
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
```

---

## Docker Compose Configuration Details

### Development Setup (`docker-compose.yml`)

Services: api (8000), web (3000)
Network: stockmassive-network (bridge)
Volumes: Source code hot reload
Environment: From config file

API Service:
- Build: ./apps/api/Dockerfile
- Container: stockmassive-api
- Volumes: src/ and alembic/ for hot reload
- Environment: DATABASE_URL, AUTH_SECRET, CORS_ORIGINS, scheduler config

Web Service:
- Build: ./apps/web/Dockerfile
- Container: stockmassive-web
- Volumes: src/ and public/ for hot reload
- Environment: NEXT_PUBLIC_API_URL, INTERNAL_API_URL, WATCHPACK_POLLING
- Depends on: api service

### Production Setup (`docker-compose.prod.yml`)

Services: api (8000), web (3000)
Network: stockmassive-network (bridge)
Restart Policy: unless-stopped
Build Args: NEXT_PUBLIC_* variables

API Service:
- Build: ./apps/api/Dockerfile.prod
- Container: stockmassive-api
- Environment: Required vars (DATABASE_URL, AUTH_SECRET)
- No volumes (immutable)

Web Service:
- Build: ./apps/web/Dockerfile.prod
- Container: stockmassive-web
- Build args: NEXT_PUBLIC_API_URL, NEXT_PUBLIC_SUPABASE_*
- No volumes (immutable)

---

## Health Checks

**API Health Check:**
```
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3
CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
```

**Web Health Check:**
```
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3
CMD wget --no-verbose --tries=1 --spider http://localhost:3000
```

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Docker Compose files | 2 (dev, prod) |
| Dockerfiles | 4 (2 per service) |
| Configuration files | 8 (config variants, configs) |
| Shell scripts | 1 (entrypoint.sh) |
| Database exports | 1 (115K lines) |
| Python dependencies | 34 packages |
| Container ports | 2 (8000 API, 3000 Web) |
| Network drivers | 1 (bridge) |

---

## Key Architectural Patterns

1. **Multi-stage Production Builds**
   - API: 2-stage (builder, production)
   - Web: 3-stage (deps, builder, production)
   - Reduces final image sizes significantly

2. **APScheduler Single-Worker Requirement**
   - Production API enforces `--workers 1`
   - Prevents duplicate job execution
   - Documented in Dockerfile.prod comment

3. **Dual Database Connection Strategy**
   - DATABASE_URL: Pooler connection (runtime)
   - DATABASE_URL_DIRECT: Direct connection (migrations)
   - Supports both local Docker and remote Supabase

4. **Non-Root Container Users**
   - API: `app` user
   - Web: `nextjs` user
   - Security best practice

5. **Hot Reload Development**
   - Source code volumes mounted
   - WATCHPACK_POLLING enabled for web
   - Rapid iteration without rebuilds

6. **Graceful Remote Database Handling**
   - Entrypoint detects local vs remote DB
   - Local: Fail if migrations fail
   - Remote: Warn but continue

7. **Environment Variable Separation**
   - Dev: Defaults provided, flexible
   - Prod: Required vars enforced with error syntax

---

## File Locations (Absolute Paths)

- `/Users/typham/Documents/GitHub/Stock_Massive/docker-compose.yml`
- `/Users/typham/Documents/GitHub/Stock_Massive/docker-compose.prod.yml`
- `/Users/typham/Documents/GitHub/Stock_Massive/package.json`
- `/Users/typham/Documents/GitHub/Stock_Massive/data_export.sql`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/Dockerfile`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/Dockerfile.prod`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/entrypoint.sh`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/requirements.txt`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/Dockerfile`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/Dockerfile.prod`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/.dockerignore`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/next.config.js`
- `/Users/typham/Documents/GitHub/Stock_Massive/apps/web/tsconfig.json`

---

## Unresolved Questions

- Are there GitHub Actions workflows in `.github/workflows/` for CI/CD pipeline?
- Is there a Makefile for common Docker operations?
- Are there docker-compose override files (.override.yml)?
- Database initialization scripts beyond data_export.sql?
- Are there any custom Docker networks or volumes defined elsewhere?
- What is the purpose of the empty `docker/` directory with only `.gitkeep`?
