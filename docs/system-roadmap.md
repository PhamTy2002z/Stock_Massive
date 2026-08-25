# System roadmap

This roadmap owns the data and product system that supplies Stock_Massive with
trusted market evidence. It covers source ownership, DNSE integration, event
ingestion, storage, derived projections, APIs, user interfaces, reliability,
and migration from overlapping live-data paths. AI reasoning, evaluation,
memory, proactive judgment, and specialist orchestration belong to the
[Harness roadmap](harness-roadmap.md).

The roadmap adopts DNSE as the internal realtime and microstructure source. It
does not promote DNSE to canonical historical EOD ownership. The decision and
empirical constraints are recorded in the
[DNSE market-data audit](research/dnse-lightspeed-market-data-audit.md).

## Roadmap status model

Checklist state distinguishes implemented system behavior from accepted future
work.

- `[x]` means current source, schema, tests, or live evidence proves the item.
- `[ ]` means the item is not implemented or has not passed its exit gate.
- A phase graduates only when all required exit-gate items are complete.
- Product consumers must not depend on an experimental phase as if it were
  canonical.

## Source ownership decision

The system keeps provider strengths separate and preserves provenance through
normalization and derived outputs.

- **FiinQuant:** retain current main ownership for persisted EOD market and
  valuation data until a separate evidence-backed decision changes it.
- **vnstock:** retain current reference and fundamental ownership and use it for
  gaps DNSE does not cover. A future production package change does not alter
  semantic ownership by itself.
- **DNSE:** own realtime trades, book snapshots, session state, auction expected
  price, intraday foreign flow, indices, futures, and event-derived bars.
- **Stock_Massive deterministic engines:** own unit normalization, board rules,
  bars, metrics, reconciliation, quality state, and product projections.

DNSE does not supply fundamentals, valuation history, corporate actions, news,
proprietary trading, complete industry taxonomy, point-in-time index membership,
full HOSE depth, or order add/cancel events. Those remain explicit gaps or
separate source contracts.

## Architecture boundary with the Harness

System services expose source-neutral, evidence-bearing contracts. The Harness
must consume them through the architecture in
[`Harness/target-architecture.md`](Harness/target-architecture.md), which
synthesizes the accepted Hermes and OpenCode patterns.

- The System does not create an alternate AI runtime, tool executor, policy
  plane, evidence graph, or model-facing provider client.
- Product UI and Harness tools read the same projections and evidence IDs.
- Provider recovery can restore data delivery, but it cannot decide the AI's
  retry, context, judgment, or autonomy policy.
- DNSE credentials, wire payloads, and provider-specific units stop at the
  adapter boundary.
- A model never connects directly to DNSE, Redis, or the event store.

## Dependency path

The System advances from contracts to a reliable feed, then to product and
operational adoption.

```text
S0 Data contracts and source ownership
  -> S1 DNSE adapter and conformance
  -> S2 Realtime ingestion spine
  -> S3 Trades, bars, and foreign-flow MVP
  -> S4 Depth, auction, session, and market pulse
  -> S5 Replay, derivatives, and feature projections
  -> S6 Product APIs and user surfaces
  -> S7 Reliability, migration, and production readiness
```

Harness dependencies use identifiers from the
[Harness roadmap](harness-roadmap.md). System data may be collected before the
AI consumes it, but no model-facing tool bypasses Harness capability and
evidence gates.

## Phase S0 — Establish data contracts and source ownership

This phase fixes semantic boundaries before the first DNSE production adapter.
It prevents provider wire fields and board-specific units from leaking into
storage, APIs, calculations, or prompts.

**Delivery checklist:**

- [x] Complete a read-only live audit of DNSE REST and WebSocket authentication,
  documented channels, historical coverage, pagination, rate headers, units,
  and known failure semantics.
- [x] Decide that DNSE owns internal realtime/microstructure data, not canonical
  historical EOD data.
