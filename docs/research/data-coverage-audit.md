# Data coverage audit: `apps/api` vs the four analysis axes

Resolves wayfinder research ticket [#19](https://github.com/PhamTy2002z/Stock_Massive/issues/19).
Audited at commit `426c23b` (branch `develop`, 2026-08-10). All paths relative to `apps/api`.

The planned AI stock analyst needs four axes: **technical** (price/volume/trend), **fundamental**
(valuation, growth, financial-statement health), **money flow / foreign investor activity**, and
**news**. This audit maps what the API already serves on each axis, where the data comes from, how
fresh it is, how deep the history goes, and what is missing.

## Summary verdict

| Axis | Verdict |
|---|---|
| 1. Technical | **Mostly covered** for raw price/volume; **zero trend indicators** (no SMA/EMA/RSI/MACD anywhere) |
| 2. Fundamental | **Best-covered axis**: full statements, ratios, health score, F-score, trends, FCF, peers — but almost entirely live vnstock pass-through, thin persistence (4 line items/quarter) |
| 3. Money flow / foreign | **Biggest gap.** Adapters and storage exist (`providers/`, `provider_snapshots`) but are **unwired** — no collector runs them, no endpoint reads them. Only aggregate buy/sell tick stats are served |
| 4. News | **Not served at all.** Service methods and schemas exist as dead code; no route, no table, no sentiment |

A cross-cutting finding: the **Universe** (`src/stocks/universe.py`) is validated at startup but
gates nothing — no endpoint or collector consults it. The collectors that actually run use
unrelated symbol sets (`INTRADAY_SYMBOLS`, full-market listing, VN100/VN30 groups).

## How data flows today

Two parallel stacks exist:

1. **Legacy live path (what actually serves traffic).** Routers in `src/stocks/{market,price,company,financial,analytics,trading}` call vnstock at request time through `src/core/vnstock_client.py` (guarded proxy, max 4 concurrent calls) and cache responses in Redis via `TradingHoursCache` (`src/core/cache.py`; trading hours = Mon–Fri 09:00–15:00 ICT, separate TTLs for trading/off-hours, stale-on-failure where configured). Three Postgres tables back the few persisted reads.
2. **New provider/snapshot path (built, not wired).** `src/stocks/providers/` defines four capabilities (`MARKET`, `VALUATION` → FiinQuant main; `REFERENCE`, `FUNDAMENTAL` → vnstock main; `contracts.py`, per `docs/adr/0002`), fully implemented adapters (`fiinquant.py`, `vnstock_provider.py`), and `SnapshotStore` (`store.py`) writing the `provider_snapshots` table + Redis current view. **Zero production call sites**: no scheduler job, collector, or router imports any adapter or `SnapshotStore` (test files only). `provider_snapshots` is never written outside tests.

### Persistence (complete schema, 6 tables — `src/stocks/models.py`, `src/auth/models.py`)

| Table | Axis | Contents | History depth |
|---|---|---|---|
| `stock_daily_ohlcv` | Technical | OHLCV per symbol × trade date (no trade value, no adjusted close) | Accumulates only while `DAILY_OHLCV_ENABLED` job runs (each run fetches last **7 days**); **default off**, so empty by default. No pruning |
| `stock_intraday_bars` | Technical | 5-min bars: OHLCV + trade_value + trade_count | **30-day retention** (`INTRADAY_RETENTION_DAYS`, daily cleanup 16:00 ICT). Only `INTRADAY_SYMBOLS` (default 5: VCB,FPT,VNM,VIC,VHM) |
| `financial_statements` | Fundamental | Per symbol × year × quarter: net_profit, revenue, profit_margin, eps, rank. **Only 4 line items** | Weekly job (Sun 02:00, **on** by default) ingests **latest quarter only** — history accrues one quarter per week of uptime, no backfill |
| `provider_snapshots` | All 4 capabilities (JSON payload) | market/valuation/reference/fundamental snapshots incl. foreign buy/sell values, foreign room, share counts, P/E, P/B | **Never written in production** (unwired) |
| `users`, `refresh_tokens` | — | auth | — |

No table stores news, sentiment, dividends, ownership history, or per-order flow. A prior
market-context schema (`stock_daily_returns`, `stock_market_metrics`, `sector_daily_benchmark`)
was added in commit `def781e` and **reverted in `e0d4211`** "due to vnstock rate limits".

### Scheduler jobs (`src/core/scheduler.py`, cron in Asia/Ho_Chi_Minh; master switch `SCHEDULER_ENABLED=True`)

| Job | Schedule (default) | Writes | Enabled by default |
|---|---|---|---|
| `intraday-collection-daily` | 15:30 daily | `stock_intraday_bars` (5 symbols) | Yes — **but see defect note below** |
| `data-cleanup-daily` | 16:00 daily (hard-coded) | deletes intraday bars > 30 days | Yes |
| `daily-ohlcv-collection` | 16:00 daily | `stock_daily_ohlcv`, all listed symbols, 7-day window, batches of 50 | **No** (`DAILY_OHLCV_ENABLED=False`) — `config.py`: "the full-market job exhausts vnstock Guest quota and competes with interactive dashboard requests" |
| `collect-financial-statements` | Sun 02:00 weekly | `financial_statements` (HOSE+HNX, ~700+ symbols, 2s+ delay/symbol) | Yes (`FINANCIAL_STATEMENTS_ENABLED=True`) |
| `sector-historical-daily` | 15:45 daily | Redis only (`stock:sector_hist:`, TTL 24h) — no table | **No** (`SECTOR_HISTORICAL_ENABLED=False`) — "disabled until a persisted cache exists; otherwise every restart after 15:45 retries a broad vnstock scan and starves interactive requests" |

**vnstock quota is the binding constraint on everything above**: 20 req/min without
`VNSTOCK_API_KEY`, 60 with (`providers/vnstock_provider.py:56-57`; env-only by design, not a
pydantic setting). The running jobs use the legacy `src/core/vnstock_wrapper.py`
(retry/backoff/adaptive delay) which **shares no allowance** with the new `RequestPacer` in
`vnstock_provider.py` — two independent throttles against one account quota.

**Suspected defect (verified in code, not at runtime):** the scheduled intraday job
(`src/stocks/jobs.py:38`) opens `async_session_factory()` directly and never commits;
`IntradayCollector.save_bars` (`intraday_collector.py:141`) says "commit handled by get_db()
dependency", which is true only for the admin endpoint `POST /stocks/intraday/collect`. The
session context manager exits without commit, so the scheduled path's upserts appear to be rolled
back on close. The `GET /{symbol}/volume-anomalies` route commits explicitly, which may be what
has been keeping `stock_intraday_bars` populated in practice.

## Axis 1 — Technical (price/volume history, trend indicators)

| Data | Endpoint | Source at request time | Freshness | History depth |
|---|---|---|---|---|
| OHLCV history, intervals `1m,5m,15m,30m,1H,1D,1W,1M` | `GET /api/v1/stocks/{symbol}/history` | vnstock `Quote.history()` live, **no cache** | Live per request (quota-bound) | **No depth limit enforced** — as deep as vnstock serves; nothing persisted |
| Intraday ticks (current session) | `GET /{symbol}/intraday` | vnstock `Quote.intraday()`, no cache | Live | Current session only |
| Market indices (VNINDEX, VN30, HNXINDEX, UPCOMINDEX) | `GET /market-indices` | vnstock, 30-day window, last 2 closes | Cache 30s trading / 1h off | 1 day of change |
| Price board (ceiling/floor/ref, match, totals) | `GET /price-board` (max 50 symbols) | vnstock `Trading.price_board`; change/% derived locally | Cache 15s / 1h | Snapshot |
| 5-min bar volume profile | `GET /{symbol}/volume-analysis` | **DB `stock_intraday_bars`** | Collected daily 15:30 | ≤ 30 days, 5 symbols by default |
| Volume anomalies (72 slots/day, thresholds 1.5/2.0/3.0×) | `GET /{symbol}/volume-anomalies` | live collect + DB read-back (writes on GET) | Cache 60s / 1h | Baseline 5–60 days (default 20) |
| Daily volume spikes vs 20-day average, grouped by ICB sector | `GET /analytics/volume-spikes` | **DB `stock_daily_ohlcv`** + live industry mapping | Cache 5 min / 1h | Needs ≥21 rows in a 30-day window — empty unless the OHLCV job has run ≥1 month |
| 52-week high/low/avg volume | inside `GET /{symbol}/detail` | vnstock `ohlcv(count=260)` live | Cache 60s / 1h | 260 bars, computed per request |

**Gaps:**
- **No trend indicators at all.** Grep for `rsi|macd|sma|ema|bollinger|indicator` over `src/` returns nothing. `/{symbol}/trend-metrics` is fundamental trends, not price technicals.
- **No persisted price history by default.** The only durable daily-OHLCV store depends on a default-off job that fetches just 7 days per run and has no backfill job; the AI analyst cannot compute MA50/MA200 from local data.
- No adjusted close / corporate-action adjustment anywhere.
- Intraday coverage is 5 hard-coded symbols, not the Universe.

## Axis 2 — Fundamental (valuation, growth, statement health)

| Data | Endpoint | Source | Freshness | History depth |
|---|---|---|---|---|
| Ratio history (ROE/ROA, margins, P/E, P/B, P/S, liquidity, leverage) | `GET /{symbol}/financials/ratios` | vnstock `Finance.ratio()` **VCI** live | Cache 1h / 24h, stale 7d | All periods vnstock returns |
| Income / balance / cash-flow (summary + full line-item Vietnamese statements) | `GET /{symbol}/financials/{income,income-statement,balance-sheet,balance-sheet-detailed,cash-flow}` | vnstock `Finance.*` VCI live | Cache 1h / 24h, stale 7d | Detailed forms limited to **1–12 periods** (default 4) |
| Health score (0–100, 5 weighted dimensions) + simplified Piotroski F-score | `GET /{symbol}/health-score` | vnstock ratios **KBS** (VCI feed "still answers ratio queries with 2018 quarters") | Cache 1h / 24h; ratio layer 4h / 24h | 2 quarters of ratios + 1 of cash flow. Note: schema declares `f_score ≤ 9` but only **6 of 9** criteria are computed (`financial/health_scoring.py`) |
| Growth trends: revenue, profit, margins, ROE/ROA, CFO/CFI/CFF arrays | `GET /{symbol}/trend-metrics` | vnstock KBS, 3 fan-out calls | Cache 1h / 24h | **4–16 quarters** (default 8) |
| FCF, FCF margin/yield, cash-conversion cycle | `GET /{symbol}/fcf-analysis` | vnstock KBS | Cache 1h / 24h | Latest quarter only |
| Sector peer comparison (median + premium per metric) | `GET /analytics/sector-peers` | one vnstock ratio call **per peer** (5–20 peers) | Response 4h / 24h; partial results only 300s | Latest period per peer |
| Ratio summary (P/E, P/B, ROE, ROA, ROIC…) | `GET /{symbol}/ratio-summary`, also inside `/detail` | vnstock `ratio_summary()` | 1h / 24h, stale 7d | Snapshot |
| Profit ranking table (net_profit, revenue, margin, EPS, rank) | `GET /analytics/financial-statements` | **DB `financial_statements`** | Weekly job Sun 02:00 | One quarter per week of uptime; 4 line items only |

**Gaps:**
- Almost everything is a **live vnstock pass-through** — the analyst's fundamental context is hostage to quota and provider uptime; only 4 line items/quarter are durable.
- No valuation *history* endpoint (P/E / P/B time series) — `ValuationSnapshot` in the unwired provider path would carry it (FiinQuant `fetch_valuation` requires an explicit window, designed for backfill) but nothing runs it.
- F-score is 6/9 criteria; no YoY/CAGR growth computations (only raw arrays).
- Ratio data comes from **two different sources** depending on endpoint (VCI vs KBS), so numbers can disagree between `/financials/ratios` and `/health-score`.

## Axis 3 — Money flow / foreign investor activity

| Data | Endpoint | Source | Freshness | History depth |
|---|---|---|---|---|
| Intraday buy/sell order stats (counts, volumes, net, ATO/ATC) from tick `match_type` | `GET /{symbol}/intraday-order-stats` | vnstock `Market.equity().trades(source="KBS")` live | Cache 2 min trading / 30 min off | Latest session only |

That is the **entire** served surface on this axis, and it is aggregate matched-order flow — not
foreign, not proprietary.

**Built but unwired** (`src/stocks/providers/`): `MarketSnapshot` carries
`foreign_buy_volume/value_vnd`, `foreign_sell_*`, `foreign_net_value_vnd`,
`active_buy/sell_volume` (FiinQuant fields `bu,sd,fb,fs,fn`, 30-day lookback);
`ReferenceSnapshot` carries `current_foreign_room` / `total_foreign_room` + share counts
(vnstock). Staleness ceilings are defined (`store.py`: market 300s, reference 7d) but no job
populates them and no endpoint reads them. FiinQuant credentials (`FIINQUANT_USERNAME/PASSWORD`)
are read by nothing outside config.

**Gaps:**
- **No foreign buy/sell endpoint, no foreign-flow history, no foreign-room endpoint, no proprietary-trading data.** This axis is a design (ADR 0002) plus adapters awaiting a collector and read path.
- No money-flow indicators (accumulation/distribution, net-flow time series).

## Axis 4 — News

Nothing is served. Specifically:

- `CompanyService.get_company_news()` (`src/stocks/company/service.py:261`, vnstock `company.news()`) and `get_company_dividends()` exist, with `NewsItem`/`NewsResponse`/`DividendItem`/`DividendsResponse` schemas (`src/stocks/schemas/company.py`) — **no router references them; dead code**.
- Zero occurrences of "sentiment", "article", or "headline" in `apps/api/src`.
- No news table in any Alembic revision; no collector; no external news provider configured.

**Gaps:** the whole axis — routing the existing vnstock company-news call would be the cheapest
first step, but there is no persistence, no market-wide news, and no sentiment anywhere.

## Universe mechanics (product constraint: only Universe symbols are supported)

- Declared via env var `UNIVERSE_SYMBOLS` (comma-separated; `src/core/config.py:47`, parsed in `src/stocks/universe.py`). No config file, no DB table, no seed.
- Cap: `UNIVERSE_MAX_SYMBOLS = 100`. Parsing validates each symbol (`^[A-Z0-9]{1,10}$`), dedupes order-preserving **before** the cap, and **raises `UniverseConfigurationError` (never truncates)** past 100 distinct symbols. Empty declaration is legal.
- Enforcement point: app startup only — `get_universe()` is the first statement of the FastAPI lifespan (`src/main.py:36-40`), so a bad list aborts boot.
- **Nothing else consults it.** `Universe.contains` has no callers; no endpoint rejects non-Universe symbols; no collector iterates the Universe (they use `INTRADAY_SYMBOLS`, full-market listing, VN100/VN30). The Universe-driven collector described in `docs/adr/0001` is not implemented.
- **Deployment gap:** neither `docker-compose.yml` nor `docker-compose.prod.yml` forwards `UNIVERSE_SYMBOLS` (or `FIINQUANT_*`) into the `api` container, and there is no `env_file:` directive — in Docker the Universe is always empty. `.env.example` files also omit all `DAILY_OHLCV_*`, `FINANCIAL_STATEMENTS_*`, `SECTOR_HISTORICAL_*` keys.

## Top gaps, ranked for the AI analyst

1. **Money flow / foreign axis has no serving path** — adapters + `provider_snapshots` exist but no collector or endpoint is wired (ADR 0001/0002 unimplemented).
2. **News axis absent** — dead service code, no route, no storage, no sentiment.
3. **No technical indicators and no durable price history by default** — `DAILY_OHLCV_ENABLED=False`, 7-day fetch window, no backfill; indicators can't be computed from local data.
4. **Universe is decorative** — validated at boot, gates nothing, not forwarded into Docker; collectors run on unrelated symbol sets.
5. **Fundamental persistence is 4 fields/quarter, latest quarter only** — everything richer is a live quota-bound vnstock call, with VCI/KBS source inconsistency and an F-score capped at 6/9.
6. **Suspected intraday-commit defect** — the scheduled 15:30 job's session never commits (`src/stocks/jobs.py:38` + `intraday_collector.py:141`), so its writes appear to be discarded.
7. **Two uncoordinated vnstock throttles** (`vnstock_wrapper` retries vs `RequestPacer`) sharing one 20–60 req/min account quota.
