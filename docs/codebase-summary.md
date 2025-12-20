# Codebase Summary - Stock Massive

## 1. Project Overview and Purpose

Stock Massive is a Vietnamese stock market data platform powered by the `vnstock` library. Its primary purpose is to provide real-time data, charting, and analysis for the Vietnam stock market (HOSE, HNX, UPCOM).

**Goals:**
*   Display Vietnamese stock data with interactive charts.
*   Provide sortable/filterable data tables for stock screening.
*   Enable portfolio tracking and watchlist management (planned).
*   Secure user authentication and data persistence (planned).
*   Integrate `vnstock` library for comprehensive Vietnam market data.
*   Implement and visualize advanced analytical features like Volume Anomaly Detection.

## 2. Tech Stack

**Frontend:**
*   **Framework**: Next.js 14.2 (App Router)
*   **Language**: TypeScript 5.x
*   **Styling**: TailwindCSS 3.4, ShadCN/UI (Radix-based component library)
*   **Data Fetching**: TanStack Query v5
*   **Charting**: TradingView Lightweight Charts (planned for full integration)
*   **State Management**: `useState` for local, URL search params for shared, `next-themes` for theme.
*   **Notifications**: Sonner

**Backend:**
*   **Framework**: FastAPI 0.100+
*   **Language**: Python 3.11+
*   **ORM**: SQLAlchemy 2.0
*   **Migrations**: Alembic
*   **Data Validation**: Pydantic 2.x
*   **ASGI Server**: Uvicorn
*   **Data Source**: `vnstock >= 3.0.0` (VCI source), Fmarket API (for fund data)
*   **Scheduler**: APScheduler 4.0
*   **Volume Anomaly Libraries**: Pandas, Greenlet
*   **Caching**: Redis (for extended caching, including `TradingHoursCache`, volume anomaly detection, market data)

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
*   **Dashboard Layout**: Responsive sidebar, header, dark/light theme toggle.
*   **Stock Detail Page**: Comprehensive view with search, ticker header, stats panel, and tabbed sections.
*   **Market Indices**: Cards displaying VN-INDEX, VN30, HNX, UPCOM with sparklines.
*   **Stock Data API**: 27 endpoints via `vnstock` for various data types.
*   **Financial Data**: Detailed income statements, balance sheets, and cash flow statements.
*   **Shareholders/Officers**: Data on major holders, company management, and insider deals.
*   **Volume Analysis**: 5-minute bar aggregation and peak period analysis.
*   **Intraday Data Collection**: Scheduled daily collection of intraday data.
*   **Volume Anomaly Detection**: Backend API and frontend visualization for detecting and displaying volume anomalies, with advanced Redis caching (trading-hours aware TTL, graceful degradation).
*   **Sector Performance**: ICB Level 2 sector performance with sorting and top gainers/losers.
*   **Fund Certificates**: Endpoint and display for fund certificates data.
*   **Loading/Error States**: Consistent use of skeleton loaders and error handling across the frontend.
*   **API Documentation**: Auto-generated OpenAPI/Swagger UI.

**Planned (Roadmap):**
*   **Authentication System**: User registration, login (JWT), password hashing, token refresh, protected routes.
*   **Stock Charts**: Integration of TradingView Lightweight Charts for candlestick, line, and area charts with time interval selection and volume overlay.
*   **Stock List & Screening**: Data tables with sorting, filtering, and search functionality using TanStack Table.
*   **Watchlist Management**: Create, delete, add/remove stocks from watchlists.
*   **Portfolio Tracking**: Add positions, calculate P&L, track history.
*   **Technical Analysis**: Implement indicators like SMA, EMA, RSI, MACD, Bollinger Bands.
*   **Alerts & Notifications**: Price alerts, email/in-app notifications.

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

*   `/apps/web/src/app/layout.tsx`: Root layout for the Next.js application, including providers.
*   `/apps/web/src/components/ui/`: Contains ShadCN/UI components.
*   `/apps/web/src/components/dashboard/`: Feature-specific UI components for the dashboard.
*   `/apps/web/src/lib/utils.ts`: Utility functions, including `cn` for Tailwind class merging.
*   `/apps/web/src/lib/query-keys.ts`: Centralized query key factory for TanStack Query.
*   `/apps/api/src/main.py`: Main FastAPI application instance and routing setup.
*   `/apps/api/src/core/config.py`: Application settings and environment variable loading.
*   `/apps/api/src/core/database.py`: SQLAlchemy engine, session, and base model definitions.
*   `/apps/api/src/core/scheduler.py`: APScheduler configuration and job management.
*   `/apps/api/src/core/redis.py`: Redis client setup and utilities for caching.
*   `/apps/api/src/core/cache.py`: Generic `TradingHoursCache` class for time-sensitive data caching.
*   `/apps/api/src/stocks/router.py`: Aggregates all stock-related API routes.
*   `/apps/api/src/stocks/service.py`: Central service for interacting with the `vnstock` library and implementing business logic.
*   `/apps/api/src/stocks/schemas/`: Pydantic models for API request/response validation.
*   `/apps/api/src/stocks/models.py`: SQLAlchemy declarative models for the PostgreSQL database.
*   `/apps/api/src/stocks/intraday_collector.py`: Logic for collecting intraday data and detecting volume anomalies.
*   `/alembic/env.py`: Alembic environment script for database migrations.
*   `/docker-compose.yml`: Defines Docker services for web, api, and database.
*   `/repomix-output.xml`: The generated compaction of the codebase for AI analysis.

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
