# Codebase Summary - Stock Massive

Generated: 2025-12-21
Total Files: 256 | Total Python: 40 | Total TypeScript/TSX: 81 | Total Components: 45

## 1. Project Overview and Purpose

Stock Massive is a Vietnamese stock market data platform powered by the `vnstock` library. Provides real-time data, charting, and analysis for Vietnam stock market (HOSE, HNX, UPCOM).

**Goals:**
*   Display Vietnamese stock data with interactive charts
*   Provide sortable/filterable data tables for stock screening
*   Enable portfolio tracking and watchlist management (planned)
*   Secure user authentication via Supabase (scaffolded)
*   Integrate `vnstock` library for comprehensive Vietnam market data
*   Implement advanced analytical features (volume anomaly detection, sector performance)

## 2. Tech Stack

**Frontend:**
*   **Framework**: Next.js 15.5.9 (App Router)
*   **Language**: TypeScript
*   **Styling**: TailwindCSS 3.4 + ShadCN/UI (45 Radix-based components)
*   **Data Fetching**: TanStack Query v5.90 (5min staleTime, 10min gcTime)
*   **Auth**: Supabase (Google OAuth scaffolded)
*   **Charts**: Recharts (sparklines), TradingView Lightweight Charts (planned)
*   **State**: useState (local), URL params (shared), next-themes (theme)
*   **Notifications**: Sonner
*   **UI Components**: 19 ShadCN primitives, 18 dashboard, 4 layout
*   **Custom Hooks**: 10 total (data fetching + responsive)
*   **Pages**: 8 total (home, login, register, analytics/deep-dive, charts, portfolio, watchlist)

**Backend:**
*   **Framework**: FastAPI 0.100+
*   **Language**: Python 3.11+
*   **ORM**: SQLAlchemy 2.0 + Alembic
*   **Validation**: Pydantic 2.x
*   **Server**: Uvicorn
*   **Data Source**: vnstock >= 3.0.0 (VCI), Fmarket API
*   **Scheduler**: APScheduler 4.0
*   **Cache/Rate Limit**: Upstash Redis
*   **Analytics**: Pandas, Greenlet

**Database:**
*   **Primary**: PostgreSQL 16

**DevOps:**
*   **Containerization**: Docker
*   **Orchestration (local)**: Docker Compose
*   **Package Manager (Frontend)**: pnpm
*   **Package Manager (Backend)**: pip/uv

**Design:**
*   Modern + Clean philosophy
*   HSL color system with CSS variables
*   Dark/light themes support

## 3. Directory Structure with Key Directories Explained

```
Stock_Massive/
├── apps/
│   ├── web/                     # Next.js frontend application (port 3000)
│   │   └── src/
│   │       ├── app/             # Next.js App Router pages and layouts
│   │       ├── components/      # Reusable UI components (ui/, dashboard/, layout/, providers/)
│   │       ├── hooks/           # Custom React hooks
│   │       └── lib/             # Utility functions and configurations (e.g., query-keys.ts)
│   │
│   └── api/                     # FastAPI backend application (port 8000)
│       └── src/
│           ├── stocks/          # Feature-based modules for stock data
│           │   ├── market/      # Endpoints for symbols, sectors, fund certificates
│           │   ├── price/       # Endpoints for history, intraday, indices, volume analysis
│           │   ├── company/     # Endpoints for company info
│           │   ├── financial/   # Endpoints for financials, ratios
│           │   ├── router.py    # HTTP endpoints for stock features
│           │   ├── service.py   # Business logic, vnstock integration
│           │   ├── schemas/     # Pydantic models for request/response validation
│           │   ├── models.py    # SQLAlchemy models for database interaction
│           │   ├── jobs.py      # Scheduled background tasks (APScheduler)
│           │   └── intraday_collector.py # Intraday data collection and volume anomaly detection logic
│           ├── core/            # Core configurations, database connection, scheduler setup
│           └── main.py          # Main FastAPI application entry point
│       ├── alembic/             # Database migration scripts
│       └── requirements.txt     # Python dependencies
│
├── packages/                    # Placeholder for shared code/libraries (currently empty)
├── docker/                      # Docker-related configurations (e.g., Dockerfiles for web/api)
├── docs/                        # Project documentation (PDR, architecture, code standards, etc.)
├── plans/                       # Project plans and reports
├── docker-compose.yml           # Docker Compose configuration for local development
└── README.md                    # Project README file
```

## 4. Key Features and Functionality

