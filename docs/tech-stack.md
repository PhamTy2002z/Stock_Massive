# Stock Massive - Tech Stack

## Overview
Monorepo architecture for stock analysis platform with Next.js frontend, FastAPI backend, and PostgreSQL database.

## Frontend Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| Next.js | 15.5.9 | React framework (App Router) |
| React | 18.3.1 | UI library |
| TypeScript | 5.3 | Type safety |
| TailwindCSS | 3.4 | Utility-first CSS |
| ShadCN/UI | latest | Component library (Radix-based) |
| TanStack Query | 5.90 | Server state management, caching |
| Recharts | 3.6 | Charts (sparklines, bar, pie, treemap) |
| next-themes | 0.4.6 | Dark/light theme switching |
| Sonner | 2.0.7 | Toast notifications |

## Backend Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Runtime |
| FastAPI | 0.100+ | API framework |
| SQLAlchemy | 2.0 | ORM (async + sync) |
| Alembic | latest | DB migrations |
| Pydantic | 2.x | Data validation |
| Uvicorn | latest | ASGI server |
| APScheduler | 4.0 | Background job scheduling |
| Upstash Redis | 1.0+ | Caching + rate limiting |
| vnstock | 3.0+ | Vietnam stock data (VCI source) |
| Pandas | 2.0+ | Data manipulation |

## Database

| Technology | Version | Purpose |
|------------|---------|---------|
| PostgreSQL | 16 | Primary database |

## DevOps

| Technology | Purpose |
|------------|---------|
| Docker | Containerization |
| Docker Compose | Local orchestration |
| pnpm | Package manager (frontend) |
| uv/pip | Package manager (backend) |

## Architecture Decisions

### Monorepo Structure
- **Choice**: Simple workspace with pnpm
- **Rationale**: Lower complexity, sufficient for single team, easy Docker integration

### Frontend Architecture
- **Pattern**: Feature-based component organization
- **State**: TanStack Query v5 for server state (5min stale, 10min gc)
- **Routing**: Next.js App Router with route groups
- **SSR**: Server Components + HydrationBoundary pattern

### Backend Architecture
- **Pattern**: Domain-driven with repository pattern
- **Layers**: Router → Service → Repository → Model
- **API Versioning**: URL prefix (`/api/v1/`)

### Security
- JWT authentication with refresh tokens
- CORS configured for specific origins
- Input validation via Pydantic
- Rate limiting middleware
