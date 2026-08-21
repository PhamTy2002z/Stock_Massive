# No model call happens without an atomic worst-case spend reservation, and no route ever falls back on its own

Every provider call is admitted by a short Postgres transaction that locks the
relevant budget scopes, checks actual spend plus open reservations, inserts a
**worst-case reservation**, and commits — *before* the network call, which then
happens with no transaction held. A successful response reconciles the reservation to
actual usage.

Models are chosen **per workload**, never inside a loop, and there is **no automatic
model fallback**.

## Why reserve the worst case before dispatch

An agent loop has no fixed token cost, so a budget checked *after* the fact is a
budget that reports overruns rather than preventing them. Reserving up front makes
one guarantee that matters at the boundary: **already-admitted work always finishes**,
because its worst case was already charged. At 100% of the envelope new work is
rejected; nothing is killed mid-answer to balance a ledger.

Reserving inside a transaction and calling outside it is the other half. Holding a
session across a provider call would put a 15-connection pool behind a 120-second
timeout, so the pool — not the budget — would become the concurrency limit.

## Usage gets its own table, and the trace cannot replace it

Every provider call owns exactly one `llm_call_usage` row, owned by an Analysis Run, a
Turn's request message, a **Capability Probe**, or an **Eval Battery** run. **Tool
Call Trace is not a sound accounting seam**: one generation may emit several parallel
tool calls, a final no-tool generation emits none at all, and the nightly pipeline's
retry and regeneration usage has nowhere to live. Accounting per call and tracing per
tool are different cardinalities, so they are different tables.

The row records owner type and id, route and exact model, input / cached-read /
cache-write / output / reasoning token detail without double-counting reasoning
outside output, the pricing version and the four token prices used, reserved and
actual cost as integer micro-USD, and a lifecycle status including `usage_unknown`.

If the process dies after provider acceptance but before reconciliation, the row
becomes `usage_unknown` and the **full reservation stays charged** through the
applicable period; it is refunded only against provider evidence, and otherwise the
ordinary daily/monthly reset restores allowance. Failed calls count actual usage
whenever the provider reports it. Costs belong to the ICT period containing the real
provider-call timestamp, not to the Analysis Trading Day — so a month-end Analysis
generated after midnight consumes the new month's budget while keeping its original
`trading_day` for audit.

## The envelope

A hard **$50 per calendar month** for the internal production project: **$10**
Analysis production, **$30** interactive Turns, **$5** emergency shared by retries and
operational calls, **$5** for the Eval Battery. Alert at 70%. The Analysis reservation
is not lent to interactive use before the month's last Trading Day has completed, and
the eval lane never borrows from the other two.

Per workload: one Analysis is capped at 6,000 input and 1,500 output tokens per
generation and **$0.0045** across every call and attempt for that
`(symbol, trading_day)`. One Turn is capped at 32,000 constructed-context tokens per
call, 100,000 aggregate input, 20,000 aggregate output including hidden reasoning, and
**$0.50** across all model calls. Per user: 20 Turn starts per ICT day, $3 per ICT day,
$15 per rolling 30 days, one active Turn — against three active Turns system-wide.
The first token, output, or monetary ceiling reached stops further dispatch.

**The per-workload and per-Turn ceilings are constants; the five per-user ones and the
monthly envelope are configuration.** What one account may spend in a day is a spend
decision, not a promise the product makes, and a deployment used internally over a
subscription route answers it differently from one serving strangers over a metered
API. The numbers above remain the defaults, so the contract still has one written home
and one env var restores it: `LLM_USER_TURN_STARTS_PER_DAY`, `LLM_USER_ACTIVE_TURNS`,
`LLM_SYSTEM_ACTIVE_TURNS`, `LLM_USER_DAILY_USD`, `LLM_USER_ROLLING_30D_USD`. `0` is
unlimited, one ceiling at a time. `LLM_SYSTEM_ACTIVE_TURNS` sizes the in-process
semaphore as well as the ledger check, because the two enforce one number from opposite
sides and raising only one of them would raise nothing.

The four lane amounts and the envelope take the same convention, but **all five at once
or none**: zero across all of them declares a deployment with no monthly ceiling, while
a single zero among four funded lanes is a variable nobody filled in and fails Budget
Validation, because an unfunded lane refuses every call in it. The price table is
validated either way — it is what the ledger records against every call, and an
unmetered envelope is not a licence to boot with prices nobody set.

Turning a ceiling off never turns the ledger off with it. Every call is still reserved
and reconciled into `llm_call_usage`, which is what makes the decision reversible: a
deployment that stopped writing cost rows could not go back to enforcing anything,
because the counts the ceilings compare against would be missing for the whole period
it ran that way.

The Eval Battery additionally supports a configurable per-run monetary ceiling through
`LLM_EVAL_RUN_COST_CEILING_USD`. A positive value enforces both the monthly Eval lane
and the owner ceiling atomically. `0` disables those synthetic USD refusals for the
local CLIProxy/CCS route while retaining every token and cost row in the ledger.
Production must choose a positive value when its route is directly metered.

When a Turn cannot reserve enough worst-case budget for its next call, the loop ends
**without another LLM apology call**, persists the partial assistant message and all
traces, and emits `turn.incomplete` with a stable budget reason. Spending a model call
to explain that there is no budget for model calls is the mistake this sentence exists
to forbid.

## Workload models, and no fallback

