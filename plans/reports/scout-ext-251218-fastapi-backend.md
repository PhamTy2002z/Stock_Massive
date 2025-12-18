# Scout Report: FastAPI Backend

**Date:** 2024-12-18  
**Path:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api`  
**Status:** Bootstrap stage - feature-based modular architecture

---

## 1. Main Application Entry Point

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/main.py`

- FastAPI app with title "Stock Massive API"
- CORS configured for `http://localhost:3000`
- Mounts stocks router at `/api/v1`
- Health endpoints: `/` and `/health`

```python
app = FastAPI(
    title="Stock Massive API",
    description="Stock analysis platform API with Vietnamese market data",
    version="0.1.0",
)
```

---

## 2. API Routes and Endpoints

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/router.py`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/stocks/symbols` | GET | List all stock symbols (filter by exchange) |
| `/api/v1/stocks/symbols/group/{group}` | GET | List symbols by group (VN30, HNX30, etc) |
| `/api/v1/stocks/{symbol}/history` | GET | Historical OHLCV data |
| `/api/v1/stocks/{symbol}/intraday` | GET | Intraday tick data |
| `/api/v1/stocks/price-board` | GET | Real-time price board (multi-symbol) |
| `/api/v1/stocks/{symbol}/company` | GET | Company overview |
| `/api/v1/stocks/{symbol}/financials/ratios` | GET | Financial ratios |
| `/api/v1/stocks/{symbol}/financials/income` | GET | Income statement |
| `/api/v1/stocks/{symbol}/financials/balance-sheet` | GET | Balance sheet |

**Placeholder directories (empty):**
- `src/api/v1/endpoints/` - future versioned endpoints
- `src/auth/` - future authentication
- `src/workers/tasks/` - future background tasks

---

## 3. Services and Business Logic

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/service.py` (~504 lines)

**StockService class** wraps `vnstock` library for Vietnamese market data:

| Method | Purpose |
|--------|---------|
| `get_history()` | Historical OHLCV via `Quote.history()` |
| `get_intraday()` | Tick data via `Quote.intraday()` |
| `get_company_overview()` | Company info via `Vnstock().stock().company.overview()` |
| `get_financial_ratios()` | Ratios via `Finance.ratio()` |
| `get_income_statement()` | Income via `Finance.income_statement()` |
| `get_balance_sheet()` | Balance via `Finance.balance_sheet()` |
| `list_symbols()` | All symbols via `Listing().all_symbols()` |
| `list_symbols_by_group()` | Group symbols via `Listing().symbols_by_group()` |
| `get_price_board()` | Real-time via `Trading().price_board()` |

**Key patterns:**
- Singleton pattern via `get_stock_service()`
- Custom `StockServiceError` exception
- Symbol validation with regex `^[A-Z0-9]{1,10}$`
- DataFrame to Pydantic model conversion helpers

---

## 4. Schemas and Data Models

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/stocks/schemas.py`

| Schema | Purpose |
|--------|---------|
| `StockPrice` | Historical OHLCV (time, open, high, low, close, volume) |
| `IntradayTick` | Tick data (time, price, volume, match_type) |
| `CompanyOverview` | Company info (name, exchange, industry, etc) |
| `StockSymbol` | Symbol listing (symbol, organ_name, exchange) |
| `FinancialRatio` | Ratios (ROE, ROA, P/E, P/B, margins, etc) |
| `IncomeStatementItem` | Income (revenue, gross_profit, net_income, EPS) |
| `BalanceSheetItem` | Balance (assets, liabilities, equity, cash) |
| `PriceBoardItem` | Real-time (ceiling, floor, ref_price, change) |
| `ErrorResponse` | Standard error (detail, code) |

---

## 5. Core Utilities and Config

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/config.py`

```python
class Settings(BaseSettings):
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False
    database_url: str = "postgresql://postgres:postgres@localhost:5432/stockmassive"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30
    vnstock_source: str = "VCI"
```

**File:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/src/core/dependencies.py`
- `SettingsDep` - FastAPI dependency for settings injection

---

## 6. Tests Structure

**Directory:** `/Users/typham/Documents/GitHub/Stock_Massive/apps/api/tests/`

| File | Coverage |
|------|----------|
| `conftest.py` | Fixtures: `client`, `valid_symbol`, `valid_symbols` |
| `test_stocks_router.py` | 18 endpoint tests (validation, happy path, errors) |
| `test_stocks_service.py` | 12 service layer tests |

**Test patterns:**
- Uses `TestClient` from FastAPI
- Graceful handling of network issues (pytest.skip)
- Validates response schemas and error messages

---

## 7. Dependencies (requirements.txt)

| Category | Packages |
|----------|----------|
| **Core** | fastapi>=0.100.0, uvicorn, pydantic>=2.0.0, pydantic-settings |
| **Database** | sqlalchemy>=2.0.0, alembic>=1.12.0, asyncpg, psycopg2-binary |
| **Auth** | python-jose[cryptography], passlib[bcrypt], python-multipart |
| **Utils** | httpx>=0.25.0 |
| **Stock Data** | vnstock>=3.0.0 |
| **Dev** | pytest>=7.4.0, pytest-asyncio |

---

## 8. Infrastructure

**Dockerfile:** Python 3.11-slim, uvicorn with reload  
**Alembic:** Configured for DB migrations (versions dir empty)

---

## File Summary

| Path | Purpose |
|------|---------|
| `/apps/api/src/main.py` | App entry point |
| `/apps/api/src/stocks/router.py` | API endpoints |
| `/apps/api/src/stocks/service.py` | Business logic |
| `/apps/api/src/stocks/schemas.py` | Pydantic models |
| `/apps/api/src/core/config.py` | Settings |
| `/apps/api/src/core/dependencies.py` | DI helpers |
| `/apps/api/tests/conftest.py` | Test fixtures |
| `/apps/api/tests/test_stocks_router.py` | Router tests |
| `/apps/api/tests/test_stocks_service.py` | Service tests |
| `/apps/api/requirements.txt` | Dependencies |
| `/apps/api/Dockerfile` | Container config |
| `/apps/api/alembic.ini` | Migration config |

---

## Observations

1. **Well-structured** - Clean separation: router -> service -> schemas
2. **vnstock integration** - Wraps Vietnamese stock market library effectively
3. **Auth ready** - JWT config exists but auth module empty
4. **DB ready** - SQLAlchemy/Alembic configured but no models yet
5. **Workers ready** - Tasks directory placeholder exists
6. **Good test coverage** - Both unit and integration tests present