**Current (Completed):**
*   **Dashboard Layout**: Responsive sidebar, header, dark/light theme
*   **Stock Detail Page**: Search, ticker header, stats, tabbed sections (Overview, Financials, Shareholders, Volume)
*   **Market Indices**: VN-INDEX, VN30, HNX, UPCOM cards with sparklines (Recharts), 1-min auto-refresh
*   **VN30 Overview Table**: Real-time VN30 stocks with price, change, volume, market cap (cached 5min/1hr)
*   **Stock Data API**: 24+ endpoints via vnstock + Fmarket API
*   **Financial Data**: Income statements, balance sheets, cash flow (detailed)
*   **Shareholders/Officers**: Major holders, management, insider deals
*   **Volume Analysis**: 5-min bar aggregation, peak period analysis
*   **Volume Anomaly Detection**: Backend API + frontend visualization with Redis caching
*   **Sector Performance**: ICB Level 2 with sorting, top gainers/losers
*   **Fund Certificates**: 7-item display via Fmarket API
*   **Intraday Collection**: Scheduled daily collection (15:30 ICT) + cleanup (16:00 ICT)
*   **Auth Scaffold**: Login page UI with Supabase Google OAuth (actions.ts scaffolded)
*   **Loading/Error States**: Consistent skeleton loaders and error handling
*   **API Documentation**: Auto-generated OpenAPI/Swagger UI
*   **Redis Caching**: Trading-hours-aware cache (Upstash) for 6 high-traffic endpoints
*   **Rate Limiting**: Sliding window (100/60s standard, 20/60s heavy endpoints)

**Planned (Roadmap):**
*   **Authentication**: Complete Supabase integration (JWT, protected routes)
*   **Stock Charts**: TradingView Lightweight Charts integration
*   **Stock Screening**: TanStack Table with sorting/filtering
*   **Watchlist/Portfolio**: CRUD operations, P&L tracking
*   **Technical Analysis**: SMA, EMA, RSI, MACD, Bollinger Bands
*   **Alerts**: Price alerts, email/in-app notifications

## 5. Architecture Patterns Used

**Overall:**
*   **Monorepo Structure**: Simple workspace for frontend and backend applications, managed by pnpm.
*   **Microservices-like (Logical Separation)**: Frontend (Next.js) and Backend (FastAPI) are distinct applications communicating via REST API, allowing for independent development and deployment.
*   **Containerization**: Docker and Docker Compose for consistent development and deployment environments.

**Frontend (Next.js):**
*   **Feature-based Component Organization**: Components are organized by feature or domain (e.g., `dashboard/`, `stocks/`).
*   **Server Components First**: Prioritizes Next.js Server Components by default for performance, using `"use client"` only when interactive client-side features are needed.
*   **Declarative UI**: Leverages React's declarative nature and ShadCN/UI for consistent and accessible UI elements.
*   **Data Fetching Layer**: TanStack Query for efficient server state management, caching, and background re-fetching.

**Backend (FastAPI):**
*   **Domain-Driven with Repository Pattern**: Code is organized into modules based on business domains (e.g., `stocks/market`, `stocks/price`).
*   **Layered Architecture**: Clear separation of concerns:
    *   **Router**: Handles HTTP requests, defines API endpoints.
    *   **Service**: Contains business logic, integrates with external libraries (vnstock) and data access.
    *   **Repository**: Handles database interactions (using SQLAlchemy models).
    *   **Schemas**: Pydantic models for request body validation and response serialization.
*   **Asynchronous Programming**: FastAPI's native async/await support for high concurrency and non-blocking I/O operations.
*   **Dependency Injection**: FastAPI's dependency injection system for managing reusable components like database sessions and services.
*   **Scheduled Jobs**: APScheduler for background tasks such as intraday data collection.

## 6. Important Files and Their Purposes

**Frontend (apps/web/):**
*   `/src/app/layout.tsx`: Root layout with providers (Query, Theme, Supabase)
*   `/src/app/page.tsx`: Home dashboard page
*   `/src/app/(auth)/login/`: Login page with Google OAuth scaffold
*   `/src/app/auth/callback/route.ts`: Supabase OAuth callback handler
*   `/src/app/analytics/deep-dive/page.tsx`: Stock deep-dive analytics page (NEW)
*   `/src/components/ui/`: 19 ShadCN/UI primitives (button, card, dialog, etc.)
*   `/src/components/dashboard/`: 18 feature components (stock detail, market indices, sector performance, volume anomaly, vn30-overview-table)
*   `/src/components/layout/`: 4 layout components (sidebar, header, breadcrumb, separator)
*   `/src/lib/utils.ts`: Utility functions, including `cn` for Tailwind class merging
*   `/src/lib/query-keys.ts`: Centralized TanStack Query key factory
*   `/src/lib/api.ts`: Client-side API client configuration
*   `/src/lib/api-server.ts`: Server-side fetch helpers (ISR 60s)
*   `/src/lib/supabase/`: Supabase client setup (client, server, middleware)
*   `/src/hooks/`: 10 custom hooks (use-stock-detail, use-market-indices, use-responsive, use-vn30-overview, etc.)

