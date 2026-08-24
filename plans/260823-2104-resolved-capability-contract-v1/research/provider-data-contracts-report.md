# Provider data contracts: FiinQuant vs VNStock

## Scope and method

This report is a static code-and-document review for Resolved Capability Contract
v1. It made no provider calls, read no credentials or environment values, and
changed no source, plan, database, or runtime configuration. The attempted
skill-mandated background delegation could not start because the agent thread
limit was already reached; the review therefore used the same primary sources
directly in this session.

The central finding is that three different concepts must remain separate:

1. `SOURCE_OWNERSHIP_BY_CAPABILITY` declares which provider may write/read a
   normalized stock snapshot. A cover is explicit coverage, **not** an automatic
   runtime fallback (`SourceOwnership`, `main_source`, `cover_source`, and
   `owns_capability` in `apps/api/src/stocks/providers/contracts.py`).
2. A provider class with the relevant `fetch_*` method is the executable adapter.
   Declaration without such a class is not executable availability.
3. A generic resolved capability describes model/runtime execution policy and a
   handler. Provider price, time, quota, batch, and partial-data semantics remain
   in provider/evidence/policy owners; they are not a second generic capability
   taxonomy.

## Exact ownership and execution matrix

| Data surface | Declared Main / Cover | Executable adapter(s) now | Exact conclusion for v1 |
|---|---|---|---|
| Market/current equity session | FiinQuant Main; VNStock Cover | `FiinQuantMarketProvider.fetch_market` and `.fetch_market_history`; `VnstockMarketHistoryProvider.fetch_market_history` only | Current collection is executable only through FiinQuant. VNStock is executable only for named historical cover; it cannot satisfy current market. Never resolve Cover as an implicit failover. |
| Market index | FiinQuant Main; no Cover | `FiinQuantMarketIndexProvider.fetch_index_history` only | Executable as history only. There is deliberately no current-index method and no VNStock cover. A current index request must not be inferred from ownership. |
| Valuation | FiinQuant Main; VNStock Cover | `FiinQuantValuationProvider.fetch_valuation`; no VNStock valuation class/method | VNStock valuation is declaration-only and currently unavailable. The resolver must not advertise a fallback or executable route merely because `cover_source(VALUATION)` returns VNStock. |
| Reference / share count / foreign room | VNStock Main; no Cover | `VnstockReferenceProvider.fetch_reference` | Executable through one VNStock price-board call. It carries listed shares only plus current/total foreign room. FiinQuant has no executable reference adapter. |
| Fundamentals | VNStock Main; no Cover | `VnstockFundamentalProvider.fetch_fundamentals` | Executable per symbol, unbatched. It emits up to eight reported quarters and may retain a filing with missing cash-flow fields. No FiinQuant adapter exists. |
| Corporate actions | No standalone `Capability` enum member or `SOURCE_OWNERSHIP_BY_CAPABILITY` row | `VnstockCorporateActionProvider.fetch_corporate_actions`; `CorporateActionProvider` protocol | Executable but not declared as a provider snapshot capability. Tests currently assert that its source equals the Reference Main source. This is a deliberate association, not evidence that `Capability.REFERENCE` and corporate actions have identical schemas, storage, time, or refusal semantics. |

Primary evidence:

- Declaration: `Capability`, `SourceOwnership`, and
  `SOURCE_OWNERSHIP_BY_CAPABILITY` in
  `apps/api/src/stocks/providers/contracts.py:31-166`; locked by
  `test_source_ownership_matches_the_measured_main_cover_table` and
  `test_source_ownership_answers_which_sources_may_own_a_capability` in
  `apps/api/tests/test_provider_contracts.py:296-328`.
- Executable FiinQuant surface: `FiinQuantMarketProvider` at
  `fiinquant.py:416`, `FiinQuantMarketIndexProvider` at `:584`, and
  `FiinQuantValuationProvider` at `:660`.
- Executable VNStock surface: `VnstockReferenceProvider` at
  `vnstock_provider.py:261`, `VnstockMarketHistoryProvider` at `:570`,
  `VnstockFundamentalProvider` at `:710`, and
  `VnstockCorporateActionProvider` at `:869`. There is no valuation or index
  provider class in that module.
- `SnapshotStore._require_owning_source` enforces declaration at persistence/read
  time; `SnapshotStore.series` reads named Main and Cover rows, and
  `resolve_sessions` chooses Main for an overlapping effective session
  (`apps/api/src/stocks/providers/store.py:90-123, 156-185, 290-354`). This is
  source-aware composition, not live failover.
