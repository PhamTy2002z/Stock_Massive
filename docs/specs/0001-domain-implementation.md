# Implementation specification — domain model of 2026-08

This specification turns the shared understanding recorded in `CONTEXT.md` and
`docs/adr/0001`, `0003`, `0004`, `0005` into buildable work. Anything not
derivable from it or from those artifacts is an open decision listed in
[Open decisions](#3-open-decisions), not a choice made silently during coding.

Terms in **bold** are glossary terms and always carry their `CONTEXT.md`
meaning.

> **Partly superseded.** §M0–§M2 stand as written. **§M3 and §M4 are superseded** by
> [`0002-alpha-desk-product.md`](0002-alpha-desk-product.md) and
> [`0003-intelligent-quant-architecture.md`](0003-intelligent-quant-architecture.md),
> which re-issue that work as A1–A7 against the persistence model, table names, and
> contracts settled after this spec was written. They are kept below as the record of
> what was assumed before those decisions closed; **do not build from them.** Four of the
> five entries under [Open decisions](#3-open-decisions) have since been settled and
> carry their resolutions there.

## 1. Where the code stands today

| Domain concept | Code today | Verdict |
| --- | --- | --- |
| **Provider Source**, **Adapter**, **Snapshot**, **Capability** | `src/stocks/providers/{contracts,store,fiinquant,vnstock_provider}.py` | Matches the model. Extend, do not rewrite. |
| **Main Source** / **Cover Source** | `SOURCE_OWNERSHIP_BY_CAPABILITY` in `providers/contracts.py` | Matches ADR-0002. |
| **Universe** | `src/stocks/universe.py`, cap 100, purely from config | Cap and composition must change (ADR-0003). |
| **Collector** | `src/stocks/collector.py` | Matches. Gains a cohort-aware symbol set. |
| **Backfill** | `src/stocks/backfill.py` | Matches ADR-0005's deep half. Needs fair rotation + retry backoff. |
| **Warm-up** | — | Missing entirely. |
| **Trading Day** | `src/core/trading_calendar.is_trading_day` is a weekday test | Not the domain concept. Keep it as a *scheduling* gate only. |
| **Profit Ranking Census**, **Cohort Version** | `FinancialStatement` + `financial_statements_collector.py` rank quarterly profit | Ancestor with the wrong shape. Superseded. |
| **Volume Spike** | `src/stocks/signals/{volume_spike,router}.py` | Built (M2). The legacy market-wide `stock_daily_ohlcv` path is gone; the table survives per §4. |
| **Watchlist**, **Analysis**, **Analysis Run** | `apps/web/src/app/(dashboard)/watchlist/_components/.gitkeep` | Missing entirely. Built by spec `0003` §A2. |
| **Thread**, **Turn**, **Tool Call Trace**, **Widget**, **Capability Probe** | — | Missing entirely. No LLM route is wired anywhere. Built by spec `0003` §A3, §A5, §A6. |
| **Signal Field**, **Signal Registry**, **Window Health**, `prepare_bars()` | — | Missing entirely. Built by spec `0003` §A1. |

Two legacy paths are *replaced*, not extended: the full-market
`stock_daily_ohlcv` volume-anomaly path and the `financial_statements` ranking.
Removal is scheduled in M2 and M1 respectively so no window exists where both a
correct and an incorrect answer are servable.

## 2. Milestones

Each milestone is independently shippable and ends at a stated exit criterion.
`M0 → M1 → M2` is a hard chain.

| ID | Title | Depends on | Status |
| --- | --- | --- | --- |
| M0 | Trading Day, market generation, Warm-up | — | built |
| M1 | Profit Ranking Census and Cohort Version | M0 | built |
| M2 | Volume Spike serving with coverage and provenance | M1 | built |
| ~~M3~~ | ~~Watchlist, Analysis, Analysis Run~~ | M0 | superseded by spec `0003` §A2 |
| ~~M4~~ | ~~Thread, Turn, Tool Call Trace, Widget, Capability Probe~~ | M3 | superseded by spec `0003` §A3/§A5/§A6 |

Spec `0003` re-issues the superseded pair as A1–A7 and adds the milestones those
decisions turned out to need — a signals foundation, an LLM boundary, the nightly
pipeline, and an evaluation gate.

Every milestone must pass the repository gates before it is called done:
`make test` in `apps/api`, and `pnpm type-check`, `pnpm lint`, `pnpm test`,
`pnpm build` in `apps/web`.

---

## M0 — Trading Day, market generation, Warm-up

### Scope

Give the system one data-derived answer to "which day is this", one monotonic
token for "has stored market data moved", and a repeatable way to load the
recent market window for a symbol.

### Trading Day

New module `src/stocks/trading_day.py`. A **Trading Day** is
`date(max(effective_at))` over `provider_snapshots` where `capability='market'`,
read in `VN_TZ` (`providers/normalize.VN_TZ`), and it is market-wide — never
per-symbol.

```python
def latest_trading_day(session) -> date | None
def trading_days_before(session, day: date, count: int) -> tuple[date, ...]
def trading_days_between(session, start: date, end: date) -> tuple[date, ...]
```

`trading_days_before` returns the `count` distinct Trading Days strictly before
`day`, newest first, and returns fewer than `count` when the store does not hold
them. It never pads with calendar days.

Market-wide resolution is the load-bearing decision. Resolving the 20-day
baseline per symbol would let a symbol with gaps silently reach further back and
average a different stretch of market than its peers; resolved market-wide, a
symbol missing any of those 20 days is *unevaluable* and says so.

`src/core/trading_calendar.is_trading_day` stays exactly as it is and keeps its
two callers in `scheduler.py` and `collector_schedule.py`. It answers "should we
attempt a cycle today", which is a weekday question. It must never be used to
date a **Snapshot**, an **Analysis**, or a signal. Add that sentence to its
docstring.

Requires a new index for the `max(effective_at)` and range scans:

```
ix_provider_snapshot_capability_effective  ON provider_snapshots (capability, effective_at DESC)
```

### Market generation

ADR-0005 requires that successful **Collector** and **Warm-up** transactions
advance a generation used in **Volume Spike** cache keys. Do not add a table:
the generation is

```sql
SELECT max(observed_at) FROM provider_snapshots WHERE capability = 'market'
```

It advances exactly when a market write commits, survives restart, and needs no
second thing to keep in step with the data. Expose it as
`market_generation(session) -> datetime | None` in `trading_day.py` and render
it into cache keys as an integer microsecond epoch.

### Warm-up

New module `src/stocks/warmup.py`. **Warm-up** loads recent **Main Source**
market history for one symbol so it becomes evaluable without waiting 21
**Collector** cycles. It is repeatable, bounded, and distinct from **Backfill**.

- Window: `WARMUP_WINDOW_TRADING_DAYS = 25` most recent sessions the Main Source
  will serve. Twenty-five, not twenty-one: the baseline needs 20 preceding plus
  the target day, and a spare few absorb a session the provider has not appended
  yet.
- Source: **Main Source** for `market` only. Warm-up never reads the **Cover
  Source** and never touches `valuation`, `reference`, or `fundamental`.
- Persistence: every session in the window is written through `SnapshotStore.save`,
  so repeats collapse on the existing identity constraint and a Warm-up can
  repair missed recent cycles.
- Entry points: called by M1 when a **Cohort Version** stages candidates, and by
  an operator command (below). It is never called from a serving request.

A dated-window read already exists: `MarketHistoryProvider` lives in
`backfill.py` with a single-symbol signature, and both `FiinQuantMarketProvider`
and `VnstockMarketHistoryProvider` implement it. Warm-up reuses it rather than
adding a second protocol for the same call. The protocol moves to
`providers/contracts.py` — it is now shared by two callers, and Warm-up must not
import from Backfill — and gains the `source` attribute both adapters already
carry, so `Warmup` can refuse the Cover Source at construction instead of
discovering the mistake as a wrong ratio weeks later.

### Backfill fairness

ADR-0005: "Backfill selection must use fair rotation and retry backoff so
repeatedly failing symbols cannot occupy every per-run slot."

In `src/stocks/backfill.py`, symbols still inside their backoff are dropped from
selection entirely and the rest are ordered by `updated_at ASC` (no record at
all sorts first), so the allowance becomes a rotation. Each failure sets
`next_attempt_at = now + min(2 ** attempts hours, 7 days)`.

The cap is a week rather than the day this spec first named: the load runs once
daily, so a backoff shorter than the interval between runs is no backoff at all.
The ordering is what makes the rotation fair; the cap is what stops a dead
symbol spending the allowance. Two columns on `symbol_backfills`:

```
attempts        INTEGER NOT NULL DEFAULT 0
next_attempt_at TIMESTAMPTZ NULL
```

A success resets `attempts` to 0 and clears `next_attempt_at`.

### Market catch-up

ADR-0005 requires a 23:00 retry when the Main Source has not advanced the
**Trading Day**. Add to `collector_schedule.py`: a job at 23:00 VN that compares
`latest_trading_day()` with the session it expected to close today; if the store
has not advanced and today is a weekday, run one more collection cycle. It obeys
the existing one-at-a-time guard.

### Operator commands

ADR-0005: census retry, Warm-up, and market catch-up are operator-triggerable
through the existing tracked-run mechanism (`src/stocks/jobs.py`,
`jobs_router.py`, `core/job_status_store.py`) and obey the same guards as
scheduled work. Register three tracked jobs: `warmup`, `market_catchup`, and
(in M1) `profit_census`. They are admin-only, reusing the `is_admin` gate.

### Config

```python
warmup_window_trading_days: int = 25
market_catchup_enabled: bool = True
market_catchup_hour: int = 23
market_catchup_minute: int = 0
```

### Tests

`tests/test_trading_day.py`
- `latest_trading_day` returns `None` on an empty store.
- Snapshots at 23:30 UTC on 2026-08-12 resolve to Trading Day 2026-08-13 in VN_TZ.
- `trading_days_before` skips a weekend and a holiday gap without padding.
- `trading_days_before` returns fewer than requested rather than reaching past
  what is stored.
- `market_generation` advances on a market write and not on a fundamental write.

`tests/test_warmup.py`
- Warm-up writes every session in the window through the store.
- Re-running Warm-up over the same window writes no duplicate rows.
- Warm-up reads only `Capability.MARKET` and only from the Main Source.
- A `BatchTooLarge` halves the batch rather than failing the window.

`tests/test_backfill.py` (extend)
- A symbol failing repeatedly does not occupy consecutive runs' slots.
- A success clears `attempts` and `next_attempt_at`.

### Exit criterion

`latest_trading_day` and `market_generation` are the only sources of those two
facts anywhere in the codebase, and a Warm-up makes a symbol with no stored
history evaluable for a 20-day baseline in one run.

---

## M1 — Profit Ranking Census and Cohort Version

### Scope

Identify the actual 50 profit leaders among currently listed HOSE and HNX
equities, hold them as an immutable versioned read model, and seat them inside
the bounded **Universe**.

### Universe recomposition

ADR-0003 reserves 50 of the 100 **Universe** places for the **Profit Leaders
Cohort**. `src/stocks/universe.py` changes:

- `UNIVERSE_MAX_SYMBOLS = 100` stays as the total.
- New `UNIVERSE_EXPLICIT_MAX = 50`. `parse_universe` rejects a configuration
  declaring more than 50 distinct symbols, with a message naming the reserved
  half. This is a breaking configuration change; note it in the release notes.
- `Universe` gains cohort members:

```python
@dataclass(frozen=True)
class Universe:
    explicit: tuple[str, ...]
    cohort: tuple[str, ...] = ()

    @property
    def symbols(self) -> tuple[str, ...]:  # explicit first, then cohort, deduplicated
```

Deduplication is by symbol, explicit wins, and the total is asserted `<= 100`
after deduplication. An explicitly configured symbol is never evicted to make
room for a cohort member — if the union would exceed 100 after deduplication the
*cohort activation* is refused and logged, not the configuration.

`get_universe()`'s `lru_cache` must go: cohort membership changes at runtime.
Replace it with `build_universe(session, settings)` reading the active
**Cohort Version**, and a short-lived process cache keyed by cohort version id.

### Listing roster

The census needs exchange and listing status market-wide, which no existing
adapter provides. New contract in `providers/contracts.py`:

```python
class ListingEntry(InternalSnapshot):
    symbol: str
    exchange: str          # HOSE | HNX | UPCOM
    is_listed: bool
    company_name: str | None = None

class ListingRosterProvider(Protocol):
    source: ProviderSource
    def fetch_listing_roster(self) -> Sequence[ListingEntry]: ...
```

Implemented on vnstock. The roster is market-wide reference data that is not
per-symbol **Snapshot** data, so it gets its own table rather than
`provider_snapshots`:

```
listing_roster
  symbol        VARCHAR(20)  PRIMARY KEY
  exchange      VARCHAR(10)  NOT NULL
  is_listed     BOOLEAN      NOT NULL
  company_name  VARCHAR(255) NULL
  source        VARCHAR(32)  NOT NULL
  observed_at   TIMESTAMPTZ  NOT NULL
```

This table also answers ADR-0003's delisting question: when a roster refresh
shows an active cohort member is no longer a listed HOSE/HNX equity, the next
eligible symbol from the same ranking becomes a candidate replacement and
receives a **Warm-up**.

ADR-0004 keeps company name, exchange, listing status, and ICB Level 2 as
reference data persisted through `ReferenceSnapshot` **for Universe members**.
The roster does not replace that; it is the market-wide census input only.

### Census

New module `src/stocks/census.py`.

The census reads, for every currently listed HOSE or HNX equity, only:
trailing-12-month net income attributable to the parent, reporting period,
exchange, and listing status. Profit and period arrive as `FundamentalSnapshot`
through the existing `VnstockFundamentalProvider`, and are persisted through
`SnapshotStore.save(Capability.FUNDAMENTAL, ...)` — raw observations keep their
source and effective time, exactly as ADR-0004 requires. No market **Snapshot**
is collected for a censused symbol outside the **Universe**.

Progress and outcome live in a run table:

```
profit_ranking_census_runs
  id                 SERIAL PK
  started_at         TIMESTAMPTZ NOT NULL
  finished_at        TIMESTAMPTZ NULL
  status             VARCHAR(16) NOT NULL   -- running | complete | failed
  target_period      DATE        NULL       -- period_end being assessed
  eligible_symbols   INTEGER     NOT NULL DEFAULT 0   -- listed HOSE+HNX equities
  covered_symbols    INTEGER     NOT NULL DEFAULT 0   -- with valid profit at target_period
  last_error         VARCHAR(500) NULL
```

`coverage = covered_symbols / eligible_symbols`. A period is a **Rankable
Reporting Period** at `>= 0.95`. Until a newer period reaches it, the active
ranking stays on the previous period.

Cadence, per ADR-0004: weekly full census; daily targeted retry for symbols
missing at the newer period while that period is below threshold. Both are
tracked runs under the existing one-at-a-time guard.

Quota is the real constraint here: roughly 1,600 listed symbols against
vnstock's 20/min guest or 60/min keyed tier. The census therefore paces itself
with `census_request_delay` and resumes from `covered_symbols`, and the weekly
slot is Sunday 02:00 VN — the window the superseded `financial_statements` job
occupied.

### Ranking

Applied at one common reporting period. Eligible: currently listed, exchange in
`{HOSE, HNX}`, profit non-null and strictly positive. Order by profit
descending, then symbol ascending — the tiebreak keeps the cohort exactly 50
without a coin flip. Take the first 50. If fewer than 50 qualify, the previous
**Cohort Version** stays active and the refresh ends without staging a
candidate.

### Cohort Version

```
cohort_versions
  id                     SERIAL PK
  reporting_period       DATE        NOT NULL
  census_run_id          INTEGER     NOT NULL REFERENCES profit_ranking_census_runs(id)
  state                  VARCHAR(16) NOT NULL   -- candidate | active | superseded
  created_at             TIMESTAMPTZ NOT NULL
  activated_at           TIMESTAMPTZ NULL
  superseded_at          TIMESTAMPTZ NULL
  coverage_at_activation INTEGER     NULL       -- evaluable members at activation

cohort_members
  cohort_version_id  INTEGER     NOT NULL REFERENCES cohort_versions(id)
  symbol             VARCHAR(20) NOT NULL
  rank               INTEGER     NOT NULL
  net_income_vnd     NUMERIC(24,2) NOT NULL
  exchange           VARCHAR(10) NOT NULL
  PRIMARY KEY (cohort_version_id, symbol)
  UNIQUE (cohort_version_id, rank)
```

Partial unique index enforcing at most one active version:

```
uq_cohort_version_single_active  ON cohort_versions (state) WHERE state = 'active'
```

Members are immutable once written. A ranking change produces a new version; it
never rewrites an older one.

Lifecycle:

1. A rankable census produces a ranking → insert a `candidate` version with its
   50 ordered members.
2. Every candidate member not already carrying 21 sessions of history receives a
   **Warm-up**.
3. When at least 45 candidate members are evaluable for the newest **Trading
   Day**, activation runs in one transaction: candidate → `active`, previous
   active → `superseded` with `superseded_at`, `activated_at` and
   `coverage_at_activation` stamped. Activation is atomic; a partial activation
   is not a reachable state.
4. Until then the previous version keeps serving. A failed census, Warm-up, or
   collection cycle can neither replace the active version nor erase the
   last-known-good signal.

Historical resolution — the query M2 needs — is by activation window:

```python
def cohort_version_active_on(session, day: date) -> CohortVersion | None:
    # activated_at <= end_of(day) AND (superseded_at IS NULL OR superseded_at > end_of(day))
```

Never "today's members projected backward".

### Legacy removal

In the same milestone, delete `FinancialStatement`, `financial_statements_collector.py`,
the `financial-statements` analytics endpoints, and their scheduler entry; drop
the `financial_statements` table in the migration. The web
`analytics/financial-statements` page and `use-financial-statements.ts` go with
them. Two rankings of "top profitable companies" answering differently is the
failure mode this removal prevents.

### Config

```python
profit_census_enabled: bool = True
profit_census_weekday: int = 6          # Sunday
profit_census_hour: int = 2
profit_census_minute: int = 0
profit_census_retry_hour: int = 3       # daily targeted retry
cohort_size: int = 50
cohort_activation_min_members: int = 45
rankable_period_coverage: float = 0.95
```

### Tests

`tests/test_census.py`
- Coverage below 95% leaves the previous period rankable and stages nothing.
- Coverage at exactly 95% makes the period rankable.
- UPCOM and delisted symbols are excluded from both numerator and denominator.
- Null and non-positive profit are excluded from eligibility.
- A tie at rank 50 resolves by symbol ascending and yields exactly 50 members.
- Fewer than 50 eligible companies leaves the active version untouched.
- The census writes fundamental snapshots but no market snapshots for
  non-Universe symbols.

`tests/test_cohort_version.py`
- A new ranking stages a `candidate`, never mutating the active version's members.
- Activation below 45 evaluable members does not happen.
- Activation at 45 is atomic: exactly one `active` row, previous marked
  `superseded` with a timestamp.
- `cohort_version_active_on` returns the version active on that date, not the
  newest one.
- A delisted active member stages a replacement candidate and does not
  deactivate the version.

`tests/test_universe.py` (extend)
- More than 50 explicitly configured symbols is refused at parse time.
- Cohort and explicit sets deduplicate, explicit wins, total never exceeds 100.
- A cohort activation that would push the union past 100 is refused, and the
  explicit configuration survives.

### Exit criterion

An active **Cohort Version** exists with 50 ordered members at a **Rankable
Reporting Period**, its members are inside the **Universe** and collected by the
existing **Collector**, and a historical date resolves to the version that was
active then.

---

## M2 — Volume Spike serving with coverage and provenance

### Scope

Serve the **Volume Spike** signal for both **Signal Scopes** with honest
**Signal Coverage**, **Signal Freshness**, and **Signal Issues**, reading only
from stored data.

### Computation

New module `src/stocks/signals/volume_spike.py`.

For a target **Trading Day** `D` and a symbol `S`:

1. `baseline_days = trading_days_before(D, 20)`. Fewer than 20 → `S` is
   unevaluable with `insufficient_history`.
2. Load `S`'s market **Snapshot** for `D`. Missing → unevaluable with
   `missing_target_session`.
3. Load `S`'s market Snapshots for all 20 `baseline_days`. Any missing →
   unevaluable with `insufficient_history`.
4. An explicit zero-volume Snapshot **is part of the baseline** and is not a
   gap. A symbol with at least one such day is **Recently Inactive**: still
   evaluable, but carrying `recently_inactive`.
5. `ratio = volume(D) / mean(volume over baseline_days)`. A baseline mean of
   zero yields no ratio and the symbol reports `recently_inactive` without a
   spike.
6. A **Volume Spike** exists when `ratio >= threshold`.

The distinction in steps 3 and 4 is the point: an explicit zero is data saying
"nothing traded", a missing row is the absence of data. Treating them alike
would either invent a baseline or discard a real suspension.

### Signal resolution

- **Signal Trading Day**: the newest **Trading Day** on which at least 45 active
  **Profit Leaders Cohort** members are evaluable. Walk back from
  `latest_trading_day()` up to `SIGNAL_LOOKBACK_TRADING_DAYS = 10`; none
  qualifying → `insufficient_data` with `ranking_unavailable` or
  `cohort_warming`.
- **Signal Coverage** — `profit_leaders`: `ready` at 50/50, `partial` at 45–49,
  `insufficient_data` below 45. `universe`: `ready` at 100%, `partial` at ≥90%,
  `insufficient_data` below 90%. An exchange filter on `universe` narrows both
  the evaluated members and the denominator.
- **Signal Freshness** — `fresh` when the Signal Trading Day is the newest
  market **Trading Day**; `lagging` when a newer market Trading Day exists but
  lacks coverage; `stale` when the signal data is more than 7 calendar days old.
  It is computed independently of coverage: a result can be `ready` and `stale`,
  or `partial` and `fresh`, and collapsing them into one status would hide one
  of the two.
- **Signal Issue** codes, closed set: `missing_target_session`,
  `insufficient_history`, `recently_inactive`, `volume_basis_break`,
  `cohort_warming`, `lagging_market_data`, `stale_market_data`,
  `ranking_unavailable`. They are domain provenance and are carried in the 200
  response body — never as an HTTP status, never as prose.

### API

Replaces `GET /api/v1/analytics/volume-spikes`.

```
GET /api/v1/signals/volume-spikes
  ?scope=profit_leaders|universe        (default profit_leaders)
  &threshold=<float>                    (default 1.5, min 1.0)
  &exchange=HOSE|HNX                    (universe scope only)
  &trading_day=<YYYY-MM-DD>             (optional; historical query)
```

```jsonc
{
  "scope": "profit_leaders",
  "trading_day": "2026-08-12",
  "threshold": 1.5,
  "coverage": {
    "state": "partial",         // ready | partial | insufficient_data
    "evaluated": 47,
    "total": 50
  },
  "freshness": "lagging",       // fresh | lagging | stale
  "cohort_version": { "id": 12, "reporting_period": "2026-06-30" },
  "issues": ["lagging_market_data"],
  "spikes": [
    {
      "symbol": "FPT",
      "volume": 8410300,
      "baseline_average_volume": 3120450,
      "ratio": 2.69,
      "close_price": 138500,
      "change_pct": 3.42,
      "exchange": "HOSE",
      "issues": []
    }
  ],
  "unevaluable": [
    { "symbol": "SSB", "issues": ["insufficient_history"] }
  ]
}
```

`cohort_version` is null for `scope=universe`. `unevaluable` is always present
so the interface can show what it could not see rather than implying a complete
answer.

The secondary screen is labelled **All Universe**, never **All Market** — in the
API's own `scope` value, in the response, and in every string the web app
renders.

### Caching

Cache key is the tuple ADR-0005 names: **Signal Scope**, resolved **Trading
Day**, threshold, exchange filter, **Cohort Version** id, and market generation.
The A1 `prepare_bars()` retrofit adds corporate-action generation because Window
Health now depends on that stored series. Any dependency changing produces a
different key, so no invalidation call is needed and a stale entry is
unreachable rather than merely unlikely. Reuse `core/cache.py`.

### Web

Rebuild `apps/web/src/app/analytics/volume-spikes` and
`src/components/dashboard/volume-spike-dashboard` against the new response:

- Scope switch: **Profit Leaders** / **All Universe**.
- A coverage and freshness band always visible above the table, stating the
  **Signal Trading Day** and how it relates to the newest market data. It is
  never hidden when everything is healthy — a band that only appears on trouble
  teaches the reader that its absence means nothing.
- `insufficient_data` renders an explanatory state, not an empty table.
- **Signal Issues** map to short Vietnamese sentences in one place
  (`lib/signal-issues.ts`); the API's codes are never rendered raw.
- The unevaluable list is reachable behind progressive disclosure, not hidden.
- The **Universe** cap of 100 does not appear anywhere in the interface
  (ADR-0001).
- `use-volume-spikes.ts` is rewritten; the industry-grouped legacy components
  (`industry-spike-group.tsx`, `sector-group-header.tsx`) are deleted.

### Legacy removal

`AnalyticsService.get_volume_spikes`, its cache helpers, the anomaly-level
enum, and the `stock_daily_ohlcv` collection path go. Keep the
`stock_daily_ohlcv` *table* until M2 has shipped and been verified in an
environment with real data, then drop it in a follow-up migration — a signal
regression with the table already gone has nothing to compare against.

### Tests

`tests/test_volume_spike.py`
- Ratio is computed over exactly 20 preceding Trading Days, not 20 calendar days.
- A missing target-session Snapshot yields `missing_target_session`, not a zero.
- 19 available baseline days yields `insufficient_history`.
- An explicit zero-volume day stays in the baseline and marks `recently_inactive`.
- A baseline of all zeros produces no ratio and no spike.
- Coverage thresholds: 50/50 `ready`, 45/50 `partial`, 44/50 `insufficient_data`.
- Universe coverage: 100% `ready`, 90% `partial`, 89% `insufficient_data`.
- An exchange filter narrows the coverage denominator.
- Freshness is independent of coverage across all six combinations.
- A historical query uses the Cohort Version active on that day.
- Cache keys differ across every query and stored-data dependency.

`apps/web` — component tests for the coverage band, the `insufficient_data`
state, and the scope switch.

### Exit criterion

Both scopes serve correct signals with coverage, freshness, and issues; no
serving path reads `stock_daily_ohlcv`; no user request reaches a **Provider
Source**.

---

## M3 — Watchlist, Analysis, Analysis Run

> **Superseded** by [`0003`](0003-intelligent-quant-architecture.md) §A2. The
> lifecycle below is right in outline and wrong in its table names and column set:
> the canonical tables are `watchlist_entries`, `analysis`, and `analysis_run`, in
> one revision alongside six more. Build from `0003`.

### Scope

Let a user save symbols, and produce one shared **Analysis** per
`(symbol, trading_day)` with a durable production record.

### Data model

```
watchlist_items
  id         SERIAL PK
  user_id    INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE
  symbol     VARCHAR(20) NOT NULL
  state      VARCHAR(16) NOT NULL DEFAULT 'active'   -- active | unsupported
  added_at   TIMESTAMPTZ NOT NULL
  UNIQUE (user_id, symbol)

analyses
  id           SERIAL PK
  symbol       VARCHAR(20) NOT NULL
  trading_day  DATE        NOT NULL
  schema_version INTEGER   NOT NULL DEFAULT 1
  payload      JSONB       NOT NULL      -- fixed-template dashboard fields
  narrative    TEXT        NOT NULL      -- the written judgement
  created_at   TIMESTAMPTZ NOT NULL
  UNIQUE (symbol, trading_day)

analysis_runs
  id           SERIAL PK
  symbol       VARCHAR(20) NOT NULL
  trading_day  DATE        NOT NULL
  state        VARCHAR(16) NOT NULL      -- pending | producing | ready | failed
  attempts     INTEGER     NOT NULL DEFAULT 0
  last_error   VARCHAR(500) NULL
  started_at   TIMESTAMPTZ NULL
  finished_at  TIMESTAMPTZ NULL
  UNIQUE (symbol, trading_day)
```

`analyses` has **no `user_id`**. Two Watchlists holding the same symbol read one
**Analysis**; re-adding a symbol removed the same day produces no new one;
removing a symbol deletes nothing. The price, stated in the glossary, is that an
Analysis is not personalised.

The invariant — a run in `ready` always means its **Analysis** exists in full —
is enforced by writing the `analyses` row and the `state='ready'` transition in
one transaction. Half-produced state lives only in `analysis_runs`. Add a test
asserting no `ready` run lacks an `analyses` row, and a startup consistency check
that logs any violation rather than serving it.

### Watchlist rules

- Cap: `WATCHLIST_MAX_ACTIVE = 10` per user, counting only `state='active'`.
  (ADR-0001's two occurrences of 5 have since been amended to 10.)
- A symbol can be added only if it is in the **Universe** at that moment.
  Attempting anything else is a 422 naming the reason.
- A symbol that leaves the **Universe** — most often a cohort member dropping out
  of the ranking — transitions its watchlist items to `unsupported` rather than
  vanishing. `unsupported` items do not count against the cap, keep their
  historical **Analyses** readable, and are shown as no longer updating.
- The **Universe** cap never reaches the interface. The Watchlist cap does.

### Producing runs

After a **Collector** cycle commits and `latest_trading_day()` advances:

1. Collect the distinct symbols appearing in at least one `active` watchlist item.
2. Upsert an `analysis_runs` row at `pending` for each `(symbol, new_trading_day)`.
3. Work the pending queue, moving each to `producing`, then `ready` or `failed`
   with a reason and an incremented `attempts`.

A restart mid-production leaves rows at `producing`; a startup sweep returns any
`producing` row older than `ANALYSIS_RUN_STUCK_MINUTES = 30` to `pending`. This
is why the run is a separate record: without it a failed symbol and a
not-yet-reached symbol look identical, and the interface cannot know whether to
offer a retry.

The **Analysis** payload template is not yet specified — see
[Open decisions](#3-open-decisions). M3 builds the lifecycle, storage, states,
API, and interface against a versioned payload; the template's fields are filled
in once decided, without schema churn.

### API

```
GET    /api/v1/watchlist                  -> items with state and per-symbol run state
POST   /api/v1/watchlist   {symbol}       -> 201 | 409 duplicate | 422 not in Universe | 422 cap
DELETE /api/v1/watchlist/{symbol}         -> 204 (removes the item, deletes no Analysis)
GET    /api/v1/analyses/{symbol}          ?trading_day=<YYYY-MM-DD>  (default latest ready)
GET    /api/v1/analyses/{symbol}/runs     -> recent run states for the retry affordance
POST   /api/v1/analyses/{symbol}/retry    -> re-queues a failed run (admin or owner)
```

All are authenticated. The watchlist endpoints are per-user; the analysis
endpoints are not scoped to a user by design.

### Web

Build `apps/web/src/app/(dashboard)/watchlist` (currently a `.gitkeep`):

- Add/remove with the 10-symbol cap surfaced as a count, and symbol entry
  restricted to the **Universe**.
- Each row is state-driven off its **Analysis Run**: `pending` reads as queued,
  `producing` as in progress, `ready` links to the Analysis, `failed` shows the
  reason and a retry.
- Every number shows its **Trading Day** and its age. ADR-0001 requires this:
  all data has an age, and a user adding a symbol mid-session sees nothing for
  that day until after 15:00 — say so rather than showing an empty panel.
- `unsupported` items render distinctly, outside the cap count, with their last
  Analysis still reachable.

### Config

```python
watchlist_max_active: int = 10
analysis_run_stuck_minutes: int = 30
analysis_run_max_attempts: int = 3
```

### Tests

`tests/test_watchlist.py`
- The cap counts only `active` items; an eleventh active is refused.
- `unsupported` items do not count against the cap.
- A symbol outside the Universe is refused with a reason.
- Removing an item deletes no `analyses` row.
- A symbol leaving the Universe becomes `unsupported`, not deleted.

`tests/test_analysis_run.py`
- Two users watching one symbol share exactly one Analysis for a Trading Day.
- Re-adding a symbol removed the same day produces no second Analysis.
- A `ready` run always has its `analyses` row; the transition is one transaction.
- A crash during production leaves `producing`, and the sweep returns it to
  `pending` after the timeout.
- A failed run records its reason and increments `attempts`.
- Runs are keyed on the data-derived **Trading Day**, not on the calendar date.

### Exit criterion

A user saves up to 10 symbols, each shows a truthful production state for the
current **Trading Day**, and the shared-Analysis invariants hold under
concurrent watchlists.

---

## M4 — Thread, Turn, Tool Call Trace, Widget, Capability Probe

> **Superseded** by [`0003`](0003-intelligent-quant-architecture.md) §A3, §A5, and
> §A6. Its three modelling decisions survive verbatim — order by `seq`, traces
> anchored to the user message, `symbols` as a GIN-indexed column — but the table
> names differ (`agent_thread`, `agent_message`, `agent_tool_call`, `agent_turn`),
> **there is no `widgets` table**, and the Redis-stream replay sketched below is
> replaced by snapshot-based SSE replay. Build from `0003`.

### Scope

The conversational surface, with the durability and provenance the glossary
requires. This milestone cannot start until the LLM route is chosen and recorded
as an ADR — see [Open decisions](#3-open-decisions).

### Data model

```
threads
  id          SERIAL PK
  user_id     INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE
  title       VARCHAR(255) NULL
  symbols     JSONB       NOT NULL DEFAULT '[]'   -- symbols this Thread has touched
  created_at  TIMESTAMPTZ NOT NULL
  updated_at  TIMESTAMPTZ NOT NULL

thread_messages
  id          SERIAL PK
  thread_id   INTEGER     NOT NULL REFERENCES threads(id) ON DELETE CASCADE
  seq         INTEGER     NOT NULL           -- order within the Thread
  role        VARCHAR(16) NOT NULL           -- user | assistant
  content     TEXT        NOT NULL
  created_at  TIMESTAMPTZ NOT NULL
  UNIQUE (thread_id, seq)

turns
  id               SERIAL PK
  thread_id        INTEGER     NOT NULL REFERENCES threads(id) ON DELETE CASCADE
  user_message_id  INTEGER     NOT NULL REFERENCES thread_messages(id)
  state            VARCHAR(16) NOT NULL   -- accepted | running | completed | cancelled | failed
  tool_rounds      INTEGER     NOT NULL DEFAULT 0
  input_tokens     INTEGER     NOT NULL DEFAULT 0
  output_tokens    INTEGER     NOT NULL DEFAULT 0
  created_at       TIMESTAMPTZ NOT NULL
  finished_at      TIMESTAMPTZ NULL

tool_call_traces
  id               SERIAL PK
  user_message_id  INTEGER     NOT NULL REFERENCES thread_messages(id) ON DELETE CASCADE
  seq              INTEGER     NOT NULL
  tool_name        VARCHAR(64) NOT NULL
  arguments        JSONB       NOT NULL
  result           JSONB       NULL
  latency_ms       INTEGER     NULL
  tokens           INTEGER     NULL
  error            VARCHAR(500) NULL
  created_at       TIMESTAMPTZ NOT NULL
  UNIQUE (user_message_id, seq)

widgets
  id          SERIAL PK
  turn_id     INTEGER     NOT NULL REFERENCES turns(id) ON DELETE CASCADE
  widget_type VARCHAR(64) NOT NULL
  version     INTEGER     NOT NULL
  data        JSONB       NOT NULL     -- registered fields only
  created_at  TIMESTAMPTZ NOT NULL
```

Three modelling decisions come straight from the glossary and must not be
"simplified" during implementation:

- **Order is `seq`, not `created_at`.** Two messages can share a millisecond
  while streaming, and a timestamp sort would reorder a conversation.
- **A Tool Call Trace anchors to the user's message, not to the answer.** The
  user's message exists before the first tool call; the answer does not.
- **`threads.symbols` is a column, not a join table.** It exists to answer
  "which Threads discussed FPT" directly. Index it `GIN`.

### Turn ownership

Once accepted, a **Turn** belongs to the system, not to the connection. Reload,
route change, tab close, and network loss do not cancel it; only an explicit
cancellation does.

Implementation: `POST` accepts the Turn, persists it at `accepted`, and returns
its id immediately. Execution runs detached from the request. Streamed output is
appended to a Redis stream keyed by turn id, so a reconnecting client replays
from its last offset and then follows live. A cancelled or crashed Turn keeps the
**Tool Call Traces** of the part that ran.

Every ceiling is per-Turn — tool rounds, concurrent turns per user, token cost —
because the Turn is the unit the user can cancel.

### Capability Probe

New module `src/core/llm/probe.py`, run at startup against the configured route.
Four contract checks:

1. Forced `tool_choice` is honoured.
2. Parallel tool calls survive streaming.
3. Structured output conforms to the requested schema.
4. One closed tool loop completes: call, result, final answer.

A route failing any check refuses startup and prints which check failed and
what came back. This is not a health check: a gateway translation layer silently
dropping these parameters does not fail at runtime, it only makes the answers
wrong, and that failure never surfaces on its own.

Probe results are cached per process and skipped in the test suite via an
explicit flag, never by auto-detection.

### Widgets

A registry maps `widget_type` to a version and a field schema. A **Widget** is a
typed projection of registered fields only — it presents figures and never
computes them, never replaces an **Analysis** or the Stock 360 data surfaces, and
preserves the historical data context of the answer when the Thread is reopened.
Reopening a Thread renders the stored `data`; it does not re-query today's
numbers.

### Tests

`tests/test_thread.py` — `seq` ordering survives identical timestamps;
`threads.symbols` accumulates touched symbols; a symbol query needs no join.

`tests/test_turn.py` — a Turn survives a dropped connection; only explicit
cancellation ends it; a cancelled Turn keeps its partial traces; every ceiling is
enforced per-Turn; a reconnect replays the stream from its offset.

`tests/test_tool_call_trace.py` — traces anchor to the user message; ordering is
by `seq`; a failed call records its error and still counts a round.

`tests/test_capability_probe.py` — each of the four checks fails startup
independently, with the failing check named.

### Exit criterion

A Turn survives a page reload, its Tool Call Trace reads back as an ordered
decision chain, and a misconfigured LLM route refuses startup instead of
answering wrongly.

---

## 3. Open decisions

Four of the five have since been settled. They are kept with their resolutions
rather than deleted, so a reader who remembers the question finds the answer.

1. ~~**Watchlist cap: 10 or 5.**~~ **Resolved: 10.** ADR-0001 has been amended —
   its two occurrences of 5 now read 10 — and the cap counts `active` entries
   only, with `unsupported` entries outside it.
2. ~~**The Analysis template.**~~ **Resolved.** The artifact is bounded inline
   with the four fixed-order axes as tabs, expanding to the briefing treatment;
   fields come from a versioned **Analysis Field Profile** capped at six per axis.
   See [`0002`](0002-alpha-desk-product.md) §5 and
   [`0003`](0003-intelligent-quant-architecture.md) §8.
3. ~~**The LLM route.**~~ **Resolved.** Dev runs on CLIProxyAPI via CCS; production
   is a real provider API behind the same env flip, with `gpt-5.6-luna` for batch
   and `gpt-5.6-terra` for sessions. The **Capability Probe** stays, and it is why
   the boundary is a protocol rather than an SDK. See
   [`0003`](0003-intelligent-quant-architecture.md) §3 and
   [ADR-0014](../adr/0014-atomic-spend-admission-and-workload-models.md).
4. ~~**Price-level judgements and the disclaimer.**~~ **Resolved, by splitting the
   number from the judgment.** The price zone is a registered field computed in
   code, reading as *this symbol's ordinary daily range*; the verdict is the
   model's and may rest only on registered fields. The disclaimer is a versioned
   **Risk Notice** attached by the backend, which the model cannot omit, rewrite,
   or satisfy with prose. See
   [ADR-0010](../adr/0010-statistical-bar-for-computed-signal-fields.md) and
   [ADR-0015](../adr/0015-system-prompt-contract-as-the-versioned-behavioural-core.md).
5. **Whether an operator can pin a symbol into the cohort's 50 places.** ADR-0003
   says the system never silently evicts an explicitly selected symbol, but does
   not say whether an operator may reserve a cohort seat. Assumed **no** for now.
   Blocks: nothing; revisit if operations asks.

## 4. Assumptions this spec makes

Recorded because they were inferred rather than stated, and each is cheap to
reverse if wrong.

- A **Trading Day** is market-wide, from `max(effective_at)` across all symbols,
  not resolved per symbol.
- The market generation is `max(observed_at)` over market snapshots rather than a
  separate counter.
- Watchlist entry is restricted to current **Universe** members, and
  `unsupported` is a transition a previously valid symbol makes — not a state a
  new addition can be created in.
- The market-wide listing roster is its own table rather than
  `provider_snapshots`, because it is not per-symbol point-in-time observation
  data.
- `stock_daily_ohlcv` is kept through M2 and dropped only after the new signal
  path is verified against real data.