**Backend (apps/api/):**
*   `/src/main.py`: FastAPI app instance, CORS, routing setup
*   `/src/core/config.py`: Settings, environment variables
*   `/src/core/database.py`: SQLAlchemy engine, session, base model
*   `/src/core/scheduler.py`: APScheduler configuration, job management
*   `/src/core/redis.py`: Upstash Redis client setup
*   `/src/core/cache.py`: TradingHoursCache class for time-sensitive caching
*   `/src/core/ratelimit.py`: Redis-based rate limiting middleware
*   `/src/stocks/router.py`: 25+ API endpoint aggregation
*   `/src/stocks/service.py`: vnstock library integration, business logic
*   `/src/stocks/schemas/`: Pydantic models (price, market incl. VN30OverviewItem/Response, company, financial)
*   `/src/stocks/schemas/market_context.py`: Schemas for market context API (ChartDataPoint, MarketMetrics, SectorContext, PerformanceSummary, MarketContextResponse)
*   `/src/stocks/models.py`: SQLAlchemy IntradayBar model
*   `/src/stocks/intraday_collector.py`: Intraday data collection, volume anomaly detection
*   `/src/stocks/jobs.py`: Scheduled jobs (collection, cleanup, market context EOD)
*   `/src/stocks/market_context_service.py`: EOD pipeline for computing market metrics (breadth, sector, volatility)
*   `/src/stocks/market_context_api_service.py`: Service layer for market context API endpoint (normalization, metrics aggregation)
*   `/src/stocks/market_context_router.py`: Manual trigger endpoints for EOD pipeline and backfill
*   `/src/stocks/{market,price,company,financial}/`: Domain-specific routers and services
*   `/src/stocks/price/router.py`: Price endpoints including market context analysis
*   `/alembic/`: Database migration scripts
*   `/requirements.txt`: Python dependencies
*   `/tests/test_market_context_api.py`: Test suite for market context API endpoint

## 7. Development Setup Instructions

**Prerequisites:**
*   Node.js 18+
*   Python 3.11+
*   Docker & Docker Compose
*   pnpm (for frontend)

**Quick Start (Docker):**
1.  `git clone <repo-url>`
2.  `cd Stock_Massive`
3.  `cp apps/api/.env.example apps/api/.env`
4.  `cp apps/web/.env.example apps/web/.env`
5.  `docker-compose up -d`
    *   Frontend: `http://localhost:3000`
    *   Backend API: `http://localhost:8000`
    *   API Docs: `http://localhost:8000/docs`

**Manual Setup:**
*   **Frontend (`apps/web`):**
    1.  `cd apps/web`
    2.  `pnpm install`
    3.  `pnpm dev`
*   **Backend (`apps/api`):**
    1.  `cd apps/api`
    2.  `python -m venv .venv`
    3.  Activate virtual environment (e.g., `source .venv/bin/activate` for macOS/Linux)
    4.  `pip install -r requirements.txt`
    5.  `uvicorn src.main:app --reload --host 0.0.0.0 --port 8000`

**Database Migrations:**
*   `cd apps/api`
*   `alembic revision --autogenerate -m "description"`
*   `alembic upgrade head`

## 8. Any Notable Conventions or Patterns

**Code Standards:**
*   **DRY, KISS, YAGNI**: Principles guiding development (Don't Repeat Yourself, Keep It Simple, You Ain't Gonna Need It).
*   **Frontend Naming**: `kebab-case.tsx` for components, `use-kebab-case.ts` for hooks.
*   **Backend Naming**: `snake_case.py` for modules, `PascalCase` for classes, `snake_case` for functions/variables.
*   **Type Hinting**: Extensive use of TypeScript for frontend and Python type hints for backend.
*   **Consistent Error/Loading States**: Standardized patterns for displaying skeleton loaders and error messages.

**Design Guidelines (Modern + Clean):**
*   **HSL Color System**: All colors defined using HSL CSS variables for easy theming.
*   **Dark/Light Theme**: Full support implemented via `next-themes`.
*   **ShadCN/UI**: Standard component library, strongly preferred over custom UI implementations.
*   **Responsive Design**: Mobile-first approach.
*   **Accessibility**: Focus on keyboard navigation, semantic HTML, ARIA labels, and color contrast.
*   **Animation Patterns**: Purposeful animations for transitions and feedback.

**Git Conventions:**
*   **Branch Naming**: `feature/`, `fix/`, `refactor/` prefixes.
*   **Commit Messages**: Conventional Commits (e.g., `feat(scope): description`).

**API Design:**
*   **RESTful Principles**: Plural nouns for collections, kebab-case for multi-word segments, logical nesting.
*   **Versioning**: `/api/v1/` prefix.
*   **JSON Responses**: Consistent JSON format with `snake_case` fields.
*   **Query Parameters**: Validated using FastAPI's `Query` dependency.
*   **Error Handling**: Standardized error response format and HTTP status codes.
*   **Security**: CORS configuration, Pydantic input validation.
