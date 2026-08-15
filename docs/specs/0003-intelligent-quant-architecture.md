# Implementation specification — Intelligent Quant architecture

The engineering half of **Intelligent Quant**. It turns the closed decisions on the
Wayfinder map ([issue #16](https://github.com/PhamTy2002z/Stock_Massive/issues/16))
into buildable work: the LLM boundary, the signals package, the **Tool
Catalog**, the agent loop, the nightly **Analysis** pipeline, persistence, the streaming
transport, orchestration and budgets, and the evaluation harness.

Read with:

- [`0002-alpha-desk-product.md`](0002-alpha-desk-product.md) — what the user sees.
- [`0001-domain-implementation.md`](0001-domain-implementation.md) — the data
  foundation. **This spec supersedes its §M3 and §M4** and re-issues them below; §M0–§M2
  stand.
- `docs/adr/0006` … `0016` — the arguments behind every hard-to-reverse choice.
- `CONTEXT.md` — every **bold** term.

Anything not derivable from this spec, the ADRs, or the glossary is an open decision
listed in [§14](#14-open-decisions), not a choice made silently while coding.

## 1. Where the code stands today

| Concern | Code today | Verdict |
| --- | --- | --- |
| **Trading Day**, market generation, **Warm-up** | `src/stocks/trading_day.py`, `warmup.py` | Built (spec 0001 M0). Consume as-is. |
| **Profit Ranking Census**, **Cohort Version** | `src/stocks/census.py`, `cohort.py`, `listing_roster.py` | Built (spec 0001 M1). |
| **Volume Spike** serving | `src/stocks/signals/{volume_spike,router}.py` | Built (spec 0001 M2). The legacy `stock_daily_ohlcv` path is gone. |
| `src/stocks/signals/` — `prepare_bars()`, **Signal Registry**, the fourteen computations | package exists from M2; none of these are in it | A1 below. |
| **Corporate Action** persistence | — | Missing. Prerequisite, not a follow-up (ADR-0006). |
| **Watchlist**, **Analysis**, **Analysis Run** | — | Missing. A2 below. |
| `LLMClient`, **Capability Probe** | — | Missing. `requirements.txt` carries **no** provider SDK and no agent framework — but does have `httpx`, `tenacity`, pydantic v2. |
| `src/agent/` — **Tool Catalog**, the loop | — | Missing. A5 below. |
| Streaming anywhere in `apps/web` | — | None. Real-time today is TanStack Query polling. Alpha Desk is the first consumer. |
| Money-flow serving | adapters and snapshot fields exist, fully unwired | Ingestion prerequisite. |
| News persistence | dead service code, no route, no storage | Ingestion prerequisite. |
| Technical indicators, durable daily history | `DAILY_OHLCV_ENABLED=False`, 7-day window | Ingestion prerequisite. `stock_daily_ohlcv` is **not** a history store: median 72 sessions/symbol, a seven-month hole, and prices in thousands while `provider_snapshots` holds VND. |

## 2. Package layout

```
apps/api/src/
├── core/
│   └── llm/              # LLMClient protocol, transport, Capability Probe,
│                         #   Budget Validation, error taxonomy
├── stocks/
│   └── signals/          # what is true: computations, prepare_bars(),
│                         #   Signal Registry, null harness, volume_spike
└── agent/
    ├── tools/            # what the model may see: the 12-tool catalog
    ├── loop.py           # the Turn
    ├── prompt/           # the System Prompt Contract, versioned
    ├── turns.py          # admission, registry, checkpointing, SSE publishing
    └── widgets.py        # server-side Widget validation
```

`src/stocks/signals/` decides *what is true* and is not agent-specific — the nightly
pipeline and the **Volume Spike** endpoint read it too. `src/agent/tools/` is a thin
adapter deciding *what the model may see*. Keeping the maths at domain level is what
makes ADR-0010's bar bind both surfaces (ADR-0007).

## 3. The LLM boundary

One `LLMClient` protocol in `src/core/llm/`, over an OpenAI-compatible transport, so a
route change is an env-var flip.

The boundary carries three guarantees, each earned by a measured failure:

1. **A boot-time Capability Probe.** Four contract checks against the configured route:
   forced `tool_choice` is honoured, parallel tool calls survive streaming, strict
   `json_schema` output conforms, and one closed tool loop completes. A route failing any
   check **refuses startup** with the failing check and the response printed.
2. **A per-request JSON-parse invariant.** Every returned tool call's `arguments` must
   parse; on failure raise immediately, never hand garbage back for the model to guess
   at.
3. **`auth_unavailable` as a first-class error class.** A 401 from the route means the
   channel's credential died. Interactive Turns surface *re-auth needed* to the operator;
   the nightly lane marks the symbol failed-retryable. It is **never retried blindly**.

The probe exists because a gateway's translation layer was measured **silently dropping**
`tool_choice`, `response_format`, and `parallel_tool_calls`, and keying streamed tool
calls on a counter instead of the upstream `output_index` — concatenating two calls'
arguments into invalid JSON under the wrong id, while returning 200. That class of
failure does not surface at runtime; it only makes the answers wrong.

### Placement

Inside `lifespan`, **immediately after `get_universe()` and before the scheduler
starts**. With `alpha_desk_enabled` true and the probe failing, the app does not start;
with Alpha Desk off, it logs a warning only. This reuses the existing fail-fast
precedent, whose own comment already argues the case.

Probe results are cached per process and skipped in the test suite by an **explicit
flag, never by auto-detection**. Probe calls reserve and reconcile spend like any other
call, under a hard $0.25/day ceiling (ADR-0014).

### Routes and models

| Lane | Route | Model |
| --- | --- | --- |
| dev | CLIProxyAPI via CCS, on the driving dev's Codex subscription — zero API budget at this stage | `gpt-5.6-terra` |
| production | a real provider API behind the same env flip | `llm_model_batch` = `gpt-5.6-luna`, `llm_model_session` = `gpt-5.6-terra` |

The dev route passed all six functional contract probes live, and its OAuth channel died
mid-test and needed manual re-auth — which is where guarantee 3 comes from.

Two recorded taxes on the dev lane: a ~300-token CLI system prompt is injected into
every request, and absent cache control. **Dev traffic therefore produces no cost
figures**; the production budget is computed analytically from measured token counts ×
published prices and validated empirically when a direct route first goes live.

Final pre-release prompt tuning must run against the **production** model family:
harness behaviour tuned on the dev family does not transfer sight-unseen.

> **Reconciled conflict.** The route decision recorded production intent as
> Anthropic; the later orchestration decision set production defaults to
> `gpt-5.6-luna` / `gpt-5.6-terra` and the evaluation decision gates against those.
> The later decision governs. All model ids stay env config, never constants, and the
> `LLMClient` boundary is what keeps the swap free.

### Error taxonomy

Single-sourced across both lanes.

| Class | Behaviour |
| --- | --- |
| `tool_error` | structured error returned to the model, which may try another approach; max 2 attempts on the same tool |
| `malformed_arguments` | **raise immediately**; the Turn fails saying the route violated its contract |
| `gateway_timeout` | retry via `tenacity`, 2 attempts with backoff, then fail the Turn |
| `auth_unavailable` | **never retried**; interactive surfaces re-auth, batch marks failed-retryable |
| `model_refusal` | shown verbatim; no re-prompting to work around it |

**No auto-disable of a route.** `malformed_arguments` is counted and logged loudly; the
operator flips `alpha_desk_enabled` by hand (ADR-0008).

## 4. The signals package

### `prepare_bars()`

```python
def prepare_bars(symbol: str, window_days: int) -> tuple[Frame, WindowHealth]
```

**The only path a computation may take to bars.** It is where the Vietnamese-market
hazard list is enforced by construction rather than by a review checklist, and — per
ADR-0006 — where the read-time corporate-action transform happens.

It reads **raw** prices, applies the **Adjustment Factor** computed from the persisted
**Corporate Action** series, and serves an all-`raw` window only. **Window Health**
carries `sessions_used`, `limit_lock_days`, `band_regime`, `adjustment`, and
`adtv_percentile`; `adjustment` reports whether adjustment was *applied* and from how
many actions, derived from the rows loaded rather than from configuration.

Four refusals:

| Refusal | Cause |
| --- | --- |
| `insufficient_history` | fewer sessions than the field's `min_sessions` |
| `mixed_price_basis` | the window crosses a **Price Basis** seam — meaningless, not degraded |
| `unadjustable_price_basis` | the window lies wholly in the `adjusted_at_source` era |
| `unexplained_price_gap` | a session moves further than its band permits with no Corporate Action accounting for it |

Bands and limit-lock detection **read raw prices**, and take the band from the symbol's
**exchange regime for that session** (±7/±10/±15, including HNX→HOSE migrations through
31/12/2026) — not from a stored field. Neither stored field can serve: `reference_price`
is the previous close from the same frame rather than the exchange's reference, and
`ceiling_price`/`floor_price` are `None` on every history bar.

A field reading a quantity across a **share-count-changing** action is `degraded` with
reason `volume_basis_break`, not refused. An ADTV in money crosses an ex-date; an ADTV in
shares does not.

### The Signal Registry

Every model-visible field registers `unit`, `sign`, `interpretation`, `kind`, **Claim**,
`source`, `min_sessions`, `threshold`, and `null_fpr`. The tool layer serializes
**registered fields only**, so an unregistered computation needs no prohibition — it has
no route to a model.

`min_sessions` covers **window plus skip** (the momentum rank is 273, not 252 — see §14.1
for the naming inconsistency that number exposes).
`null_fpr` rides in the tool schema description, not the payload. Thresholds are derived
from the null offline and frozen as constants; where literature has a convention, the
stricter of convention and derived value wins and the registry records which.

Full contract, including the two nulls and the `descriptive` schema constraint: ADR-0010.

### The null harness

A pytest parametrised over the registry at a fixed seed, running both nulls (≥1000 paths
each) and **failing when FPR > 1% or a metadata field is missing**. Offline and free, so
it belongs in `make test` — not in the paid `make eval` lane.

### The fourteen computations

Grouped into the five clusters of §5. Formulae, output contracts, null calibrations, and
per-method VN hazards are in `docs/research/quant-methods-eod-vn.md`; §10 of that
document is the catalog-wide contract and is adopted wholesale.

## 5. The Tool Catalog

Twelve semantic tools in `src/agent/tools/`, consuming the service layer and
`src/stocks/signals/`.

| Tool | Returns |
| --- | --- |
| `get_analysis(symbol, date?)` | the nightly artifact, not raw data |
| `get_price_series(symbol, window_days)` | OHLCV summary + decimated sample + **Data Reference** |
| `get_financials(symbol, ...)` | statements, quarterly staleness stamped |
| `get_company_profile(symbol)` | profile, ICB industry, ownership and room facts |
| `search_news(symbol, window_days)` | cleared sources only, wrapped as `untrusted_evidence` |
| `screen_universe(criteria)` | filter and rank the Universe on stored metrics |
| `risk_metrics` | Yang-Zhang realized vol, drawdown vs E[MDD], Sharpe/Sortino with Lo SE |
| `market_behavior` | GK volatility-regime z, liquidity profile, band pressure, mean-reversion gauge |
| `cross_sectional` | cross-sectional momentum rank, trend sign, relative strength (Ledoit-Wolf), factor percentiles |
| `foreign_flow` | net-buy pressure vs ADTV, persistence run length |
| `indicator_pack` | RSI/MACD/Bollinger as descriptive vocabulary, fractional Kelly on user-supplied edge |
| `get_watchlist()` | the caller's Watchlist, from injected **Tool Context** |

Contract rules (ADR-0009): store-only except the `search_news` cache-aside lane; ≤ ~4KB
returns with a **Data Reference** in place of any raw series; registered fields only;
**Structured Refusal** for a non-Universe symbol with up to three same-ICB suggestions
by descending ADTV, computed by query; identity injected out of band and never a
model-visible parameter.

A model reaching for a tool that does not exist is recorded as
`status = 'unknown_tool'` — the free demand signal ADR-0011 measures against.

## 6. The agent loop

Hand-rolled over `LLMClient`; no framework (ADR-0008). A **Turn** is the unit of every
ceiling.

- `build_messages(thread, budget) -> list[Message]` is a **pure function outside the
  loop**, so trimming is testable with no LLM involved.
- Parallel calls dispatch through `asyncio.gather(..., return_exceptions=True)`, and
  **every result is asserted against its own `tool_call_id`** before returning to the
  model.
- **Eight tool-call rounds** per Turn, counted by round. On the ceiling, one further call
  with `tool_choice="none"` answers from what is there, plus a transcript line stating
  all eight lookup steps were used.
- **Prompt injects only what no tool can supply**: identity (out of band), the
  data-defined `trading_day`, market state as a short string, and the active symbol. The
  Watchlist goes through `get_watchlist()`. **No figure is ever injected.**
- **Context trimming, in order**: keep recent Turns intact → replace old tool results
  with a one-line *called X with arguments Y* (results are stored whole in
  `agent_tool_call`, so this costs nothing in auditability) → past a threshold, one
  model-written summary stored as an `agent_message` with `role = 'summary'`, cached and
  never re-summarised.
- **Cancellation stops after the in-flight tool call completes.** Every tool is
  read-only. The partial message persists as `cancelled` with the traces of what ran.
- **Concurrency**: an in-process `asyncio.Semaphore` of **3 sessions** at the route, plus
  the existing `heavy` rate limit (20/60s). The 4th is refused `503` immediately, never
  queued. In-process is correct because uvicorn runs a single worker.

### The nightly lane's relationship to the loop

**Separate loop; shared `LLMClient` and shared computations.** The pipeline calls into
`src/stocks/signals/` from Python in a fixed order, collects results, then makes one
structured-output call. Sharing at the client and computation layer single-sources the
error taxonomy and the unit contracts; sharing the loop would make the batch
unbudgetable and undiffable (ADR-0007).

> **Reconciled conflict.** The loop decision described this as sharing "the tool
> functions", written before the signals package existed. The pipeline decision then
> required the pipeline to assemble its envelope from `SnapshotStore` and the Signal
> Registry and to call **no** agent tool, and the statistical-bar decision moved the
> computations to `src/stocks/signals/` for exactly this reason — *"the real reason the
> registry lives at domain level rather than under the agent"*. **The shared layer is
> `src/stocks/signals/`, not `src/agent/tools/`.** So A4 does not depend on A5, and the
> pipeline must not import from the agent package: the tool layer's job is the ≤4KB
> model-facing projection, which a pipeline assembling a full evidence envelope does not
> want.

## 7. Streaming transport and the web boundary

Full contract: ADR-0013. The engineering surface:

```
POST /api/alpha-desk/threads/{threadId}/turns    → admit, create, return turnId
GET  /api/alpha-desk/turns/{turnId}/events       → same-origin EventSource
POST /api/alpha-desk/turns/{turnId}/cancel       → authenticated, idempotent
```

- The browser generates the UUID `turnId` before `POST`; the backend treats it as an
  **owner-scoped idempotency key** — same id and payload returns the existing Turn, same
  id with a different payload returns `409`.
- Admission errors are ordinary HTTP before any stream opens: `429` for an exhausted
  user allowance, `503` for exhausted service budget or a full semaphore, each with a
  stable reason.
- Events carry a versioned envelope with a monotonic per-Turn `seq`, which is also the
  SSE `id`. Types: `turn.snapshot`, `turn.activity`, `content.block`, `widget.ready`,
  `turn.completed`, `turn.incomplete`, `turn.failed`, `turn.cancelled`. A 15-second SSE
  comment heartbeat consumes no sequence.
- **`content.block`, not `content.delta`.** The backend buffers provider deltas into
  Markdown-safe units; a block is also the smallest unit whose grounding can be proven
  (§9).
- **Replay is snapshot-based.** Subscriber registration and snapshot capture are atomic
  with respect to the publisher; after the snapshot the subscriber receives only
  `seq > throughSeq`. A duplicate sequence is ignored; a gap forces a fresh snapshot.
  Each subscriber has a bounded queue, so a slow tab cannot apply backpressure to the
  loop.
- **Execution lifetime**: the create transaction commits the user message and
  `agent_turn` before execution; FastAPI then holds an `asyncio.Task` in a process-local
  registry, and the SSE request only subscribes. Draft content is checkpointed **at most
  once per second** and at activity, Widget, cancellation, and terminal boundaries —
  never per token. One terminal transaction freezes the draft into the canonical
  assistant `agent_message`. On startup, any Turn left active by a crash or deploy is
  frozen and marked `incomplete`; **v1 never resumes execution after a restart.**
- **Timings**: 10-minute Turn deadline, 120-second LLM call timeout, shorter per-tool
  timeouts, 30 seconds of graceful shutdown to reach a safe checkpoint — the container
  stop grace must exceed it.
- **Auth**: Next owns cookies and forwards a bearer token; `/api/alpha-desk/*` is
  excluded from the middleware login redirect and authenticates inside each handler,
  with one process-local single-flight refresh on upstream `401`. **FastAPI
  independently verifies user and ownership** of the Thread and Turn on create,
  subscribe, snapshot, and cancel — the proxy is not the authorization boundary. The
  auth DB scope closes before the long response begins.
- **Client state**: a dedicated reducer for the live Turn; TanStack Query keeps every
  canonical resource. At a terminal event the client refetches the Thread and replaces
  the draft projection.
- **Proxy contract**: forward the upstream body unbuffered with
  `Content-Type: text/event-stream`, `Cache-Control: no-store, no-transform`,
  `X-Accel-Buffering: no`, and no synthesized `Content-Length`.
  `docker-compose.prod.yml` must gain an internal API URL for the web container rather
  than falling back to the public build-time URL.

Streaming is accepted only against an end-to-end test through the real browser → Next →
FastAPI path (ADR-0013).

## 8. The nightly Analysis pipeline

A deterministic orchestration around **one strict structured-output call**. Deterministic
means fixed inputs, fixed control flow, bounded validation, immutable publication, and
idempotent persistence — not bit-identical prose from a probabilistic model.

### 8.1 Input boundary

The pipeline reads **durable stored data and registered Signal Fields only**. It never
calls a Provider Source, never touches the legacy live vnstock service, and never runs a
tool loop. The backend assembles a normalized **evidence envelope** owning all facts:
symbol, company metadata, ICB industry, exchange, Trading Day; the registered price-zone
field; every registered figure with value, unit, `interpretation`, `source`, freshness,
health and reason code; fixed axis membership and order; and Window Health.

The model cannot manufacture or edit any of those facts.

### 8.2 Readiness

An Analysis becomes `ready` only when a Market Snapshot exists for the **exact**
data-defined Trading Day, the registered price-zone field is usable, and at least one
further registered field is usable and citable.

The price zone is core evidence because the artifact requires it, so a refused price zone
fails the run with `insufficient_core_evidence` rather than publishing a structurally
incomplete artifact. Other axes fail independently: missing or stale fundamental,
money-flow, or news data degrades or refuses **that section** without failing the
Analysis.

### 8.3 Health and freshness

Wire-level field and section health is **`ok | degraded | refused`**, with the cause
carried separately as a stable `reasonCode`. `insufficient_history` is a refusal reason,
not a fourth state.

Section health is derived by the backend, never chosen by the model: `ok` when the
intended fields are available and at least one is healthy, `degraded` when a usable field
sits beside degraded or refused evidence, `refused` when no field in the section can be
used. A refused field stays in the artifact with `value: null` and an inline
human-readable reason; it may be displayed as honesty evidence and **can never support
the verdict**.

Freshness: the Market Snapshot must match the exact Trading Day, or the run fails.
Fundamental, valuation, reference, and future news fields use thresholds declared by
their registry contract; a stale non-core field is `degraded`, keeps its `asOf` stamp,
and may be cited **only when the narration makes the age visible**.

> **Reconciled conflict.** The pipeline decision listed `mixed_adjustment` among its
> reason codes. The canonical vocabulary is the **Signal Issue** set in `CONTEXT.md`,
> where the corresponding value is **`mixed_price_basis`** (ADR-0006). Use the glossary
> value; `mixed_adjustment` is not a code.

### 8.4 The Analysis Field Profile

The model does not choose freely from the registry. The backend supplies a versioned
**Analysis Field Profile**, capped at **six fields per axis**, so the input bundle is
stable, reviewable, and bounded. Profile v1:

- **Technical** — `realized_volatility.yang_zhang_annualized_pct`,
  `volatility_regime.gk_variance_robust_z`, `drawdown_stats.current_drawdown_pct`,
  `band_pressure.limit_days_in_window`, `momentum_rank.percentile_12_2`,
  `indicator_pack.rsi_14`
- **Fundamental, all industries** — `factor_percentiles.roe_percentile`,
  `factor_percentiles.earnings_yield_percentile`,
  `factor_percentiles.book_yield_percentile`
- **Banks** — `bank_metrics.nim_pct`, `bank_metrics.npl_ratio_pct`,
  `bank_metrics.llr_coverage_pct`
- **Real estate** — `developer_metrics.net_debt_to_ebitda`,
  `developer_metrics.inventory_share_of_assets_pct`
- **Retail** — `retail_metrics.gross_margin_pct`,
  `retail_metrics.inventory_turnover_x`, `retail_metrics.store_count`
- **Money flow** — `foreign_flow_pressure.net_value_over_adtv`,
  `foreign_flow_pressure.persistence_run_days`, `liquidity_profile.adtv_vnd`,
  `company_profile.foreign_room_pct`
- **News** — approved-source item count over 7 sessions; over 30 sessions

The registered price-zone field is `price_zone.ordinary_range_pct` — a ±1 realized
Yang-Zhang σ over 20 sessions around the reference price, returned as the half-width in
percent with the two prices beside it. It is core artifact evidence and does **not**
consume a Technical slot.

**A profile field that is not yet implemented is still emitted as `refused` with reason
`unavailable`.** Silently dropping it would make two Analyses carrying the same
`profile_version` mean different things.

### 8.5 News in the nightly lane

V1 does **not** ask the model to synthesise headline meaning or sentiment; it may use
only registered news-count fields. Until approved-source news is persisted, the News
section is `refused` with reason `unavailable`, and **the pipeline does not call the live
`company.news()` service.**

Once news is persisted, the backend may render up to three original title/source/link
references. They are **not** verdict evidence and do not enter `citedFieldIds`. Event or
sentiment synthesis requires its own citation contract rather than a weakened registry
rule.

> This is not in tension with `search_news`. The **agent** may fetch news through the
> cache-aside lane; the **pipeline** may not. Two surfaces, two rules, one reason: the
> nightly artifact must be reproducible from stored data.

### 8.6 The model's fragment

The backend owns the envelope and merges in only: `verdict`, `verdictLine`, `thesis`,
`citedFieldIds`, and per fixed axis `emphasis`, `emphasisReason`, `read`.

`verdict` is one scalar — `accumulate | hold | reduce | avoid | watch` — because it is an
extracted column. The artifact-level `claim` field from the prototype is **removed**:
claim semantics belong to each registered field, and the verdict is model judgment rather
than a descriptive measurement.

The model sees the full profile **including refused fields and their reason codes**, so
it can choose emphasis honestly. It may cite only usable fields.

### 8.7 Citation invariants

`citedFieldIds` is non-empty; every id exists in the supplied envelope; only `ok` or
`degraded` fields may be cited; refused fields cannot support the verdict; **all
displayed numbers come from backend-owned evidence, never from model output**; the
inline artifact shows the count while expanded and audit views expose the ids; the
payload always stores the complete list.

### 8.8 Generation and validation

One fixed strict structured-output call: fixed prompt and `promptVersion`, the configured
route, **temperature 0**, no tool calls, no loop, no dynamic prompt branching.

Provider-level strict JSON Schema validation is followed by **backend semantic
validation**: evidence membership, citation health, axis order, exactly-one-`lead`, enum
values, required narration.

**One semantic regeneration** is allowed inside the same attempt, supplied with
machine-readable validation errors, and only when the remaining per-Analysis budget can
fund it. **The backend never patches invalid model output.** A still-invalid regeneration
fails the attempt with `invalid_model_output`. The durable run stays capped at three
attempts per `(symbol, trading_day)`.

### 8.9 Audit metadata

The immutable payload stores `schemaVersion`, `fieldProfileVersion`, `promptVersion`, the
configured model, the route identifier, `generatedAt`, and a SHA-256 `inputFingerprint`
of the normalized envelope. **No chain-of-thought.** The figures embedded in the payload
*are* the evidence snapshot shown to the model, so the prompt need not be duplicated.

### 8.10 Failure taxonomy

`analysis_run.error` carries a stable code plus a sanitized message, never a stack trace:
`missing_market_snapshot`, `insufficient_core_evidence`, `auth_unavailable`,
`llm_transport_error`, `invalid_model_output`, `persistence_error`.

### 8.11 Reruns

Postgres is canonical; Redis may cache reads but never decides whether work exists.
`analysis` is immutable and unique on `(symbol, trading_day)`; the complete Analysis is
written **first**, then the run is marked `ready`; a retry finding an existing Analysis
only repairs the run state; a rerun request for an already-ready pair is a no-op
returning the existing Analysis. **V1 never silently overwrites a published Analysis** —
that would need its own correction/versioning decision.

## 9. Where each invariant is enforced

Full contract: ADR-0015. Where each invariant is proven:

| Invariant | Layer |
| --- | --- |
| Universe, identity, read-only, result size, Provider Source boundary | Tool Catalog |
| which fields the model may see, and their sanctioned reading | Signal Registry |
| recommendation evidence and price-zone requirements | Recommendation Validator |
| the Risk Notice | rendering contract |
| what survives a dispute | persistence (**Evidence Manifest**) |

The **Recommendation Gate** is a runtime block, not a measurement. Each material number
references `tool_call_id + field_path`; the backend resolves it against the **same
Turn's** traces and validates field, unit, `as_of`, **Claim**, and sanctioned
interpretation **before** the `content.block` is emitted. An invalid block is never
displayed — the Turn ends `incomplete` with reason `grounding_failed`, and previously
checkpointed valid blocks stay useful.

News is the only untrusted external prose, admitted wrapped in an `untrusted_evidence`
block with markup stripped, each document bounded, and source and publication time
attached. A number found only in news is a `source_claim` and cannot independently
support a verdict or a price zone. **No second summarising model** is added: the useful
blast-radius controls are architectural.

`answer_kind` is `analysis | education | refusal`, classified by the harness under the
Contract — **no separate model router in v1**. Input is capped at **8 KiB UTF-8**; no
attachments; no user-supplied URL is ever fetched.

## 10. Persistence

### 10.1 Nine tables, JSONB throughout, one Alembic revision

```
watchlist_entries   user_id · symbol · added_at · last_seen_analysis_date

analysis_run        symbol · trading_day · status · error · attempts · origin
                    · next_attempt_at · started_at · finished_at
                    mutable, UPDATE in place

analysis            symbol · trading_day · verdict · payload JSONB · schema_version
                    UNIQUE(symbol, trading_day)          append-only, immutable

agent_thread        id · user_id · title · symbols text[] (GIN) · created_at · updated_at

agent_message       id · thread_id · seq · role · content · created_at
                    · flagged_reason · flagged_at        both nullable, see §A7
                    UNIQUE(thread_id, seq)               role ∈ user|assistant|summary

agent_tool_call     thread_id · request_message_id → agent_message(id) NOT NULL
                    tool_name · arguments JSONB · result JSONB · status · error
                    latency_ms · prompt_tokens · completion_tokens · started_at

agent_turn          id (client UUID) · thread_id · request_message_id
                    · response_message_id · retry_of_turn_id · status · terminal_reason
                    · cancel_requested_at · started_at · finished_at · last_event_seq
                    · draft_content JSONB

llm_call_usage      owner_type · owner_id · route · model
                    · input/cached_read/cache_write/output/reasoning tokens
                    · pricing_version · four token prices
                    · reserved_micro_usd · actual_micro_usd · status
                    owner_type ∈ analysis_run | turn_request_message
                                | capability_probe | eval_run

eval_run            id · started_at · mode · route · model · prompt_version
                    · tool_catalog_version · registry_version · fixture_version
                    · per-category totals · report_path
```

**One revision for all nine**, created at A2 — the first milestone that needs any of
them. Five tables then sit empty until A5, which costs nothing, and it preserves the
reason the persistence decision gave for a single revision: these tables come into
existence together, `agent_message` means nothing without `agent_thread`, and splitting
into nine links on an already-inconsistent Alembic chain adds nine places to rebase
wrong while buying no partial rollback that is real. Name it by `--autogenerate`; do not
hand-write a hash.

The **Corporate Action** table is *not* part of this set — it belongs to the signals
domain and lands in A1 with its own revision:
roughly `(symbol, exright_date, event_code, exercise_ratio, value_per_share, confirmed)`
from `Company(source='VCI').events()` on a slow Collector cadence.

> **Reconciled conflict — table count.** The persistence decision settled six tables;
> orchestration added `llm_call_usage`; the transport decision added `agent_turn` and the
> evaluation decision added `eval_run`, each counting "seven → eight" without knowledge
> of the other. **The union is nine.** No other table is implied by any closed decision.

> **Reconciled conflict — table names.** Spec 0001 §M3–§M4 sketched `watchlist_items`,
> `analyses`, `analysis_runs`, `threads`, `thread_messages`, `turns`,
> `tool_call_traces`, and `widgets`. The names above supersede them, and **there is no
> `widgets` table**: a message stores the validated Widget *spec*, per §10.4.

### 10.2 The five invariants

1. **A row in `analysis` existing means it is complete.** In-flight state lives only in
   `analysis_run`. This is what makes *serve yesterday instantly while today runs* need
   no mechanism at all: `ORDER BY trading_day DESC LIMIT 1`. There is never a
   half-written Analysis to filter out.
2. **`run = ready` ⇒ the `analysis` row exists.** So write `analysis` first, then flip
   the status. Dying between leaves the run at `producing`; the retry hits
   `UNIQUE(symbol, trading_day)`, finds the Analysis, and flips the status without
   re-producing. **Idempotency is a consequence of the constraint, not extra code.**
3. **Traces anchor to the user message** (`request_message_id NOT NULL`) — the one row
   that exists before the first tool call. A nullable id patched in after the assistant
   message forms would orphan traces exactly when a Turn dies mid-flight and the trace
   matters most. Per-Turn tool cost is then a `SUM` over that column.
4. **Transcript order is held by `UNIQUE(thread_id, seq)`, never by timestamps.** Two
   streamed messages can share a millisecond, and a timestamp cannot express inserting
   between two rows. `seq` is allocated inside the writing transaction; a conflict
   retries.
5. **`analysis`'s unique key excludes `schema_version`** — deliberately unlike
   `provider_snapshots`. There is one author, at most one Analysis per pair, and every
   reader reads by exactly that pair. Two rows differing only by template version would
   force every reader to choose, and no choice rule is correct. Readers handle several
   `schema_version` values instead; that is what the column is for.

### 10.3 Shape decisions

- **`analysis` split from `analysis_run`** because the run is mutable while the content
  is written once. Merged, every `attempts` bump would make Postgres MVCC rewrite a row
  dragging a large JSONB payload along.
- **JSONB payload plus extracted `symbol`, `trading_day`, `verdict`** — not four
  normalised per-axis tables. The template is fixed but *will* change, and normalising
  the axes turns every template change into four migrations; a pure blob would force the
  rail to parse whole payloads to show one word for ten symbols.
- **`agent_thread.symbols text[]` with a GIN index, no join table.** The question asked
  in practice is *which Threads discussed FPT*.
- **`agent_tool_call` stores full results.** Results are the first thing usually dropped
  for fear of bloat, but ADR-0009 already caps them at 4KB, and they are exactly what is
  needed to debug a wrong answer: what the model actually saw.
- **`agent_turn` holds the lifecycle and the checkpointed draft**, which cannot live in
  `agent_message` (canonical and immutable) or `agent_tool_call` (anchored to one call).

### 10.4 Widgets, `data_ref`, and replay

A message stores the **validated Widget spec** — a fixed-date retrieval descriptor —
never the chart data. The 24-hour Redis `data_ref` is a hot cache only; after expiry the
same historical slice is reconstructed from the store, which is sound because EOD data is
settled. Embedding the data would copy the same price array into the database once per
chart, forever.

Traces are **readable, not re-runnable.** Bit-exact replay would need pinned input
snapshots against a nightly-changing store, and the model is non-deterministic above
temperature 0. That price is not worth paying for internal debugging, and it is stated
openly rather than implied.

### 10.5 Sessions and pooling

The agent path is async (`get_db`); the tool layer reaches the sync `SnapshotStore`
through `asyncio.to_thread` rather than being rewritten. **No DB session is held across a
streaming Turn** — each write opens, writes, closes. The async pool is
`pool_size=5, max_overflow=10` → **15 connections**, so holding one per Turn would cap
concurrent Turns at 15 and make the 16th wait 30 seconds and then fail. A Turn with
several tool calls easily exceeds 60 seconds, so this is not theoretical. The trade-off
— no transaction spanning a Turn — is correct anyway: a Turn killed mid-flight *should*
leave the trace of what already ran.

### 10.6 Retention

| Table | Retention |
| --- | --- |
| `analysis` | indefinite; no purge job (~100 symbols × ~250 sessions ≈ 25k rows/year) |
| `agent_thread`, `agent_message` | indefinite — user-authored content |
| **Evidence Manifest** (with the message) | indefinite |
| `agent_tool_call` | **90 days**, folded into the existing 16:00 ICT cleanup job |
| `agent_turn`, `llm_call_usage`, `eval_run` | indefinite — **derived, see §15**; small and audit-bearing |
| Redis `data_ref` | 24h TTL |

Deleting a Thread cascades to its messages, traces, and turns. Analyses are untouched:
they never belonged to the Thread.

## 11. Orchestration, quotas, and budget

Full contract: ADR-0014. The engineering surface:

- **Admission before dispatch.** A short Postgres transaction locks the budget scopes,
  checks actual spend plus open reservations, inserts the worst-case reservation, and
  commits; the network call then runs with **no transaction held**; the response
  reconciles to actual usage. A death after provider acceptance leaves `usage_unknown`
  with the full reservation charged.
- **Envelope**: $50/month = **$10** Analysis + **$30** Turn + **$5** emergency + **$5**
  eval. Alert at 70%; at 100% reject new work while admitted work finishes.
- **Per Analysis**: ≤6,000 input / 1,500 output tokens per generation, ≤$0.0045 across
  all attempts for the pair. **Per Turn**: ≤32,000 constructed-context tokens per call,
  ≤100,000 aggregate input, ≤20,000 aggregate output including reasoning, ≤$0.50.
  **Per user**: 20 Turn starts/ICT day, $3/ICT day, $15/rolling 30 days, one active Turn
  — against three system-wide.
- **A Turn that cannot fund its next call ends without another LLM apology call**,
  persists the partial message and traces, and emits `turn.incomplete` with a stable
  budget reason.
- **Nightly schedule is data-readiness driven**: full Collector at 16:15 ICT, then
  FiinQuant-owned `market` and `valuation` re-runs at 18:30, 21:30, 23:00 if no new
  Trading Day was established. Availability deadline **07:00 ICT**; an Analysis is never
  manufactured from the previous Trading Day to meet it. Cohort states are
  `running | complete | partial | blocked`.
- **The nightly cohort is the distinct Watchlist union**, captured when the first Market
  Snapshot establishes a new data-defined Trading Day. **Removing a symbol after cohort
  creation does not cancel its committed Analysis Run** — the Analysis is keyed by
  `(symbol, trading_day)` and shared, so it was never that user's to cancel. A later
  addition uses the on-demand lane and still deduplicates on the same key.
- **Only a Watchlist addition may create an on-demand Analysis**, capped at **three new
  ones per user per Trading Day**. Adding a symbol whose Analysis already exists costs
  nothing and does not consume the allowance; above it the addition still succeeds and
  its Analysis waits for the next nightly cohort. Asking the agent about another Universe
  symbol uses store-only tools and silently produces no artifact.
- **Ordering** within the queue: on-demand with a user waiting → never-analysed symbols →
  oldest prior Analysis → most Watchlists containing the symbol → symbol ascending. One
  worker, `FOR UPDATE SKIP LOCKED`, `origin = nightly | on_demand`, and an in-flight
  provider call is never preempted.
- **Retry**: immediately after readiness, then +5 minutes, then +30 minutes, inside the
  three-attempt ceiling. `auth_unavailable` is route-wide — pause the dispatcher and
  probe every 15 minutes rather than recording the same failure per symbol.
- **Scheduler state and `next_attempt_at` live in Postgres**, so a restart before the
  deadline resumes rather than relying on the in-memory job status store.
- **One Redis leaky bucket owns the vnstock account allowance** for every live path: ≥3s
  spacing without `VNSTOCK_API_KEY` and ≥1s with it; a distributed Collector lease for
  exclusive access while it runs; `search_news` on its own 5/15 rpm lane with per-symbol
  single-flight, a 6-hour fresh cache, and ≤24h of visibly stale service; Backfill and
  frozen legacy routes below news. **Redis failure is fail-closed for Provider Source
  calls**; store-backed APIs keep serving.
- **Prompt caching** covers only the stable prefix — system prompt, output schema, tool
  schemas — keyed by model, `prompt_version`, `tool_catalog_version`. It never changes
  correctness or control flow.

## 12. Milestones

`M0`–`M2` are spec 0001's and are unchanged. `A1`–`A7` below **replace** spec 0001's §M3
and §M4.

| ID | Title | Depends on |
| --- | --- | --- |
| A1 | Signals foundation: Corporate Actions, `prepare_bars()`, Signal Registry, null harness | M0 |
| A2 | Watchlist, Analysis, Analysis Run — persistence, API, rail | M0 |
| A3 | LLM boundary, Capability Probe, Budget Validation, spend admission | A2 |
| A4 | The nightly Analysis pipeline | A1, A2, A3 |
| A5 | Tool Catalog and the agent loop | A1, A2, A3 |
| A6 | Streaming transport, the Alpha Desk surface, the Widget registry | A2, A4, A5 |
| A7 | Eval Fixture, Eval Battery, one passing gate run | A4, A5, A6 |

Every milestone passes the repository gates before it is called done: `make test` in
`apps/api`, and `pnpm type-check`, `pnpm lint`, `pnpm test`, `pnpm build` in `apps/web`.

### A1 — Signals foundation

`src/stocks/signals/` with `prepare_bars()`, the registry, the null harness, the fourteen
computations grouped into the five clusters, and the `corporate_actions` table with its
slow Collector cadence and ex-date confirmation.

**The one-time price-basis repair belongs here** and needs no provider calls and no
truncation: every FiinQuant row already *is* raw (`adjusted=False` since the day each
call was written) and every vnstock row already *is* `adjusted_at_source`, so the fix is
an in-place payload `UPDATE` keyed on `source`, stamping `price_basis` under
`schema_version` 2 — **not** a re-collection, because `schema_version` is part of the
store's uniqueness key.

**A1 also retrofits the Volume Spike signal M2 already shipped.** M2 reads
`provider_snapshots` directly and knows nothing about **Price Basis**, so once
`prepare_bars()` exists the 20-Trading-Day baseline must go through it and gain the
`volume_basis_break` condition of ADR-0006 — a baseline crossing a share-count-changing
action is `degraded`, not silently comparable. This is not a defect in M2: the contract it
would need did not exist when it shipped. It is why the retrofit is named here rather
than left for someone to notice.

Exit criterion: a registered field either returns with honest **Window Health** or
refuses with a named reason, the null harness fails the suite when any `signal` field's
FPR exceeds 1%, and no computation reaches bars except through `prepare_bars()` —
Volume Spike included.

### A2 — Watchlist, Analysis, Analysis Run

The nine tables in one revision; the Watchlist API with the ten-symbol cap counting
`active` entries only, Universe-restricted addition, and the `unsupported` transition; the
five rail states with `failed` never rendering empty; `last_seen_analysis_date` advancing
only on opening that Analysis; three-attempt retry per symbol per session; the
`producing` sweep after `analysis_run_stuck_minutes`.

Exit criterion: two users watching one symbol share exactly one Analysis for a Trading
Day; no `ready` run lacks its `analysis` row; a restart mid-production recovers.

### A3 — LLM boundary and spend admission

`src/core/llm/` with the protocol, transport, the four-check Capability Probe in
`lifespan`, local Budget Validation, the error taxonomy, and `llm_call_usage` reservation
and reconciliation.

Exit criterion: a route silently dropping any probed parameter refuses startup with the
failing check named; no provider call is possible without a committed reservation.

### A4 — Nightly Analysis pipeline

§8 in full, plus the ingestion prerequisites it declares in §13.

Exit criterion: an Analysis is produced for the exact data-defined Trading Day, cites
registered fields only, carries its audit metadata, and a rerun of a ready pair is a
no-op.

### A5 — Tool Catalog and the agent loop

`src/agent/` with the twelve tools, the loop, the versioned System Prompt Contract, the
Recommendation Validator, and the thread/message/trace persistence paths.

Exit criterion: a Turn survives a dropped connection, its traces read back as an ordered
decision chain, an unprovable content block is never displayed, and a mismatched
`tool_call_id` fails loudly.

### A6 — Transport and surface

§7 plus the Alpha Desk route, the Next Route Handler proxy, and the Widget registry with
its leaf-chart extraction and accessible palette.

Exit criterion: the end-to-end streaming test of ADR-0013 passes through the real
browser → Next → FastAPI path.

### A7 — Evaluation

The Eval Fixture, ~56 Eval Cases across six categories over both surfaces, the
deterministic layer, the blind human rubric, `make eval`, the report format in
`docs/eval/`, and `eval_run`.

It also builds the two production-observability pieces ADR-0016 names, because without
them the battery has no way to grow and no field signal to reconcile against:

- **Flag a message** — one action carrying `message_id` plus a reason label
  (`wrong_figure | overreach | wrongly_refused | other`). ADR-0016 forbids a new table for
  observability, so this rides as a nullable `flagged_reason` + `flagged_at` pair on
  `agent_message`, inside A2's revision. A flag confirmed as a genuine failure becomes a
  new Eval Case, frozen with its fixture. There is no dispute workflow beyond this, and
  replay means re-reading the **Evidence Manifest**, not reproducing the answer.
- **One fixed ops query** over signals that already exist — `grounding_failed` in the Turn
  lifecycle, `unknown_tool` in `agent_tool_call`, the `answer_kind` distribution,
  incomplete reasons, and flag counts. Its output **must appear in the next Eval Report**.
  No automatic alerting. One threshold is read by eye: `grounding_failed` above **5% of
  Turns over 7 days** reopens category B, because that pattern means the Gate is blocking
  wrongly rather than the model fabricating.

Exit criterion: **one passing `gate` run**, which is part of the definition of v1 done,
with the ops-query output included in its report.

## 13. Prerequisites this spec does not fictionalise

The Analysis Field Profile is a **target contract**, not proof that every field exists.
Implementation must create precursor ingestion tickets or surface the declared refusals.
**It must never substitute a legacy live read to make the artifact look complete.**

1. **Money flow is unwired.** Adapters and snapshot fields exist; no collector or
   endpoint uses them. `foreign_flow_pressure` and `company_profile.foreign_room_pct`
   have no inputs until this lands.
2. **Durable daily history and indicators.** `DAILY_OHLCV_ENABLED=False` with a 7-day
   window; `stock_daily_ohlcv` is not a history store and its prices are in thousands.
   Trailing windows must read `provider_snapshots`.
3. **News is not persisted.** Until it is, the News section is `refused/unavailable` and
   its two count fields have no inputs.
4. **Rich fundamentals are not durably stored.** Bank, developer, and retail metrics are
   live quota-bound calls today.
5. **Corporate Actions must be loaded before trailing technical fields are trustworthy.**
   Until the table exists, every raw-era window containing one of the measured
   unexplained gaps is refused — for some symbols that is most windows. This is why the
   table is a prerequisite rather than a follow-up.
6. **The Universe cap is not forwarded into `docker-compose`**, so the configured
   Universe is not the one a container runs.

## 14. Open decisions

Genuinely undecided. None blocks a build session from starting A1, A2, or A3.

1. **Per-field `min_sessions` and frozen threshold constants.** ADR-0010 fixes the rule
   (window plus skip; derived from the null; stricter of convention and derived); the
   concrete numbers are produced by the null harness at implementation and then frozen.
   Blocks: A1 completion.

   One inherited inconsistency to settle while registering the momentum field, flagged
   rather than resolved here because it needs the formula, not a document: the field is
   named `momentum_rank.percentile_12_2` and the bar decision calls it "12-2 momentum",
   but its stated `min_sessions` of **273** is `252 + 21` — a **one-month** skip, i.e.
   12-1, which is also what the research shortlist calls it. Either the name or the skip
   is wrong. Pick one, and let the registered `min_sessions` follow the formula actually
   implemented.
2. **How the limit-lock detector is written.** ADR-0006 settles that it reads raw prices
   and takes the band from the exchange regime for that session; the detector itself
   belongs to A1.
3. **The System Prompt Contract's *content*.** Its structure, sections, and precedence
   are fixed (ADR-0015); the prose belongs to the build session, tuned against the
   production model family. Blocks: A5 completion, not A5 start.
4. **`docker-compose.prod.yml`'s outer proxy and internal API URL.** ADR-0013 states the
   requirement; the concrete deployment topology is not chosen. Blocks: A6 completion.
5. **Whether an operator may pin a symbol into the cohort's fifty places.** Carried over
   from spec 0001 and still assumed **no**. Blocks: nothing.

## 15. Assumptions recorded

Inferred rather than stated, and each cheap to reverse.

- The nine tables land in **one Alembic revision at A2**, leaving five empty until A5.
  The alternative — a revision per milestone group — is a live option if an empty-table
  migration proves awkward in review; nothing else depends on the choice.
- `src/stocks/signals/` is shared by the **Volume Spike** signal and the registry. M2
  shipped first and established the package, so A1 extends it rather than creating it.
- A3 has no dependency on **A1** and may be built alongside it, but it does depend on
  **A2** — for the migration alone, since its exit criterion needs `llm_call_usage` to
  exist. Splitting the migration per milestone group would free A3 from A2 entirely; that
  is the live alternative named above, and nothing else turns on the choice.
- A4 and A5 need A1, A2, and A3. A5 in particular because the tool layer reads `analysis`
  and the loop writes threads and traces created by A2's revision.
- The Widget registry's leaf-chart extraction is `apps/web` work with no API dependency
  beyond a validated spec, so it may start during A5.
- **Retention for `agent_turn`, `llm_call_usage`, and `eval_run` is derived, not decided.**
  No closed decision set it. Indefinite is chosen because all three are audit-bearing and
  bounded by Turn and gate-run counts rather than by tool calls — the one thing that grows
  per call, `agent_tool_call`, is the one thing pruned. If `llm_call_usage` ever grows
  awkward it prunes on the same 16:00 ICT job, and nothing depends on the window.
- **Flag-a-message lands as two nullable columns on `agent_message`**, because ADR-0016
  forbids a new table for observability but the action needs somewhere to live. A separate
  `message_flag` table would be the alternative if a message ever needs more than one
  flag; nothing in v1 does.
