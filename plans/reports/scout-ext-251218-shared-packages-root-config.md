# Scout Report: Shared Packages & Root Config
**Date:** 2025-12-18 | **Scope:** /Users/typham/Documents/GitHub/Stock_Massive

---

## 1. packages/ Directory

**Status:** Scaffolded, empty placeholders

| Path | Contents |
|------|----------|
| `/packages/config/.gitkeep` | Empty placeholder |
| `/packages/types/.gitkeep` | Empty placeholder |

**Purpose (per docs):**
- `config/` - Shared configs (ESLint, TypeScript, etc.)
- `types/` - Shared TypeScript types between frontend/backend

---

## 2. docker/ Directory

**Status:** Scaffolded, empty

| Path | Contents |
|------|----------|
| `/docker/.gitkeep` | Empty placeholder |

**Note:** Docker configs currently live at root level (`docker-compose.yml`) and in app-specific Dockerfiles.

---

## 3. docker-compose.yml

**Location:** `/Users/typham/Documents/GitHub/Stock_Massive/docker-compose.yml`

**Services:**
| Service | Image/Build | Port | Purpose |
|---------|-------------|------|---------|
| `db` | postgres:16-alpine | 5432 | PostgreSQL database |
| `api` | ./apps/api/Dockerfile | 8000 | FastAPI backend |
| `web` | ./apps/web/Dockerfile | 3000 | Next.js frontend |

**Key Features:**
- Health check on db before api starts
- Volume mounts for hot-reload (src directories)
- Environment variables with defaults
- Named volume `postgres_data` for persistence

---

## 4. Root package.json

**Location:** `/Users/typham/Documents/GitHub/Stock_Massive/package.json`

```json
{
  "name": "stock-massive",
  "version": "0.1.0",
  "private": true
}
```

**Scripts:**
| Script | Command | Purpose |
|--------|---------|---------|
| `dev` | docker-compose up --build | Start all services |
| `dev:detach` | docker-compose up --build -d | Start detached |
| `stop` | docker-compose down | Stop services |
| `stop:clean` | docker-compose down -v | Stop + remove volumes |
| `logs` | docker-compose logs -f | Follow all logs |
| `logs:api` | docker-compose logs -f api | API logs only |
| `logs:web` | docker-compose logs -f web | Web logs only |
| `db:shell` | docker-compose exec db psql... | PostgreSQL shell |
| `api:shell` | docker-compose exec api bash | API container shell |
| `web:shell` | docker-compose exec web sh | Web container shell |

**Note:** No pnpm workspaces configured yet. Root package.json is Docker orchestration only.

---

## 5. docs/ Directory

**Location:** `/Users/typham/Documents/GitHub/Stock_Massive/docs/`

| File | Status | Content Summary |
|------|--------|-----------------|
| `project-overview-pdr.md` | Complete | Purpose, goals, scope, tech decisions, risks |
| `system-architecture.md` | Complete | High-level diagram, directory structure, data flow |
| `tech-stack.md` | Complete | Full stack breakdown with versions |
| `code-standards.md` | Complete | Naming conventions, patterns, git workflow |

**Missing docs (per CLAUDE.md template):**
- `codebase-summary.md`
- `design-guidelines.md`
- `deployment-guide.md`
- `project-roadmap.md`

---

## 6. Other Root Config Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Service orchestration |
| `package.json` | Root scripts (Docker commands) |
| `.git/` | Git repository |

**Missing common configs:**
- `.env.example` - Environment template
- `.gitignore` - (may exist, not checked)
- `pnpm-workspace.yaml` - Workspace config (if using pnpm workspaces)
- `turbo.json` - Turborepo config (if using)

---

## 7. Apps Overview (for context)

### apps/web/ (Next.js 14)
- ShadCN UI components installed (button, sidebar, avatar, etc.)
- Dashboard layout scaffolded
- Route groups: `(auth)`, `(dashboard)`
- TailwindCSS configured

### apps/api/ (FastAPI)
- Stocks module started (router, service, schemas)
- Alembic migrations scaffolded
- Tests scaffolded with pytest
- Core config/dependencies in place

---

## Summary

| Area | Status |
|------|--------|
| packages/config | Empty (needs shared ESLint, TS configs) |
| packages/types | Empty (needs shared types) |
| docker/ | Empty (configs in root/apps) |
| docker-compose.yml | Complete, functional |
| Root package.json | Docker scripts only, no workspaces |
| docs/ | 4/8 docs complete |

---

## Unresolved Questions

1. Will pnpm workspaces be configured for shared packages?
2. Should shared TypeScript types be generated from Pydantic schemas?
3. Is Turborepo or similar build orchestration planned?
