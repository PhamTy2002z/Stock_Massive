# Codebase Summary

This document provides a high-level overview of the Stock Massive project's codebase, derived from recent scouting and `repomix` analysis.

## Project Structure

The project is structured as a monorepo with separate `apps` for the frontend and backend, and shared `packages`.

```
Stock_Massive/
├── apps/
│   ├── web/                 # Next.js frontend (port 3000)
│   │   └── src/
│   │       ├── app/         # App Router (page.tsx, layout.tsx, not-found.tsx)
│   │       ├── components/  # ui/, dashboard/, layout/, providers/
│   │       ├── hooks/       # Custom React hooks
│   │       └── lib/         # API clients, query keys, utilities
│   │
│   └── api/                 # FastAPI backend (port 8000)
│       └── src/
│           ├── stocks/      # Feature-based modules (market, price, company, financial)
│           │   ├── router.py, service.py, schemas/, models.py
│           │   ├── market/  # Symbols, sectors, fund certificates
│           │   ├── price/   # History, intraday, indices, volume analysis
│           │   ├── company/ # Company info
│           │   └── financial/ # Financials, ratios
│           ├── core/        # config.py, database.py, scheduler.py
│           └── main.py
│
├── packages/                # Shared code (config/, types/)
├── docker/                  # Docker configs
└── docs/                    # Documentation
```

## Frontend (apps/web)

-   **Framework**: Next.js 14.2 with TypeScript
-   **Styling**: TailwindCSS 3.4, ShadCN/UI
-   **State Management**: React Query for server state, React hooks for local UI state
-   **UI Components**:
    -   **UI**: 16 components (alert, avatar, button, card, collapsible, dropdown-menu, input, select, separator, sheet, skeleton, sonner, sparkline, spinner, tabs, tooltip)
    -   **Dashboard**: 19 components (finance-tab-content, fund-certificates, market-indices, sector-performance, shareholders-tab-content, stock-company-info, stock-detail-* (client, empty, error, panel, skeleton, tabs), stock-index-card, stock-search-bar, stock-stats-table, stock-ticker-header, volume-anomaly-chart, volume-tab-content)
    -   **Layout**: 4 components (app-sidebar, dashboard-header, dashboard-layout, dashboard-layout-client)
    -   **Providers**: 2 components (query-provider for React Query, theme-provider for dark/light mode)
-   **Custom Hooks**: 9 hooks (use-balance-sheet, use-cash-flow, use-fund-certificates, use-income-statement, use-mobile, use-sector-performance, use-shareholders, use-stock-detail, use-volume-analysis)

## Backend (apps/api)

-   **Framework**: FastAPI with Python 3.11+
-   **Libraries**: `vnstock >= 3.0.0`, SQLAlchemy 2.0, APScheduler
-   **Architecture**: Feature-based modular structure within the `stocks` directory.
-   **Key Routers/Endpoints**:
    -   `/api/v1/stocks/symbols`: List/search stock symbols
    -   `/api/v1/stocks/{symbol}/history`: Historical OHLCV data
    -   `/api/v1/stocks/{symbol}/intraday`: Intraday data
    -   `/api/v1/stocks/market-indices`: VN-INDEX, VN30, HNX, UPCOM
    -   `/api/v1/stocks/price-board`: Real-time stock prices
    -   `/api/v1/stocks/{symbol}/company`: Company information
    -   `/api/v1/stocks/{symbol}/financials/*`: Financial statements (balance sheet, income statement, cash flow)
    -   `/api/v1/stocks/{symbol}/shareholders`: Major shareholder data
    -   `/api/v1/stocks/{symbol}/officers`: Company officer information
    -   `/api/v1/stocks/{symbol}/insider-deals`: Insider trading information
    -   `/api/v1/stocks/{symbol}/volume-analysis`: Basic volume analysis
    -   `/api/v1/stocks/{symbol}/volume-anomalies`: Volume anomaly detection (NEW)
    -   `/api/v1/stocks/sector-performance`: ICB Level 2 sector performance (top gainers/losers)
    -   `/api/v1/stocks/fund-certificates`: Fund data from Fmarket
    -   `/api/v1/stocks/intraday/collect`: Manual trigger for intraday data collection
-   **Database Model**: `StockIntradayBar` (stores 5-minute OHLCV bars)
-   **Scheduler**: APScheduler is used for daily intraday data collection and cleanup tasks.
-   **Data Sources**: Primarily `vnstock` library (VCI source) for market data, and Fmarket API for fund certificates.

## Database

-   **Type**: PostgreSQL 16
-   **Containerization**: Managed via Docker.

## DevOps

-   **Tools**: Docker, Docker Compose, pnpm
-   **Services**:
    -   `db`: `postgres:16-alpine`
    -   `api`: `python:3.11-slim` running Uvicorn
    -   `web`: `node:20-alpine` running `npm run dev`

## Recent Major Features (Dec 2025)

-   **Volume Anomaly Detection**: Fully implemented with a new backend API endpoint (`/api/v1/stocks/{symbol}/volume-anomalies`) and a corresponding frontend visualization component (`volume-anomaly-chart`).
-   **Fund Certificates Display Adjustment**: Frontend now displays 7 items instead of 6 for fund certificates.
-   **Sector Performance Enhancement**: The sector performance feature now includes top gainers/losers information.

This summary provides a foundational understanding of the project's technical landscape and recent developments.