Analysis and batch generation default to `gpt-5.6-luna`; interactive Turns default to
`gpt-5.6-terra`. Both are `llm_model_*` configuration, and a change is admitted only
after the Capability Probe **and** Budget Validation pass. The Standard service tier is
used; the Batch API is excluded because its 24-hour completion contract cannot meet the
07:00 ICT availability deadline, and fast mode is excluded.

**No automatic fallback**, for a reason that is not conservatism: a fallback route may
have different capabilities — the very capabilities the Capability Probe exists to
verify — and different prices, which invalidates the monetary ceiling that was reserved
against the original model. A route failure therefore follows the shared error taxonomy.
`auth_unavailable` is route-wide: mark the current run retryable, pause the dispatcher,
and probe every 15 minutes rather than walking the rest of the cohort to record the
same failure against every symbol.

**Budget Validation is local and costs no tokens.** At startup it checks the configured
model, the pricing effective date, and the four rates against the token and monetary
ceilings; with `alpha_desk_enabled`, an impossible configuration fails startup rather
than rejecting the first real Turn midway. Capability Probe calls reserve and reconcile
through the same mechanism against the emergency budget, under a hard **$0.25/day**
ceiling so a crash loop cannot spend without bound — exceeding it fails startup with
`probe_budget_exhausted`.

## Only the stable prefix is cached

The cacheable prefix is the system prompt, the strict output schema, and the tool
schemas, keyed by model, `prompt_version`, and `tool_catalog_version`. Analysis
evidence, Thread history, and tool results stay after the breakpoint. Caching never
changes correctness or control flow: admission reserves the cache-write worst case, and
provider-reported cached reads reconcile the actual cost downward. Provider cache ids
are not business data and are not persisted as such.

## One Redis arbiter owns the vnstock account allowance

A single Redis-backed distributed leaky bucket replaces the currently disconnected
pacers and concurrency guards for **every** live Provider Source path.

- Account spacing of at least 3 seconds without `VNSTOCK_API_KEY`, 1 second with it
  (20 / 60 rpm).
- A distributed **Collector lease** gives the Collector exclusive live-provider access
  while it runs.
- Outside that lease, `search_news` has its own lower lane capped at 5 / 15 rpm, with
  per-symbol single-flight, a 6-hour fresh Redis cache, and permission to serve visibly
  stale data for at most 24 hours during Collector activity or provider failure.
- Backfill and the frozen legacy live routes rank below news and still pass through the
  same account bucket.
- **Redis failure is fail-closed for Provider Source calls.** Store-backed APIs keep
  serving; the system never falls back to an unsafe process-local pacer.

This deliberately narrows ADR-0001's rule that the Collector is the only Provider Source
caller, and with it the sentence ADR-0004 and ADR-0005 each state in their own words —
*user requests never call a Provider Source*. Those two stay true for every Snapshot
**Capability**; news is neither a Capability nor a row in `provider_snapshots`, which is
what lets it leave the rule without reopening the serving boundary. `search_news` is the
**sole** cache-aside exception, the arbiter is what makes it bounded rather than a
precedent, and ADR-0001 carries the amendment naming all three.

## Considered Options

- **Post-hoc accounting from provider `usage`.** Rejected: it reports overruns instead
  of preventing them, and a measured gateway added a flat 2,000-token buffer with a
  `length/4` estimation fallback, so `usage` is not trustworthy on every route.
- **A per-Turn token ceiling only, with no monetary ceiling.** Rejected: token
  ceilings do not survive a model or price change, and the envelope is denominated in
  money.
- **Automatic fallback to a cheaper or alternative model on failure.** Rejected above.
- **Reserving inside the same transaction as the provider call.** Rejected: the pool
  becomes the concurrency limit.
- **Per-process rate pacing for vnstock.** Rejected: it is what exists today, in two
  uncoordinated copies sharing one account quota.

## Consequences

- Nightly production is **data-readiness driven**, not a fixed offset after the 16:15
  Collector cron: the full Collector at 16:15 ICT, then FiinQuant-owned `market` and
  `valuation` re-runs at 18:30, 21:30, and 23:00 if no new Trading Day was established
  — never repeating the vnstock reference and fundamental reads. A symbol is enqueued
  as soon as its exact-Trading-Day Market Snapshot and core evidence are usable. The
  availability deadline is **07:00 ICT**, and an Analysis is never manufactured from
  the previous Trading Day to meet it.
- Scheduler state and `next_attempt_at` live in **Postgres**, so a restart before the
  deadline resumes readiness checks rather than relying on the in-memory job status
  store.
- One Analysis worker in v1, claiming runs with `FOR UPDATE SKIP LOCKED`, with
  `UNIQUE(symbol, trading_day)` as the final duplicate barrier and
  `origin = nightly | on_demand` recorded. An in-flight provider call is never
  preempted.
- Users see state and reset time, never USD. Operations sees cohort counts, actual /
  reserved / unknown spend, the retry queue, and route health.
- ADR-0001 is **amended, not superseded**: its serving boundary stands, its Watchlist
  figure becomes 10, and `search_news` is named as the one exception. The orchestration
  decision asked for supersession, but superseding would retire the boundary the same
  sentence asks to preserve — and ADR-0004 already set the precedent of narrowing
  ADR-0001 through an in-place note pointing at the ADR that owns the exception.
- Revisit when the deployment gains a second uvicorn worker or an external user base.
  Both make the in-process pieces — the session semaphore, the Turn registry —
  distributed, and the second also invalidates the internal-use $50 envelope entirely.
