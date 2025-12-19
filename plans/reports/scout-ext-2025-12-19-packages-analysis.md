# Packages Directory Analysis Report

**Date:** 2025-12-19  
**Scout ID:** ab7fa1d  
**Scope:** D:\Stock_Massive\packages\

---

## Executive Summary

The `packages/` directory contains **placeholder directories only** with `.gitkeep` files. No shared packages are currently implemented. Types and configurations are **duplicated** between apps rather than shared.

---

## 1. Package Structure

```
packages/
├── config/
│   └── .gitkeep          # Empty placeholder
└── types/
    └── .gitkeep          # Empty placeholder
```

**Status:** Both directories are scaffolded but contain no actual code.

---

## 2. Current Type Definitions (Not Shared)

### API Types (Python - Pydantic)
**File:** `D:\Stock_Massive\apps\api\src\stocks\schemas.py`

| Schema | Purpose |
|--------|---------|
| `StockPrice` | Historical OHLCV data |
| `IntradayTick` | Intraday tick data |
| `CompanyOverview` | Company info |
| `StockSymbol` | Symbol listing |
| `FinancialRatio` | PE, PB, ROE, etc. |
| `IncomeStatementRow/Response` | Income statement |
| `BalanceSheetRow/Response` | Balance sheet |
| `CashFlowRow/Response` | Cash flow |
| `PriceBoardItem` | Real-time prices |
| `MarketIndexItem` | VN-INDEX, VN30, etc. |
| `StockDetail` | Comprehensive stock data |
| `ShareholderItem/Response` | Major shareholders |
| `OfficerItem/Response` | Company officers |
| `InsiderDealItem/Response` | Insider trades |
| `SectorPerformanceItem/Response` | Sector data |
| `FundCertificateItem/Response` | ETF/fund data |
| `VolumeTimePeriod/AnalysisResponse` | Volume analysis |
| `IntradayBar/Create/CollectionResult` | Intraday bars |

### Web Types (TypeScript)
**File:** `D:\Stock_Massive\apps\web\src\lib\api.ts`

| Interface | Purpose |
|-----------|---------|
| `PriceBoardItem` | Price board data |
| `MarketIndex` | Market indices |
| `StockSymbol` | Symbol search |
| `StockDetail` | Stock details |
| `IncomeStatementRow/Response` | Income statement |
| `BalanceSheetRow/Response` | Balance sheet |
| `CashFlowRow/Response` | Cash flow |
| `ShareholderItem/Response` | Shareholders |
| `OfficerItem/Response` | Officers |
| `InsiderDealItem/Response` | Insider deals |
| `SectorPerformanceItem/Response` | Sector perf |
| `FundCertificateItem/Response` | Fund certs |

**Note:** Types are manually duplicated between Python and TypeScript.

---

## 3. Configuration Exports

### API Configuration
**File:** `D:\Stock_Massive\apps\api\src\core\config.py`

```python
class Settings(BaseSettings):
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False
    
    # Database
    database_url: str = "postgresql://..."
    
    # JWT
    jwt_secret, jwt_algorithm, jwt_expire_minutes
    
    # Vnstock
    vnstock_source: str = "VCI"
    
    # Scheduler
    scheduler_enabled, intraday_collect_hour/minute
    intraday_symbols, intraday_retention_days
```

### Web Configuration
- Uses `NEXT_PUBLIC_API_URL` env var (default: `http://localhost:8000/api/v1`)
- No shared config package

---

## 4. Database Layer

**File:** `D:\Stock_Massive\apps\api\src\core\database.py`
- SQLAlchemy 2.0 async with asyncpg
- `Base` declarative base class
- `get_db()` dependency for sessions

**Models:** `D:\Stock_Massive\apps\api\src\stocks\models.py`
- `StockIntradayBar` - 5-min OHLCV bars

---

## 5. Package Consumption Analysis

### Current State
- **No cross-package imports** - apps are independent
- Types duplicated manually between Python/TypeScript
- No shared utilities or constants

### Potential Shared Packages

| Package | Contents | Consumers |
|---------|----------|-----------|
| `@stock-massive/types` | TypeScript interfaces | web |
| `@stock-massive/config` | Shared constants, env vars | web, api |
| `@stock-massive/utils` | Formatters, validators | web |

---

## 6. Key File Paths

### Packages (Placeholders)
- `D:\Stock_Massive\packages\config\.gitkeep`
- `D:\Stock_Massive\packages\types\.gitkeep`

### API Core
- `D:\Stock_Massive\apps\api\src\core\config.py`
- `D:\Stock_Massive\apps\api\src\core\database.py`
- `D:\Stock_Massive\apps\api\src\stocks\schemas.py`
- `D:\Stock_Massive\apps\api\src\stocks\models.py`

### Web Core
- `D:\Stock_Massive\apps\web\src\lib\api.ts` (types + API client)
- `D:\Stock_Massive\apps\web\src\lib\utils.ts` (cn utility)

### App Configs
- `D:\Stock_Massive\apps\web\package.json`
- `D:\Stock_Massive\apps\api\requirements.txt`

---

## 7. Recommendations

1. **Implement shared types package** - Generate TS types from Pydantic schemas
2. **Add shared constants** - Market symbols, API endpoints, formatters
3. **Consider OpenAPI codegen** - Auto-generate TS client from FastAPI

---

## Unresolved Questions

1. Is there a plan to implement the packages/ directory?
2. Should types be auto-generated from API schemas?
3. Are there plans for additional shared utilities?