- The earlier eval plan reaches the same executable/declaration distinction in
  its Development provider boundary and Phase 1 validation log
  (`plans/260823-1744-investment-intelligence-eval-replay-harness/plan.md`,
  “Development provider boundary” and “Validation log”).

## Data semantics that the plan must preserve by reference

### Price basis and units

- FiinQuant explicitly passes `adjusted=False` and writes
  `PriceBasis.RAW` (`MARKET_ADJUSTED`, `MARKET_PRICE_BASIS`, and
  `_build_snapshot`/`_build_index_snapshot` in
  `apps/api/src/stocks/providers/fiinquant.py:71-76, 776-873`). Market and index
  sessions are schema version 2, and the adapter is the only owner allowed to
  state what its upstream flag meant.
- VNStock quote history has no adjustment flag and is normalized as
  `PriceBasis.ADJUSTED_AT_SOURCE`; it also converts quote prices from thousands
  of VND to canonical VND (`MARKET_PRICE_BASIS` and
  `VnstockMarketHistoryProvider`,
  `apps/api/src/stocks/providers/vnstock_provider.py:102-113, 570-707`).
- `SessionSnapshot.price_basis` is required. `PriceBasis.RAW` means the
  exchange-published session price; `ADJUSTED_AT_SOURCE` means a provider answer
  rescaled through the observation time and not reproducible from stored rows
  (`contracts.py:58-76, 242-306`).
- An index is a level, not an equity: it has no band, corporate action, foreign
  flow, or market capitalization. It still declares raw basis so stored meaning
  is explicit (`MarketIndexSnapshot`, `contracts.py:308-334`). This is why
  `MARKET_INDEX` has no VNStock cover.
- FiinQuant market foreign `fb/fs/fn` fields are normalized as VND value, while
  active `bu/sd` are share volumes. The contract forbids unit-name ambiguity and
  bounds net foreign value by gross buy plus sell (`MarketSnapshot`,
  `contracts.py:337-383`; `_build_snapshot`, `fiinquant.py:776-831`).

**Implication:** the resolved capability declaration may say the handler has
external/mixed provenance and returns typed evidence, but `price_basis`, unit,
and provider field meaning belong on each evidence/result row. They must not be
static capability properties: the same generic market tool can read a series
containing an explicit Main/Cover seam, and each observation must retain its
own source and basis.

### Effective, observation, publication, and ingestion time

- Provider snapshots carry only timezone-aware `effective_at` and
  `observed_at`, with `effective_at <= observed_at` (`SnapshotMetadata`,
  `contracts.py:169-192`). They do **not** carry publication or ingestion time.
- FiinQuant market, index, and valuation normalize upstream timestamps to the
  Vietnam session start; `observed_at` is collection time
  (`_session_start`, `_build_snapshot`, `_build_index_snapshot`, and
  `_build_valuation_snapshot`, `fiinquant.py:776-914, 1015-1029`).
- VNStock reference rows have no own effective period; the adapter stamps the
  Vietnam session day on which the board was read and separately records
  collection time (`VnstockReferenceProvider._to_snapshots/_build`,
  `vnstock_provider.py:307-392`). That date means “session observed,” not when
  the share/room fact legally changed.
- VNStock fundamentals use quarter end for both `period_end` and
  `effective_at`, and collection time for `observed_at`
  (`VnstockFundamentalProvider._fetch_one`, `vnstock_provider.py:759-866`). The
  normalized snapshot has no filing publication timestamp. Therefore this
  adapter alone cannot prove a filing was knowable at a historical as-of.
- Corporate action events separately retain `ex_date`, `record_date`, and
  `public_date`, but `CorporateActionEvent` has no `SnapshotMetadata`, provider
  identity, observation time, or ingestion time (`contracts.py:634-710`). A
  null ex-date with a public date is intentionally retained.
- The Investment Intelligence contract requires event/effective/publication/
  ingestion time when different and forbids using a filing before publication
  (`docs/Harness/investment-intelligence-contract.md`, “Financial truth model”
  and “Point-in-time và anti-lookahead”). Eval `EvidenceRecord` already models
  `effective_at`, `published_at`, and `ingested_at` independently
  (`apps/api/src/eval/contracts.py`, `EvidenceRecord`).