- [x] Decide that the official DNSE SDK is reference material rather than a
  production dependency in its audited form.
- [x] Define normalized contracts for `TradeTick`, `BookSnapshot`,
  `ForeignFlowSnapshot`, `AuctionSnapshot`, `SessionState`, `IndexTick`,
  `SecurityDefinition`, and `ClosedBar` in the
  [realtime contract boundary](../apps/api/src/stocks/realtime/contracts.py).
- [x] Require source, event family, symbol, exchange, board, product group,
  trading day/session, provider time, observed time, units, schema version, raw
  payload hash, and quality state on every event through `EventMetadata`.
- [x] Version board-specific price and quantity normalization rules in the
  [normalization registry](../apps/api/src/stocks/realtime/normalization.py).
- [x] Define explicit outcomes for invalid request, unknown symbol, no session,
  retention miss, silent-empty response, stale data, duplicate, gap, and
  provider failure in the [typed policy](../apps/api/src/stocks/realtime/policy.py).
- [x] Define source-neutral reconciliation and provenance rules for daily,
  intraday, and cross-provider comparisons in the same policy boundary.
- [x] Decide retention classes for raw events, normalized events, projections,
  replay artifacts, and operational metadata in the versioned retention policy.

**Exit gate:**

- [x] [Contract and mutation tests](../apps/api/tests/test_realtime_contracts.py)
  reject wrong unit, board, timestamp, identity, price basis, and duplicate
  semantics before persistence.
- [x] [Provenance tests](../apps/api/tests/test_realtime_policy.py) prove provider
  additions cannot silently overwrite another source's evidence.
