# Infrastructure Setup Report

**Date:** 2025-12-19  
**Scout ID:** a0c27cc  
**Topic:** Root-level configuration and Docker setup

---

## 1. Root package.json

**Path:** `D:\Stock_Massive\package.json`

**Type:** Monorepo orchestration (not workspace manager)

**Scripts:**
| Script | Command | Purpose |
|--------|---------|---------|
| `dev` | `docker compose up --build` | Start all services with rebuild |
| `dev:detach` | `docker compose up --build -d` | Start detached |
| `stop` | `docker compose down` | Stop services |
| `stop:clean` | `docker compose down -v` | Stop + remove volumes |
| `logs` | `docker compose logs -f` | Follow all logs |
| `logs:api` | `docker compose logs -f api` | API logs only |
| `logs:web` | `docker compose logs -f web` | Web logs only |
| `db:shell` | `docker compose exec db psql -U postgres -d stockmassive` | PostgreSQL shell |
| `api:shell` | `docker compose exec api bash` | API container shell |
| `web:shell` | `docker compose exec web sh` | Web container shell |

**Note:** No workspace config (no `workspaces` field). Each app manages own deps.

---

## 2. docker-compose.yml

**Path:** `D:\Stock_Massive\docker-compose.yml`

### Services Defined

| Service | Image/Build | Port | Container Name |
|---------|-------------|------|----------------|
| `db` | `postgres:16-alpine` | 5432:5432 | stockmassive-db |
| `api` | Build from `./apps/api/Dockerfile` | 8000:8000 | stockmassive-api |
| `web` | Build from `./apps/web/Dockerfile` | 3000:3000 | stockmassive-web |

### Service Details

**db (PostgreSQL):**
- Image: `postgres:16-alpine`
- Healthcheck: `pg_isready` every 10s
- Volume: `postgres_data` (named volume)
- Env vars from `.env` with defaults

**api (FastAPI):**
- Python 3.11-slim base
- Hot-reload via volume mount: `./apps/api/src:/code/src`
- Depends on: `db` (healthy)
- Installs gcc/g++ for C compilation (wordcloud, etc.)

**web (Next.js):**
- Node 20-alpine base
- Hot-reload via volume mounts: `src/`, `public/`, `package.json`
- `WATCHPACK_POLLING=true` for Windows file watching
- Depends on: `api`

### Volumes
- `postgres_data` - persistent DB storage

---

## 3. docker/ Directory

**Path:** `D:\Stock_Massive\docker\`

**Contents:** Only `.gitkeep` (placeholder)

**Note:** Dockerfiles live in app directories:
- `D:\Stock_Massive\apps\api\Dockerfile`
- `D:\Stock_Massive\apps\web\Dockerfile`

---

## 4. .env.example

**Path:** `D:\Stock_Massive\.env.example`

| Variable | Default | Used By |
|----------|---------|---------|
| `DB_USER` | postgres | db, api |
| `DB_PASSWORD` | postgres | db, api |
| `DB_NAME` | stockmassive | db, api |
| `DATABASE_URL` | postgresql://postgres:postgres@localhost:5432/stockmassive | api (local dev) |
| `JWT_SECRET` | change-me-in-production | api |
| `API_HOST` | 0.0.0.0 | api |
| `API_PORT` | 8000 | api |
| `NEXT_PUBLIC_API_URL` | http://localhost:8000/api/v1 | web |

---

## 5. Other Root Config Files

| File | Purpose |
|------|---------|
| `.gitignore` | Ignores: node_modules, __pycache__, .venv, .next, .env*, IDE files, logs, coverage, postgres_data |
| `LICENSE` | MIT License (Pham Phuoc Ty, 2025) |
| `README.md` | Project docs, API endpoints, setup instructions |

---

## 6. App-Level Dockerfiles

### apps/api/Dockerfile
```dockerfile
FROM python:3.11-slim
WORKDIR /code
RUN apt-get update && apt-get install -y gcc g++ python3-dev
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

### apps/web/Dockerfile
```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
CMD sh -c "npm install && npm run dev"
```

---

## 7. Summary

**Architecture:** Docker-first monorepo with 3 services
- PostgreSQL 16 (database)
- FastAPI/Python 3.11 (backend API)
- Next.js 14/Node 20 (frontend)

**Dev Experience:**
- Single command start: `npm run dev`
- Hot-reload enabled for both api and web
- Shell access scripts for debugging
- Volume mounts for live code changes

**Production Considerations:**
- JWT_SECRET needs changing
- DB credentials need securing
- No production Dockerfiles yet (dev-focused)

---

## Files Analyzed

| File | Path |
|------|------|
| package.json | `D:\Stock_Massive\package.json` |
| docker-compose.yml | `D:\Stock_Massive\docker-compose.yml` |
| .env.example | `D:\Stock_Massive\.env.example` |
| .gitignore | `D:\Stock_Massive\.gitignore` |
| LICENSE | `D:\Stock_Massive\LICENSE` |
| README.md | `D:\Stock_Massive\README.md` |
| API Dockerfile | `D:\Stock_Massive\apps\api\Dockerfile` |
| Web Dockerfile | `D:\Stock_Massive\apps\web\Dockerfile` |
| docker/.gitkeep | `D:\Stock_Massive\docker\.gitkeep` |

---

## Unresolved Questions

None.