**Implication:** generic resolution must carry trusted task `as_of` through
`ToolContext` and require evidence identity in results, as target architecture
already specifies. It must not claim that provider snapshot availability alone
is point-in-time safe. Publication/ingestion completeness is an evidence-plane
health property; until present, historical filing/corporate-action use needs a
named gap/refusal rather than an inferred timestamp.

## Entitlement, quota, and batch constraints

### FiinQuant

- Every adapter shares a login/session and circuit breaker, but missing
  credentials fail before login (`FiinQuantProviderBase`,
  `fiinquant.py:333-414`). Error text is sanitized because upstream login errors
  have echoed credentials.
- Token entitlement is best-effort metadata. An unreadable/missing token does
  not refuse; a disabled or already-ended entitlement raises
  `FiinQuantEntitlementExpired`; “ends today” logs a warning because the provider
  may already refuse on the boundary (`Entitlement`, `read_entitlement`, and
  `_check_entitlement`, `fiinquant.py:203-302`; corresponding entitlement tests
  at `test_fiinquant_provider.py:1060-1136`). This is not a complete capability
  probe for a package/tier.
- `MAX_BATCH_SYMBOLS = 100` is an adapter safety limit. More than 100 is rejected
  before upstream; a gateway timeout is typed as `FiinQuantBatchTooLarge` so a
  caller may split the same symbols, while an ordinary provider outage is not
  misclassified (`fiinquant.py:48, 102-122, 357-366, 392-410`; tests
  `test_fiinquant_provider.py:508-512, 562-596, 855-863`).
- Market/current uses one candle batch plus overview and ceiling/floor calls;
  market history and index history are one-symbol window reads; valuation is one
  batched window call (`FiinQuantMarketProvider`,
  `FiinQuantMarketIndexProvider`, `FiinQuantValuationProvider`).
- Published provider research records a free-tier realtime scope of 33 symbols
  and tier-varying history/request/connection limits, while repository
  experience says historical calls exceeded 100. Those commercial limits are
  volatile entitlement facts, not source-code contract constants
  (`docs/research/vn-market-data-sources.md:175-196`).

### VNStock

- All VNStock live paths share `VnstockQuotaArbiter`; the adapters intentionally
  have no local pacer (`vnstock_provider.py:1-15, 225-259`). Source calls pass
  through `src/core/vnstock_client.py` before the provider is reached.
- The account model is 20 requests/min guest, 60/min keyed, and 3,000/hour with
  a 0.9 safety factor. Redis owns the shared leaky-bucket state. A Redis failure
  fails closed as `QuotaUnavailable`, the collector lease refuses all other
  lanes as `CollectorLeaseHeld`, and overlong interactive waits refuse rather
  than queue indefinitely (`apps/api/src/core/quota.py:78-181, 212-330`).
- Reference is one batched board request for all requested symbols; there is no
  adapter-side numeric `maxItems` (`VnstockReferenceProvider.fetch_reference`,
  `vnstock_provider.py:261-329`; `TestReferenceQuota` in
  `test_vnstock_provider.py:323-346`).
- Market history is one request per symbol/window. Corporate actions are one
  request per symbol for the whole event history
  (`VnstockMarketHistoryProvider.fetch_market_history`; corporate action test
  `test_the_feed_is_read_once_per_symbol`).
- Fundamentals are unbatched. The implementation currently performs **three**
  upstream reads per symbol—income statement, balance sheet, and cash flow—not
  two. Cash-flow failure degrades to missing CFO/CFI/CFF, while income/balance
  establish the filing (`VnstockFundamentalProvider._fetch_one`,
  `vnstock_provider.py:759-866`; `FakeFinance` and
  `test_a_failed_cash_flow_read_keeps_the_filing` in
  `test_vnstock_provider.py:503-539, 626-641`). The module header said “two
  requests per symbol”; the implementation is the current executable truth. The
  Stage 0 plan was corrected during this planning pass to say three calls:
  income and balance required, cash flow degradable.
- `STATEMENT_QUARTERS = 8`; fewer returned periods/fields remain absent rather
  than being synthesized (`vnstock_provider.py:93-100`, fundamental tests).