- [x] Security review and strict-boundary tests confirm secrets remain outside
  logs, payloads, and committed configuration. See the
  [security posture](system-data-contracts.md#security-posture).

## Phase S1 — Build the DNSE adapter and conformance suite

This phase isolates authentication, REST, WebSocket, wire parsing, rate
handling, and provider quirks behind the normalized contracts from S0.

**Delivery checklist:**

- [x] Implement HMAC REST authentication with verified TLS and bounded timeouts
  in the [DNSE authentication and REST boundary](../apps/api/src/stocks/realtime/dnse/).
- [x] Implement WebSocket authentication, ping/pong, eight-hour rotation,
  reconnect, resubscribe, and cancellation in the
  [bounded WebSocket client](../apps/api/src/stocks/realtime/dnse/websocket.py).
- [x] Implement REST clients for instruments, security definitions, OHLC,
  trades, quotes, foreign trading, expected price, close, sessions, and working
  dates.
- [x] Validate resolution, instrument type, date order, one-day event windows,
  and page size locally before sending a request.
- [x] Consume rate-limit headers and enforce endpoint-family budgets without
  quota-exhaustion probing.
- [x] Parse JSON first; admit MessagePack only after live payload conformance is
  proven.
- [x] Use opaque pagination tokens and make page replay idempotent.
- [x] Deduplicate snapshot families without assuming provider timestamps are
  unique sequence numbers.
- [x] Capture
  [sanitized fixtures](../apps/api/tests/fixtures/dnse/admitted-json-events.json)
  for every admitted REST and WebSocket event family.
- [x] Add
  [conformance tests](../apps/api/tests/test_dnse_auth_and_rest.py) for
  API/document drift, malformed fields, silent-empty success, disconnect,
  duplicate, out-of-order event, and partial response.
- [ ] Run a controlled market-hours probe for payloads, throughput,
  subscription limits, quote quantity scale, ordering, and reconnect gaps.

  This operational validation remains scheduled for the next open-market
  window. Outside-hours development may continue into S2 against the strict S1
  fixtures and deterministic recovery tests, but no downstream consumer may
  treat unverified book quantities or live capacity as production-proven.

**Exit gate:**

- [x] Every admitted wire payload maps to a valid normalized event or a typed
  refusal with no raw-field leakage to consumers.
- [x] Reconnect and REST reconciliation recover a measured test gap without
  double counting in the
  [reconciliation contract tests](../apps/api/tests/test_dnse_reconciliation.py).
- [x] Adapter metrics expose quota, latency, disconnect, parse failure,
  duplicate, gap, and queue pressure.

**Dependency:** S0 contracts must be stable enough to write fixtures and
conformance tests.

## Phase S2 — Build the realtime ingestion spine

This phase creates one durable path from DNSE events to hot projections and
replayable storage. It must not force ticks into the existing EOD
`provider_snapshots` model.

**Delivery checklist:**

- [x] Create a
  [dedicated realtime event boundary](../apps/api/src/stocks/realtime/storage.py)
  separate from `provider_snapshots`.
- [x] Use REST for instrument bootstrap, one-day backfill, reconnect
  reconciliation, and EOD checks through the
  [DNSE ingestion coordinator](../apps/api/src/stocks/realtime/coordinator.py).
- [x] Use WebSocket for live event delivery and closed-bar updates through the
  [opt-in runtime](../apps/api/src/stocks/realtime/runtime.py).
- [x] Partition durable events by trading day and event family with explicit
  retention and replay order in the
  [realtime migration](../apps/api/alembic/versions/c8f2a6d31e04_add_realtime_ingestion_spine.py).
- [x] Maintain Redis hot projections for current session, latest trade, book,
  foreign flow, auction, indices, and health in the
  [projection store](../apps/api/src/stocks/realtime/projections.py).
- [x] Preserve provider event time and platform observation time separately.
- [x] Make writes idempotent across duplicate delivery, retry, reconnect, and
  process restart.
- [x] Bound queues and define backpressure, spill, degradation, and shutdown
  behavior in the [ingestion spine](../apps/api/src/stocks/realtime/spine.py).
- [x] Persist checkpoints needed to resume without claiming exactly-once
  delivery.
- [x] Add data-health and feed-health states that consumers can query through
  the [durable health API](../apps/api/src/stocks/realtime/router.py).
- [x] Provide deterministic replay from normalized events without a live DNSE
  call.

**Exit gate:**

- [x] A process restart and WebSocket reconnect produce no unexplained gap or
  double-counted projection in the
  [controlled ingestion tests](../apps/api/tests/test_realtime_ingestion.py).
- [x] The deterministic load test stays within its declared queue, CPU, memory,
  and latency envelope.
- [x] A degraded feed remains visible as degraded through storage, the health
  API, and low-cardinality counters.

**Dependency:** S1 must prove the admitted event families and deterministic
recovery behavior. The outside-hours S2 build may proceed on those contracts;
production activation still requires the deferred S1 market-hours evidence.

## Phase S3 — Deliver trades, bars, and foreign-flow MVP

This phase delivers the smallest complete DNSE outcome: reliable trades,
closed one-minute bars, session volume, and foreign flow for the configured
Universe.

**Delivery checklist:**

- [x] Ingest round-lot and odd-lot trades with board-specific quantity units.
- [x] Aggregate trades into one-minute bars and accepted higher resolutions
  with deterministic session boundaries.
- [x] Persist source, resolution, board policy, price unit/basis, schema version,
  and collision-safe identity for intraday bars.
- [x] Ingest foreign buy/sell volume, value, room, and observation health.
- [x] Reconcile trade volume to minute bars and minute bars to DNSE daily data.
- [x] Compare DNSE daily reconciliation with FiinQuant without overwriting
  either source.
- [x] Publish session VWAP, signed flow, trade intensity, volume acceleration,
  and foreign-flow projections through source-neutral service contracts.
- [x] Reconstruct UPCOM reference-price inputs from eligible prior-day boards
  while excluding negotiated and odd-lot activity.
- [x] Add APIs for bars, trades, foreign flow, and health with bounded windows
  and pagination.
- [x] Prove Universe filtering and full-market instrument refresh are separate
  concerns.

**Exit gate:**

- [x] Accepted comparisons reconcile under the owner-approved exact-zero v1
  shadow profile; failures are durably audited and
  produce quality states instead of adjusted data.
- [x] Foreign traded share volume is sufficient to remove the current
  `net_volume_over_adtv` refusal through its existing signal contract.
- [x] Replay produces the same bars and projections as live ingestion for the
  same normalized events.

**Dependencies:** S2 plus stable S0 unit and trading-day contracts.

The deterministic reconciliation implementation records the immutable
exact-zero v1 profile, both evidence sources, comparisons and actual deltas in
an append-only audit. It emits match, mismatch, incomplete, or not-comparable
quality in shadow mode and never adjusts evidence or blocks ingestion. The
owner approved this profile on August 24, 2026. Keep v1 unchanged and introduce
a v2 only if 10–20 live sessions prove a legitimate repeatable difference.
Production activation remains subject to the deferred S1 market-hours
conformance probe.

## Phase S4 — Deliver depth, auction, session, and market pulse

This phase expands the realtime system from trade flow to market state. It
retains venue depth limitations and auction semantics in every derived output.

**Delivery checklist:**

- [ ] Ingest three-level HOSE and available ten-level HNX/UPCOM book snapshots
  with board identity.
- [ ] Derive spread, spread basis points, visible depth, imbalance, liquidity
  shock, and limit queue metrics.
- [ ] Ingest ATO/ATC expected price and quantity with duplicate-safe identity.
- [ ] Derive auction imbalance, indicative dislocation, and close-quality
  projections.
- [ ] Ingest session transitions and prevent off-session data from appearing
  fresh.
- [ ] Ingest current index and estimated-index events.
- [ ] Derive breadth, advancing/declining/unchanged counts, ceiling/floor locks,
  market regime inputs, and index-relative moves.
- [ ] Expose venue depth coverage and partial-market health with each aggregate.
- [ ] Add market-board and market-pulse APIs that read hot projections instead
  of polling providers.

**Exit gate:**

- [ ] Market-hours tests prove quote quantity scale, session transitions,
  auction paths, index updates, and end-to-end latency.
- [ ] Snapshot duplicates and reconnect replay cannot inflate depth or auction
  metrics.
- [ ] Consumers can distinguish full Universe, partial Universe, stale, and
  disconnected market state.

**Dependency:** S3 establishes the feed, reconciliation, and serving patterns.

## Phase S5 — Add replay, derivatives, and feature projections

This phase turns the normalized event store into a reusable analysis substrate
for historical session replay, derivatives, and deterministic features.

**Delivery checklist:**

- [ ] Version session replay by source, schema, normalization rules, Universe,
  and trading calendar.
- [ ] Build event-time replay controls that preserve original ordering limits,
  duplicates, gaps, and observation latency.
- [ ] Ingest futures aliases and concrete contracts as separate identities.
- [ ] Derive basis, front/next spread, expiry, roll state, futures-index
  lead/lag, and open-interest projections when the field is available.
- [ ] Build feature projections for realized volatility, liquidity, flow,
  auction, breadth, and regime without storing model judgments.
- [ ] Version every deterministic method and retain input evidence references.
- [ ] Support point-in-time replay fixtures for Harness evaluation without live
  provider calls.
- [ ] Define correction and supersession semantics for late or repaired events.

**Exit gate:**

- [ ] Repeated replay produces identical projections for an identical event and
  method version.
- [ ] Futures and cash units cannot be combined without an explicit method.
- [ ] Harness evaluation can freeze compact, provenance-complete live-market
  cases from persisted evidence.

**Dependencies:** S3 for event-derived bars and S4 for full market-state replay.

## Phase S6 — Integrate product APIs and user surfaces

This phase replaces fragmented live paths with coherent, health-aware product
surfaces. UI work consumes stable service contracts and never connects directly
to DNSE.

**Delivery checklist:**

- [ ] Define public response contracts for market pulse, intraday chart, trade
  flow, liquidity, foreign flow, auction, and derivatives.
- [ ] Stream bounded product events through the existing authenticated product
  transport with reconnect-safe snapshots.
- [ ] Display as-of time, source, session, freshness, depth coverage, units, and
  degraded/refused state where they affect interpretation.
- [ ] Add session replay and evidence inspection without exposing credentials or
  raw provider payloads.
- [ ] Route AI tools through the same source-neutral services and evidence IDs
  used by non-AI surfaces.
- [ ] Preserve Vietnamese market terminology and board/session distinctions in
  UI copy.
- [ ] Add accessible loading, empty, stale, partial, disconnected, and error
  states for every realtime surface.
- [ ] Measure user-visible latency from provider event to rendered projection.

**Exit gate:**

- [ ] API, UI, and Harness resolve the same projection and evidence identity for
  the same observation.
- [ ] Reconnect restores a coherent snapshot before incremental events resume.
- [ ] Product tests cover stale, partial, empty, disconnected, and recovered
  states, not only the happy path.

**Dependencies:** S3 supplies the MVP surfaces; S4–S5 unlock their corresponding
advanced views. Harness H1 gates AI-facing tool adoption.

## Phase S7 — Complete reliability, migration, and production readiness

This phase makes DNSE-backed data an operationally owned system and removes
overlapping paths only after measured parity. Commercial provider changes can
occur here without rewriting semantic contracts.

**Delivery checklist:**

- [ ] Define service-level objectives for freshness, completeness, latency,
  reconnect recovery, reconciliation, and projection availability.
- [ ] Alert on quota pressure, disconnect, parse drift, duplicate spikes, gaps,
  queue pressure, stale projections, and reconciliation failure.
- [ ] Add dashboards and runbooks for market open, provider incident, schema
  drift, backfill, replay, credential rotation, and shutdown.
- [ ] Prove controlled failover or explicit degradation for every product
  surface; never substitute semantically different data silently.
- [ ] Capacity-test the target Universe and retained event window during peak
  market load.
- [ ] Review retention, access control, encryption, redaction, backup, and
  deletion for raw and normalized data.
- [ ] Compare DNSE-backed outputs with the current VCI request-time ticks,
  five-minute collector, and KBS order-stat path.
- [ ] Migrate consumers one by one and delete an old path only after parity,
  rollback, and observability gates pass.
- [ ] Validate production package/licensing choices without changing source
  semantics or losing provenance.
- [ ] Run incident and reconnect drills before enabling proactive Harness
  monitoring.

**Exit gate:**

- [ ] The DNSE-backed path meets accepted service objectives across a measured
  market period and a recovery drill.
- [ ] No retired live path remains an undocumented fallback or duplicate quota
  consumer.
- [ ] Operations can disable DNSE ingestion or a projection independently while
  preserving historical evidence and explicit product degradation.

**Dependencies:** S2–S6 must supply the paths and evidence this phase operates.

## Priority and maintenance rules

Use these rules to keep delivery aligned with the source decision.

1. Correct identity, time, unit, board, and data-quality failures before adding
   a projection or UI.
2. Complete trades, bars, and foreign flow before widening to every channel.
3. Prefer WebSocket delivery plus REST reconciliation over provider polling.
4. Preserve raw and normalized provenance; never hide disagreement by
   overwriting one source with another.
5. Keep AI reasoning and capability graduation in `harness-roadmap.md`.
6. Update a checkbox only with a linkable schema, executable owner, test,
   operational trace, or accepted live-market report.

## Next execution slice

The immediate outside-hours System slice is S2's durable ingestion spine. Run
the deferred S1 market-hours conformance probe in the next open-market window
before production graduation. The first production-shaped vertical slice is
S3: trades, closed one-minute bars, foreign flow, reconciliation, and health for
the configured Universe. Book depth, auction intelligence, indices, futures,
replay, and proactive monitoring follow only after that slice proves event
identity, recovery, and unit correctness.
