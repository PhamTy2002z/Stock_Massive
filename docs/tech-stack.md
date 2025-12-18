# Stock Massive - Tech Stack

## Overview
Monorepo architecture for stock analysis platform with Next.js frontend, FastAPI backend, and PostgreSQL database.

## Frontend Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| Next.js | 14+ | React framework (App Router) |
| TypeScript | 5.x | Type safety |
| TailwindCSS | 3.x | Utility-first CSS |
| ShadCN/UI | latest | Component library (Radix-based) |
| TanStack Table | 8.x | Data tables with sorting/filtering |
| TradingView | Lightweight Charts | Stock charting |

## Backend Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Runtime |
| FastAPI | 0.100+ | API framework |
| SQLAlchemy | 2.0 | ORM |
| Alembic | latest | DB migrations |
| Pydantic | 2.x | Data validation |
| Uvicorn | latest | ASGI server |

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
- **State**: React Query for server state, Zustand for client state (if needed)
- **Routing**: Next.js App Router with route groups

### Backend Architecture
- **Pattern**: Domain-driven with repository pattern
- **Layers**: Router → Service → Repository → Model
- **API Versioning**: URL prefix (`/api/v1/`)

### Security
- JWT authentication with refresh tokens
- CORS configured for specific origins
- Input validation via Pydantic
- Rate limiting middleware