**Implication:** the resolved capability can expose a generic concurrency/
ordering class, deadline, availability status, and sanitized refusal reason. It
should reference the handler and its probe. Exact account allowances, collector
lease, paid entitlement, retry/split decisions, and provider call fan-out belong
to quota/policy/provider owners. If a model-facing tool itself accepts a symbol
list, its strict schema may declare that tool's real `maxItems`; do not copy
FiinQuant's adapter limit into every generic market capability or expose a
provider raw batch interface to the model.

## Refused, unavailable, absent, and partial are different outcomes

| Condition | Current executable meaning | Resolution/evidence implication |
|---|---|---|
| FiinQuant entitlement expired/disabled; credentials absent; circuit open; malformed or wholly empty frame | Typed provider unavailable/error; no valid snapshot | Resolve unavailable only from an actual probe/handler state, with sanitized reason. Do not advertise declaration-only cover. |
| FiinQuant batch >100 or gateway timeout recognized as oversized | Request shape can be split; not proof provider is down | Keep as provider/domain retry taxonomy behind handler; generic executor still settles exactly once. |
| FiinQuant requested symbol absent, invalid zero-price row, or valuation row with neither P/E nor P/B | Drop only that symbol/session; do not fabricate | Structured result must represent partial/absent evidence, not turn it into global success or zero. |
| VNStock quota arbiter/collector lease/capability unsupported | Account/lane refusal propagated unchanged; provider call does not occur | Availability/refusal must be model-visible and sanitized. Runtime must not bypass policy by trying a cover. |
| VNStock market-history empty frame | Valid empty window (e.g. before listing) | Empty is not unavailable. |
| VNStock reference wholly empty/missing required columns | Batch-level provider contract error | Do not render “no reference facts” as a healthy empty market. |
| VNStock reference symbol absent/all fields absent/invalid room | Symbol row skipped; other batch rows retained | Report partial health; current room greater than total room is refused, not caveated into storage. |
| VNStock fundamental layout unknown | Batch-level contract refusal because unit/scale would be guessed | Fail closed for truth; do not coerce old billion-VND layout into VND. |
| VNStock fundamental per-symbol read failure or missing cash flow | Other symbols continue; missing cash-flow lines are explicit `None` | Preserve partial evidence and field-level health. |
| Corporate action feed empty | Valid no-events result | Distinguish from failed read. |
| Corporate action identifying fields missing | Feed-level refusal | Never treat malformed feed as “market has no actions.” |
| Corporate action optional terms missing | Event retained but downstream adjustment factor may refuse | Capability execution can succeed while derived evidence is unavailable. This belongs to evidence/financial-engine health. |

These distinctions are supported by focused tests in
`apps/api/tests/test_fiinquant_provider.py`,
`apps/api/tests/test_vnstock_provider.py`,
`apps/api/tests/test_provider_contracts.py`,
`apps/api/tests/test_vnstock_quota.py`,
`apps/api/tests/test_vnstock_quota_redis.py`, and
`apps/api/tests/test_vnstock_client_quota.py`.

## What Resolved Capability Contract v1 must encode

The generic resolved declaration should implement the target architecture's
minimum runtime contract, not duplicate provider snapshot schemas:

- stable model-facing name/description and strict input schema;
- human label/display projection;
- actual handler/adapter identity and contract version;
- availability probe result with a sanitized, typed reason; declaration and
  execution must be separately testable;
- read/write, idempotency, approval, sensitivity/authorization, and
  internal/external/mixed provenance classes;
- concurrency/ordering class, deadline, output budget, and artifact policy;
- trusted identity/symbol/as-of supplied through `ToolContext`, not freely
  chosen outside scope;
- structured settled result with evidence handles, health, missing/partial
  status, and refusal reason.

This list follows `docs/Harness/target-architecture.md` “Capability plane” and
“Tool design rules”. It also satisfies the Investment Intelligence contract's
requirement that point-in-time selection, freshness, calculation, tool
execution, budget, and authorization remain deterministic owners.

Provider-facing conformance needed by this plan:

1. Add a static/fixture-backed concordance test that a resolved capability never
   claims an executable handler from `SOURCE_OWNERSHIP_BY_CAPABILITY` alone.
2. Explicitly cover the two inverse mismatches:
   - declared VNStock valuation cover + no VNStock valuation adapter => named
     unavailable, no fallback;
   - executable VNStock corporate-action adapter + no standalone provider
     `Capability` row => do not invent snapshot ownership or reuse Reference
     result semantics.
3. Assert market/current vs market-history and index-history method shape;
   “provider owns market/index” is insufficient to advertise current data.
