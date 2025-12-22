# Brainstorm: Top 50 Most Profitable Companies Feature

**Date:** 2024-12-22
**Status:** Research Complete
**Target:** `/analytics/top-performers` page

---

## Problem Statement

Implement a dashboard feature displaying top 50 most profitable companies from the most recent quarter at `http://localhost:3000/analytics/top-performers`.

---

## Vnstock Data Assessment

### Available Data Sources

| Method | Source | Data | Rate Limit Risk |
|--------|--------|------|-----------------|
| `Screener().stock()` | TCBS | Basic stock info, exchanges | Single call, low risk |
| `Listing().all_symbols()` | VCI | ~1700 symbols | Single call, low risk |
| `Finance().income_statement(period='quarter')` | VCI | Net profit, revenue, EPS per symbol | **HIGH** - 1 call/symbol |
| `finance.ratio()` | VCI | ROE, ROA, P/E per symbol | **HIGH** - 1 call/symbol |

### Key Finding: No Batch Financial Endpoint

Vnstock **does not provide** a batch endpoint for financial data across all stocks. Getting profit data requires:
- 1 API call per symbol for `income_statement()`
- ~1700 symbols on Vietnam exchanges
- Estimated ~1700 API calls minimum

### Rate Limit Reality

From `vnstock_wrapper.py`:
```python
base_delay: float = 2.0    # 2 sec between retries
max_delay: float = 60.0    # cap at 60 sec
max_retries: int = 3       # 3 retry attempts
```

**Calculation for sequential fetching:**
- 1700 symbols × 1.5s adaptive delay = **~42 minutes** (best case)
- With rate limit hits: **2-4 hours** realistically
- vnstock calls `sys.exit()` on rate limit (wrapper catches this)

---

## Evaluated Approaches

### Approach 1: Real-time Batch Fetch (NOT RECOMMENDED)

**How:** Fetch all ~1700 income statements on page load, sort, return top 50.

**Pros:**
- Always current data
- Simple logic

**Cons:**
- 42+ minute response time - unusable
- High rate limit risk - API will block
- Server resource exhaustion
- Poor UX

**Verdict:** ❌ Not feasible

---

### Approach 2: Pre-computed with Scheduled Job (RECOMMENDED)

**How:**
1. Add scheduled job (daily/weekly) to fetch financial data for all stocks
2. Store results in PostgreSQL table `top_performers`
3. API endpoint serves cached data instantly

**Architecture:**
```
Scheduled Job (off-hours) → Fetch all financials → Store in DB
                                    ↓
Frontend request → API reads from DB → Return top 50 instantly
```

**Pros:**
- Fast response (<100ms)
- Rate limit friendly - spread calls overnight
- Cacheable with Redis
- Predictable server load

**Cons:**
- Data staleness (acceptable - quarterly financials don't change hourly)
- Initial setup complexity
- Requires new DB table

**Implementation Steps:**
1. Create `TopPerformerEntry` SQLAlchemy model
2. Add scheduled job in `stocks/jobs.py` (run 2-4 AM ICT)
3. New endpoint `GET /api/v1/stocks/top-performers`
4. Frontend table component with TanStack Query

**Verdict:** ✅ Recommended

---

### Approach 3: Screener + Limited Financial Fetch (ALTERNATIVE)

**How:**
1. Use `Screener().stock()` to get all stocks with market cap
2. Filter to top ~100 by market cap (larger companies = usually more profitable)
3. Fetch income statements for only those 100 stocks
4. Sort by net profit, return top 50

**Pros:**
- Reduces API calls from 1700 to ~100
- Can run on-demand with reasonable latency (~3-5 min)
- No DB changes required

**Cons:**
- Heuristic assumption (market cap ≠ profitability)
- May miss small but highly profitable companies
- Still slow for real-time use

**Verdict:** ⚠️ Compromise option if avoiding DB changes

---

### Approach 4: VN30/VN100 Subset Only (SIMPLEST)

**How:**
1. Use `symbols_by_group('VN30')` or `VN100` (30-100 stocks)
2. Fetch income statements for only these
3. Sort by quarterly net profit

**Pros:**
- Only 30-100 API calls
- Real-time feasible (~1-3 min)
- Covers most market cap anyway
- No DB changes

**Cons:**
- Limited to index constituents
- Misses mid/small cap gems

**Verdict:** ✅ Good for MVP/quick win

---

## Recommended Solution

### Primary: Approach 2 (Scheduled Job + DB)

For production-grade feature with complete coverage.

**Database Schema:**
```sql
CREATE TABLE top_performers (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    company_name VARCHAR(255),
    quarter INT NOT NULL,
    year INT NOT NULL,
    net_profit BIGINT,
    revenue BIGINT,
    profit_margin FLOAT,
    eps FLOAT,
    rank INT,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, year, quarter)
);

CREATE INDEX ix_top_performers_rank ON top_performers(rank);
CREATE INDEX ix_top_performers_period ON top_performers(year, quarter);
```

**Scheduled Job Strategy:**
- Run at 2:00 AM ICT (off-market hours)
- Batch processing with 2s delay between calls
- Track progress in Redis (resume on failure)
- ~2-3 hours to complete full scan
- Run weekly (quarterly data doesn't change often)

### Alternative MVP: Approach 4 (VN30/VN100)

For quick implementation and validation.

---

## API Design

```
GET /api/v1/stocks/top-performers
  ?period=quarter (default) | year
  ?limit=50 (default, max 100)
  ?scope=all | vn30 | vn100

Response:
{
  "period": "Q4-2024",
  "updated_at": "2024-12-22T02:00:00Z",
  "data": [
    {
      "rank": 1,
      "symbol": "VCB",
      "company_name": "Vietcombank",
      "net_profit": 12500000000000,
      "revenue": 45000000000000,
      "profit_margin": 27.8,
      "eps": 3250,
      "quarter": 4,
      "year": 2024
    }
  ]
}
```

---

## Frontend Components

```
apps/web/src/app/analytics/top-performers/
├── page.tsx                     # Main page
├── components/
│   ├── top-performers-table.tsx # Data table with sorting
│   ├── period-selector.tsx      # Q1-Q4, Year selector
│   └── scope-toggle.tsx         # All/VN30/VN100 toggle
```

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Rate limit during batch job | High | Exponential backoff, resume capability |
| Data staleness | Low | Show "Last updated" timestamp, weekly refresh |
| Partial data (API failures) | Medium | Track failed symbols, retry next run |
| vnstock API changes | Medium | Monitor, version pin |

---

## Success Metrics

- Page load time: <500ms
- Data freshness: <7 days old
- Coverage: 95%+ of listed stocks
- Zero rate limit errors during batch job

---

## Next Steps

1. **Decision needed:** Full implementation (Approach 2) vs MVP (Approach 4)?
2. If Approach 2: Create DB migration, scheduled job, endpoint
3. If Approach 4: Implement VN30/VN100 subset endpoint first
4. Build frontend table component
5. Add caching layer

---

## Unresolved Questions

1. **Scope preference:** Should we start with VN30/VN100 MVP or full market coverage?
2. **Refresh frequency:** Daily vs weekly scheduled job?
3. **Profitability metric:** Net profit absolute value or profit margin %?
4. **Historical data:** Show only latest quarter or allow period selection?