4. Preserve provider/evidence metadata through handles/results and test that
   source, effective/observed time, price basis, units, and health survive the
   runtime seam.
5. Assert every refusal settles as one structured result without fallback,
   transcript holes, secret text, or zero/empty fabrication.

## What the plan must not encode

- Do not import `Capability`, `ProviderSource`, `SourceOwnership`, snapshot
  models, or provider classes into a generic runtime declaration as its
  canonical capability taxonomy. Runtime capabilities are financial intents;
  provider capabilities are ingestion/storage data classes.
- Do not turn Main/Cover into automatic runtime fallback. Cover is explicit and
  semantically different; Main wins overlap, and price-basis seams remain on
  evidence rows.
- Do not make price basis, exchange units, share type, foreign-room meaning,
  statement period, corporate-action terms, publication completeness, or
  staleness thresholds generic static declaration fields. These belong to
  provider contracts, evidence identities, and deterministic financial engines.
- Do not put VNStock 20/60/3,000 limits, FiinQuant tier limits, collector leases,
  credentials, entitlement packages, or account state in the declaration.
  Keep dynamic admission/probing in policy/quota/provider owners; expose only a
  safe availability/refusal projection.
- Do not make `MAX_BATCH_SYMBOLS=100` a global capability limit. It is a current
  FiinQuant adapter bound and split signal. Only a real model-facing handler
  input bound belongs in that handler's schema.
- Do not “fix” absent executable coverage by adding a provider, fallback, live
  call, or collector in this plan. Provider conformance/collector health are
  separate suites, and `docs/research/data-coverage-audit.md` establishes that
  the provider snapshot stack is largely unwired from serving paths.
- Do not encode SSI FastConnect as prospective fallback or broaden v1 around a
  future provider. Current SSI research confirms it has market/index/foreign
  coverage but no valuation, fundamentals, or corporate actions, and v3 has no
  adjusted close (`docs/research/ssi-fastconnect-capabilities.md:137-168`). That
  is provider-selection evidence, not a reason to generalize this contract.
- Do not let eval materialization, validation, trials, or baseline refresh call
  FiinQuant/VNStock or consume quota. `store_only_execution()` must continue to
  fail before credentials, quota, or network via
  `ensure_provider_source_allowed()`
  (`apps/api/src/core/provider_access.py`; `FixtureWorld.__enter__` in
  `apps/api/src/eval/world.py`). Eval reads only frozen normalized results and
  persisted rows.
- Do not add eval persistence, DB migrations, provider calls, new provider
  configuration, or a production dependency on `src.eval`; these are explicit
  anti-repeat and non-goal boundaries in the eval/replay harness plan.

## Focused test implications

The plan should reuse provider tests as conformance evidence and add runtime
tests around the seam, without retesting provider internals in the resolver:

- resolver: declared+executable, declared-only, executable-without-data-capability,
  probe-unavailable, environment requirement absent, and handler version cases;
- schema: `market_current` cannot resolve to a history-only method; index has no
  current or VNStock route; valuation VNStock cover resolves unavailable;
- result: source, price basis, effective/observed time, publication/ingestion
  gaps, unit, partial/absent/refused health, and evidence handle survive;
- policy: quota/collector/entitlement refusal is sanitized and no alternate
  provider is attempted; generic executor produces exactly one settlement;
- store-only eval: fixture miss and provider-access attempt fail loudly, with
  zero credentials, quota arbitration, network, or provider calls;
- regression: preserve existing provider contract tests for ownership, batch
  ceiling/split taxonomy, entitlement boundary, VNStock quota fail-closed,
  listed-vs-outstanding shares, room bounds, statement period/partial cash flow,
  and corporate-action missing-term refusal.

No tests were executed for this research-only task; the evidence above is from
static source and focused-test inspection, avoiding any risk of environment or
provider access.

## Unresolved questions

1. Should corporate actions become a future standalone provider `Capability`,
   or remain a separately typed adapter/collector whose runtime financial tool
   references its evidence? V1 must not decide this implicitly by aliasing it to
   Reference.
2. What owner will add filing publication and ingestion time before historical
   fundamental cases can be declared anti-lookahead-safe? The current provider
   snapshot cannot answer that.
3. **Resolved for this plan:** budget and replay use the executable three-call
   shape (income and balance required, cash flow degradable). Any later provider
   call reduction is a separately measured optimization, not resolver metadata.
